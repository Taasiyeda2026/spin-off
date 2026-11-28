"""Focused typography/header acceptance; synthetic local drafts, no accounts or backend."""
import os
from pathlib import Path
import fitz
from playwright.sync_api import sync_playwright

out=Path('test-results/poster-header');out.mkdir(parents=True,exist_ok=True)
url=os.getenv('POSTER_TEST_URL','http://127.0.0.1:8000/poster.html')
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'))
    page=browser.new_page(viewport={'width':1400,'height':1300})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    # No real users or backend requests in this suite.
    page.route('**/*.supabase.co/**',lambda route:route.abort())
    page.goto(url)
    page.evaluate('posterEditor.open()')
    page.evaluate('document.fonts.ready')
    fixed=page.evaluate("Object.fromEntries(Object.keys(LAYOUT).map(id=>[id,G(id).style.cssText]))")
    for lang in ['he','ar']:
        if lang=='ar':page.locator('#poster-editor-language').click()
        for long in [False,True]:
            title=('מערכת חכמה להגנה על הסביבה' if lang=='he' else 'نظام ذكي لحماية البيئة')
            if long:title='W'*35
            desc=('מערכת שמסייעת לזהות בעיות בסביבה ולפעול בזמן באמצעות חיישנים וטכנולוגיות מהחלל.' if lang=='he' else 'نظام يساعد على اكتشاف المشكلات البيئية والعمل في الوقت المناسب باستخدام المستشعرات وتقنيات الفضاء.')
            names=(['משתתף לדוגמה עם שם משפחה ארוך']*8 if lang=='he' else ['مشارك تجريبي مع اسم عائلة طويل']*8) if long else (['נועה לדוגמה','יובל לדוגמה'] if lang=='he' else ['نور للتجربة','رامي للتجربة'])
            values={'poster-project':title,'short-desc':desc[:105],'solution-type':'physical','poster-class':'ו׳ 2' if lang=='he' else 'السادس 2','poster-school':'בית הספר לדוגמה' if lang=='he' else 'مدرسة تجريبية','poster-students':', '.join(names),'slogan':'טכנולוגיות החלל עוזרות לשמור על הסביבה שלנו' if lang=='he' else 'تقنيات الفضاء تساعدنا في حماية بيئتنا','problem':'בעיה לדוגמה' if lang=='he' else 'مشكلة تجريبية'}
            # Loading synthetic saved state exercises the same path as existing posters.
            page.evaluate('data=>posterEditor.open({draft:{values:data.values,participants:data.names}})',{'values':values,'names':names})
            page.evaluate('document.fonts.ready')
            page.evaluate('fitPreview()')
            metrics=page.evaluate("""() => {
                const p=G('poster'),scale=p.getBoundingClientRect().width/p.offsetWidth;
                const rect=id=>{const r=G(id).getBoundingClientRect(),pr=p.getBoundingClientRect();return {top:(r.top-pr.top)/scale,bottom:(r.bottom-pr.top)/scale,height:r.height/scale};};
                const t=rect('poster-project'),d=rect('short-desc-box'),b=rect('p-bar'),n=rect('p-names');
                return {gaps:[d.top-t.bottom,b.top-d.bottom,n.top-b.bottom,G('c-problem').offsetTop-n.bottom],top:t.top,
                  clipped:['poster-project','poster-students'].filter(id=>G(id).scrollHeight>G(id).clientHeight+1),
                  weights:[...document.querySelectorAll('#poster .bq,#poster-project,#slogan-output,#slogan-output *')].map(e=>getComputedStyle(e).fontWeight),
                  sizes:['poster-project','solution-description-heading','c-problem','poster-students'].map(id=>getComputedStyle(G(id)).fontSize)};
            }""")
            assert all(w=='700' for w in metrics['weights']),metrics
            assert not metrics['clipped'] and metrics['top']>=0,metrics
            assert all(abs(a-b)<1 for a,b in zip(metrics['gaps'],[4,18,4,18])),metrics
            assert page.evaluate("Object.fromEntries(Object.keys(LAYOUT).map(id=>[id,G(id).style.cssText]))")==fixed
            assert page.locator('#poster-project').input_value()==title
            assert page.locator('#short-desc').input_value()==desc[:105]
            if long:continue
            # Populate the remaining answers and images only for visual review.
            page.evaluate("""lang=>{
              qs('#poster .box textarea:not([hidden])').forEach(e=>{e.value=lang==='he'?'תשובה לדוגמה לצורך בדיקת הפוסטר':'إجابة تجريبية لفحص الملصق';});
              for(const id of ['research1','research2','findings1','findings2','findings3','requirements1','requirements2','requirements3','use1','use2','use3'])G(id).value=lang==='he'?'תשובה לדוגמה':'إجابة تجريبية';
              updateAllCombinedFields();
              const svg='<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"><rect width="300" height="300" fill="#12354d"/><circle cx="150" cy="150" r="80" fill="#52c0ce"/><path d="M40 220L260 80M50 70L250 240" stroke="white" stroke-width="12"/></svg>';
              for(const id of ['img-main','img-1','img-2']){const img=G(id);if(img){img.src='data:image/svg+xml;base64,'+btoa(svg);img.classList.add('show');img.parentElement.querySelector('.iph')?.style.setProperty('display','none');}}
            }""",lang)
            for id,color in zip(['project-color','description-color','q-color','t-color'],['#eeeeff','#ddffee','#ffeecc','#ffffff']):
                page.locator('#'+id+'-hex').fill(color)
            assert page.evaluate("['poster-project','solution-description-heading'].map(id=>getComputedStyle(G(id)).color)")==['rgb(238, 238, 255)','rgb(221, 255, 238)']
            page.locator('#poster').screenshot(path=str(out/f'poster-{lang}.png'))
            screen=page.evaluate("['p-bar','p-names','short-desc-box'].map(id=>[G(id).style.top,G(id).style.height])")
            page.pdf(path=str(out/f'poster-{lang}.pdf'),prefer_css_page_size=True,print_background=True)
            assert page.evaluate("['p-bar','p-names','short-desc-box'].map(id=>[G(id).style.top,G(id).style.height])")==screen
            with fitz.open(out/f'poster-{lang}.pdf') as doc:
                assert len(doc)==1
                assert abs(doc[0].rect.width-595.28)<1 and abs(doc[0].rect.height-841.89)<1
                doc[0].get_pixmap(matrix=fitz.Matrix(1,1)).save(out/f'pdf-{lang}.png')
        print(lang,': headings/slogan 700; short/long saved/new header; exact gaps; fixed image/content coordinates; colors; single A4 passed')
    assert not errors,errors
    browser.close()
