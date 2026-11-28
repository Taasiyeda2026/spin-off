import base64
import json
import hashlib
from pathlib import Path
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
    expected_labels = ["1. שם הפתרון שלנו?","2א. סוג הפתרון שלנו","2ב. תיאור הפתרון שלנו?","3. כיתה","4. שם בית הספר","5. איזו בעיה בחרנו לפתור?","6. מי נתקל בבעיה ומה הוא צריך?","7. מה למדנו מטכנולוגיות החלל?","8. איך טכנולוגיות החלל תרמו לפתרון?","9א. רעיון ראשון","9ב. רעיון שני","9ג. רעיון שלישי","10. איזה רעיון בחרנו ולמה?","11א. דרישה ראשונה","11ב. דרישה שנייה","11ג. דרישה שלישית","12. מה כולל הפתרון שלנו?","13א. שלב ראשון","13ב. שלב שני","13ג. שלב שלישי","14. מה בדקנו בתכנון הפתרון שלנו?","15. איזה משוב קיבלנו על הפתרון?","16. מה שיפרנו בעקבות המשוב?","17. איך נציג את הפתרון שלנו במשפט אחד?"]
    expected_arabic = ["1. اسم حلّنا؟","2أ. نوع حلّنا","2ب. وصف حلّنا؟","3. الصف","4. اسم المدرسة","5. أي مشكلة اخترنا حلّها؟","6. من يواجه المشكلة وماذا يحتاج؟","7. ماذا تعلمنا من تكنولوجيا الفضاء؟","8. كيف ساهمت تكنولوجيا الفضاء في الحل؟","9أ. الفكرة الأولى","9ب. الفكرة الثانية","9ج. الفكرة الثالثة","10. أي فكرة اخترنا ولماذا؟","11أ. المتطلب الأول","11ب. المتطلب الثاني","11ج. المتطلب الثالث","12. ماذا يتضمّن حلّنا؟","13أ. الخطوة الأولى","13ب. الخطوة الثانية","13ج. الخطوة الثالثة","14. ماذا فحصنا في تصميم حلّنا؟","15. ما الملاحظات التي تلقّيناها حول الحل؟","16. ماذا حسّنّا بناءً على الملاحظات؟","17. كيف نعرض حلّنا في جملة واحدة؟"]
    expected_limits = [35,None,105,None,None,85,80,55,55,55,55,55,125,60,60,60,115,60,60,60,60,60,60,85]
    page.locator('[data-tab="content"]').click()
    for language, labels in [('he', expected_labels), ('ar', expected_arabic)]:
        if language == 'ar':
            page.locator('#poster-editor-language').click()
        expect(page.locator('#fill-list .edit-card > label').first).to_have_text(labels[0])
        assert page.locator('#fill-list .edit-card > label').all_text_contents()[:24] == labels
        expect(page.locator('#fill-list .fill-question-group')).to_have_count(4)
        assert page.locator('#fill-list .fill-question-heading').all_text_contents() == (['2. סוג הפתרון שלנו ותיאורו?', '9. אילו רעיונות לפתרון הצענו?', '11. מה הפתרון חייב לעשות?', '13. איך הפתרון אמור לעבוד?'] if language=='he' else ['2. نوع حلّنا ووصفه؟', '9. ما الأفكار التي اقترحناها للحل؟', '11. ماذا يجب أن يفعل الحل؟', '13. كيف يُفترض أن يعمل الحل؟'])
        assert page.locator('#fill-list .edit-card > label').evaluate_all('(labels) => labels.every(el => el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight)')
        for index, field in enumerate(page.evaluate('FILL_FIELDS.map(f => f.id)')):
            if field=='solution-type':
                continue
            source = page.locator('#' + field)
            panel = page.locator('#panel-' + field)
            limit = (40 if index==0 else 85 if index==2 else expected_limits[index]) if language=='ar' else expected_limits[index]
            expected_max = str(limit) if limit else None
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
      G('arrow-color').value = '#ff0000';
      G('box-opacity').value = '0';
      applyDesign();
      scheduleAutosave();
      setGlow('title', 'light');
    }""")
    assert page.locator('[onclick*="chSz"]').count() == 0
    for selector, size, weight in [('#poster-project','30px','700'),('#c-problem .bq','14px','500'),('#problem','12px','300'),('#feedback','11px','400'),('#c-feedback .bq','13px','500'),('#solution-description-heading','13px','400'),('#poster-school','13px','400'),('#poster-students','12px','300'),('#slogan-output','15px','500')]:
        assert page.locator(selector).evaluate('(el)=>[getComputedStyle(el).fontSize,getComputedStyle(el).fontWeight]') == [size,weight], selector
    assert page.evaluate("getComputedStyle(G('arrow-feedback-improvement').querySelector('.head')).borderTopColor") == 'rgb(255, 0, 0)'
    assert page.evaluate("boxOpacityActual()") == 30
    assert page.evaluate("Object.isFrozen(SZ)")
    assert page.locator('#research svg.research-answer-icon').count() == 2
    assert page.evaluate("(()=>{const ids=['c-problem','c-target','c-question','img-pair','c-research','c-findings','c-requirements'];return ids.every((id,i)=>!i||LAYOUT[id].top>LAYOUT[ids[i-1]].top)})()")
    short_width=page.evaluate("G('poster-project').value='א';measureGlow('title');parseFloat(G('p-hdr').style.getPropertyValue('--glow-w'))")
    long_width=page.evaluate("G('poster-project').value='מערכת ניסיונית';measureGlow('title');parseFloat(G('p-hdr').style.getPropertyValue('--glow-w'))")
    assert long_width > short_width > 0
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
    expect(page.locator("#approved-bg-image")).to_have_attribute("src", "poster-backgrounds/versions/" + hashlib.sha256(Path("poster-backgrounds/webp/bg2.webp").read_bytes()).hexdigest() + ".webp")
    assert page.evaluate("async () => await backgroundReady")
    expect(page.locator('[data-background-id="bg2"]')).to_have_attribute("aria-pressed", "true")
    assert page.evaluate("SZ.h === 30 && glowState.title === 'light' && boxOpacityActual() === 30 && G('arrow-color').value === '#ff0000'")
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
