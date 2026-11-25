// This function accepts anonymous poster sessions as well as verified Dashboard JWTs.
// Deploy with gateway JWT verification disabled. The RPC authorizes every request.
const project = Deno.env.get('SUPABASE_URL')!;
const publicKey = Deno.env.get('SUPABASE_ANON_KEY')!;
const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const bucketUrl = project + '/storage/v1/object';
const bucket = 'spacetech-posters';
const maxSize = 8 * 1024 * 1024;
const types = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/avif']);
const origins = new Set((Deno.env.get('POSTER_ALLOWED_ORIGINS') ?? 'https://taasiyeda2026.github.io').split(','));

async function readImage(request: Request): Promise<Uint8Array> {
  if (!request.body) throw new Error('missing body');
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.length;
    if (length > maxSize) {
      await reader.cancel();
      throw new Error('size limit');
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  return bytes;
}

function imageType(bytes: Uint8Array): string {
  const ascii = (start: number, end: number) => String.fromCharCode(...bytes.slice(start, end));
  if (bytes.length < 12) return '';
  if (bytes[0] === 0x89 && ascii(1, 8) === 'PNG\r\n\x1a\n') return 'image/png';
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'image/jpeg';
  if (ascii(0, 6) === 'GIF87a' || ascii(0, 6) === 'GIF89a') return 'image/gif';
  if (ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP') return 'image/webp';
  if (ascii(4, 8) === 'ftyp' && ['avif', 'avis'].includes(ascii(8, 12))) return 'image/avif';
  return '';
}

Deno.serve(async (request) => {
  const origin = request.headers.get('origin') ?? '';
  const headers = new Headers({
    'Access-Control-Allow-Origin': origins.has(origin) ? origin : 'null',
    'Access-Control-Allow-Methods': 'GET, PUT, OPTIONS',
    'Access-Control-Allow-Headers': 'authorization, apikey, x-poster-session, content-type',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Vary': 'Origin',
  });
  const reply = (status: number) => new Response(null, { status, headers });
  if (!origins.has(origin)) return reply(403);
  if (request.method === 'OPTIONS') return reply(204);
  if (!['GET', 'PUT'].includes(request.method)) return reply(405);

  const url = new URL(request.url);
  const id = url.searchParams.get('id') ?? '';
  const hash = url.searchParams.get('image') ?? '';
  const schoolId=url.searchParams.get('schoolId');
  const schoolMode=schoolId!==null;
  if(schoolMode&&!/^[1-9][0-9]{0,18}$/.test(schoolId!))return reply(400);
  if ((!schoolMode||id)&&!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(id) ||
      !/^[0-9a-f]{64}$/.test(hash)) return reply(400);

  const write = request.method === 'PUT';
  if(schoolMode&&id&&write)return reply(403);
  try {
    const authHeaders = new Headers({ apikey: publicKey, 'content-type': 'application/json' });
    const bearer = request.headers.get('authorization');
    if (bearer) authHeaders.set('authorization', bearer);
    const endpoint=schoolMode&&!id?'spacetech_school_logo':'spacetech_poster';
    const check = await fetch(project + '/rest/v1/rpc/'+endpoint, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify({
        p_action: schoolMode&&id?'logo_media':'media',
        p: { id, schoolId, hash, mode: write ? 'write' : 'read', session: request.headers.get('x-poster-session') },
      }),
    });
    if(!check.ok)return reply(403);
    const permission=await check.json();
    if(permission.allowed!==true||(schoolMode&&id&&permission.schoolId!==schoolId))return reply(403);

    const path = '/' + bucket + '/' + (schoolMode?'schools/'+schoolId:id) + '/' + hash;
    const storageHeaders = new Headers({ apikey: serviceKey, authorization: 'Bearer ' + serviceKey });
    const privateRead = () => fetch(bucketUrl + '/authenticated' + path, { headers: storageHeaders });

    if (write) {
      const type = request.headers.get('content-type') ?? '';
      if (!types.has(type)) return reply(415);
      let bytes;
      try {
        bytes = await readImage(request);
      } catch {
        return reply(413);
      }
      if (imageType(bytes) !== type) return reply(415);
      const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
      if (Array.from(digest, (byte) => byte.toString(16).padStart(2, '0')).join('') !== hash) return reply(400);

      // Skip identical content and never overwrite a version used by another revision.
      const existing = await privateRead();
      await existing.body?.cancel();
      if (existing.ok) return reply(204);
      storageHeaders.set('content-type', type);
      const uploaded = await fetch(bucketUrl + path, {
        method: 'POST',
        headers: storageHeaders,
        body: bytes,
      });
      await uploaded.body?.cancel();
      if (uploaded.ok) return reply(204);
      const retry = await privateRead();
      await retry.body?.cancel();
      return reply(retry.ok ? 204 : 502);
    }

    const image = await privateRead();
    const type = image.headers.get('content-type')?.split(';')[0] ?? '';
    if (!image.ok || !types.has(type)) {
      await image.body?.cancel();
      return reply(image.status === 404 ? 404 : 502);
    }
    headers.set('Content-Type', type);
    return new Response(image.body, { headers });
  } catch {
    return reply(502);
  }
});
