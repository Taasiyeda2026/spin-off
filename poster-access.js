import { arabic, setArabic, translate as t, schoolNameArabic, classNameArabic, translateInterfaceText } from './poster-language.js?v=20261128-poster-complete-v1';
import { createPosterMedia, decodePosterState, encodePosterState, newToken, posterRequest, verifyPosterStaff, schoolLogoRequest, schoolLogoMedia } from './poster-cloud.js?v=20261128-poster-complete-v1';

import { dashboardLogin } from './poster-dashboard-login.js?v=20261128-poster-complete-v1';

const root = document.getElementById('poster-access-content');
const status = document.getElementById('poster-access-status');
const homeTitle = 'SpaceTech | פוסטר חקר';
const title = document.getElementById('poster-access-title');
const editor = window.posterEditor;
const drafts = window.posterDrafts;
const toolbar = document.createElement('div');
toolbar.className = 'poster-cloud-toolbar';
document.querySelector('#toolbar .poster-nav').append(toolbar);

const messages = {
  code: 'הקוד לא נמצא או שאינו זמין. בדקו אותו ונסו שוב.',
  denied: 'אין גישה לפוסטר. נסו להיכנס מחדש.',
  rate_limit: 'בוצעו ניסיונות רבים. המתינו ונסו שוב.',
  login: 'ההתחברות לא הושלמה. יש להתחבר דרך הדשבורד ולנסות שוב.',
  network: 'לא ניתן להתחבר כרגע. בדקו את החיבור ונסו שוב.',
  image: 'בחרו תמונת PNG, JPEG, WebP, GIF או AVIF בגודל של עד 8 MB.',
  invalid: 'בדקו את הפרטים ונסו שוב.',
  invalid_entry_code: 'קוד הכניסה החדש חייב להכיל 4–6 ספרות בלבד.',
  capacity: 'אין אפשרות להקצות קוד כרגע.',
  popup_blocked: 'חלון ההתחברות נחסם. יש לאפשר חלונות קופצים ולנסות שוב.',
  popup_closed: 'חלון ההתחברות נסגר לפני השלמת האימות. אפשר לנסות שוב.',
  popup_timeout: 'זמן ההתחברות הסתיים. אפשר לנסות שוב.',
};

let staff = null;
let waitForPosterSave = () => Promise.resolve();
window.addEventListener('poster:dirty',()=>{const el=toolbar.querySelector('[role=status]');if(el&&el.dataset.conflicted!=='true'){el.dataset.statusKey='שומר...';el.textContent=t('שומר...');}});
const editorHome = document.getElementById('poster-editor-home');
let managementLanguageRefresh = null;
let accessChoicesRefresh = null;
let leavingForHome = false;
editorHome.addEventListener('click', async (event) => {
  event.preventDefault();
  if(!accessRoot.hidden){window.location.assign(editorHome.href);return;}
  if (leavingForHome) return;
  leavingForHome = true;
  editorHome.setAttribute('aria-busy', 'true');
  try {
    await editor.flush();
    await waitForPosterSave();
    if (editor.hasUnsavedChanges() &&
        !confirm(t('יש שינויים שטרם נשמרו בענן. לחזור בכל זאת?'))) return;
    window.location.assign(editorHome.href);
  } catch (error) {
    alert(t(messages[error.message] ?? messages.network));
  } finally {
    leavingForHome = false;
    editorHome.removeAttribute('aria-busy');
  }
});

const language = document.getElementById('poster-editor-language');
const accessRoot = document.getElementById('poster-access');

