import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('../poster-dashboard-login.js', import.meta.url), 'utf8');
const { dashboardLogin } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const origin = 'https://taasiyeda2026.github.io';
function fixture(blocked = false) {
  const listeners = new Map();
  const popup = {closed:false,close(){this.closed=true;}};
  let opened;
  const win = {location:{origin},open(url){opened=new URL(url);return blocked?null:popup;},addEventListener(type,fn){listeners.set(type,fn);},removeEventListener(type){listeners.delete(type);}};
  const random = {getRandomValues(bytes){return bytes.fill(7);}};
  const promise = dashboardLogin({win,random,timeoutMs:1000});
  const message = {origin,source:popup,data:{type:'spin-off:session',state:opened.searchParams.get('state'),access_token:'test-token'}};
  return {promise,message,popup,opened,listeners,send(event){listeners.get('message')?.(event);}};
}
test('SSO validates origin, popup source and nonce before accepting token', async()=>{
  const f=fixture();
  assert.equal(f.opened.pathname,'/dashboard_system/spin-off-bridge.html');
  assert.equal(f.opened.searchParams.size,2);
  f.send({...f.message,origin:'https://evil.invalid'});
  f.send({...f.message,source:{}});
  f.send({...f.message,data:{...f.message.data,state:'wrong'}});
  assert.equal(f.popup.closed,false);
  f.send(f.message);
  assert.equal(await f.promise,'test-token');
  assert.equal(f.listeners.size,0);
});
test('blocked popup and missing token rejected',async()=>{
  await assert.rejects(fixture(true).promise,/popup_blocked/);
  const f=fixture();
  f.send({...f.message,data:{...f.message.data,access_token:''}});
  await assert.rejects(f.promise,/login/);
});
test('poster staff verification keeps active account and allowed roles',async()=>{
  globalThis.window={posterCloudConfig:{url:'https://test.invalid',publishableKey:'test'}};
  const cloud=await readFile(new URL('../poster-cloud.js',import.meta.url),'utf8');
  const {verifyPosterStaff}=await import('data:text/javascript;base64,'+Buffer.from(cloud).toString('base64'));
  let row={auth_user_id:'one',is_active:true,role:'instructor'};
  globalThis.fetch=async(url)=>Response.json(url.endsWith('/auth/v1/user')?{id:'one'}:[row]);
  assert.equal(await verifyPosterStaff('test'),true);
  for(const invalid of [{...row,is_active:false},{...row,role:'unauthorized'},{...row,auth_user_id:'two'}]){
    row=invalid;await assert.rejects(verifyPosterStaff('test'),/denied/);
  }
});
test('poster login no longer accepts credentials; student entry remains independent',async()=>{
  const access=await readFile(new URL('../poster-access.js',import.meta.url),'utf8');
  const cloud=await readFile(new URL('../poster-cloud.js',import.meta.url),'utf8');
  assert.match(access,/await dashboardLogin\(\)/);
  assert.match(access,/await verifyPosterStaff\(token\)/);
  assert.doesNotMatch(cloud,/grant_type=password|management-password-reset/);
  assert.match(access,/codeForm\('יצירת פוסטר חדש', 'קוד מדריך'/);
  assert.match(access,/codeForm\('המשך עבודה על פוסטר', 'קוד הפוסטר'/);
});
