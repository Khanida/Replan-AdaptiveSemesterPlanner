const test=require('node:test');
const assert=require('node:assert/strict');
const E=require('./replanv2-engine.js');
const fixtures=require('./test-fixtures/scheduling.json');
for(const f of fixtures)test('shared Dart/JavaScript contract: '+f.name,()=>{
  let s=E.emptyState(f.start);s.cap=f.cap/60;s.hoursPerCH=f.rate;
  s.courses=f.courses.map(c=>({name:c.name,credit_hours:c.credits,exam_date:c.exam,topics:c.topics}));
  if(f.availability)s.availability={weekdays:Object.fromEntries(Object.entries(f.availability.weekdays).map(([d,m])=>[d,m/60])),dates:{}};
  s=E.generate(s);
  s.rows=f.done.map((r,i)=>({id:String(i+1),Course:f.courses.find(c=>c.id===r.courseId).name,Topic:r.topic,Date:r.date,'Target Hours':r.minutes/60,Status:'Completed'}));
  s.nextId=f.done.length+1;
  // replan requires a generated/imported row; generate handles an empty history.
  if(s.rows.length)s=E.replan(s,f.start);else s=E.generate(s);
  const m=E.analyze(s,f.start);
  assert.equal(Math.round(m.unplaced*60),f.unscheduled);
  assert.deepEqual(Object.fromEntries(m.daily.map(d=>[d.date,Math.round(d.hours*60)])),f.daily);
});