function languageDestination() {
  const url = new URL(location.href);
  if (arabic) url.searchParams.delete('lang');
  else url.searchParams.set('lang', 'ar');
  return url;
}
function syncLanguageControls() {
  language.textContent = arabic ? 'עברית' : 'العربية';
  language.lang = arabic ? 'he' : 'ar';

  for(const toggle of document.querySelectorAll('#poster-editor-language')){
    toggle.textContent=language.textContent;toggle.lang=language.lang;
    toggle.setAttribute('aria-label',arabic?'מעבר לעברית':'التبديل إلى العربية');
  }
  accessRoot.lang = toolbar.lang = arabic ? 'ar' : 'he';
  const homeLabel = arabic ? 'العودة إلى الصفحة الرئيسية' : 'חזרה לדף הבית';
  for (const link of [editorHome]) {
    link.title = homeLabel;
    link.setAttribute('aria-label', homeLabel);
  }
}
syncLanguageControls();
function setPosterLanguage(value) {
  const destination=new URL(location.href);
  if(value) destination.searchParams.set('lang','ar');else destination.searchParams.delete('lang');
  history.replaceState(history.state,'',destination.href);
  setArabic(value);
  syncLanguageControls();
  window.dispatchEvent(new Event('poster:language-changed'));
}
function switchEditorLanguage() {
  if(language.disabled)return;
  const destination=languageDestination();
  history.replaceState(history.state,'',destination.href);
  setArabic(!arabic);
  syncLanguageControls();
  for(const control of toolbar.querySelectorAll('[data-translation-key]'))control.textContent=t(control.dataset.translationKey);
  for(const control of toolbar.querySelectorAll('[data-poster-code]'))control.textContent=t('קוד הפוסטר')+': '+control.dataset.posterCode;
  for(const control of toolbar.querySelectorAll('[data-status-key]'))control.textContent=t(control.dataset.statusKey);
  window.dispatchEvent(new Event('poster:language-changed'));
  if(!accessRoot.hidden){
    const walker=document.createTreeWalker(accessRoot,NodeFilter.SHOW_TEXT);
    while(walker.nextNode()){
      const node=walker.currentNode;
      if(node.parentElement.closest('article,summary,option,input,textarea'))continue;
      node.nodeValue=translateInterfaceText(node.nodeValue);
    }
    for(const el of accessRoot.querySelectorAll('[aria-label],[alt],[title]'))for(const attr of ['aria-label','alt','title']){
      if(el.hasAttribute(attr))el.setAttribute(attr,translateInterfaceText(el.getAttribute(attr)));
    }
    accessChoicesRefresh?.();managementLanguageRefresh?.();
  } else {editor.markChanged();}
}
for(const toggle of document.querySelectorAll('#poster-editor-language'))toggle.addEventListener('click',switchEditorLanguage);


function element(tag, text, parent = root) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  parent.append(node);
  return node;
}

function button(text, action, parent = root, primary = false) {
  const control = element('button', t(text), parent);
  control.type = 'button';
  control.dataset.translationKey = text;
  if (primary) control.dataset.primary = '';
  control.addEventListener('click', action);
  return control;
}

function screen(heading, back) {
  language.disabled=false;
  managementLanguageRefresh = null;accessChoicesRefresh=null;
  document.body.classList.add('poster-access-mode');
  document.getElementById('toolbar').hidden=false;toolbar.replaceChildren();
  document.getElementById('poster-access').classList.remove('is-home');
  root.replaceChildren();
  status.textContent = '';
  title.textContent = t(heading);
  title.focus();
  if (back) button('חזרה', back).dataset.back = '';
}

function field(form, label, properties) {
  const wrapper = element('label', t(label), form);
  const input = element('input', '', wrapper);
  Object.assign(input, properties);
  return input;
}

function showError(error) {
  status.textContent = t(messages[error.message] ?? messages.network);
}

function submit(form, label, action) {
  const submitButton = element('button', t(label), form);
  submitButton.type = 'submit';
  submitButton.dataset.primary = '';
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const back = root.querySelector('[data-back]');
    if (back) back.disabled = true;
    submitButton.disabled = true;
    status.textContent = '';
    try {
      await action();
    } catch (error) {
      showError(error);
    } finally {
      submitButton.disabled = false;
      if (back) back.disabled = false;
    }
  });
}

function home() {
  staff = null;
  screen(homeTitle);
  document.getElementById('poster-access').classList.add('is-home');
  const actions = element('nav', '', root);
  actions.className = 'poster-home-actions';
  actions.setAttribute('aria-label', t(homeTitle));
  button('יצירת פוסטר חדש', createEntry, actions, true);
  button('המשך עבודה על פוסטר', resumeEntry, actions, true);
  const researchEntry=button(arabic?'أسئلة الاستقصاء':'שאלות חקר',()=>resumeEntry(true),actions,true);
  button('כניסת מדריכים', instructorEntry, actions);
}

function codeForm(heading, caption, pattern, length, action) {
  screen(heading, home);
  const form = element('form');
  const code = field(form, caption, { required: true, pattern, maxLength: length, inputMode: 'numeric', dir: 'ltr' });
  submit(form, 'המשך', () => action(code.value));
  code.focus();
}

