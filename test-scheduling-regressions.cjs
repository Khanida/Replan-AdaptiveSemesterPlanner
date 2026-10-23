const test=require('node:test');
const assert=require('node:assert/strict');
const E=require('./replanv2-engine.js');
const ON='2026-10-23';
function state(courses,cap=1){return {...E.emptyState(ON),courses,cap,hoursPerCH:1};}
const course=(name,days,topics=[name],credit_hours=1)=>({name,exam_date:E.addDays(ON,days),topics,credit_hours});
test('a completed topic does not block remaining time on the final study day',()=>{
  let s=E.generate(state([course('A',1,['First','Second'])],2));
  s=E.setStatus(s,[s.rows[0].id],'Completed',ON);
  const completed=E.clone(s.rows[0]);
  s=E.replan(s,ON);
  assert.deepEqual(s.rows.find(r=>r.Status==='Completed'),completed);
  assert.equal(E.analyze(s,ON).unplaced,0);
  assert.equal(E.analyze(s,ON).total,1);
  assert.equal(s.rows.filter(r=>r.Status!=='Completed').reduce((n,r)=>n+r['Target Hours'],0),0.5);
});
test('shared capacity and earliest deadlines produce a feasible competing-course plan',()=>{
  const s=E.generate(state([course('Later',3),course('Urgent',1)]));
  assert.equal(E.analyze(s,ON).unplaced,0);
  assert.ok(E.analyze(s,ON).daily.every(d=>d.hours<=1));
  assert.equal(s.rows.find(r=>r.Date===ON).Course,'Urgent');
});
test('zero capacity and insufficient capacity report exact remaining work',()=>{
  for(const cap of [0,0.25,0.5]){
    const s=E.generate(state([course('A',2)],cap));
    const m=E.analyze(s,ON);
    assert.equal(E.cents(m.unplaced)+E.cents(E.sum(s.rows,r=>r['Target Hours'])),100);
    assert.ok(m.daily.every(d=>d.hours<=cap));
  }
});
test('repeated replans preserve completed work and all unplaced topic workload',()=>{
  let s=E.generate(state([course('A',8,['X','Y','Z'],6)],1));
  s=E.setStatus(s,[s.rows[0].id],'Completed',ON);
  for(let i=0;i<10;i++){
    s=E.replan(s,E.addDays(ON,2));
    const m=E.analyze(s,ON);
    assert.equal(E.cents(m.done)+E.cents(E.sum(s.rows.filter(r=>!['Completed','Missed'].includes(r.Status)),r=>r['Target Hours']))+E.cents(m.unplaced),600);
    assert.ok(m.daily.every(d=>d.hours<=1));
  }
});
test('date availability overrides weekday availability and survives JSON/metadata imports',()=>{
  let input=state([course('A',4)],1);
  input.availability={weekdays:{5:0},dates:{[ON]:0.5,[E.addDays(ON,1)]:0}};
  const s=E.generate(input);
  assert.equal(E.sum(s.rows.filter(r=>r.Date===ON),r=>r['Target Hours']),0.5);
  assert.ok(!s.rows.some(r=>r.Date===E.addDays(ON,1)));
  assert.deepEqual(E.validateState(JSON.parse(JSON.stringify(s))).availability,s.availability);
  assert.deepEqual(E.importCSV(E.toCSV(s),s,ON).availability,s.availability);
  assert.throws(()=>E.validateAvailability({weekdays:{7:1}}));
  assert.throws(()=>E.validateAvailability({dates:{'2026-02-30':1}}));
});
test('explicit topic estimates replace equal credit estimates and preserve exact work',()=>{
  const c={...course('A',3,['Easy','Hard']),topicHours:{Easy:0.25,Hard:1.75}};
  const s=E.generate(state([c],1));
  assert.equal(E.analyze(s,ON).total,2);
  assert.equal(E.sum(s.rows.filter(r=>r.Topic==='Easy'),r=>E.cents(r['Target Hours'])),25);
  assert.equal(E.sum(s.rows.filter(r=>r.Topic==='Hard'),r=>E.cents(r['Target Hours'])),175);
  assert.deepEqual(E.validateState(s).courses,s.courses);
});
test('a generated zero-capacity plan can be replanned after capacity is restored',()=>{
  let s=E.generate(state([course('A',2)],0));
  assert.equal(s.rows.length,0);
  assert.equal(E.analyze(s,ON).unplaced,1);
  s.cap=1;s=E.replan(s,ON);
  assert.equal(E.analyze(s,ON).unplaced,0);
});
test('Flutter JSON can be imported with completion, availability and calendar identity',()=>{
  const backup={version:1,app:'Replan Flutter',planId:'portable-contract',start:ON,daily:120,hours:1,unscheduled:30,
    courses:[{id:'a',name:'Math',credits:1,exam:'2026-10-27',topics:['Easy','Hard'],topicMinutes:{Easy:30,Hard:90}}],
    sessions:[{courseId:'a',topic:'Easy',date:ON,minutes:30,done:true},{courseId:'a',topic:'Hard',date:ON,minutes:60,done:false}],
    availability:{weekdays:{0:0},dates:{'2026-10-24':60}}};
  const s=E.validateState(backup),m=E.analyze(s,ON);
  assert.equal(s.planId,backup.planId);
  assert.equal(m.total,2);assert.equal(m.done,.5);assert.equal(m.unplaced,.5);
  assert.equal(s.availability.dates['2026-10-24'],1);
  assert.equal(E.analyze(E.replan(s,ON),ON).unplaced,0);
  assert.throws(()=>E.validateState({...backup,version:999}));
});
test('unknown or noninteger workload metadata cannot corrupt progress totals',()=>{
  for(const mutate of [s=>s.workload.Unknown={Ghost:100},s=>s.workload.A.Ghost=100,s=>s.workload.A.A='100',s=>s.workload.A.A=0.5]){
    const s=E.generate(state([course('A',2)]));mutate(s);
    assert.throws(()=>E.validateState(s));
  }
});
test('daily roadmap mixes courses and selects only one topic per course',()=>{
  const s=E.generate(state(['A','B','C'].map(c=>course(c,4,['X','Y'],2)),3));
  for(const date of [ON,E.addDays(ON,1)]){
    const rows=s.rows.filter(r=>r.Date===date);
    assert.equal(new Set(rows.map(r=>r.Course)).size,3);
    for(const c of ['A','B','C'])assert.equal(new Set(rows.filter(r=>r.Course===c).map(r=>r.Topic)).size,1);
  }
  assert.equal(E.analyze(s,ON).unplaced,0);
});
test('courses skipped by the daily limit carry over ahead of courses already served',()=>{
  const s=E.generate(state(['A','B','C'].map(c=>course(c,6,['X','Y'],2)),1));
  assert.deepEqual([0,1,2].map(i=>s.rows.find(r=>r.Date===E.addDays(ON,i)).Course),['A','B','C']);
  assert.ok(E.analyze(s,ON).daily.every(d=>d.hours<=1));
});
