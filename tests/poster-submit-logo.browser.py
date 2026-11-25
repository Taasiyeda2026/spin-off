"""Acceptance with isolated network fixtures; never changes live posters or schools."""
import base64, copy, hashlib, json, os, re
import fitz
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import sync_playwright, expect

url=os.getenv('POSTER_TEST_URL','http://127.0.0.1:8000/poster.html')
origin=f'{urlsplit(url).scheme}://{urlsplit(url).netloc}'
png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFtUAAAAASUVORK5CYII=')
hash_=hashlib.sha256(png).hexdigest()
ids=['230a7470-7352-467a-94e9-57f1ef0cec50','230a7470-7352-467a-94e9-57f1ef0cec51','230a7470-7352-467a-94e9-57f1ef0cec52']
posters={id:{'id':id,'code':str(222222+i),'activityId':f'activity-{i}','schoolId':'1' if i<2 else '2','revision':0,'updatedAt':'2026-11-25T00:00:00Z','state':{'values':{'poster-project':'Existing answer','poster-school':'Fixture School','poster-class':'4A'},'participants':['Student A'],'design':{'bgId':'bg2'},'media':{}}} for i,id in enumerate(ids)}
logos={'1':None,'2':None};receipts={};stored={};calls=[];fail_save=False;fail_submit=False;errors=[]
def info(p):
    return {**p,'schoolLogo':logos[p['schoolId']],'submittedAt':receipts.get((p['id'],p['revision']))}
def handle(route):
    global fail_save
    req=route.request;u=urlsplit(req.url);path=u.path
    if not req.url.startswith(origin+'/'):
        route.abort();return
    if path=='/rest/v1/rpc/lookup_login_user_by_username':
        route.fulfill(json=[{'auth_email':'manager@example.invalid','auth_user_id':'fixture','role':'activities_manager'}]);return
    if path=='/auth/v1/token':
        route.fulfill(json={'access_token':'fixture-manager','user':{'id':'fixture'}});return
    if path=='/functions/v1/poster-media':
        q=parse_qs(u.query);key=(q.get('schoolId',['poster'])[0],q['image'][0])
        if req.method=='PUT':stored[key]=req.post_data_buffer;route.fulfill(status=204)
        else:route.fulfill(body=stored[key],content_type='image/png')
        return
    if path=='/rest/v1/rpc/spacetech_school_logo':
        c=req.post_data_json;a,p=c['p_action'],c['p'];calls.append(('logo',a))
        if req.headers.get('authorization')!='Bearer fixture-manager':route.fulfill(json={'error':'denied'});return
        if a=='list':result={'schools':[{'id':i,'name':'School '+i,'logo':logos[i]} for i in logos]}
        elif a=='set':logos[p['schoolId']]=p['hash'];result={'saved':True}
        elif a=='remove':logos[p['schoolId']]=None;result={'saved':True}
        else:raise AssertionError(a)
        route.fulfill(json=result);return
    if path=='/rest/v1/rpc/spacetech_poster':
        c=req.post_data_json;a,p=c['p_action'],c['p'];calls.append(('poster',a))
        if a=='resume':result=next(info(x) for x in posters.values() if x['code']==p['code'])
        elif a=='load':result=info(posters[p['id']])
        elif a=='save':
            if fail_save:route.fulfill(status=503);return
            current=posters[p['id']]
            assert p['revision']==current['revision']
            if p['state']!=current['state']:current['revision']+=1;current['state']=p['state']
            result=info(current)
        elif a=='submit':
            if fail_submit:route.fulfill(status=503);return
            current=posters[p['id']];assert p['revision']==current['revision']
            receipts.setdefault((current['id'],current['revision']),'2026-11-25T00:01:00Z');result=info(current)
        elif a=='manage':result={'name':'Fixture Manager','admin':False,'activities':[{'id':x['activityId'],'school':'Fixture School','schoolId':x['schoolId'],'grade':'4','classGroup':'A','posters':[{**info(x),'title':x['state']['values']['poster-project']}]} for x in posters.values()]}
        else:raise AssertionError(a)
        route.fulfill(json=result);return
    route.continue_()
def context(browser):
    c=browser.new_context();c.add_init_script(f'window.posterCloudConfig={{url:{json.dumps(origin)},publishableKey:"fixture"}}');c.route('**/*',handle);return c