function createEntry() {
  codeForm('יצירת פוסטר חדש', 'קוד מדריך', '[0-9]{4}', 4, async (code) => {
    const ticket = newToken();
    const result = await posterRequest('activities', { code, ticket });
    createDetails(ticket, result.activities);
  });
}

function activityLabel(activity) {
  return [arabic?schoolNameArabic(activity.schoolId,activity.school):activity.school, arabic?classNameArabic(activity.grade??''):activity.grade, arabic?classNameArabic(activity.classGroup??''):activity.classGroup].filter(Boolean).join(' · ') || activity.id;
}

function createDetails(ticket, activities) {
  screen('יצירת פוסטר חדש', createEntry);
  const form = element('form');
  const label = element('label', t('בית הספר והכיתה'), form);
  const activity = element('select', '', label);
  activity.required = true;
  if (activities.length > 1) element('option', t('בחרו פעילות'), activity).value = '';
  for (const item of activities) element('option', activityLabel(item), activity).value = item.id;
  accessChoicesRefresh=()=>{for(const option of activity.options){const item=activities.find(item=>item.id===option.value);option.textContent=item?activityLabel(item):t('בחרו פעילות')}};
  const access = { session: newToken() };
  const requestId = crypto.randomUUID();
  let created;
  submit(form, 'יצירת פוסטר', async () => {
    created ??= await posterRequest('create', { requestId, ticket, activityId: activity.value, participants: [] }, access);
    await openPoster(created, access, home);
    document.querySelector('[data-tab="students"]').click();
    document.querySelector('#pcf input')?.focus();
  });
}

function resumeEntry(research = false) {
  codeForm('המשך עבודה על פוסטר', 'קוד הפוסטר', '[1-9][0-9]{5}', 6, async (code) => {
    const access = { session: newToken() };
    const poster = await posterRequest('resume', { code }, access);
    await openPoster(poster, access, home);
    if(research===true) window.researchWorksheet?.show();
  });
}

function instructorEntry() {
  staff = null;
  screen('כניסת מדריכים', home);
  const form = element('form');
  element('p', t('התחברות באמצעות חשבון דשבורד תעשיידע.'), form);
  submit(form, 'התחברות דרך הדשבורד', async () => {
    try {
      const token = await dashboardLogin();
      await verifyPosterStaff(token);
      staff = { bearer: token };
      await manage();
    } catch (error) {
      staff = null;
      throw error;
    }
  });
}

function copyCode(code) {
  return navigator.clipboard.writeText(code).then(() => { status.textContent = t('הקוד הועתק'); }).catch(showError);
}

async function openFromManagement(id, mode) {
  const managementArabic=arabic;
  const poster = await posterRequest('load', { id }, staff);
  const back=async()=>{setPosterLanguage(managementArabic);await manage();};
  await openPoster(poster, staff, back, mode !== 'edit');
  if (mode === 'pdf') await window.producePdf();
}

async function manage() {
  const data = await posterRequest('manage', {}, staff);
  try {data.logoSchools=(await schoolLogoRequest('list',{},staff)).schools;} catch(error) {if(error.message!=='denied')throw error;data.logoSchools=[];}
  renderManagement(data);
}

