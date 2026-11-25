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
    expect(page.locator(".poster-home-actions > button")).to_have_count(3)
    expect(page.locator("#poster-access-home")).to_be_visible()
    assert page.get_by_role("button", name="טיוטה שמורה בדפדפן").count() == 0
    assert page.locator(".poster-home-actions > button").evaluate_all(
        "(buttons) => Math.max(...buttons.map(b=>b.offsetWidth))-Math.min(...buttons.map(b=>b.offsetWidth)) <= 1")
    assert "data:image/webp" in page.evaluate("getComputedStyle(document.body,'::before').backgroundImage")
    page.get_by_role("button", name="יצירת פוסטר חדש").click()
    expect(page.get_by_label("קוד מדריך")).to_be_visible()
    assert page.get_by_label("קוד מדריך").evaluate("(el) => el.offsetWidth") <= 150
    page.get_by_role("button", name="חזרה", exact=True).click()
    page.evaluate("window.posterEditor.open()")
    expect(page.locator("#poster-editor-home")).to_be_visible()
    assert page.evaluate("FILL_FIELDS.length === 23 && FILL_FIELDS[10].label.includes('איך מה שלמדנו') && FILL_FIELDS[20].label.includes('איזה משוב')")
    expect(page.locator(".poster-image-question")).to_have_count(1)
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
    assert page.locator("#bg-up").count() == 0
    assert page.locator("#poster-background-gallery button").count() >= 4
    page.locator("#img-main-file").set_input_files({"name": "fixture.png", "mimeType": "image/png", "buffer": png})
    page.locator('[data-background-id="bg2"]').click()
    expect(page.locator('[data-background-id="bg2"]')).to_have_attribute("aria-pressed", "true")
    assert page.evaluate("async () => await backgroundReady")
    assert "data:image/webp" in page.evaluate("getComputedStyle(document.body,'::before').backgroundImage")
    page.emulate_media(media="print")
    assert page.evaluate("getComputedStyle(document.body,'::before').display") == "none"
    expect(page.locator("#approved-bg-image")).to_be_visible()
    page.emulate_media(media=None)
    for attempt in range(20):
        if page.evaluate("""async () => {
          const draft = await posterDrafts.read(null);
          return draft?.images.main.startsWith('data:') && draft.design.bgId === 'bg2' && !('bgImage' in draft.design);
        }"""):
            break
        page.wait_for_timeout(100)
    else:
        raise AssertionError("Image and background were not saved")
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.reload()
    page.evaluate("window.posterEditor.open()")
    page.wait_for_function("!document.getElementById('wrap').inert")
    expect(page.locator("#poster-project")).to_have_value("")
    assert page.evaluate("(async () => (await posterDrafts.read(null)).values['poster-project'])()") == "מערכת ניסיונית"
    page.once("dialog", lambda dialog: dialog.accept())
    page.reload()
    page.evaluate("window.posterEditor.open()")
    expect(page.locator("#poster-project")).to_have_value("מערכת ניסיונית")
    expect(page.locator("#problem")).to_have_value("תשובה לבדיקה בלבד")
    expect(page.locator("#border-color")).to_have_value("#ff0000")
    expect(page.locator("#img-main")).to_have_attribute("src", re.compile("^data:image/png"))
    assert page.locator("#pcf input").evaluate_all("(inputs) => inputs.map(input => input.value)") == ["שם א", "", "שם ב"]
    expect(page.locator("#approved-bg-image")).to_have_attribute("src", "poster-backgrounds/webp/bg2.webp")
    assert page.evaluate("async () => await backgroundReady")
    expect(page.locator('[data-background-id="bg2"]')).to_have_attribute("aria-pressed", "true")
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
        page.pdf(path=pdf, prefer_css_page_size=True, print_background=False)
        image_info = subprocess.check_output(["pdfimages", "-list", str(pdf)], text=True)
        assert any(int(match.group(1)) >= 500 for match in re.finditer(r"^\s*1\s+\d+\s+image\s+(\d+)\s+\d+", image_info, re.MULTILINE)), image_info
        metadata = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
        assert re.search(r"^Pages:\s+1$", metadata, re.MULTILINE), metadata
        assert re.search(r"^Page size:.*\(A4\)$", metadata, re.MULTILINE), metadata
    assert not errors, errors
    print("Restore, dismiss without deleting, participant slots, images, background, design, draft isolation and PDF passed.")