def resume(c,code):
    p=c.new_page();p.on('pageerror',lambda error:errors.append(str(error)));p.goto(url)
    p.get_by_role('button',name='המשך עבודה על פוסטר',exact=True).click();p.get_by_label('קוד הפוסטר',exact=True).fill(code);p.get_by_role('button',name='המשך',exact=True).click()
    expect(p.locator('#poster-project')).to_have_value('Existing answer');return p
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'))
    student=resume(context(browser),'222222');student.locator('[data-tab=content]').click()
    assert student.locator('#toolbar [id$="language"]').count()==1
    assert student.locator('#poster-panel-language,#logo-file').count()==0
    assert student.locator('#toolbar').get_by_role('button',name=re.compile('PDF')).count()==0
    assert student.locator('#poster-submit + #poster-pdf').count()==1
    for width in [1440,1024,768,390]:
        student.set_viewport_size({'width':width,'height':1000})
        assert student.locator('#toolbar').evaluate('(el)=>el.scrollWidth<=innerWidth')
        nav=student.locator('#toolbar .poster-nav').bounding_box();brand=student.locator('#toolbar .tb-brand').bounding_box()
        assert nav['x']<brand['x'] or width<=900
        assert student.locator('#fill-list .edit-card > label').evaluate_all('(els)=>els.every(el=>el.scrollWidth<=el.clientWidth&&el.scrollHeight<=el.clientHeight)')
    student.set_viewport_size({'width':1440,'height':1000})
    student.locator('#panel-problem').fill('Saved answer')
    student.locator('#poster-editor-language').click()
    expect(student.locator('[data-tab=content]')).to_have_class(re.compile('active'))
    expect(student.locator('#panel-problem')).to_have_value('Saved answer')
    student.locator('#poster-editor-language').click()
    student.locator('#img-main-file').set_input_files({'name':'fixture.png','mimeType':'image/png','buffer':png})
    student.locator('#poster-submit').click()
    expect(student.locator('#poster-submit-status')).to_have_text('הפוסטר נשמר ונשלח בהצלחה למערכת הניהול.')
    assert len(receipts)==1 and posters[ids[0]]['state']['media']['main']==hash_
    assert posters[ids[0]]['state']['values']['problem']=='Saved answer'
    assert posters[ids[0]]['state']['participants']==['Student A']
    student.locator('#poster-submit').dblclick()
    expect(student.locator('#poster-submit-status')).to_have_text('הפוסטר נשמר ונשלח בהצלחה למערכת הניהול.')
    assert len(receipts)==1
    fail_save=True
    student.locator('#panel-problem').fill('Offline answer')
    student.locator('#poster-submit').click()
    expect(student.locator('#poster-submit-status')).to_contain_text('לא ניתן לשלוח')
    expect(student.locator('#panel-problem')).to_have_value('Offline answer')
    fail_save=False;fail_submit=True
    student.locator('#poster-submit').click();expect(student.locator('#poster-submit-status')).to_contain_text('לא ניתן להתחבר')
    fail_submit=False;student.locator('#poster-submit').click();expect(student.locator('#poster-submit-status')).to_contain_text('בהצלחה')
    manager=context(browser).new_page();manager.goto(url);manager.get_by_role('button',name='כניסת מדריכים',exact=True).click()
    manager.get_by_label('שם משתמש',exact=True).fill('manager');manager.get_by_label('סיסמה',exact=True).fill('fixture');manager.get_by_role('button',name='כניסה',exact=True).click()
    expect(manager.locator('.poster-school-logos')).to_be_visible()
    assert manager.get_by_text('הוגש',exact=False).count()>=1
    manager.get_by_label('העלאת לוגו',exact=True).set_input_files({'name':'logo.png','mimeType':'image/png','buffer':png})
    manager.get_by_role('button',name='שמירת לוגו',exact=True).click()
    expect(manager.get_by_text('הלוגו עודכן בכל הפוסטרים של בית הספר.',exact=True)).to_be_visible()
    assert logos['1']==hash_ and logos['2'] is None
    first=resume(context(browser),'222222');second=resume(context(browser),'222223');other=resume(context(browser),'222224')
    expect(first.locator('#school-logo-box')).to_be_visible();expect(second.locator('#school-logo-box')).to_be_visible();expect(other.locator('#school-logo-box')).to_be_hidden()
    assert first.locator('#school-logo-img').evaluate('(el)=>getComputedStyle(el).objectFit')=='contain'
    first.locator('[data-tab=content]').click()
    first.evaluate('window.__printed=false;window.print=()=>{window.__printed=true}')
    first.locator('#poster-pdf').click();first.wait_for_function('window.__printed')
    with TemporaryDirectory() as directory:
        pdf=Path(directory)/'poster.pdf';first.pdf(path=pdf,prefer_css_page_size=True,print_background=True)
        with fitz.open(pdf) as document:
            assert document.page_count==1
            assert len(document[0].get_images())>=3
    with manager.expect_response(lambda response:urlsplit(response.url).path=='/rest/v1/rpc/spacetech_school_logo' and response.request.post_data_json['p_action']=='remove'):
        manager.get_by_role('button',name='הסרת לוגו',exact=True).click()
    expect(manager.get_by_text('הלוגו עודכן בכל הפוסטרים של בית הספר.',exact=True)).to_be_visible()
    no_logo=resume(context(browser),'222223');expect(no_logo.locator('#school-logo-box')).to_be_hidden()
    # Automatic defaults follow the interface language; manual edits survive both switching and reopening.
    localized=posters[ids[2]]
    localized.update(schoolId='2914',schoolDefault='מאי זיאדה -אלשיכון',classDefault='קבוצה 1')
    localized['state']['values'].update({'poster-school':'מאי זיאדה -אלשיכון','poster-class':'קבוצה 1'})
    logos['2914']=None
    edited=resume(context(browser),'222224');edited.locator('[data-tab=content]').click()
    expect(edited.locator('#panel-poster-school')).to_be_editable();expect(edited.locator('#panel-poster-class')).to_be_editable()
    expect(edited.locator('#c-research .bq > span')).to_have_text('מה למדנו מטכנולוגיות החלל?')
    edited.locator('#poster-editor-language').click()
    expect(edited.locator('#panel-poster-school')).to_have_value('مي زيادة - حي شيكون العرب')
    expect(edited.locator('#panel-poster-class')).to_have_value('المجموعة 1')
    expect(edited.locator('#c-research .bq > span')).to_have_text('ماذا تعلمنا من تكنولوجيا الفضاء؟')
    edited.locator('#panel-poster-school').fill('مدرسة معدّلة للاختبار')
    edited.locator('#panel-poster-class').fill('الصف الخامس ب')
    edited.locator('#poster-submit').click();expect(edited.locator('#poster-submit-status')).to_have_text('تم حفظ الملصق وإرساله بنجاح إلى نظام الإدارة.')
    assert posters[ids[2]]['schoolId']=='2914'
    reopened=resume(context(browser),'222224');reopened.locator('[data-tab=content]').click()
    expect(reopened.locator('#panel-poster-school')).to_have_value('مدرسة معدّلة للاختبار')
    expect(reopened.locator('#panel-poster-class')).to_have_value('الصف الخامس ب')
    reopened.locator('#poster-editor-language').click()
    expect(reopened.locator('#panel-poster-school')).to_have_value('مدرسة معدّلة للاختبار')
    expect(reopened.locator('#panel-poster-class')).to_have_value('الصف الخامس ب')
    # Solution type is independent from the 135-character description and survives language/save/reopen.
    expect(reopened.locator('#panel-solution-type')).to_have_value('')
    # Only submitted answers appear on the poster; editing questions remain in the panel.
    reopened.locator('#panel-short-desc').fill('תיק דיגיטלי לניהול משימות')
    reopened.locator('#panel-solution-type').select_option('app')
    expect(reopened.locator('#solution-description-heading')).to_have_text('אפליקציה: תיק דיגיטלי לניהול משימות')
    reopened.locator('#panel-slogan').fill('המשימות שלנו תמיד איתנו')
    expect(reopened.locator('#slogan')).to_have_value('המשימות שלנו תמיד איתנו')
    expect(reopened.locator('#c-slogan .bq')).to_be_hidden()
    expect(reopened.locator('label[for=panel-slogan]')).to_have_text('23. איך נציג את הפתרון שלנו במשפט אחד?')
    # Empty type on older posters shows only their description.
    reopened.locator('#panel-solution-type').select_option('')
    expect(reopened.locator('#solution-description-heading')).to_have_text('תיק דיגיטלי לניהול משימות')
    description='ת' * 135
    reopened.locator('#panel-short-desc').fill(description)
    for kind in ['physical','smart','app','web','digital']:
        reopened.locator('#panel-solution-type').select_option(kind)
        expected_ratio=9/16 if kind=='app' else 16/9 if kind in ['web','digital'] else 1
        for selector in ['#main-image-box','#img-pair .image-box']:
            for box in reopened.locator(selector).all():
                bounds=box.bounding_box();assert abs(bounds['width']/bounds['height']-expected_ratio)<0.02
        expect(reopened.locator('#short-desc')).to_have_value(description)
        expect(reopened.locator('#panel-counter-short-desc')).to_have_text('135/135')
    assert reopened.locator('#panel-solution-type option[value=other]').count()==0
    reopened.locator('#poster-editor-language').click()
    reopened.locator('#panel-solution-type').select_option('digital')
    expect(reopened.locator('#poster-solution-type')).to_have_text('מערכת דיגיטלית: ')
    reopened.locator('#poster-submit').click();expect(reopened.locator('#poster-submit-status')).to_contain_text('בהצלחה')
    assert posters[ids[2]]['state']['values']['solution-type']=='digital'
    assert posters[ids[2]]['state']['values']['short-desc']==description
    again=resume(context(browser),'222224');again.locator('[data-tab=content]').click()
    expect(again.locator('#panel-solution-type')).to_have_value('digital')
    expect(again.locator('#short-desc')).to_have_value(description)
    again.locator('#poster-editor-language').click()
    expect(again.locator('#poster-solution-type')).to_have_text('نظام رقمي: ')
    expect(again.locator('#poster-solution-description')).to_have_text(description)
    expect(again.locator('#slogan')).to_have_value('המשימות שלנו תמיד איתנו')
    expect(again.locator('#c-slogan .bq')).to_be_hidden()
    expect(again.locator('label[for=panel-slogan]')).to_have_text('23. كيف نعرض حلّنا في جملة واحدة؟')
    before=again.locator('#solution-description-heading').text_content()
    again.emulate_media(media='print')
    expect(again.locator('#solution-description-heading')).to_have_text(before)
    expect(again.locator('#solution-description-heading')).to_be_visible()
    expect(again.locator('#c-slogan .bq')).to_be_hidden()
    assert again.locator('#solution-description-heading').evaluate('(el)=>el.scrollHeight<=el.clientHeight')
    pdf=fitz.open(stream=again.pdf(prefer_css_page_size=True),filetype='pdf')
    assert len(pdf)==1
    assert 'كيف نعرض' not in pdf[0].get_text()
    again.emulate_media(media='null')
    with again.expect_popup() as popup:
        again.locator('#poster-visualization').click()
    visual=popup.value
    visual.wait_for_load_state()
    assert visual.evaluate('state.kind')=='digital'
    assert visual.evaluate('state.lang')=='ar'
    assert visual.evaluate('state.values.purpose')==description
    for kind in ['physical','smart','app','web','digital']:
        visual.evaluate('(kind)=>{state.kind=kind;state.values.appearance="A described solution";generate()}',kind)
        prompt=visual.evaluate('state.outputs[0].body')
        assert 'IMAGE 1' in prompt and 'IMAGE 2' in prompt and 'IMAGE 3' in prompt
        if kind=='digital':assert 'Digital system' in prompt and 'MAIN INTERFACE' in prompt
        expected_aspect='9:16' if kind=='app' else '16:9' if kind in ['web','digital'] else '1:1'
        assert expected_aspect+' aspect ratio each' in prompt
    # Import is one-time and the token carries no student answers in the URL.
    assert description not in visual.url
    assert visual.evaluate('localStorage.getItem("spacetech.poster.visualization."+new URLSearchParams(location.search).get("posterBrief"))') is None
    assert not errors,errors
    print('PASS: responsive header, final actions, language/state, save/submit/retry/idempotency, manager logo, school isolation, existing posters, removal and A4 PDF')
