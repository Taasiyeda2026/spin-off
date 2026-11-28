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
    throw new Error(response.status === 401 ? 'denied' : 'network');
  }
  const result = await response.json();
  if (result?.error) throw new Error(result.error);
  return result;
}

// Staff credentials are handled exclusively by the dashboard bridge.
export async function verifyPosterStaff(token) {
  if (typeof token !== 'string' || !token) throw new Error('login');
  const response = await fetch(project + '/auth/v1/user', {
    headers: { apikey: publicKey, Authorization: 'Bearer ' + token },
    cache: 'no-store', signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'login' : 'network');
  const identity = await response.json();
  const result = await jsonRequest('/rest/v1/rpc/get_current_app_user', {}, token);
  const row = Array.isArray(result) ? result.length === 1 ? result[0] : null : result;
  if (!identity?.id || row?.is_active !== true || String(row.auth_user_id || '') !== String(identity.id) ||
      (!['instructor', 'activities_manager', 'admin'].includes(row.role) && ![true, 1, 'yes', 'true', '1'].includes(row.permissions?.manage_all_posters))) throw new Error('denied');
  return true;
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
