const project = window.posterCloudConfig?.url ?? 'https://szinlhjuwyiyszdpsdop.supabase.co';
const publicKey = window.posterCloudConfig?.publishableKey ??
  'sb_publishable_k0IbDJlgPA9KTVuDWrCyFw_Zsa5kZIM';

export function newToken() {
  return hex(crypto.getRandomValues(new Uint8Array(32)));
}

function hex(bytes) {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

async function jsonRequest(path, body, bearer) {
  const response = await fetch(project + path, {
    method: 'POST',
    headers: {
      apikey: publicKey,
      'Content-Type': 'application/json',
      ...(bearer ? { Authorization: 'Bearer ' + bearer } : {}),
    },
    body: JSON.stringify(body),
    cache: 'no-store',
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) {
    if (path === '/auth/v1/token?grant_type=password' && [400, 401, 422].includes(response.status)) {
      throw new Error('login');
    }
    throw new Error(response.status === 401 ? 'denied' : 'network');
  }
  const result = await response.json();
  if (result?.error) throw new Error(result.error);
  return result;
}

export async function signIn(username, password) {
  // Use the same credential normalization as loginWithSupabaseAuth in Dashboard.
  const login = username.trim().toLowerCase();
  const submittedPassword = password.trim();
  if (!login || !submittedPassword) throw new Error('login');
  const [identity] = await jsonRequest('/rest/v1/rpc/lookup_login_user_by_username', { p_username: login });
  const email = identity?.auth_email?.trim().toLowerCase();
  if (!email || !['instructor', 'activities_manager', 'admin'].includes(identity.role)) throw new Error('login');
  const session = await jsonRequest('/auth/v1/token?grant_type=password', {
    email,
    password: submittedPassword,
  });
  if (session.user?.id !== identity.auth_user_id || !session.access_token) throw new Error('login');
  return session.access_token;
}

export function posterRequest(action, params = {}, access = {}) {
  return jsonRequest('/rest/v1/rpc/spacetech_poster', {
    p_action: action,
    p: { ...params, ...(access.session ? { session: access.session } : {}) },
  }, access.bearer);
}

export function createPosterMedia(id, access, schoolId = null) {
  const pending = new Map();
  const downloaded = new Map();
  function request(image, body) {
    const url = new URL(project + '/functions/v1/poster-media');
    url.search = new URLSearchParams({ ...(id ? {id} : {}), image, ...(schoolId ? {schoolId:String(schoolId)} : {}) });
    return fetch(url, {
      method: body ? 'PUT' : 'GET',
      headers: {
        apikey: publicKey,
        ...(access.bearer ? { Authorization: 'Bearer ' + access.bearer } : {}),
        ...(access.session ? { 'x-poster-session': access.session } : {}),
        ...(body ? { 'Content-Type': body.type } : {}),
      },
      body,
      cache: 'no-store',
      signal: AbortSignal.timeout(30000),
    });
  }
  function upload(dataUrl) {
    if (!pending.has(dataUrl)) {
      const operation = (async () => {
        const blob = await (await fetch(dataUrl)).blob();
        const hash = hex(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())));
        const response = await request(hash, blob);
        if (!response.ok) throw new Error(response.status === 413 || response.status === 415 ? 'image' : 'network');
        downloaded.set(hash, dataUrl);
        return hash;
      })();
      pending.set(dataUrl, operation);
      operation.catch(() => pending.delete(dataUrl));
    }
    return pending.get(dataUrl);
  }
  async function download(hash) {
    if (downloaded.has(hash)) return downloaded.get(hash);
    const response = await request(hash);
    if (!response.ok) throw new Error('network');
    const blob = await response.blob();
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
    downloaded.set(hash, dataUrl);
    pending.set(dataUrl, Promise.resolve(hash));
    return dataUrl;
  }
  return { upload, download };
}

export async function encodePosterState(draft, media) {
  const { images, savedAt, design: { bgImage, bgOpacity, ...design }, ...state } = draft;
  const { logo, ...slots } = images ?? {};
  const uploaded = await Promise.all(Object.entries(slots)
    .filter(([, source]) => source?.startsWith('data:image/'))
    .map(async ([slot, source]) => [slot, await media.upload(source)]));
  return { ...state, design, media: Object.fromEntries(uploaded) };
}

export async function decodePosterState(state, media) {
  const sources = await Promise.all(Object.entries(state.media ?? {})
    .filter(([slot]) => !['background', 'logo'].includes(slot))
    .map(async ([slot, hash]) => [slot, await media.download(hash)]));
  const images = Object.fromEntries(sources);
  const { bgImage, bgOpacity, ...design } = state.design ?? {};
  return { ...state, images, design };
}

export async function schoolLogoRequest(action, params, access) {
  return jsonRequest('/rest/v1/rpc/spacetech_school_logo', {p_action:action,p:params}, access?.bearer);
}
export function schoolLogoMedia(schoolId, access, posterId = null) {
  return createPosterMedia(posterId, access, schoolId);
}
