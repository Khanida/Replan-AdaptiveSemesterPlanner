const test = require('node:test');
const assert = require('node:assert/strict');
const E = require('./replanv2-engine.js');
const ON = '2026-10-19';
function plan(days = 5, topics = ['Limits', 'Derivatives'], credits = 1) {
  const state = E.emptyState(ON);
  state.courses = [{name:'Calculus',credit_hours:credits,exam_date:E.addDays(ON,days),topics,...E.THEMES[1]}];
  state.courses[0].name='Calculus';
  return E.generate(state);
}
const total = rows => Math.round(E.sum(rows,r=>r['Target Hours'])*100);
const unfinished = state => state.rows.filter(r=>!['Completed','Missed'].includes(r.Status));

test('Generation conserves exact workload, covers every topic, and stays before the exam',()=>{
  for(const days of [1,2,7,90]) {
    const state=plan(days,['One','Two','Three','Four'],3.3);
    assert.equal(total(state.rows),14850);
    assert.equal(new Set(state.rows.map(r=>r.Topic)).size,4);
    assert.ok(state.rows.every(r=>r.Date<state.courses[0].exam_date));
    assert.ok(state.rows.every(r=>r['Target Hours']>0));
    assert.equal(E.analyze(state,ON).unplaced,0);
  }
});
test('Multi-course workloads and nearest exam are tracked independently',()=>{
  const state=E.emptyState(ON);state.courses=[{name:'A',credit_hours:1,exam_date:E.addDays(ON,3),topics:['A1','A2']},
    {name:'B',credit_hours:2,exam_date:E.addDays(ON,5),topics:['B1']}];
  const generated=E.generate(state),m=E.analyze(generated,ON);
  assert.equal(m.total,135);assert.equal(m.upcoming[0].name,'A');
  assert.equal(total(generated.rows.filter(r=>r.Course==='A')),4500);
  assert.equal(total(generated.rows.filter(r=>r.Course==='B')),9000);
});
test('Replanning preserves completed sessions and recovers the entire remaining curriculum',()=>{
  let state=plan(7,['One','Two','Three']);
  const first=state.rows[0];state=E.setStatus(state,[first.id],'Completed',ON);
  const before=E.clone(state.rows.find(r=>r.id===first.id));
  state=E.replan(state,E.addDays(ON,3));
  assert.deepEqual(state.rows.find(r=>r.id===first.id),before);
  assert.ok(state.rows.some(r=>r.Status==='Missed'));
  assert.ok(unfinished(state).every(r=>r.Date>=E.addDays(ON,3)));
  assert.equal(total(unfinished(state))+E.cents(first['Target Hours']),4500);
  assert.ok(unfinished(state).some(r=>r.Topic==='Three'));
  assert.equal(E.analyze(state,E.addDays(ON,3)).unplaced,0);
});
test('Repeated replanning does not multiply workload or lose topics',()=>{
  let state=plan(10,['One','Two','Three']);
  for(let i=1;i<6;i++){
    state=E.replan(state,E.addDays(ON,i));
    assert.equal(total(unfinished(state)),4500);
    assert.equal(E.analyze(state,E.addDays(ON,i)).total,45);
  }
});
test('Expired deadlines produce explicit unscheduled work instead of false success',()=>{
  const state=E.replan(plan(2),E.addDays(ON,3));
  const m=E.analyze(state,E.addDays(ON,3));assert.equal(m.unplaced,45);assert.equal(unfinished(state).length,0);
  assert.match(E.roast(state,E.addDays(ON,3)),/cannot fit/);
});
test('Marking today missed rebuilds later days and keeps missed history',()=>{
  let state=plan(5);const ids=state.rows.filter(r=>r.Date===ON).map(r=>r.id);
  state=E.setStatus(state,ids,'Missed',ON);
  assert.ok(state.rows.filter(r=>ids.includes(r.id)).every(r=>r.Status==='Missed'));
  assert.ok(unfinished(state).every(r=>r.Date>ON));
  assert.equal(total(unfinished(state)),4500);
  assert.equal(state.history.length,1);
});
test('Completed work is counted in daily feasibility and no completed-only day is called pending',()=>{
  let state=plan(5);const ids=state.rows.filter(r=>r.Date===ON).map(r=>r.id);
  state=E.setStatus(state,ids,'Completed',ON);
  const m=E.analyze(state,ON);assert.equal(m.leftToday,0);assert.equal(m.daily[0].hours,9);assert.equal(m.daily[0].completed,9);
});
test('CSV roundtrip preserves multiline, comma, quote, and formula-like names',()=>{
  const state=plan(4,['=Topic, "one"\ncontinued','Another']);
  const csv=E.toCSV(state);assert.match(csv,/'=Topic/);
  const metadata={courses:state.courses,workload:state.workload,start:state.start};
  const restored=E.importCSV(csv,metadata,ON);
  assert.equal(total(restored.rows),total(state.rows));
  assert.deepEqual(restored.courses,state.courses);assert.equal(restored.rows[0].Topic,state.rows[0].Topic);
});
test('Desktop-style CSV without metadata infers reviewable courses and exam dates',()=>{
  const state=plan();const imported=E.importCSV(E.toCSV(state),null,ON);
  assert.equal(imported.courses[0].name,'Calculus');assert.equal(imported.courses[0].exam_date,state.courses[0].exam_date);
  assert.equal(E.analyze(imported,ON).total,45);
});
test('JSON import rejects invalid dates, statuses, and inconsistent course references',()=>{
  const state=plan();assert.equal(E.validateState(state).rows.length,state.rows.length);
  for(const mutate of [s=>s.rows[0].Date='2026-02-30',s=>s.rows[0].Status='Fake',s=>s.rows[0].Course='Unknown',s=>s.cap=-2]){
    const invalid=E.clone(state);mutate(invalid);assert.throws(()=>E.validateState(invalid));
  }
});
test('Course validation rejects duplicate names, duplicate topics, and non-finite workloads',()=>{
  const state=plan();assert.throws(()=>E.validateCourses([...state.courses,...state.courses]));
  state.courses[0].topics=['A','a'];assert.throws(()=>E.generate(state));
  state.courses[0].topics=['A'];state.courses[0].credit_hours=Infinity;assert.throws(()=>E.generate(state));
});
test('Calendar selection respects course, scope, and selection filters',()=>{
  let state=plan();state=E.setStatus(state,[state.rows[0].id],'Completed',ON);
  const upcoming=E.calendarRows(state,{scope:'upcoming'},ON);assert.ok(upcoming.every(r=>r.Status!=='Completed'));
  assert.equal(E.calendarRows(state,{scope:'selected',ids:[state.rows[0].id]},ON).length,1);
  assert.equal(E.calendarRows(state,{scope:'all',courses:[]},ON).length,0);
});
test('Timed calendar sessions on the same day do not overlap',()=>{
  const state=plan(1,['One','Two']);const events=E.calendarEvents(state.rows,{hour:8,reminder:15});
  assert.equal(events.length,2);assert.equal(events[0].end.dateTime,events[1].start.dateTime);
});
test('ICS contains reminders, exclusive all-day ends, escaped text, and UTF-8 line folding',()=>{
  const state=plan(2,['📐'.repeat(80)+', one; two\nthree']);
  const content=E.toICS(state.rows,{name:'Study',allDay:true,hour:18,reminder:15});
  assert.equal((content.match(/BEGIN:VEVENT/g)||[]).length,state.rows.length);
  assert.ok(content.split('\r\n').every(line=>Buffer.byteLength(line)<=75));
  const unfolded=content.replaceAll('\r\n ','');assert.match(unfolded,/\\, one\\; two\\nthree/);
  assert.match(unfolded,/DTEND;VALUE=DATE:20261020/);assert.match(unfolded,/TRIGGER:-PT15M/);
});
test('Roasts respond to state, intensity, and variation',()=>{
  let state=E.emptyState(ON);assert.match(E.roast(state,ON),/generate a plan/);
  state=plan(90);state.roast='Off';assert.match(E.roast(state,ON),/^Next:/);
  state.roast='Mild';assert.match(E.roast(state,ON),/^One session/);
  state.roast='Extra spicy';assert.match(E.roast(state,ON),/Procrastination/);
  const line=E.roast(state,ON);state.variation++;assert.notEqual(E.roast(state,ON),line);
  state.rows.forEach(r=>r.Status='Completed');assert.match(E.roast(state,ON),/All scheduled work is complete/);
});

test('Resetting or completing missed history does not duplicate recovered workload',()=>{
  for(const status of ['Pending','Completed']){
    let state=plan(5);const original=state.rows[0];state=E.setStatus(state,[original.id],'Missed',ON);
    state=E.setStatus(state,[original.id],status,ON);
    assert.equal(total(state.rows.filter(r=>r.Status!=='Missed')),4500);
    assert.equal(E.analyze(state,ON).unplaced,0);
  }
});
test('A JSON restore retains replanning history and workload totals',()=>{
  const replanned=E.replan(plan(),E.addDays(ON,2));
  const restored=E.validateState(JSON.parse(JSON.stringify(replanned)));
  assert.equal(restored.history.length,1);assert.equal(E.analyze(restored,ON).total,45);
});
test('Object-like course and topic names remain ordinary user data',()=>{
  const input=E.emptyState(ON);input.courses=[{name:'__proto__',credit_hours:1,exam_date:E.addDays(ON,3),topics:['constructor','__proto__']}];
  const state=E.generate(input);assert.equal(E.analyze(state,ON).total,45);
  assert.equal(E.analyze(E.validateState(state),ON).total,45);
});
test('Partial metadata and malformed history cannot replace a valid plan',()=>{
  assert.throws(()=>E.validateState({courses:plan().courses}));
  const invalid=plan();invalid.history=[null];assert.throws(()=>E.validateState(invalid));
});
