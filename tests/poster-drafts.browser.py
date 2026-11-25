import base64
import os
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from playwright.sync_api import expect, sync_playwright

url = os.environ.get("POSTER_TEST_URL", "http://127.0.0.1:8000/poster.html")
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"))
    context = browser.new_context()
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(url)
    page.wait_for_function("!document.getElementById('wrap').inert")
    page.locator("#poster-project").fill("מערכת ניסיונית")
    page.locator("#problem").fill("תשובה לבדיקה בלבד")
    page.evaluate("""() => {
      setParts(3, ['שם א', '', 'שם ב']);
      G('border-color').value = '#ff0000';
      applyDesign();
      chSz('h', 2);
      setGlow('title', 'light');
    }""")
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFtUAAAAASUVORK5CYII=")
    for field in ("img-main-file", "bg-up"):
        page.locator("#" + field).set_input_files({"name": "fixture.png", "mimeType": "image/png", "buffer": png})
    for attempt in range(20):
        if page.evaluate("""async () => {
          const draft = await posterDrafts.read(null);
          return draft?.images.main.startsWith('data:') && draft.design.bgImage.includes('data:');
        }"""):
            break
        page.wait_for_timeout(100)
    else:
        raise AssertionError("Image and background were not saved")
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.reload()
    page.wait_for_function("!document.getElementById('wrap').inert")
    expect(page.locator("#poster-project")).to_have_value("")
    assert page.evaluate("(async () => (await posterDrafts.read(null)).values['poster-project'])()") == "מערכת ניסיונית"
    page.once("dialog", lambda dialog: dialog.accept())
    page.reload()
    expect(page.locator("#poster-project")).to_have_value("מערכת ניסיונית")
    expect(page.locator("#problem")).to_have_value("תשובה לבדיקה בלבד")
    expect(page.locator("#border-color")).to_have_value("#ff0000")
    expect(page.locator("#img-main")).to_have_attribute("src", re.compile("^data:image/png"))
    assert page.locator("#pcf input").evaluate_all("(inputs) => inputs.map(input => input.value)") == ["שם א", "", "שם ב"]
    assert page.evaluate("G('bg-layer').style.backgroundImage.includes('data:')")
    assert page.evaluate("SZ.h === 38 && glowState.title === 'light'")
    assert page.evaluate("""async () => {
      await posterDrafts.write('poster-a', {value: 'a'});
      await posterDrafts.write('poster-b', {value: 'b'});
      await posterDrafts.remove('poster-a');
      return !(await posterDrafts.read('poster-a')) && (await posterDrafts.read('poster-b')).value === 'b'
        && !!(await posterDrafts.read(null));
    }""")
    with TemporaryDirectory() as directory:
        pdf = Path(directory) / "poster.pdf"
        page.pdf(path=pdf, prefer_css_page_size=True)
        metadata = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
        assert re.search(r"^Pages:\s+1$", metadata, re.MULTILINE), metadata
        assert re.search(r"^Page size:.*\(A4\)$", metadata, re.MULTILINE), metadata
    assert not errors, errors
    print("Restore, dismiss without deleting, participant slots, images, background, design, draft isolation and PDF passed.")
