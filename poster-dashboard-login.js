// Dashboard owns login, recovery and refresh. Only a short-lived access token
// crosses the window boundary; no passwords or refresh tokens are handled here.
const ORIGIN = 'https://taasiyeda2026.github.io';
const BRIDGE = ORIGIN + '/dashboard_system/spin-off-bridge.html';
export function dashboardLogin({ win = window, random = crypto, timeoutMs = 180000 } = {}) {
  const nonce = Array.from(random.getRandomValues(new Uint8Array(32)), x => x.toString(16).padStart(2,'0')).join('');
  const url = new URL(BRIDGE);
  url.searchParams.set('origin', win.location.origin);
  url.searchParams.set('state', nonce);
  const popup = win.open(url.href, 'spin-off-poster-dashboard-login', 'popup,width=580,height=760');
  if (!popup) return Promise.reject(new Error('popup_blocked'));
  return new Promise((resolve, reject) => {
    let timer, poll, settled = false;
    const finish = (error, token) => {
      if (settled) return;
      settled = true;
      win.removeEventListener('message', receive);
      clearTimeout(timer); clearInterval(poll);
      try { popup.close(); } catch {}
      if (error) reject(new Error(error)); else resolve(token);
    };
    const receive = event => {
      if (event.origin !== ORIGIN || event.source !== popup ||
          event.data?.type !== 'spin-off:session' || event.data?.state !== nonce) return;
      const token = event.data.access_token;
      if (typeof token !== 'string' || !token) return finish('login');
      finish(null, token);
    };
    win.addEventListener('message', receive);
    timer = setTimeout(() => finish('popup_timeout'), timeoutMs);
    poll = setInterval(() => { if (popup.closed) finish('popup_closed'); }, 1000);
  });
}