function renderManagement(data, previous = null) {
  screen('ניהול הפוסטרים שלי', home);
  element('p', data.name);
  const L=(he,ar)=>arabic?ar:he;
  if(data.logoSchools?.length){const settings=element('details','');settings.className='pm-settings';element('summary',L('הגדרות פעילות · לוגו בית הספר','إعدادات النشاط · شعار المدرسة'),settings);renderSchoolLogos(data.logoSchools,settings);}
  if (data.code) {
    element('p', t('קוד מדריך') + ': ' + data.code);
    button('העתקת קוד מדריך', () => copyCode(data.code));
  }
  const panel=element('section','');panel.className='pm-panel';
  const stats=element('div','',panel);stats.className='pm-stats';
  const search = field(panel, 'חיפוש לפי שם המוצר, משתתפים או קוד', { type: 'search' });
  const filters=element('div','',panel);filters.className='pm-filters';
  const school=element('select','',filters), group=element('select','',filters), state=element('select','',filters), sort=element('select','',filters);
  const options=(select,items)=>{const old=select.value;select.replaceChildren();for(const [value,label] of items)element('option',label,select).value=value;if(items.some(([v])=>v===old))select.value=old;};
  const refreshFilters=()=>{options(school,[['',L('כל בתי הספר','جميع المدارس')],...Array.from(new Map(data.activities.map(a=>[String(a.schoolId??a.school),arabic?schoolNameArabic(a.schoolId,a.school):a.school])).entries())]);options(group,[['',L('כל הקבוצות','جميع المجموعات')],...Array.from(new Set(data.activities.map(a=>String(a.classGroup??'')).filter(Boolean))).map(v=>[v,arabic?classNameArabic(v):v])]);options(state,[['',L('כל הסטטוסים','جميع الحالات')],['draft',L('טיוטה','مسودة')],['submitted',L('הוגש','تم التسليم')],['archive',L('בארכיון','في الأرشيف')]]);options(sort,[['default',L('מיון לפי פעילות','الترتيب حسب النشاط')],['recent',L('עדכון אחרון','آخر تحديث')]]);for(const [el,he,ar] of [[school,'בית ספר','المدرسة'],[group,'קבוצה','المجموعة'],[state,'סטטוס','الحالة'],[sort,'מיון','الترتيب']])el.setAttribute('aria-label',L(he,ar));};refreshFilters();
  const controls=element('div','',panel);controls.className='pm-controls';
  const results = element('div','',panel);results.className='pm-results';
  const expand=button('פתח הכל',()=>results.querySelectorAll('.pm-activity').forEach(r=>r.open=true),controls);const collapse=button('סגור הכל',()=>results.querySelectorAll('.pm-activity').forEach(r=>r.open=false),controls);
  const refreshLabels=()=>{expand.textContent=L('פתח הכל','فتح الكل');collapse.textContent=L('סגור הכל','إغلاق الكل');const settings=root.querySelector('.pm-settings summary');if(settings)settings.textContent=L('הגדרות פעילות · לוגו בית הספר','إعدادات النشاط · شعار المدرسة');};refreshLabels();
  search.value = previous?.query ?? '';
  function render(expanded = null) {
    results.replaceChildren();
    const query = search.value.trim().toLocaleLowerCase();
    const count = activity => activity.posters.filter(p=>!p.deleted).length;
    const all=data.activities.flatMap(a=>a.posters.filter(p=>!p.deleted));stats.replaceChildren();for(const [n,label] of [[data.activities.length,L('פעילויות','أنشطة')],[all.length,L('פוסטרים','ملصقات')],[all.filter(p=>!p.archived&&!p.submittedAt).length,L('טיוטות','مسودات')],[all.filter(p=>!p.archived&&p.submittedAt).length,L('הוגשו','تم تسليمها')],[all.filter(p=>p.archived).length,L('בארכיון','في الأرشيف')]]){const tile=element('div','',stats);element('strong',String(n),tile);element('span',label,tile);}
    const latest=a=>Math.max(0,...a.posters.filter(p=>!p.deleted).map(p=>Date.parse(p.updatedAt)||0));
    const ordered = [...data.activities].sort((a,b)=>sort.value==='recent'?latest(b)-latest(a):Number(count(b)>0)-Number(count(a)>0));
    for (const activity of ordered) {
      if(school.value&&String(activity.schoolId??activity.school)!==school.value||group.value&&String(activity.classGroup??'')!==group.value)continue;
      const matching = activity.posters.filter(p=>!p.deleted).filter(p=>!state.value||(p.archived?'archive':p.submittedAt?'submitted':'draft')===state.value).filter((poster) =>
        [poster.title, poster.participants, poster.code].some((value) => String(value ?? '').toLocaleLowerCase().includes(query)));
      if ((query||state.value) && !matching.length) continue;
      if(sort.value==='recent')matching.sort((a,b)=>(Date.parse(b.updatedAt)||0)-(Date.parse(a.updatedAt)||0));
      const row = element('details', '', results);
      row.className='pm-activity';row.dataset.activityId = activity.id;
      row.open = expanded ? expanded.has(activity.id) : Boolean(query||state.value||school.value||group.value);
      row.classList.toggle('no-posters', count(activity)===0);
      const summary=element('summary','',row);const heading=element('span','',summary);heading.className='pm-heading';element('strong',(arabic?schoolNameArabic(activity.schoolId,activity.school):activity.school)||activity.id,heading);element('small',[arabic?classNameArabic(activity.grade??''):activity.grade,arabic?classNameArabic(activity.classGroup??''):activity.classGroup,t('טכנולוגיות החלל')].filter(Boolean).join(' · '),heading);element('span',String(matching.length)+' '+t('פוסטרים'),summary).className='pm-count';
      if(!count(activity))element('span',arabic?'لم يبدأ بعد':'טרם התחילו',summary).className='empty-poster-status';
      const idLine = element('div', '', row);
      idLine.className = 'poster-activity-id';
      element('span', t('מזהה פעילות') + ':', idLine);
      const identifier = element('bdi', activity.id, idLine);
      identifier.dir = 'ltr';identifier.title=activity.id;
      const copy = button('העתק', async () => {
        try {
          await navigator.clipboard.writeText(activity.id);
          copy.textContent = t('הועתק');
          clearTimeout(copy.resetTimer);
          copy.resetTimer = setTimeout(() => { copy.textContent = t('העתק'); }, 1500);
        } catch (error) {
          showError(error);
        }
      }, idLine);
      copy.setAttribute('aria-label', t('העתקת מזהה פעילות'));
      for (const poster of matching) {
        const card = element('article', '', row);
        card.className='pm-card';const top=element('div','',card);top.className='pm-card-top';element('h2',poster.title||t('פוסטר ללא שם'),top);const badge=element('span',t(poster.archived?'בארכיון':poster.submittedAt?'הוגש':'טיוטה'),top);badge.className='pm-status '+(poster.archived?'archive':poster.submittedAt?'submitted':'draft');const code=button('העתקת קוד',()=>copyCode(poster.code),top);code.textContent=String(poster.code??'')+' ⧉';code.className='pm-code';code.setAttribute('aria-label',t('העתקת קוד'));const meta=element('p',[poster.participants,new Date(poster.updatedAt).toLocaleString(arabic?'ar':'he-IL')].filter(Boolean).join(' · '),card);meta.className='pm-meta';const bar=element('div','',card);bar.className='pm-actions';
        if (!poster.deleted) {
          button('צפייה', () => openFromManagement(poster.id, 'view').catch(showError), bar,true);
          if (!poster.archived) button('עריכה', () => openFromManagement(poster.id, 'edit').catch(showError), bar);
          button('PDF', () => openFromManagement(poster.id, 'pdf').catch(showError), bar);
        }
        const actions = [...(!poster.archived ? [['rotate', 'החלפת קוד']] : []),
            ...(data.admin ? [poster.archived ? ['unarchive', 'הוצאה מהארכיון'] : ['archive', 'ארכוב']] : []), ['delete', 'מחיקה']];
        const menu=element('details','',bar);menu.className='pm-menu';const trigger=element('summary','⋯',menu);trigger.setAttribute('aria-label',L('פעולות נוספות','إجراءات إضافية'));const menuBody=element('div','',menu);menuBody.className='pm-menu-body';
        for (const [action, label] of actions) {
          button(label, async (event) => {
            if (!confirm(t(label) + ' – ' + t('להמשיך?'))) return;
            const control = event.currentTarget;
            control.disabled = true;
            try {
              const updated = await posterRequest(action, { id: poster.id }, staff);
              // The RPC returns the authoritative status. Keep the management
              // screen, filters, open activities and scroll position intact.
              const index = activity.posters.findIndex(item => item.id === poster.id);
              if (index !== -1) {
                if (action==='delete' || updated.deleted) activity.posters.splice(index, 1);
                else activity.posters[index] = { ...activity.posters[index], ...updated };
              }
              const expanded = new Set(Array.from(results.querySelectorAll('.pm-activity[open]'), item => item.dataset.activityId));
              const scrollTop = window.scrollY;
              render(expanded);
              window.scrollTo(0, scrollTop);
            } catch (error) {
              showError(error);
              control.disabled = false;
            }
          }, menuBody).classList.toggle('pm-danger',action==='delete');
        }
      }
    }
    if (!results.childElementCount) element('p', t('לא נמצאו פעילויות או פוסטרים מתאימים.'), results);
  }
  search.addEventListener('input', () => render());
  for(const filter of [school,group,state,sort])filter.addEventListener('change',()=>render());
  render(previous?.expanded);
  managementLanguageRefresh = () => {refreshFilters();refreshLabels();render(new Set(Array.from(results.querySelectorAll('.pm-activity[open]'),row=>row.dataset.activityId)));};
}

