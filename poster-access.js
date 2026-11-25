import { arabic, setArabic, translate as t } from './poster-language.js?v=20261125-research-title';
import { createPosterMedia, decodePosterState, encodePosterState, newToken, posterRequest, signIn } from './poster-cloud.js?v=20261125-backgrounds';

const root = document.getElementById('poster-access-content');
const status = document.getElementById('poster-access-status');
const homeTitle = 'SpaceTech | פוסטר חקר';
const title = document.getElementById('poster-access-title');
const editor = window.posterEditor;
const drafts = window.posterDrafts;
const toolbar = document.createElement('div');
toolbar.className = 'poster-cloud-toolbar';
document.getElementById('toolbar').append(toolbar);

const messages = {
  code: 'הקוד לא נמצא או שאינו זמין. בדקו אותו ונסו שוב.',
  denied: 'אין גישה לפוסטר. נסו להיכנס מחדש.',
  rate_limit: 'בוצעו ניסיונות רבים. המתינו ונסו שוב.',
  login: 'הכניסה לא הצליחה. בדקו את שם המשתמש והסיסמה.',
  network: 'לא ניתן להתחבר כרגע. בדקו את החיבור ונסו שוב.',
  image: 'בחרו תמונת PNG, JPEG, WebP, GIF או AVIF בגודל של עד 8 MB.',
  invalid: 'בדקו את הפרטים ונסו שוב.',
  capacity: 'אין אפשרות להקצות קוד כרגע.',
};

