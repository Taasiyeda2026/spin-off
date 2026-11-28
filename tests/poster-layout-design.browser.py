"""Visual, persistence and A4 contracts. Synthetic local drafts only."""
import io, json, os
from pathlib import Path
import fitz
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright, expect

url=os.getenv('POSTER_TEST_URL','http://127.0.0.1:8000/poster.html')
out=Path('test-results/poster-acceptance');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'))
    page=browser.new_page(viewport={'width':1400,'height':1300})
    page.on('dialog',lambda dialog:dialog.accept())
    page.goto(url);page.evaluate('posterEditor.open()')
    # An old qColor must seed its title while newer colors remain independent.
    page.evaluate("posterEditor.open({draft:{design:{qColor:'#123456',tColor:'#654321'}}})")
    expect(page.locator('#project-color')).to_have_value('#123456')
    page.evaluate("posterEditor.open({draft:{design:{bgId:'bg2',qColor:'#123456',tColor:'#654321'}}})")
    assert page.evaluate("selectedBackgroundVersion===approvedBackgrounds.find(e=>e.id==='bg2').legacyVersion")
    assert page.evaluate('async()=>await backgroundReady')
    for language in ['he','ar']:
        if language=='ar':page.locator('#poster-editor-language').click()
        page.evaluate("""() => {G('poster-project').value='SpaceTech';G('short-desc').value='SpaceTech';updateSolutionTypeHeading();} """)
        selectors=['#poster-project','#solution-description-heading','#c-problem .bq','#problem']
        colors=['#a10000','#00a100','#0000a1','#a100a1']
        for id,color in zip(['project-color','description-color','q-color','t-color'],colors):
            page.locator('#'+id+'-hex').fill(color)
        assert [page.locator(s).evaluate('(el)=>getComputedStyle(el).color') for s in selectors]==['rgb(161, 0, 0)','rgb(0, 161, 0)','rgb(0, 0, 161)','rgb(161, 0, 161)']
        page.screenshot(path=str(out/f'colors-{language}.png'),full_page=True)
        for kind in ['physical','smart','app','web','digital']:
            page.evaluate("kind=>{G('solution-type').value=kind;updateSolutionTypeHeading();}",kind)
            rects=page.evaluate("""Object.keys(LAYOUT).map(id=>{let e=G(id);return {id,x:e.offsetLeft,y:e.offsetTop,w:e.offsetWidth,h:e.offsetHeight}})""")
            for i,a in enumerate(rects):
                assert a['x']>=0 and a['y']>=0 and a['x']+a['w']<=794 and a['y']+a['h']<=1123,a
                for b in rects[i+1:]:
                    assert not (a['x']<b['x']+b['w'] and b['x']<a['x']+a['w'] and a['y']<b['y']+b['h'] and b['y']<a['y']+a['h']),(a,b)
            assert page.locator('#main-image-box').evaluate('(e)=>e.offsetLeft+e.offsetWidth<=387')
            assert page.locator('#img-pair').evaluate('(e)=>e.offsetLeft>=407')
            assert page.locator('#c-slogan').evaluate('(e)=>e.offsetTop>=1036 && e.offsetWidth===734')
        ids=page.locator('#poster-background-gallery button').evaluate_all('(els)=>els.map(e=>e.dataset.backgroundId)')
        assert ids==sorted([p.stem for p in Path('poster-backgrounds/webp').glob('*.webp')],key=lambda id:int(id[2:]))
        for id in ids:
            page.locator(f'[data-background-id={id}]').click()
            assert page.evaluate('async()=>await backgroundReady')
            assert page.evaluate("id=>{const e=approvedBackgrounds.find(e=>e.id===id);return G('approved-bg-image').getAttribute('src')===e.image && document.querySelector('[data-background-id='+id+'] img').getAttribute('src')===e.thumb}",id)
            page.evaluate('posterEditor.flush()')
            state=page.evaluate('collectDraft()')
            page.evaluate('draft=>posterEditor.open({draft})',state)
            expect(page.locator(f'[data-background-id={id}]')).to_have_attribute('aria-pressed','true')
            pdf=out/f'{id}-{language}.pdf';page.pdf(path=str(pdf),prefer_css_page_size=True,print_background=False)
            with fitz.open(pdf) as doc:
                assert doc.page_count==1,(id,language,doc.page_count)
                assert abs(doc[0].rect.width-595.28)<1 and abs(doc[0].rect.height-841.89)<1
                embedded=[doc.extract_image(img[0]) for img in doc[0].get_images() if img[2]==1414 and img[3]==2000]
                assert embedded,(id,'background absent from PDF')
                actual=Image.open(io.BytesIO(embedded[0]['image'])).convert('RGB')
                source=Image.open('poster-backgrounds/webp/'+id+'.webp').convert('RGB')
                assert max(ImageStat.Stat(ImageChops.difference(actual,source)).mean)<3,(id,'wrong PDF background')
        page.locator('[data-background-id=bg2]').click();page.evaluate('posterEditor.flush()')
        page.locator('#poster').screenshot(path=str(out/f'poster-{language}.png'))
    # Restoring a removed or replaced background must retain its exact version.
    pinned=page.evaluate("collectDraft()")
    page.evaluate("""draft=>{const e=approvedBackgrounds.find(e=>e.id===draft.design.bgId);e.retired=true;window.__entry=e;}""",pinned)
    page.evaluate('draft=>posterEditor.open({draft})',pinned)
    assert page.evaluate('selectedBackgroundVersion')==pinned['design']['bgVersion']
    expect(page.locator('[data-background-id=bg2]')).to_have_attribute('aria-pressed','true')
    page.evaluate('window.__entry.retired=false')
    page.set_viewport_size({'width':390,'height':844});page.evaluate('fitPreview()')
    assert page.locator('#poster').bounding_box()['width']<=390
    page.screenshot(path=str(out/'poster-mobile.png'),full_page=True)
    # A browser reload restores the four separate colors and selected background.
    page.reload();page.evaluate('posterEditor.open()')
    for id,color in zip(['project-color','description-color','q-color','t-color'],colors):
        expect(page.locator('#'+id)).to_have_value(color)
    expect(page.locator('[data-background-id=bg2]')).to_have_attribute('aria-pressed','true')
    print('14 backgrounds × 2 languages: identity, PDF pixels, A4 page; color isolation, legacy/local persistence, five image ratios, bounds and mobile passed.')
    browser.close()