async function openPoster(poster, access, back, readOnly = false, useCloud = false) {
  window.posterSubmit=null;
  let logoGeneration=0;
  async function updateSchoolLogo(current=poster) {
    const generation=++logoGeneration;
    const source=current.schoolLogo && current.schoolId
      ? await schoolLogoMedia(current.schoolId,access,poster.id).download(current.schoolLogo) : null;
    if(generation===logoGeneration) await editor.schoolLogo(source);
  }
  window.refreshSchoolLogo=async()=>updateSchoolLogo(await posterRequest('load',{id:poster.id},access));
  const defaults=poster.schoolDefault===undefined?null:{
    'poster-school':{original:poster.schoolDefault,he:poster.schoolDefault,ar:schoolNameArabic(poster.schoolId,poster.schoolDefault)},
    'poster-class':{original:poster.classDefault,he:poster.classDefault,ar:classNameArabic(poster.classDefault??'')}
  };
  const media = createPosterMedia(poster.id, access);
  const cloudDraft = await decodePosterState(poster.state, media);
  const backup = readOnly ? null : await drafts.read(poster.id).catch(() => null);
  let draft = cloudDraft;
  let pendingBackup = false;
  if (!useCloud && backup?.pending) {
    if (backup.revision === poster.revision) {
      pendingBackup = confirm(t('יש שינויים מקומיים שטרם נשמרו בענן. לשחזר אותם?'));
      if (pendingBackup) draft = backup.draft;
    } else {
      alert(t('גרסת הענן השתנתה. הטיוטה המקומית נשמרה בנפרד.'));
      await drafts.write(poster.id + ':conflict', backup);
    }
  }
  const savedLanguage=draft.language;
  if(savedLanguage==='ar'||savedLanguage==='he') setPosterLanguage(savedLanguage==='ar');
  else if(access.bearer || poster.revision>0){
    const authored=Object.entries(draft.values??{}).filter(([k])=>!['poster-school','poster-class'].includes(k)).map(([,v])=>String(v)).join(' ');
    const arCount=(authored.match(/[\u0600-\u06ff]/g)||[]).length, heCount=(authored.match(/[\u0590-\u05ff]/g)||[]).length;
    if(arCount||heCount)setPosterLanguage(arCount>heCount);
  }
  language.disabled=Boolean(readOnly||poster.archived);
  toolbar.replaceChildren();
  element('strong', t('קוד הפוסטר') + ': ' + poster.code, toolbar).dataset.posterCode=poster.code;
  const indicator = element('span', '', toolbar);
  function setIndicator(key){indicator.dataset.conflicted=String(conflicted);indicator.dataset.statusKey=key;indicator.textContent=t(key)}
  indicator.setAttribute('role', 'status');
  const retry = button('ניסיון שמירה מחדש', () => editor.save(), toolbar);
  retry.hidden = true;
  let conflicted = false;
  const reconcile = button('פתיחת גרסת הענן', async () => {
    if (!confirm(t('לפתוח את גרסת הענן? הטיוטה המקומית תישמר בנפרד.'))) return;
    try {
      // Stop new edits and autosaves while selecting the authoritative version.
      reconcile.disabled = true;
      document.getElementById('sp').inert = true;
      document.getElementById('poster').inert = true;
      await editor.flush();
      await saveQueue;
      await localQueue;
      const local = await drafts.read(poster.id);
      if (local?.pending) await drafts.write(poster.id + ':conflict', local);
      const current = await posterRequest('load', { id: poster.id }, access);
      await openPoster(current, access, back, readOnly, true);
    } catch (error) {
      console.error('Poster cloud reconciliation failed', error);
      setIndicator(messages[error.message] ?? messages.network);
      document.getElementById('sp').inert = Boolean(readOnly);
      document.getElementById('poster').inert = Boolean(readOnly);
      reconcile.disabled = false;
    }
  }, toolbar);
  reconcile.hidden = true;
  const preserved = readOnly ? null : await drafts.read(poster.id + ':conflict').catch(() => null);
  if (preserved?.draft) {
    button('צפייה בטיוטה המקומית', async () => {
      await editor.flush();
      await saveQueue;
      if (editor.hasUnsavedChanges() && !confirm(t('לעבור לתצוגת הטיוטה המקומית?'))) return;
      const current = await drafts.read(poster.id + ':conflict').catch(() => null);
      if (!current?.draft) return;
      toolbar.replaceChildren();
      element('strong', t('טיוטה מקומית – תצוגה בלבד'), toolbar);
      button('חזרה', async () => {
        try {
          const current = await posterRequest('load', { id: poster.id }, access);
          await openPoster(current, access, back, false, true);
        } catch (error) {
          element('span', t(messages[error.message] ?? messages.network), toolbar);
        }
      }, toolbar);
      await editor.open({ id: poster.id, draft: current.draft, save, readOnly: true });
    }, toolbar);
  }

  let saveQueue = Promise.resolve();
  waitForPosterSave = () => saveQueue;
  let localQueue = Promise.resolve();
  let latest = 0;
  function writeLocal(record) {
    const operation = localQueue.then(() => drafts.write(poster.id, record));
    localQueue = operation.catch(() => {});
    return operation;
  }
  let revision = poster.revision;
  function save(snapshot) {
    const sequence = ++latest;
    const local = { revision, draft: snapshot, pending: true };
    // Keep the offline snapshot current while an older request is still in flight.
    const backup = writeLocal(local).then(() => true, () => false);
    const operation = saveQueue.then(async () => {
      if(!conflicted)setIndicator('שומר...');
      retry.hidden = true;
      const backedUp = await backup;
      if (sequence === latest && local.revision !== revision) {
        local.revision = revision;
        await writeLocal(local).catch(() => {});
      }
      try {
        if (conflicted) throw new Error('conflict');
        const state = await encodePosterState(snapshot, media);
        const saved = await posterRequest('save', { id: poster.id, revision, state }, access);
        revision = saved.revision;
        if (sequence === latest) {
          await writeLocal({ revision, draft: snapshot, pending: false }).catch(() => {});
          if (!editor.hasUnsavedChanges()) setIndicator('נשמר');
        }
      } catch (error) {
        conflicted = error.message === 'conflict';
        reconcile.hidden = !conflicted;
        retry.hidden = conflicted;
        setIndicator(conflicted
          ? (backedUp ? 'יש גרסה חדשה בענן. הטיוטה נשמרה בדפדפן.' : 'יש גרסה חדשה בענן. הטיוטה המקומית לא נשמרה.')
          : (messages[error.message] && ['denied', 'image'].includes(error.message)
            ? messages[error.message]
            : 'השמירה נכשלה – נסו שוב'));
        throw error;
      }
    });
    saveQueue = operation.catch(() => {});
    return operation;
  }

  button('חזרה', async (event) => {
    const control = event.currentTarget;
    control.disabled = true;
    try {
      await editor.save();
      await saveQueue;
      if (editor.hasUnsavedChanges() &&
          !confirm(t('יש שינויים שטרם נשמרו בענן. לחזור בכל זאת?'))) return;
      window.posterSubmit=null;window.refreshSchoolLogo=null;
      await editor.close({ flush: false });
      root.replaceChildren();
      await back();
    } catch (error) {
      showError(error);
    } finally {
      control.disabled = false;
    }
  }, toolbar);
  let submitting=false;
  window.posterSubmit=readOnly||poster.archived?null:async()=>{
    if(submitting)return;
    submitting=true;
    const panel=document.getElementById('sp'),art=document.getElementById('poster');
    const languageControl=document.getElementById('poster-editor-language');
    const submit=document.getElementById('poster-submit'),message=document.getElementById('poster-submit-status');
    panel.inert=art.inert=true;document.getElementById('toolbar').inert=true;languageControl.disabled=true;submit.disabled=true;
    message.textContent=t('שומר ושולח...');
    try {
      await editor.flush();await saveQueue;
      if(editor.hasUnsavedChanges()||conflicted)throw new Error('unsaved');
      const receipt=await posterRequest('submit',{id:poster.id,revision},access);
      if(!receipt.submittedAt)throw new Error('network');
      message.textContent=t('הפוסטר נשמר ונשלח בהצלחה למערכת הניהול.');
      setIndicator('נשמר ונשלח');
    } catch(error) {
      message.textContent=t(error.message==='unsaved'?'לא ניתן לשלוח לפני השלמת השמירה. הנתונים נשמרו בטיוטה.':(messages[error.message]??'השליחה נכשלה. הנתונים נשמרו, נסו שוב.'));
    } finally {submitting=false;panel.inert=art.inert=false;document.getElementById('toolbar').inert=false;languageControl.disabled=false;submit.disabled=false;}
  };
  await editor.open({ id: poster.id, draft, save, defaults:access.bearer?null:defaults, readOnly: readOnly || poster.archived });
  await updateSchoolLogo();
  if (pendingBackup || (!access.bearer && !poster.archived && !readOnly && !savedLanguage)) editor.markChanged();
}

