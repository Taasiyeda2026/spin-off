// SPIN-OFF team access: reuse the dashboard login; never handle employee passwords here.
// The dashboard bridge transfers only a short-lived Supabase access token.
const DASHBOARD_ORIGIN = 'https://taasiyeda2026.github.io';
const DASHBOARD_BRIDGE = DASHBOARD_ORIGIN + '/dashboard_system/spin-off-bridge.html';
const SUPABASE_URL = 'https://szinlhjuwyiyszdpsdop.supabase.co';
const PUBLISHABLE_KEY = 'sb_publishable_k0IbDJlgPA9KTVuDWrCyFw_Zsa5kZIM';
const SESSION_KEY = 'spin-off-group-session-v1';
const TIMEOUT_MS = 10 * 60 * 1000;
const arabic = document.documentElement.lang === 'ar';
const gamePage = /\/groupchallenge\.html$/.test(location.pathname);

const words = arabic ? {
  connecting:'جارٍ التحقق من تسجيل الدخول…',
  opening:'فُتحت نافذة تسجيل الدخول إلى لوحة التحكم.',
  blocked:'لم تُفتح النافذة. يُرجى السماح بالنوافذ المنبثقة لهذا الموقع والمحاولة مجددًا.',
  invalid:'لم تكتمل المصادقة. يُرجى تسجيل الدخول بحساب نشط في لوحة التحكم.',
  closed:'أُغلقت نافذة تسجيل الدخول قبل اكتمال العملية.',
  timeout:'انتهت مهلة تسجيل الدخول. يُرجى المحاولة مجددًا.',
  error:'تعذّر التحقق من الحساب. افحصوا الاتصال بالإنترنت وحاولوا مجددًا.'
} : {
  connecting:'מאמתים את ההתחברות לדשבורד…',
  opening:'נפתח חלון ההתחברות לדשבורד.',
  blocked:'חלון ההתחברות נחסם. יש לאפשר חלונות קופצים לאתר ולנסות שוב.',
  invalid:'האימות לא הושלם. יש להתחבר עם משתמש פעיל בדשבורד.',
  closed:'חלון ההתחברות נסגר לפני השלמת האימות.',
  timeout:'זמן ההתחברות הסתיים. אפשר לנסות שוב.',
  error:'לא ניתן לאמת את החשבון כרגע. בדקו את החיבור לאינטרנט ונסו שוב.'
};

function announce(message) {
  const status = document.getElementById('group-auth-status');
  if (status) status.textContent = message;
}
function currentToken() {
  try { return sessionStorage.getItem(SESSION_KEY) || ''; } catch { return ''; }
}
function clearToken() {
  try { sessionStorage.removeItem(SESSION_KEY); } catch { /* session storage unavailable */ }
}
function storeToken(token) {
  try { sessionStorage.setItem(SESSION_KEY, token); return true; } catch { return false; }
}
function randomState() {
  if (!crypto?.getRandomValues) throw new Error('secure_random_unavailable');
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}
async function readJson(response) {
  if (!response.ok) throw new Error('auth_request_failed');
  return response.json();
}
async function verifyActiveDashboardUser(token) {
  if (!token || !/^[A-Za-z0-9_=-]+\.[A-Za-z0-9_=-]+\.[A-Za-z0-9_=-]+$/.test(token)) return false;
  const commonHeaders = {
    apikey: PUBLISHABLE_KEY,
    Authorization: 'Bearer ' + token
  };
  try {
    const user = await readJson(await fetch(SUPABASE_URL + '/auth/v1/user', {
      headers: commonHeaders, cache: 'no-store'
    }));
    if (!user?.id) return false;
    const profile = await readJson(await fetch(SUPABASE_URL + '/rest/v1/rpc/get_current_app_user', {
      method: 'POST',
      headers: { ...commonHeaders, 'Content-Type': 'application/json' },
      body: '{}',
      cache: 'no-store'
    }));
    const record = Array.isArray(profile) ? profile[0] : profile;
    // There is intentionally NO role check: all active dashboard accounts may enter.
    return record?.is_active === true && !!record?.user_id &&
      String(record?.auth_user_id || '') === String(user.id);
  } catch { return false; }
}

function enterGame() {
  if (gamePage) {
    document.documentElement.classList.remove('group-auth-locked');
    document.getElementById('group-auth-gate')?.setAttribute('hidden', '');
  } else {
    location.assign(new URL(arabic ? '../groupchallenge.html' : 'groupchallenge.html', location.href).href);
  }
}

let verifiedInThisPage = false;
let pending = false;
let activeAttempt = null;
function resetAttempt() {
  if (!activeAttempt) return;
  clearInterval(activeAttempt.timer);
  clearTimeout(activeAttempt.timeout);
  window.removeEventListener('message', activeAttempt.onMessage);
  activeAttempt = null;
  pending = false;
  const button = document.querySelector('[data-group-access]');
  if (button) button.disabled = false;
}
function openDashboardLogin() {
  if (verifiedInThisPage) { enterGame(); return; }
  if (pending) {
    try { activeAttempt?.popup?.focus(); } catch { /* ignore */ }
    return;
  }
  let state;
  try { state = randomState(); } catch { announce(words.error); return; }
  const url = new URL(DASHBOARD_BRIDGE);
  url.searchParams.set('origin', location.origin);
  url.searchParams.set('state', state);
  // Open synchronously inside the user's click to avoid browser popup blockers.
  const popup = window.open(url.href, 'spin-off-dashboard-login',
    'popup=yes,width=520,height=700,resizable=yes,scrollbars=yes');
  if (!popup) { announce(words.blocked); return; }
  pending = true;
  document.querySelector('[data-group-access]')?.setAttribute('disabled', '');
  announce(words.opening);
  const attempt = { popup, state, timer:null, timeout:null, onMessage:null };
  activeAttempt = attempt;
  attempt.onMessage = async event => {
    if (event.origin !== DASHBOARD_ORIGIN || event.source !== popup ||
        event.data?.type !== 'spin-off:session' || event.data?.state !== state) return;
    resetAttempt();
    announce(words.connecting);
    const token = typeof event.data.access_token === 'string' ? event.data.access_token : '';
    if (!await verifyActiveDashboardUser(token) || !storeToken(token)) {
      clearToken();
      announce(words.invalid);
      return;
    }
    verifiedInThisPage = true;
    enterGame();
  };
  window.addEventListener('message', attempt.onMessage);
  attempt.timer = setInterval(() => {
    if (!popup.closed) return;
    resetAttempt();
    announce(words.closed);
  }, 700);
  attempt.timeout = setTimeout(() => {
    resetAttempt();
    try { popup.close(); } catch { /* ignore */ }
    announce(words.timeout);
  }, TIMEOUT_MS);
}

async function initialize() {
  const button = document.querySelector('[data-group-access]');
  if (button) button.addEventListener('click', openDashboardLogin);
  if (!gamePage && !button) return;
  const token = currentToken();
  if (!token) {
    if (gamePage) announce(words.invalid);
    return;
  }
  announce(words.connecting);
  if (await verifyActiveDashboardUser(token)) {
    verifiedInThisPage = true;
    if (gamePage) enterGame();
    else announce('');
  } else {
    clearToken();
    if (gamePage) announce(words.invalid);
    else announce('');
  }
}
initialize().catch(() => announce(words.error));
