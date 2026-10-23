const test=require('node:test');
const assert=require('node:assert/strict');
const C=require('./replanv2-calendar.js');
const event={summary:'Study',extendedProperties:{private:{replanId:'1'}}};
test('full sync paginates, updates collisions and removes only stale events owned by this plan',async()=>{
  const calls=[];
  const api=async(path,method='GET',body)=>{
    calls.push({path,method,body});
    if(method==='POST'){const e=Error();e.status=409;throw e;}
    if(method==='GET')return path.includes('pageToken=')?{items:[{id:'another-plan',extendedProperties:{private:{replanPlan:'other'}}}]}:{items:[{id:'keep',extendedProperties:{private:{replanPlan:'mine'}}},{id:'stale',extendedProperties:{private:{replanPlan:'mine'}}}],nextPageToken:'next'};
    return {};
  };
  assert.deepEqual(await C.sync(api,'/events',[{}],[event],'mine',async()=> 'keep','all'),{synced:1,removed:1});
  assert.deepEqual(calls.filter(c=>c.method==='DELETE').map(c=>c.path),['/events/stale']);
  assert.equal(calls.find(c=>c.method==='PUT').body.extendedProperties.private.replanPlan,'mine');
});
test('partial scopes never delete unselected or past events',async()=>{
  for(const scope of ['selected','upcoming']){
    const calls=[];await C.sync(async(p,m)=>{calls.push(m);return {};},'/events',[{}],[event],'mine',async()=> 'a',scope);
    assert.deepEqual(calls,['POST']);
  }
});
test('an upload failure cannot start stale event cleanup',async()=>{
  const calls=[];
  await assert.rejects(C.sync(async(p,m)=>{calls.push(m);throw Error('network');},'/events',[{}],[event],'mine',async()=> 'a','all'));
  assert.deepEqual(calls,['POST']);
});
test('empty complete desired plan removes old managed events',async()=>{
  const calls=[];
  await C.sync(async(p,m='GET')=>{calls.push(m);return {items:[{id:'old',extendedProperties:{private:{replanPlan:'mine'}}}]};},'/events',[],[],'mine',async()=> 'a','all');
  assert.deepEqual(calls,['GET','DELETE']);
});