let staff = null;
let waitForPosterSave = () => Promise.resolve();
const editorHome = document.getElementById('poster-editor-home');
let managementLanguageRefresh = null;
let leavingForHome = false;
editorHome.addEventListener('click', async (event) => {
  event.preventDefault();
  if (leavingForHome) return;
  leavingForHome = true;
  editorHome.setAttribute('aria-busy', 'true');
  try {
    await editor.save();
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

const language = document.createElement('a');
const accessRoot = document.getElementById('poster-access');
accessRoot.prepend(language);
function languageDestination() {
  const url = new URL(location.href);
  if (arabic) url.searchParams.delete('lang');
  else url.searchParams.set('lang', 'ar');
  return url;
}
function syncLanguageControls() {
  language.textContent = arabic ? 'עברית' : 'العربية';
  language.lang = arabic ? 'he' : 'ar';
  language.href = languageDestination().href;
  for(const toggle of document.querySelectorAll('#poster-editor-language,#poster-panel-language')){
    toggle.textContent=language.textContent;toggle.lang=language.lang;
    toggle.setAttribute('aria-label',arabic?'מעבר לעברית':'التبديل إلى العربية');
  }
  accessRoot.lang = toolbar.lang = arabic ? 'ar' : 'he';
  const homeLabel = arabic ? 'العودة إلى الصفحة الرئيسية' : 'חזרה לדף הבית';
  for (const link of [document.getElementById('poster-access-home'), editorHome]) {
    link.title = homeLabel;
    link.setAttribute('aria-label', homeLabel);
  }
}
syncLanguageControls();
function switchEditorLanguage() {
  const destination=languageDestination();
  history.replaceState(history.state,'',destination.href);
  setArabic(!arabic);
  syncLanguageControls();
  for(const control of toolbar.querySelectorAll('[data-translation-key]'))control.textContent=t(control.dataset.translationKey);
  for(const control of toolbar.querySelectorAll('[data-poster-code]'))control.textContent=t('קוד הפוסטר')+': '+control.dataset.posterCode;
  for(const control of toolbar.querySelectorAll('[data-status-key]'))control.textContent=t(control.dataset.statusKey);
  window.dispatchEvent(new Event('poster:language-changed'));
}
for(const toggle of document.querySelectorAll('#poster-editor-language,#poster-panel-language'))toggle.addEventListener('click',switchEditorLanguage);
language.addEventListener('click', (event) => {
  if (!staff || !managementLanguageRefresh || accessRoot.hidden) return;
  // Keep the authenticated bearer exclusively in memory. Do not reload or persist credentials.
  event.preventDefault();
  const destination = languageDestination();
  history.replaceState(history.state, '', destination.href);
  setArabic(!arabic);
  syncLanguageControls();
  window.dispatchEvent(new Event('poster:language-changed'));
  managementLanguageRefresh();
});

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
  managementLanguageRefresh = null;
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
  return [activity.school, activity.grade, activity.classGroup].filter(Boolean).join(' · ') || activity.id;
}

function createDetails(ticket, activities) {
  screen('יצירת פוסטר חדש', createEntry);
  const form = element('form');
  const label = element('label', t('בית הספר והכיתה'), form);
  const activity = element('select', '', label);
  activity.required = true;
  if (activities.length > 1) element('option', t('בחרו פעילות'), activity).value = '';
  for (const item of activities) element('option', activityLabel(item), activity).value = item.id;
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

function resumeEntry() {
  codeForm('המשך עבודה על פוסטר', 'קוד הפוסטר', '[1-9][0-9]{5}', 6, async (code) => {
    const access = { session: newToken() };
    const poster = await posterRequest('resume', { code }, access);
    await openPoster(poster, access, home);
  });
}

function instructorEntry() {
  screen('כניסת מדריכים', home);
  const form = element('form');
  const username = field(form, 'שם משתמש', { required: true, autocomplete: 'username' });
  const password = field(form, 'סיסמה', { required: true, type: 'password', autocomplete: 'current-password' });
  submit(form, 'כניסה', async () => {
    const submitted = password.value;
    password.value = '';
    try {
      staff = { bearer: await signIn(username.value.trim(), submitted) };
      await manage();
    } catch (error) {
      staff = null;
      throw error.message === 'network' ? error : new Error('login');
    }
  });
}

function copyCode(code) {
  return navigator.clipboard.writeText(code).then(() => { status.textContent = t('הקוד הועתק'); }).catch(showError);
}

async function openFromManagement(id, mode) {
  const poster = await posterRequest('load', { id }, staff);
  await openPoster(poster, staff, manage, mode !== 'edit');
  if (mode === 'pdf') await window.producePdf();
}

async function manage() {
  const data = await posterRequest('manage', {}, staff);
  renderManagement(data);
}

function renderManagement(data, previous = null) {
  screen('ניהול הפוסטרים שלי', home);
  element('p', data.name);
  if (data.code) {
    element('p', t('קוד מדריך') + ': ' + data.code);
    button('העתקת קוד מדריך', () => copyCode(data.code));
  }
  const search = field(root, 'חיפוש לפי שם המוצר, משתתפים או קוד', { type: 'search' });
  const results = element('div');
  search.value = previous?.query ?? '';
  function render(expanded = null) {
    results.replaceChildren();
    const query = search.value.trim().toLocaleLowerCase();
    for (const activity of data.activities) {
      const matching = activity.posters.filter((poster) =>
        [poster.title, poster.participants, poster.code].some((value) => String(value ?? '').toLocaleLowerCase().includes(query)));
      if (query && !matching.length) continue;
      const row = element('details', '', results);
      row.dataset.activityId = activity.id;
      row.open = expanded ? expanded.has(activity.id) : Boolean(query);
      element('summary', [activityLabel(activity), t('טכנולוגיות החלל'), activity.posters.length + ' ' + t('פוסטרים')].join(' · '), row);
      const idLine = element('div', '', row);
      idLine.className = 'poster-activity-id';
      element('span', t('מזהה פעילות') + ':', idLine);
      const identifier = element('bdi', activity.id, idLine);
      identifier.dir = 'ltr';
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
        element('h2', poster.title || t('פוסטר ללא שם'), card);
        element('p', [poster.participants, poster.code, new Date(poster.updatedAt).toLocaleString(arabic ? 'ar' : 'he-IL'),
          poster.deleted ? t('נמחק') : poster.archived ? t('בארכיון') : ''].filter(Boolean).join(' · '), card);
        if (!poster.deleted) {
          button('צפייה', () => openFromManagement(poster.id, 'view').catch(showError), card);
          if (!poster.archived) button('עריכה', () => openFromManagement(poster.id, 'edit').catch(showError), card);
          button('PDF', () => openFromManagement(poster.id, 'pdf').catch(showError), card);
          button('העתקת קוד', () => copyCode(poster.code), card);
        }
        const actions = poster.deleted
          ? (data.admin ? [['restore', 'שחזור']] : [])
          : [['delete', 'מחיקה'], ...(!poster.archived ? [['rotate', 'החלפת קוד']] : []),
            ...(data.admin ? [poster.archived ? ['unarchive', 'הוצאה מהארכיון'] : ['archive', 'ארכוב']] : [])];
        for (const [action, label] of actions) {
          button(label, async (event) => {
            if (!confirm(t(label) + ' – ' + t('להמשיך?'))) return;
            const control = event.currentTarget;
            control.disabled = true;
            try {
              await posterRequest(action, { id: poster.id }, staff);
              await manage();
            } catch (error) {
              showError(error);
              control.disabled = false;
            }
          }, card);
        }
      }
    }
    if (!results.childElementCount) element('p', t('לא נמצאו פעילויות או פוסטרים מתאימים.'), results);
  }
  search.addEventListener('input', () => render());
  render(previous?.expanded);
  managementLanguageRefresh = () => renderManagement(data, {
    query: search.value,
    expanded: new Set(Array.from(results.querySelectorAll('details[open]'), row => row.dataset.activityId))
  });
}

async function openPoster(poster, access, back, readOnly = false, useCloud = false) {
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
  toolbar.replaceChildren();
  element('strong', t('קוד הפוסטר') + ': ' + poster.code, toolbar).dataset.posterCode=poster.code;
  const indicator = element('span', '', toolbar);
  function setIndicator(key){indicator.dataset.statusKey=key;indicator.textContent=t(key)}
  indicator.setAttribute('role', 'status');
  const retry = button('ניסיון שמירה מחדש', () => editor.save(), toolbar);
  retry.hidden = true;
  let conflicted = false;
  const reconcile = button('פתיחת גרסת הענן', async () => {
    if (!confirm(t('לפתוח את גרסת הענן? הטיוטה המקומית תישמר בנפרד.'))) return;
    try {
      await editor.save();
      await saveQueue;
      const local = await drafts.read(poster.id);
      if (local?.pending) await drafts.write(poster.id + ':conflict', local);
      const current = await posterRequest('load', { id: poster.id }, access);
      await openPoster(current, access, back, readOnly, true);
    } catch (error) {
      setIndicator(messages[error.message] ?? messages.network);
    }
  }, toolbar);
  reconcile.hidden = true;
  const preserved = readOnly ? null : await drafts.read(poster.id + ':conflict').catch(() => null);
  if (preserved?.draft) {
    button('צפייה בטיוטה המקומית', async () => {
      await editor.save();
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
      setIndicator('שומר...');
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
          setIndicator('נשמר');
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
      await editor.close({ flush: false });
      await back();
    } catch (error) {
      showError(error);
    } finally {
      control.disabled = false;
    }
  }, toolbar);
  await editor.open({ id: poster.id, draft, save, readOnly: readOnly || poster.archived });
  if (pendingBackup) editor.markChanged();
}

window.addEventListener('online', () => editor.save());
if (new URLSearchParams(location.search).get('view') === 'management') instructorEntry();
else home();
