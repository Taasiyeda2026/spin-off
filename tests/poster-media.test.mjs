import assert from 'node:assert/strict';
import test from 'node:test';

const site = 'https://taasiyeda2026.github.io';
const project = 'https://fixture.invalid';
const posterId = '230a7470-7352-467a-94e9-57f1ef0cec50';
const png = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFtUAAAAASUVORK5CYII=',
  'base64',
);
const digest = Buffer.from(await crypto.subtle.digest('SHA-256', png)).toString('hex');
const url = project + '/functions/v1/poster-media?id=' + posterId + '&image=' + digest;
let handler;
globalThis.Deno = {
  env: { get: (name) => ({
    SUPABASE_URL: project,
    SUPABASE_ANON_KEY: 'fixture-public',
    SUPABASE_SERVICE_ROLE_KEY: 'fixture-service',
  })[name] },
  serve: (callback) => { handler = callback; },
};
await import('../supabase/functions/poster-media/index.ts');

test('Edge media authorization, immutable upload, and private download', async () => {
  const realFetch = globalThis.fetch;
  const calls = [];
  let stored = false;
  globalThis.fetch = async (target, init) => {
    calls.push({ target, init });
    if (target.includes('/rest/v1/rpc/')) {
      assert.equal(init.headers.get('apikey'), 'fixture-public');
      const call = JSON.parse(init.body);
      assert.equal(call.p.id, posterId);
      assert.equal(call.p.hash, digest);
      return Response.json({ allowed: call.p.session === 'fixture-session' });
    }
    assert.equal(init.headers.get('Authorization'), 'Bearer fixture-service');
    if (init.method === 'POST') {
      assert.deepEqual(Buffer.from(init.body), png);
      assert.equal(init.headers.get('x-upsert'), null);
      stored = true;
      return new Response(null, { status: 200 });
    }
    return stored
      ? new Response(png, { headers: { 'content-type': 'image/png' } })
      : new Response(null, { status: 404 });
  };
  try {
    const request = (method, { body, type, origin = site, session = 'fixture-session' } = {}) =>
      new Request(url, {
        method,
        headers: { origin, 'x-poster-session': session, ...(type ? { 'content-type': type } : {}) },
        body,
      });
    assert.equal((await handler(request('OPTIONS'))).status, 204);
    assert.equal((await handler(request('GET', { origin: 'https://other.invalid' }))).status, 403);
    assert.equal(calls.length, 0);
    assert.equal((await handler(request('GET', { session: 'foreign' }))).status, 403);
    assert.equal(calls.length, 1);
    assert.equal((await handler(request('PUT', { type: 'image/png', body: Buffer.from('forged') }))).status, 415);
    assert.equal((await handler(request('PUT', { type: 'image/png', body: png }))).status, 204);
    assert.equal((await handler(request('PUT', { type: 'image/png', body: png }))).status, 204);
    const downloaded = await handler(request('GET'));
    assert.equal(downloaded.status, 200);
    assert.equal(downloaded.headers.get('Cache-Control'), 'no-store');
    assert.deepEqual(Buffer.from(await downloaded.arrayBuffer()), png);
    assert.equal(calls.filter(({ init }) => init.method === 'POST' &&
      init.headers.get('authorization') === 'Bearer fixture-service').length, 1);
  } finally {
    globalThis.fetch = realFetch;
  }
});
