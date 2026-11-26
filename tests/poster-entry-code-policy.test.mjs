import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
globalThis.window = { posterCloudConfig: { url: 'https://test.invalid', publishableKey: 'test' } };
const source = await readFile(new URL('../poster-cloud.js', import.meta.url), 'utf8');
const { signIn, completePasswordRecovery } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const identity = { auth_email: 'test@example.invalid', auth_user_id: 'test-id', role: 'instructor' };
function mock(expectedPassword, { status = 400, id = identity.auth_user_id, role = identity.role } = {}) {
  const attempts = [];
  globalThis.fetch = async (url, options) => {
    const body = JSON.parse(options.body);
    if (url.includes('lookup_login_user_by_username')) return Response.json([{ ...identity, role }]);
    if (url.includes('/auth/v1/token')) {
      attempts.push(body.password);
      if (body.password !== expectedPassword) return new Response('{}', { status });
      return Response.json({ user: { id }, access_token: 'test-token' });
    }
    if (url.includes('management-password-reset')) { attempts.push(body.new_password); return Response.json({ ok: true }); }
    throw new Error('unexpected request');
  };
  return attempts;
}
for (const [input, expected, sequence] of [
  ['0123','c:0123',['0123','c:0123']], ['01234','c:01234',['01234','c:01234']],
  ['012345','012345',['012345']], ['1234567','1234567',['1234567']],
  ['Legacy!123','Legacy!123',['Legacy!123']], ['1234','1234',['1234']]
]) test('login compatibility '+input, async () => {
  const attempts = mock(expected);
  assert.equal(await signIn(' TEST ', input), 'test-token');
  assert.deepEqual(attempts, sequence);
});
test('no retry for network or rate limit error', async () => {
  for (const status of [429,500]) {
    const attempts = mock('other', {status});
    await assert.rejects(signIn('test','0123'), /network/);
    assert.deepEqual(attempts,['0123']);
  }
});
test('wrong code and mismatched identity rejected', async () => {
  const attempts = mock('other');
  await assert.rejects(signIn('test','0123'), /login/);
  assert.deepEqual(attempts,['0123','c:0123']);
  mock('0123',{id:'different'});
  await assert.rejects(signIn('test','0123'),/login/);
});
test('existing role restriction preserved', async () => {
  const attempts = mock('0123',{role:'unauthorized'});
  await assert.rejects(signIn('test','0123'),/login/);
  assert.deepEqual(attempts,[]);
});
test('recovery encodes only valid new codes', async () => {
  for (const [password, expected] of [['0123','c:0123'],['01234','c:01234'],['012345','012345']]) {
    const attempts = mock('');
    assert.equal(await completePasswordRecovery({challengeId:'test',code:'123456',password}),true);
    assert.deepEqual(attempts,[expected]);
  }
  for (const password of ['123','1234567','abcd','12a4']) {
    const attempts = mock('');
    await assert.rejects(completePasswordRecovery({challengeId:'test',code:'123456',password}),/invalid_entry_code/);
    assert.deepEqual(attempts,[]);
  }
});
