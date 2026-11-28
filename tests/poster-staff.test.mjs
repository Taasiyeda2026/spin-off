import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
globalThis.window={posterCloudConfig:{url:'https://fixture.invalid',publishableKey:'fixture'}};
const source=await readFile(new URL('../poster-cloud.js',import.meta.url),'utf8');
const {verifyPosterStaff}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('staff verification uses live identity, active app user and the explicit poster capability',async()=>{
  const original=globalThis.fetch;
  let row;
  globalThis.fetch=async url=>({ok:true,json:async()=>String(url).endsWith('/auth/v1/user')?{id:'fixture'}:[row]});
  try {
    for(const flag of ['yes','true','1',true,1,' YES ']){
      row={auth_user_id:'fixture',is_active:true,role:'business_development_manager',permissions:{manage_all_posters:flag}};
      assert.equal(await verifyPosterStaff('token'),true);
    }
    for(const flag of ['no',false,0,undefined,'admin']){
      row={auth_user_id:'fixture',is_active:true,role:'business_development_manager',permissions:{manage_all_posters:flag}};
      await assert.rejects(verifyPosterStaff('token'),/denied/);
    }
    for(const change of [{is_active:false},{auth_user_id:'other'}]){
      row={auth_user_id:'fixture',is_active:true,role:'business_development_manager',permissions:{manage_all_posters:'yes'},...change};
      await assert.rejects(verifyPosterStaff('token'),/denied/);
    }
    for(const role of ['admin','activities_manager','instructor']){
      row={auth_user_id:'fixture',is_active:true,role,permissions:{}};
      assert.equal(await verifyPosterStaff('token'),true);
    }
  }finally{globalThis.fetch=original;}
});
