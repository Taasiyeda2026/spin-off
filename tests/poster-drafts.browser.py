import base64
import json
import os
import re
import fitz
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
    expect(page.locator(".poster-home-actions > button")).to_have_count(4)
    expect(page.locator("#poster-editor-home")).to_be_visible()
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
    expected_labels = ['שם הפתרון שלנו?', 'תיאור הפתרון שלנו?', 'כיתה', 'שם בית הספר', 'איזו בעיה בחרנו לפתור?', 'מי נתקל בבעיה ומה הוא צריך?', 'מה הפתרון חייב לעשות? – דרישה ראשונה', 'מה הפתרון חייב לעשות? – דרישה שנייה', 'מה הפתרון חייב לעשות? – דרישה שלישית', 'מה למדנו מטכנולוגיות החלל?', 'איך טכנולוגיות החלל תרמו לפתרון?', 'איזה רעיון לפתרון הצענו? – רעיון ראשון', 'איזה רעיון לפתרון הצענו? – רעיון שני', 'איזה רעיון לפתרון הצענו? – רעיון שלישי', 'איזה רעיון בחרנו ולמה?', 'מה כולל הפתרון שלנו?', 'איך הפתרון אמור לעבוד? – שלב ראשון', 'איך הפתרון אמור לעבוד? – שלב שני', 'איך הפתרון אמור לעבוד? – שלב שלישי', 'מה בדקנו בתכנון הפתרון שלנו?', 'איזה משוב קיבלנו על הפתרון?', 'מה שיפרנו בעקבות המשוב?', 'איך נציג את הפתרון שלנו במשפט אחד?']
    expected_arabic = ['اسم حلّنا؟', 'وصف حلّنا؟', 'الصف', 'اسم المدرسة', 'أي مشكلة اخترنا حلّها؟', 'من يواجه المشكلة وماذا يحتاج؟', 'ماذا يجب أن يفعل الحل؟ – المتطلب الأول', 'ماذا يجب أن يفعل الحل؟ – المتطلب الثاني', 'ماذا يجب أن يفعل الحل؟ – المتطلب الثالث', 'ماذا تعلمنا من تكنولوجيا الفضاء؟', 'كيف ساهمت تكنولوجيا الفضاء في الحل؟', 'أي فكرة للحل اقترحنا؟ – الفكرة الأولى', 'أي فكرة للحل اقترحنا؟ – الفكرة الثانية', 'أي فكرة للحل اقترحنا؟ – الفكرة الثالثة', 'أي فكرة اخترنا ولماذا؟', 'ماذا يتضمّن حلّنا؟', 'كيف يُفترض أن يعمل الحل؟ – الخطوة الأولى', 'كيف يُفترض أن يعمل الحل؟ – الخطوة الثانية', 'كيف يُفترض أن يعمل الحل؟ – الخطوة الثالثة', 'ماذا فحصنا في تصميم حلّنا؟', 'ما الملاحظات التي تلقّيناها حول الحل؟', 'ماذا حسّنّا بناءً على الملاحظات؟', 'كيف نعرض حلّنا في جملة واحدة؟']
    expected_labels.insert(1, 'סוג הפתרון שלנו')
    expected_arabic.insert(1, 'نوع حلّنا')
    expected_limits = [40,None,135,None,None,120,110,55,55,55,50,50,50,50,50,125,115,55,55,55,110,110,110,90]
    page.locator('[data-tab="content"]').click()
    for language, labels in [('he', expected_labels), ('ar', expected_arabic)]:
        if language == 'ar':
            page.locator('#poster-editor-language').click()
        expect(page.locator('#fill-list .edit-card > label').first).to_have_text('1. ' + labels[0])
        prefixes = ['1. ', '2א. ' if language=='he' else '2أ. ', '2ב. ' if language=='he' else '2ب. '] + [f'{i}. ' for i in range(3,24)]
        assert page.locator('#fill-list .edit-card > label').all_text_contents()[:24] == [prefix+text for prefix,text in zip(prefixes,labels)]
        assert page.locator('#fill-list .edit-card > label').evaluate_all('(labels) => labels.every(el => el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight)')
        for index, field in enumerate(page.evaluate('FILL_FIELDS.map(f => f.id)')):
            if field=='solution-type':
                continue
            source = page.locator('#' + field)
            panel = page.locator('#panel-' + field)
            expected_max = str(expected_limits[index]) if expected_limits[index] else None
            assert panel.get_attribute('maxlength') == expected_max
            assert panel.get_attribute('maxlength') == (source.get_attribute('data-max') or source.get_attribute('maxlength'))
            if expected_max:
                panel.fill('x' * (int(expected_max) + 1))
                expect(panel).to_have_value('x' * int(expected_max))
            panel.fill('בדיקה')
            expect(source).to_have_value('בדיקה')
            if panel.get_attribute('maxlength'):
                counter = page.locator('#panel-counter-' + field)
                expect(counter).to_have_text('5/' + panel.get_attribute('maxlength'))
                assert counter.bounding_box()['y'] >= panel.bounding_box()['y'] + panel.bounding_box()['height']
    page.locator('#poster-editor-language').click()
    expect(page.locator('#panel-poster-project')).to_have_value('בדיקה')
    page.locator('[data-tab="design"]').click()
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
    page.emulate_media(media="null")  # restore native media selection for page.pdf()
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
        with fitz.open(pdf) as document:
            assert document.page_count == 1
            assert any(image[2] >= 500 for image in document[0].get_images())
            assert abs(document[0].rect.width - 595.28) < 1
            assert abs(document[0].rect.height - 841.89) < 1
    assert not errors, errors
    print("Restore, dismiss without deleting, participant slots, images, background, design, draft isolation and PDF passed.")