window.addEventListener('online', () => editor.save());
if (new URLSearchParams(location.search).get('view') === 'management') instructorEntry();
else if(new URLSearchParams(location.search).get('view')==='research') resumeEntry(true);
else home();

window.addEventListener('focus',()=>window.refreshSchoolLogo?.().catch(()=>{}));

function renderSchoolLogos(schools,parent=root) {
  const section=element('section','',parent);section.className='poster-school-logos';
  element('h2',t('לוגו בית הספר'),section);
  const label=element('label',t('בחירת בית הספר'),section);
  const select=element('select','',label);
  for(const school of schools)element('option',arabic?schoolNameArabic(school.id,school.name):school.name,select).value=school.id;
  accessChoicesRefresh=()=>{for(const option of select.options){const school=schools.find(s=>s.id===option.value);option.textContent=arabic?schoolNameArabic(school.id,school.name):school.name}};
  const preview=element('img','',section);preview.alt=t('תצוגה מקדימה של הלוגו');preview.hidden=true;
  const fileLabel=element('label',t('העלאת לוגו'),section);
  const input=element('input','',fileLabel);input.type='file';input.accept='image/png,image/jpeg,image/webp,image/gif,image/avif';
  const info=element('p','',section);info.setAttribute('role','status');
  let pending=null,generation=0;
  const media=new Map();
  const schoolMedia=id=>{if(!media.has(id))media.set(id,schoolLogoMedia(id,staff));return media.get(id)};
  async function show(){
    const token=++generation;pending=null;input.value='';preview.hidden=true;preview.removeAttribute('src');info.textContent='';
    const school=schools.find(s=>s.id===select.value);saveButton.disabled=true;
    removeButton.disabled=!school?.logo;
    try {if(school?.logo){const source=await schoolMedia(school.id).download(school.logo);if(token===generation){preview.src=source;preview.hidden=false;}}}
    catch(error){if(token===generation)info.textContent=t(messages[error.message]??messages.network);}
  }
  input.addEventListener('change',async()=>{
    const file=input.files?.[0],token=++generation;
    if(!file)return;
    saveButton.disabled=true;
    if(file.size>8388608||!['image/png','image/jpeg','image/webp','image/gif','image/avif'].includes(file.type)){info.textContent=t(messages.image);return;}
    try {
      const source=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error);reader.readAsDataURL(file)});
      if(token!==generation)return;pending=source;preview.src=source;preview.hidden=false;saveButton.disabled=false;info.textContent=t('הלוגו מוכן לשמירה.');
    }catch{info.textContent=t(messages.image);}
  });
  async function mutate(remove){
    const school=schools.find(s=>s.id===select.value),source=pending;
    if(!school||(!remove&&!source))return;
    select.disabled=input.disabled=saveButton.disabled=removeButton.disabled=true;
    info.textContent=t('שומר...');
    try{
      if(remove){await schoolLogoRequest('remove',{schoolId:school.id},staff);school.logo=null;}
      else {const hash=await schoolMedia(school.id).upload(source);await schoolLogoRequest('set',{schoolId:school.id,hash},staff);school.logo=hash;}
      await show();info.textContent=t('הלוגו עודכן בכל הפוסטרים של בית הספר.');
    }catch(error){info.textContent=t(messages[error.message]??messages.network);saveButton.disabled=!pending;removeButton.disabled=!school.logo;}
    finally{select.disabled=input.disabled=false;}
  }
  const saveButton=button('שמירת לוגו',()=>mutate(false),section,true);
  const removeButton=button('הסרת לוגו',()=>mutate(true),section);
  select.addEventListener('change',show);show();
}
