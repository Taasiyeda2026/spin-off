"""Visual, persistence and A4 contracts. Synthetic local drafts only."""
import io, json, os, re
from pathlib import Path
import fitz
from PIL import Image, ImageChops, ImageStat, ImageOps
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
        page.evaluate("""() => {G('poster-project').value='SpaceTech';G('short-desc').value='SpaceTech';G('problem').value='SpaceTech';updateSolutionTypeHeading();} """)
        selectors=['#poster-project','#solution-description-heading','#c-problem .bq','#problem']
        colors=['#a10000','#00a100','#0000a1','#a100a1']
        page.evaluate("""colors=>{for(const [id,color] of Object.entries(colors)){G(id).value=color;}applyDesign();}""",dict(zip(['project-color','description-color','q-color','t-color'],colors)))
        assert [page.locator(s).evaluate('(el)=>getComputedStyle(el).color') for s in selectors]==['rgb(161, 0, 0)','rgb(0, 161, 0)','rgb(0, 0, 161)','rgb(161, 0, 161)']
        assert page.locator('#poster-project').evaluate('(el)=>getComputedStyle(el).webkitTextFillColor')=='rgb(161, 0, 0)'
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
        ids=page.locator('#poster-background-gallery button[data-background-id]').evaluate_all('(els)=>els.map(e=>e.dataset.backgroundId)')
        assert ids==sorted([p.stem for p in Path('poster-backgrounds/webp').glob('*.webp')],key=lambda id:[(1,int(p)) if p.isdigit() else (0,p.lower()) for p in re.split(r'(\d+)',id)])
        for id in ids:
            page.locator(f'[data-background-id={id}]').click()
            assert page.evaluate('async()=>await backgroundReady')
            assert page.evaluate("id=>{const e=approvedBackgrounds.find(e=>e.id===id);return G('approved-bg-image').getAttribute('src')===e.image && document.querySelector('[data-background-id='+id+'] img').getAttribute('src')===e.thumb}",id)
            page.evaluate('posterEditor.flush()')
            state=page.evaluate('collectDraft()')
            page.evaluate('draft=>posterEditor.open({draft})',state)
            expect(page.locator(f'[data-background-id={id}]')).to_have_attribute('aria-pressed','true')
            regions=page.evaluate("selectors=>{const p=G('poster').getBoundingClientRect();return selectors.map(s=>{const r=document.querySelector(s).getBoundingClientRect();return [(r.left-p.left)/p.width,(r.top-p.top)/p.height,r.width/p.width,r.height/p.height]})}",selectors)
            pdf=out/f'{id}-{language}.pdf';page.pdf(path=str(pdf),prefer_css_page_size=True,print_background=False)
            with fitz.open(pdf) as doc:
                assert doc.page_count==1,(id,language,doc.page_count)
                # Chrome can emit invisible black extraction text over painted glyphs.
                # Check the rasterized PDF pixels in each actual component instead.
                for region,color in zip(regions,colors):
                    x,y,w,h=region
                    clip=fitz.Rect(x*doc[0].rect.width,y*doc[0].rect.height,(x+w)*doc[0].rect.width,(y+h)*doc[0].rect.height)
                    # Resolve thin Arabic glyphs at print resolution before matching colors.
                    pix=doc[0].get_pixmap(matrix=fitz.Matrix(6,6),clip=clip)
                    pixels=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                    target=tuple(int(color[i:i+2],16) for i in (1,3,5))
                    masks=[channel.point([255 if abs(value-target[i])<=6 else 0 for value in range(256)]) for i,channel in enumerate(pixels.split())]
                    mask=ImageChops.multiply(ImageChops.multiply(masks[0],masks[1]),masks[2])
                    matches=mask.histogram()[255]
                    assert matches>5,(id,language,color,matches)
                assert abs(doc[0].rect.width-595.28)<1 and abs(doc[0].rect.height-841.89)<1
                source=ImageOps.exif_transpose(Image.open('poster-backgrounds/webp/'+id+'.webp')).convert('RGB')
                embedded=[doc.extract_image(img[0]) for img in doc[0].get_images() if (img[2],img[3])==source.size]
                assert embedded,(id,'background absent from PDF')
                actual=Image.open(io.BytesIO(embedded[0]['image'])).convert('RGB')
                assert max(ImageStat.Stat(ImageChops.difference(actual,source)).mean)<3,(id,'wrong PDF background')
        page.locator('[data-background-id=bg2]').click();page.evaluate('posterEditor.flush()')
        page.locator('#poster').screenshot(path=str(out/f'poster-{language}.png'))
    # Restoring a removed or replaced background must retain its exact version.
    pinned=page.evaluate("collectDraft()")
    page.evaluate("""draft=>{const e=approvedBackgrounds.find(e=>e.id===draft.design.bgId);e.retired=true;window.__entry=e;}""",pinned)
    page.evaluate('draft=>posterEditor.open({draft})',pinned)
    assert page.evaluate('selectedBackgroundVersion')==pinned['design']['bgVersion']
    expect(page.locator('[data-saved-background-id=bg2]')).to_have_attribute('aria-pressed','true')
    page.evaluate('window.__entry.retired=false;renderBackgroundGallery()')
    page.set_viewport_size({'width':390,'height':844});page.evaluate('fitPreview()')
    assert page.locator('#poster').bounding_box()['width']<=390
    page.screenshot(path=str(out/'poster-mobile.png'),full_page=True)
    # A browser reload restores the four separate colors and selected background.
    page.reload();page.evaluate('posterEditor.open()')
    for id,color in zip(['project-color','description-color','q-color','t-color'],colors):
        expect(page.locator('#'+id)).to_have_value(color)
    expect(page.locator('[data-background-id=bg2]')).to_have_attribute('aria-pressed','true')
    page.evaluate("G('slogan-color').value='#abcdef';applyDesign()")
    expect(page.locator('#slogan-output')).to_have_css('color','rgb(171, 205, 239)')
    assert page.evaluate("collectDraft().design.sloganColor")=='#abcdef'
    # Older posters without sloganColor keep the previous white closing-sentence color.
    assert page.evaluate("async()=>{await applyDraft({design:{qColor:'#123456',tColor:'#654321'}});return G('slogan-color').value;}")=='#ffffff'
    assert page.evaluate("""async colors=>{
      await applyDraft({design:{projectColor:colors[0],descriptionColor:colors[1],qColor:colors[2],tColor:colors[3],sloganColor:'#abcdef',bgId:'bg2'}});
      return [G('project-color').value,G('description-color').value,G('q-color').value,G('t-color').value,G('slogan-color').value];
    }""",colors)==colors+['#abcdef']
    page.evaluate('clearPoster()')
    for id,color in zip(['project-color','description-color','q-color','t-color'],colors):
        expect(page.locator('#'+id)).to_have_value(color)
    assert page.locator('input[id$="-hex"]').count()==0
    print(f'{len(ids)} backgrounds × 2 languages: identity, PDF pixels, A4 page; color isolation, legacy/local persistence, five image ratios, bounds and mobile passed.')
    browser.close()
