import {test} from 'node:test';
import assert from 'node:assert/strict';
import {localStore} from '../lib/store.mjs';
import path from 'node:path';
test('real seekdb hybrid ranking, incremental refresh, collection isolation, persistence and concurrency',async()=>{
 const directory=path.resolve('.runtime/integration-db');let store=await localStore(directory);
 const kb='test_'+Date.now().toString(36);const v=Array(384).fill(0);v[0]=1;const alt=Array(384).fill(0);alt[1]=1;
 try{
  let imported=await store.import({kb,precision:'q8',records:[{id:'index',title:'index',text:'database indexing accelerates SQL queries',embedding:v},{id:'fruit',text:'apple banana fruit salad',embedding:alt}]});assert.equal(imported.refreshed,true);assert.equal(imported.count,2);
  const result=await store.search({kb,precision:'q8',query:'database',embedding:v,limit:2});assert.equal(result.results[0].id,'index');
  imported=await store.import({kb,precision:'q8',records:[{id:'new',text:'database transaction isolation atomicity',embedding:v}]});assert.equal(imported.count,3);
  const found=await store.search({kb,precision:'q8',query:'transaction',embedding:v,limit:3});assert.ok(found.results.some(x=>x.id==='new'));
  await store.import({kb:kb+'_b',precision:'q8',records:[{id:'other',text:'different collection database',embedding:v}]});
  const replies=await Promise.all(Array.from({length:6},(_,i)=>store.search({kb:i%2?kb:kb+'_b',precision:'q8',query:'database',embedding:v,limit:5})));
  replies.forEach((r,i)=>{if(i%2)assert.ok(r.results.every(x=>x.id!=='other'));else assert.deepEqual(r.results.map(x=>x.id),['other']);});
 }finally{await store.close();}
 store=await localStore(directory);try{const c=await store.collection({kb,precision:'q8'});assert.equal(await c.count(),3);}finally{await store.close();}
});
