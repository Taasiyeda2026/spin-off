"""Focused typography/header acceptance; synthetic local drafts, no accounts or backend."""
import os
from pathlib import Path
import fitz
from playwright.sync_api import sync_playwright

out=Path('test-results/poster-header');out.mkdir(parents=True,exist_ok=True)
url=os.getenv('POSTER_TEST_URL','http://127.0.0.1:8000/poster.html')
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'))
    errors=[]
    def setup():
        page=browser.new_page(viewport={'width':1400,'height':1300})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('**/*.supabase.co/**',lambda route:route.abort())
        page.goto(url)
        page.evaluate('posterEditor.open()')
        page.evaluate('document.fonts.ready')
        page.evaluate("G('solution-type').value='physical';updateSolutionTypeHeading()")
        return page
    for lang in ['he','ar']:
        page=setup()
        if lang=='ar':page.locator('#poster-editor-language').click()
        for long in [False,True]:
            title=('מערכת חכמה להגנה על הסביבה' if lang=='he' else 'نظام ذكي لحماية البيئة')
            if long:title='W'*(35 if lang=='he' else 40)
            desc=('מערכת שמסייעת לזהות בעיות בסביבה ולפעול בזמן באמצעות חיישנים וטכנולוגיות מהחלל.' if lang=='he' else 'نظام يساعد على اكتشاف المشكلات البيئية والعمل في الوقت المناسب باستخدام المستشعرات وتقنيات الفضاء.')
            names=(['משתתף לדוגמה עם שם משפחה ארוך']*8 if lang=='he' else ['مشارك تجريبي مع اسم عائلة طويل']*8) if long else (['נועה לדוגמה','יובל לדוגמה'] if lang=='he' else ['نور للتجربة','رامي للتجربة'])
            values={'poster-project':title,'short-desc':desc[:105 if lang=='he' else 85],'solution-type':'physical','poster-class':'ו׳ 2' if lang=='he' else 'السادس 2','poster-school':'בית הספר לדוגמה' if lang=='he' else 'مدرسة تجريبية','poster-students':', '.join(names),'slogan':'טכנולוגיות החלל עוזרות לשמור על הסביבה שלנו' if lang=='he' else 'تقنيات الفضاء تساعدنا في حماية بيئتنا','problem':'בעיה לדוגמה' if lang=='he' else 'مشكلة تجريبية'}
            # Loading synthetic saved state exercises the same path as existing posters.
            page.evaluate('data=>posterEditor.open({draft:{values:data.values,participants:data.names}})',{'values':values,'names':names})
            page.evaluate('document.fonts.ready')
            page.evaluate('fitPreview()')
            metrics=page.evaluate("""() => {
                const p=G('poster'),scale=p.getBoundingClientRect().width/p.offsetWidth;
                const rect=id=>{const r=G(id).getBoundingClientRect(),pr=p.getBoundingClientRect();return {top:(r.top-pr.top)/scale,bottom:(r.bottom-pr.top)/scale,height:r.height/scale};};
                const t=rect('poster-project'),d=rect('short-desc-box'),b=rect('p-bar'),n=rect('p-names');
                const logo=G('logo-box').getBoundingClientRect(),pr=p.getBoundingClientRect();
                const logoMid=(logo.top+logo.height/2-pr.top)/scale;
                const boxes=Object.keys(LAYOUT).map(id=>{const e=G(id);return {id,x:e.offsetLeft,y:e.offsetTop,w:e.offsetWidth,h:e.offsetHeight};});
                return {gaps:[d.top-t.bottom,b.top-d.bottom,n.top-b.bottom,G('c-problem').offsetTop-n.bottom],top:t.top,logoMid,
                  contentTop:G('c-problem').offsetTop,leftTop:G('c-solution').offsetTop,
                  rightEnd:G('c-requirements').offsetTop+G('c-requirements').offsetHeight,
                  leftEnd:G('process-surface').offsetTop+G('process-surface').offsetHeight,
                  slogan:G('c-slogan').offsetTop,main:G('main-image-box').offsetHeight,pair:G('img-pair').offsetHeight,
                  clipped:['poster-project','poster-students'].filter(id=>G(id).scrollHeight>G(id).clientHeight+1),
                  weights:[...document.querySelectorAll('#poster .bq,#poster-project,#slogan-output,#slogan-output *')].map(e=>getComputedStyle(e).fontWeight),
                  sizes:['poster-project','solution-description-heading','c-problem','poster-students'].map(id=>getComputedStyle(G(id)).fontSize),
                  boxes};
            }""")
            assert all(w=='700' for w in metrics['weights']),metrics
            assert not metrics['clipped'] and metrics['top']>=0,metrics
            assert abs(metrics['gaps'][0]-4)<1 and abs(metrics['gaps'][1]-18)<1 and abs(metrics['gaps'][2]-4)<1,metrics
            assert metrics['gaps'][3]>=17,metrics
            assert metrics['top']<=metrics['logoMid']+1,metrics
            if not long:
                assert abs(metrics['gaps'][3]-36)<1,metrics
                assert abs(metrics['top']-metrics['logoMid'])<2,metrics
            assert metrics['contentTop']==metrics['leftTop'],metrics
            assert abs(metrics['rightEnd']-metrics['leftEnd'])<1,metrics
            assert metrics['slogan']-metrics['rightEnd']==18,metrics
            assert metrics['main']>=250 and metrics['pair']>=170,metrics
            meta=page.evaluate("""() => {
              const poster=G('poster').offsetWidth;
              const tops=id=>G(id).offsetTop,h=id=>G(id).offsetHeight;
              const gap=(a,b)=>tops(b)-(tops(a)+h(a));
              return {
                bar:G('p-bar').offsetWidth, names:G('p-names').offsetWidth,
                heights:['c-problem','c-target','c-question'].map(id=>G(id).offsetHeight),
                firstGaps:[gap('c-problem','c-target'),gap('c-target','c-question')],
                processGaps:[gap('c-feedback','c-improvement'),gap('c-improvement','c-value')],
                expected:Math.round(poster-364)
              };
            }""")
            assert abs(meta['bar']-meta['expected'])<=2 and abs(meta['names']-meta['expected'])<=2,meta
            assert meta['heights']==[85,85,85],meta
            assert meta['firstGaps'][0]==meta['firstGaps'][1],meta
            assert meta['processGaps'][0]==meta['processGaps'][1],meta
            for i,a in enumerate(metrics['boxes']):
                assert a['x']>=0 and a['y']>=0 and a['x']+a['w']<=794 and a['y']+a['h']<=1123,a
                for b in metrics['boxes'][i+1:]:
                    if {a['id'],b['id']} & {'c-feedback','c-improvement','c-value','process-surface'}:
                        continue
                    assert not (a['x']<b['x']+b['w'] and b['x']<a['x']+a['w'] and a['y']<b['y']+b['h'] and b['y']<a['y']+a['h']),(a,b)
            assert page.locator('#poster-project').input_value()==title
            assert page.locator('#short-desc').input_value()==desc[:105 if lang=='he' else 85]
            assert page.evaluate("""() => {
              const names=G('poster-students'),original=names.value;
              names.value=Array(8).fill('Synthetic participant with a long family name').join(', ');syncNamesToPanel();
              const host=G('p-hdr'),h=host.getBoundingClientRect(),t=G('poster-project').getBoundingClientRect(),scale=h.width/host.offsetWidth;
              const aligned=Math.abs(parseFloat(host.style.getPropertyValue('--glow-y'))-(t.top+t.height/2-h.top)/scale)<1;
              names.value=original;syncNamesToPanel();return aligned;
            }"""),'Title glow did not follow participant wrapping'
            process=page.evaluate("""() => {
              const ids=['c-feedback','c-improvement','c-value'];
              const measure=text=>{
                const box=text.closest('.box'),bi=box.querySelector('.bi'),bq=box.querySelector('.bq');
                const biRect=bi.getBoundingClientRect(),groupTop=bq.getBoundingClientRect().top,groupBottom=text.getBoundingClientRect().bottom;
                return {x:box.offsetLeft,w:box.offsetWidth,h:box.offsetHeight,center:box.offsetLeft+box.offsetWidth/2,clipped:text.scrollHeight>text.clientHeight+2,weight:getComputedStyle(text).fontWeight,align:getComputedStyle(text).textAlign,counter:getComputedStyle(box.querySelector('.counter')).display,vCenter:Math.abs((groupTop+groupBottom)/2-(biRect.top+biRect.bottom)/2)};
              };
              const rows=[];
              for(const sample of ['','קצר','W'.repeat(60)]){
                for(const id of ids){const text=G(id).querySelector('textarea');text.value=sample;updateCounterFor(text);rows.push(measure(text));}
              }
              const surface=G('process-surface');
              return {rows,arrows:['arrow-feedback-improvement','arrow-improvement-value'].map(id=>{const a=G(id);return {center:a.offsetLeft+a.offsetWidth/2,h:a.offsetHeight,w:a.offsetWidth};}),surface:[surface.offsetLeft,surface.offsetTop,surface.offsetWidth,surface.offsetHeight],valueBottom:G('c-value').offsetTop+G('c-value').offsetHeight,firstTop:G('c-feedback').offsetTop,gaps:ids.slice(1).map((id,i)=>G(id).offsetTop-G(ids[i]).offsetTop-G(ids[i]).offsetHeight),firstGaps:['c-target','c-question'].map((id,i)=>G(id).offsetTop-G(['c-problem','c-target'][i]).offsetTop-G(['c-problem','c-target'][i]).offsetHeight)};
            }""")
            assert abs(process['surface'][0]-75)<=1 and abs(process['surface'][2]-268)<=1 and abs(process['surface'][3]-282)<=1,process
            assert process['surface'][0]==process['rows'][0]['x'] and process['surface'][2]==process['rows'][0]['w'],process
            assert abs(process['firstTop']-process['surface'][1]-8)<=1,process
            assert abs((process['surface'][1]+process['surface'][3]-process['valueBottom'])-8)<=1,process
            assert abs(process['gaps'][0]-process['gaps'][1])<=1,process
            assert abs(process['firstGaps'][0]-process['firstGaps'][1])<=1,process
            assert all(not row['clipped'] and row['weight']=='400' and row['align']=='center' and row['counter']=='none' and row['vCenter']<4 for row in process['rows']),process
            assert all(abs(row['w']-process['surface'][2])<=1 and abs(row['x']-process['surface'][0])<=1 and row['h']==72 for row in process['rows']),process
            assert all(abs(a['center']-(process['surface'][0]+process['surface'][2]/2))<1 and a['w']==28 for a in process['arrows']),process
            if long:
                page.locator('#poster').screenshot(path=str(out/f'poster-long-{lang}.png'))
                continue
            # Populate the remaining answers and images only for visual review.
            page.evaluate("""lang=>{
              qs('#poster .box textarea:not([hidden])').forEach(e=>{e.value=lang==='he'?'תשובה לדוגמה לצורך בדיקת הפוסטר':'إجابة تجريبية لفحص الملصق';});
              for(const id of ['feedback','improvement','value'])G(id).value=(lang==='he'?'בדקנו ושיפרנו את הפתרון בעקבות המשוב שקיבלנו מהמשתמשים. '.repeat(2):'اختبرنا الحل وحسّناه بناء على ملاحظات المشاركين في التجربة. '.repeat(2)).slice(0,60);
              for(const id of ['research1','research2','findings1','findings2','findings3','requirements1','requirements2','requirements3','use1','use2','use3'])G(id).value=lang==='he'?'תשובה לדוגמה':'إجابة تجريبية';
              updateAllCombinedFields();
              const svg='<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"><rect width="300" height="300" fill="#12354d"/><circle cx="150" cy="150" r="80" fill="#52c0ce"/><path d="M40 220L260 80M50 70L250 240" stroke="white" stroke-width="12"/></svg>';
              for(const id of ['img-main','img-1','img-2']){const img=G(id);if(img){img.src='data:image/svg+xml;base64,'+btoa(svg);img.classList.add('show');img.parentElement.querySelector('.iph')?.style.setProperty('display','none');}}
            }""",lang)
            page.evaluate("""() => {
              const colors={ 'project-color':'#eeeeff','description-color':'#ddffee','q-color':'#ffeecc','t-color':'#ffffff','slogan-color':'#ffcc00' };
              for(const [id,color] of Object.entries(colors))G(id).value=color;
              G('border-color').value='#58e7ff';G('arrow-color').value='#00e5ff';applyDesign();
            }""")
            assert page.evaluate("['poster-project','solution-description-heading','slogan-output'].map(id=>getComputedStyle(G(id)).color)")==['rgb(238, 238, 255)','rgb(221, 255, 238)','rgb(255, 204, 0)']
            assert page.locator('#arrow-feedback-improvement .shaft').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(0, 229, 255)'
            assert page.locator('#c-feedback').evaluate('(e)=>getComputedStyle(e).borderTopColor')=='rgb(88, 231, 255)'
            assert page.evaluate("G('tab-design').querySelectorAll('input[type=color]').length")==7
            assert page.evaluate("G('tab-design').querySelectorAll('[data-design-hex],input[id$=\"-hex\"]').length")==0
            assert page.evaluate("collectDraft().design.sloganColor")=='#ffcc00'
            page.evaluate("async()=>await Promise.all(['img-main','img-1','img-2','logo-img'].map(id=>G(id).decode()))")
            page.locator('#poster').screenshot(path=str(out/f'poster-{lang}.png'))
            # Switch layouts without touching saved images, answers or identity.
            for kind,ratio,count in [('web',16/9,2),('app',9/16,3),('physical',1,3)]:
                state=page.evaluate("""kind=>{
                  const before=collectDraft();
                  G('solution-type').value=kind;updateSolutionTypeHeading();
                  const after=collectDraft(),rect=id=>G(id).getBoundingClientRect();
                  const m=rect('main-image-box'),a=rect('image-box-1'),b=rect('image-box-2'),r=rect('c-research'),u=rect('c-use');
                  const header=['poster-school','poster-class','poster-students'].every(id=>before.values[id]===after.values[id]);
                  return {header,images:JSON.stringify(before.images)===JSON.stringify(after.images),main:m.width/m.height,secondary:a.width/a.height,count:b.width?3:2,researchLeft:r.left<rect('c-problem').left,useAbove:u.top<m.top,processBelow:rect('c-feedback').top>r.bottom||kind!=='web',appRow:kind!=='app'||(Math.abs(m.top-a.top)<1&&Math.abs(a.top-b.top)<1&&Math.abs(m.width-a.width)<1&&Math.abs(a.width-b.width)<1&&Math.abs(m.height-b.height)<1&&Math.abs((a.left-m.right)-(b.left-a.right))<1&&u.bottom<=m.top&&rect('c-target').bottom<=m.top&&rect('c-question').top>=m.bottom&&rect('c-feedback').top>=m.bottom&&r.top>=rect('c-value').bottom&&Math.abs(rect('c-solution').top-rect('c-problem').top)<1&&Math.abs(u.top-rect('c-target').top)<1&&Math.abs(r.bottom-rect('c-requirements').bottom)<1)};
                }""",kind)
                assert state['header'] and state['images'] and state['count']==count,state
                assert abs(state['main']-ratio)<.04 and abs(state['secondary']-ratio)<.04,state
                assert state['researchLeft']==(kind in ['web','app']) and state['useAbove']==(kind in ['web','app']) and state['processBelow'] and state['appRow'],state
                page.locator('#poster').screenshot(path=str(out/f'poster-{kind}-{lang}.png'))
                page.pdf(path=str(out/f'poster-{kind}-{lang}.pdf'),prefer_css_page_size=True,print_background=True)
                with fitz.open(out/f'poster-{kind}-{lang}.pdf') as doc:
                    assert len(doc)==1
                    assert abs(doc[0].rect.width-595.28)<1 and abs(doc[0].rect.height-841.89)<1
            screen=page.evaluate("['p-bar','p-names','short-desc-box'].map(id=>[G(id).style.top,G(id).style.height])")
            page.pdf(path=str(out/f'poster-{lang}.pdf'),prefer_css_page_size=True,print_background=True)
            assert page.evaluate("['p-bar','p-names','short-desc-box'].map(id=>[G(id).style.top,G(id).style.height])")==screen
            with fitz.open(out/f'poster-{lang}.pdf') as doc:
                assert len(doc)==1
                assert abs(doc[0].rect.width-595.28)<1 and abs(doc[0].rect.height-841.89)<1
                doc[0].get_pixmap(matrix=fitz.Matrix(1,1)).save(out/f'pdf-{lang}.png')
        page.close()
        print(lang,': headings/slogan 700; short/long saved/new header; exact gaps; fixed image/content coordinates; colors; single A4 passed')
    assert not errors,errors
    browser.close()
