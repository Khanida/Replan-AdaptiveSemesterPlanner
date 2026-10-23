/* RePlan v1.2 browser engine. Shared by the page and Node regression checks. */
(function (root) {
  'use strict';
  const STATUSES = ['Pending', 'Completed', 'Missed', 'Rescheduled'];
  const THEMES = [
    {name:'Emerald', icon:'💻', color:'#54d997'}, {name:'Sky', icon:'📐', color:'#78b9ff'},
    {name:'Amber', icon:'🌐', color:'#edbf70'}, {name:'Rose', icon:'🔬', color:'#ff97b1'},
    {name:'Violet', icon:'📖', color:'#b4a1ff'}, {name:'Coral', icon:'🎨', color:'#ffa481'},
    {name:'Teal', icon:'🧠', color:'#71d7d5'}
  ];
  const COLUMNS = ['Day','Date','Weekday','Course','Topic Day','Topic','Target Hours','Status','Rescheduled_From'];
  const clone = value => JSON.parse(JSON.stringify(value));
  const sum = (rows, fn) => rows.reduce((value, row) => value + fn(row), 0);
  const cents = value => Math.round(Number(value) * 100);
  const hours = value => Math.round(value) / 100;
  function today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }
  function dayNumber(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw Error('Enter a date as YYYY-MM-DD.');
    const n = Date.parse(value + 'T00:00:00Z');
    if (!Number.isFinite(n) || new Date(n).toISOString().slice(0,10) !== value) throw Error('That calendar date is not valid.');
    return n / 86400000;
  }
  function addDays(value, count) { return new Date((dayNumber(value) + count) * 86400000).toISOString().slice(0,10); }
  const daysBetween = (start,end) => dayNumber(end) - dayNumber(start);
  const weekday = value => new Date(dayNumber(value)*86400000).toLocaleDateString('en',{weekday:'long',timeZone:'UTC'});
  function number(value, label, min, max) {
    if (String(value).trim() === '' || !Number.isFinite(Number(value)) || Number(value) < min || Number(value) > max) throw Error(`${label} must be between ${min} and ${max}.`);
    return Number(value);
  }
  function validateCourses(courses) {
    if (!Array.isArray(courses) || courses.length > 50) throw Error('Use up to 50 courses.');
    const seen = new Set();
    return courses.map((course, i) => {
      const name = String(course.name || '').trim();
      if (!name || name.length > 100) throw Error('Course names must contain 1–100 characters.');
      if (seen.has(name.toLowerCase())) throw Error(`A course named “${name}” already exists.`);
      seen.add(name.toLowerCase());
      const topics = (Array.isArray(course.topics) ? course.topics : []).map(t => String(t).trim()).filter(Boolean);
      if (!topics.length || topics.length > 150 || topics.some(t => t.length > 300)) throw Error(`${name}: enter 1–150 topics, one per line (up to 300 characters each).`);
      if (new Set(topics.map(t=>t.toLowerCase())).size !== topics.length) throw Error(`${name}: topic names must be unique.`);
      dayNumber(course.exam_date);
      const theme = THEMES[i % THEMES.length];
      return { name, credit_hours:number(course.credit_hours,'Credit hours',0.1,30), exam_date:course.exam_date,
        topics, topicHours:Object.fromEntries(topics.filter(t=>Object.hasOwn(course.topicHours||{},t)).map(t=>[t,number(course.topicHours[t],'Topic hours',0,10000)])), color:/^#[0-9a-f]{6}$/i.test(course.color) ? course.color : theme.color,
        icon:String(course.icon || theme.icon).slice(0,12) };
    });
  }
  function emptyState(on = today()) {
    return {version:2, planId:globalThis.crypto?.randomUUID?.()||('plan-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)), app:'Replan - Adaptive Semester Planner', courses:[], rows:[], workload:{}, history:[],
      start:on, cap:5, hoursPerCH:45, roast:'Medium', variation:0, nextId:1,
      availability:{weekdays:{},dates:{}},
      calendar:{name:'RePlan Roast Study Roadmap',scope:'upcoming',allDay:false,hour:18,reminder:15,clientId:''}};
  }
  function orderedCourses(courses) {
    return [...courses].sort((a,b)=>a.exam_date.localeCompare(b.exam_date)||b.credit_hours-a.credit_hours||a.name.localeCompare(b.name));
  }
  function capacityOn(state,date) {
    const availability=state.availability||{};
    return availability.dates?.[date] ?? availability.weekdays?.[new Date(dayNumber(date)*86400000).getUTCDay()] ?? state.cap;
  }
  function validateAvailability(value={}) {
    if(!value || typeof value!=='object' || Array.isArray(value))throw Error('Invalid availability.');
    const result={weekdays:{},dates:{}};
    for(const kind of ['weekdays','dates']) {
      if(value[kind]!=null && (typeof value[kind]!=='object'||Array.isArray(value[kind])))throw Error('Invalid availability.');
      for(const [key,h] of Object.entries(value[kind]||{})) {
        if(kind==='dates')dayNumber(key);else if(!/^[0-6]$/.test(key))throw Error('Weekdays must use 0 (Sunday) through 6 (Saturday).');
        result[kind][key]=number(h,'Available hours',0,24);
      }
    }
    return result;
  }
  function split(total, count) { return Array.from({length:count},(_,i)=>Math.floor(total/count)+(i<total%count?1:0)); }
  function buildWorkload(courses, rate) {
    const workload = {};
    for (const course of courses) {
      const totals = split(cents(course.credit_hours * rate), course.topics.length);
      Object.defineProperty(workload,course.name,{value:Object.fromEntries(course.topics.map((topic,i)=>[topic,Object.hasOwn(course.topicHours||{},topic)?cents(course.topicHours[topic]):totals[i]])),enumerable:true,writable:true,configurable:true});
    }
    return workload;
  }
  function assignSlots(state, course, from, completed, missed, markRescheduled) {
    const deadline = dayNumber(course.exam_date);
    const start = dayNumber(from);
    // A missed session releases its own time; it does not reserve capacity.
    const dates = [];
    if (deadline-start > 1827) throw Error(`${course.name}: choose an exam within five years of the plan start.`);
    const used = new Map();
    for (const row of [...completed, ...state.rows.filter(r=>!['Completed','Missed'].includes(r.Status))]) {
      used.set(row.Date, (used.get(row.Date)||0) + cents(row['Target Hours']));
    }
    for (let d=start; d<deadline; d++) {
      const date = new Date(d*86400000).toISOString().slice(0,10);
      dates.push(date);
    }
    const topicWork = state.workload[course.name] || {};
    const work = course.topics.map(topic => ({topic, remaining:Math.max(0,(topicWork[topic]||0) -
      sum(completed.filter(r=>r.Course===course.name && r.Topic===topic),r=>cents(r['Target Hours'])))}));
    const remaining = sum(work,w=>w.remaining);
    if (!remaining || !dates.length) return [];
    const rows = [];
    let topicIndex = 0;
    dates.forEach(date => {
      let budget = Math.max(0, cents(capacityOn(state,date)) - (used.get(date)||0));
      while (budget > 0 && topicIndex < work.length) {
        const item = work[topicIndex];
        if (!item.remaining) { topicIndex++; continue; }
        const amount = Math.min(budget,item.remaining,100);
        const source = missed.find(r=>r.Course===course.name && r.Topic===item.topic);
        rows.push({id:String(state.nextId++), Day:daysBetween(state.start,date)+1, Date:date,Weekday:weekday(date),
          Course:course.name, Topic:item.topic,'Topic Day':'','Target Hours':hours(amount),
          Status:markRescheduled ? 'Rescheduled' : 'Pending',
          Rescheduled_From:markRescheduled ? (source ? `Day ${source.Day} (${source.Date})` : 'Adaptive replan') : ''});
        item.remaining -= amount; budget -= amount;
      }
    });
    for (const topic of course.topics) {
      const sessions = rows.filter(r=>r.Topic===topic);
      sessions.forEach((row,index)=>row['Topic Day']=`${index+1}/${sessions.length}`);
    }
    return rows;
  }
  function sortRows(rows) { return rows.sort((a,b)=>a.Date.localeCompare(b.Date)||a.Course.localeCompare(b.Course)||Number(a.id)-Number(b.id)); }
  function generate(input) {
    const state = clone(input);
    state.courses = validateCourses(state.courses);
    if (!state.courses.length) throw Error('Add at least one course before generating a plan.');
    dayNumber(state.start); state.cap=number(state.cap,'Daily limit',0,24);
    state.hoursPerCH=number(state.hoursPerCH,'Study hours per credit',1,100);
    state.availability=validateAvailability(state.availability);
    state.rows=[]; state.history=[]; state.workload=buildWorkload(state.courses,state.hoursPerCH); state.nextId=1;
    for (const course of orderedCourses(state.courses)) {
      if (course.exam_date <= state.start) throw Error(`${course.name}: the exam must be after the plan start.`);
      state.rows.push(...assignSlots(state,course,state.start,[],[],false));
    }
    state.rows=sortRows(state.rows);
    return state;
  }
  function replan(input, on=today(), reason='Adaptive replan') {
    const state=clone(input); dayNumber(on);
    state.availability=validateAvailability(state.availability);
    state.cap=number(state.cap,'Daily limit',0,24);
    if (!state.courses.length || !Object.keys(state.workload||{}).length) throw Error('Generate or import a plan before replanning.');
    for (const row of state.rows) if (row.Date < on && ['Pending','Rescheduled'].includes(row.Status)) row.Status='Missed';
    const completed=state.rows.filter(r=>r.Status==='Completed');
    const missed=state.rows.filter(r=>r.Status==='Missed');
    const fresh=[];
    state.rows=[];
    for (const course of orderedCourses(state.courses)) {
      const hasMissed=missed.some(r=>r.Course===course.name);
      const hasRescheduled=input.rows.some(r=>r.Course===course.name && r.Status==='Rescheduled');
      const allocated=assignSlots(state,course,on>state.start ? on : state.start,completed,missed,hasMissed||hasRescheduled);
      fresh.push(...allocated); state.rows.push(...allocated);
    }
    state.rows=sortRows([...completed,...missed,...fresh]);
    const metrics=analyze(state,on);
    state.history.unshift({timestamp:new Date().toISOString(),reason,rescheduled:fresh.filter(r=>r.Status==='Rescheduled').length,
      peak:metrics.peak,overDays:metrics.overDays.length,unplaced:metrics.unplaced});
    state.history=state.history.slice(0,100);
    return state;
  }
  function setStatus(input, ids, status, on=today()) {
    if (!STATUSES.includes(status)) throw Error('Unknown study status.');
    const state=clone(input), chosen=new Set(ids);
    const wasMissed=state.rows.some(row=>chosen.has(row.id)&&row.Status==='Missed');
    for (const row of state.rows) if(chosen.has(row.id)) { row.Status=status; row.Rescheduled_From=''; }
    for(const course of state.courses) for(const topic of course.topics) {
      const done=sum(state.rows.filter(r=>r.Course===course.name&&r.Topic===topic&&r.Status==='Completed'),r=>cents(r['Target Hours']));
      if(done>((state.workload[course.name]||{})[topic]||0))throw Error('This update would count the same topic work more than once. Reset its completed sessions before completing missed history.');
    }
    return status==='Missed'||wasMissed ? replan(state,on,`Updated ${ids.length} session(s) to ${status}`) : state;
  }
  function analyze(state,on=today()) {
    const active=state.rows.filter(r=>r.Status!=='Missed');
    const dailyMap=new Map();
    for (const row of state.rows) {
      if (!dailyMap.has(row.Date)) dailyMap.set(row.Date,{date:row.Date,rows:[],hours:0,completed:0,pending:0,missed:0,rescheduled:0});
      const day=dailyMap.get(row.Date); day.rows.push(row);
      if(row.Status!=='Missed') day.hours+=cents(row['Target Hours']);
      if(row.Status==='Completed') day.completed+=cents(row['Target Hours']);
      if(row.Status==='Missed') day.missed++; else if(row.Status==='Rescheduled') day.rescheduled++; else if(row.Status==='Pending') day.pending++;
    }
    const daily=[...dailyMap.values()].sort((a,b)=>a.date.localeCompare(b.date)).map(d=>({...d,hours:hours(d.hours),completed:hours(d.completed)}));
    const done=cents(sum(active.filter(r=>r.Status==='Completed'),r=>r['Target Hours']));
    const total=sum(Object.values(state.workload),topics=>sum(Object.values(topics),n=>n));
    const pending=cents(sum(active.filter(r=>r.Status!=='Completed'),r=>r['Target Hours']));
    const unplaced=Math.max(0,total-done-pending);
    const future=daily.filter(d=>d.date>=on);
    const peak=Math.max(0,...future.map(d=>d.hours));
    const overDays=future.filter(d=>d.hours>capacityOn(state,d.date)+0.001);
    const upcoming=state.courses.filter(c=>c.exam_date>=on).sort((a,b)=>a.exam_date.localeCompare(b.exam_date));
    const todayRows=state.rows.filter(r=>r.Date===on);
    const leftToday=sum(todayRows.filter(r=>!['Completed','Missed'].includes(r.Status)),r=>r['Target Hours']);
    const overdue=active.filter(r=>r.Date<on&&r.Status!=='Completed').length;
    return {daily,done:hours(done),total:hours(total),remaining:hours(Math.max(0,total-done)),unplaced:hours(unplaced),peak,
      average:future.length ? sum(future,d=>d.hours)/future.length : 0,overDays,upcoming,todayRows,leftToday,
      progress:total ? Math.min(100,100*done/total) : 0, overdue};
  }
  function topicPeriods(state, courseName) {
    const course=state.courses.find(c=>c.name===courseName);
    if (!course) return [];
    return course.topics.map(topic=>{
      const rows=state.rows.filter(r=>r.Course===courseName&&r.Topic===topic&&r.Status!=='Missed');
      const dates=rows.map(r=>r.Date).sort();
      const total=(state.workload[courseName]||{})[topic] || 0;
      const done=sum(rows.filter(r=>r.Status==='Completed'),r=>cents(r['Target Hours']));
      return {topic,start:dates[0]||'',end:dates.at(-1)||'',sessions:rows.length,total:hours(total),done:hours(done),progress:total?Math.min(100,done/total*100):0};
    });
  }
  const ROASTS={
    empty:['A blank plan. Bold exam strategy.','Your syllabus filed a missing-person report.'],
    complete:['You finished everything. There goes my entire comedy routine.','Actual follow-through? I had jokes prepared.'],
    overdue:['Your overdue tasks are developing their own civilization.','Yesterday’s work would like a word with your scrolling thumb.'],
    overload:['You scheduled a miracle. Your calendar declined.','Your ambition is writing checks your available hours cannot cash.'],
    rescheduled:['Your tasks moved. Unfortunately, they did not disappear.','Replanned again. The syllabus remains unimpressed.'],
    today:['The laptop lid is not a knowledge-transfer device.','Your study plan has done its part. Awkwardly, it is your turn.'],
    rest:['A free day with an actual calendar alibi.','Nothing due today. Try not to invent a guilt assignment.']};
  function roast(state,on=today()) {
    const m=analyze(state,on); let kind='empty',action='Add courses and generate a plan.';
    const next=m.todayRows.find(r=>!['Completed','Missed'].includes(r.Status));
    if(state.rows.length || m.total>0) {
      if(m.remaining<0.005) { kind='complete'; action='All scheduled work is complete. Take a break.'; }
      else if(m.unplaced>0.005) { kind='overload'; action=`${m.unplaced.toFixed(1)}h cannot fit before the exam dates. Review scope and deadlines.`; }
      else if(m.overdue) { kind='overdue'; action='Use Adaptive Replan to rebuild unfinished sessions.'; }
      else if(m.overDays.length) {kind='overload';action='Review your daily limit, available time, and scope.';}
      else if(next) {kind=next.Status==='Rescheduled'?'rescheduled':'today';action=`Next: ${next.Course} / ${next.Topic} (${next['Target Hours'].toFixed(1)}h).`;}
      else {kind='rest';action='Check your next study date. No unfinished sessions are due today.';}
    }
    if(state.roast==='Off') return action;
    if(state.roast==='Mild') return 'One session at a time. '+action;
    return ROASTS[kind][state.variation%ROASTS[kind].length]+(state.roast==='Extra spicy'?' Procrastination is not a degree requirement.':'')+' '+action;
  }
  function csvCell(value) {
    let text=String(value??'');
    if(/^[=+@\-\t\r]/.test(text)) text="'"+text;
    return /[",\r\n]/.test(text) ? '"'+text.replaceAll('"','""')+'"' : text;
  }
  function toCSV(state) { return [COLUMNS.join(','),...state.rows.map(r=>COLUMNS.map(c=>csvCell(r[c])).join(','))].join('\r\n')+'\r\n'; }
  function parseCSV(text) {
    text=text.replace(/^\uFEFF/,''); const rows=[]; let row=[],cell='',quoted=false;
    for(let i=0;i<text.length;i++) {
      const c=text[i];
      if(c==='"') {if(quoted&&text[i+1]==='"'){cell+='"';i++;}else if(quoted){quoted=false;}else if(!cell){quoted=true;}else throw Error('Invalid quote in CSV.');}
      else if(c===','&&!quoted){row.push(cell);cell='';}
      else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(Boolean))rows.push(row);row=[];cell='';}
      else cell+=c;
    }
    if(quoted)throw Error('CSV has an unclosed quoted field.');
    row.push(cell);if(row.some(Boolean))rows.push(row);
    if(rows.length<2)throw Error('The CSV contains no study sessions.');
    if(rows.length>100001)throw Error('Use a CSV with at most 100,000 sessions.');
    const headers=rows.shift();
    for(const name of COLUMNS.filter(c=>!['Rescheduled_From','Course'].includes(c)))if(!headers.includes(name))throw Error(`CSV is missing the ${name} column.`);
    return rows.map((values,i)=>{
      const entry=Object.fromEntries(headers.map((h,j)=>[h,values[j]??'']));
      for(const name of ['Course','Topic']) if(/^'[=+@\-\t\r]/.test(entry[name]||'')) entry[name]=entry[name].slice(1);
      return {...entry,id:String(i+1),Course:entry.Course||'Course 1','Target Hours':Number(entry['Target Hours']),Day:Number(entry.Day),Rescheduled_From:entry.Rescheduled_From||''};
    });
  }
  function importCSV(text, metadata, on=today()) {
    const state=emptyState(on); state.rows=parseCSV(text);state.nextId=state.rows.length+1;
    state.start=state.rows.map(r=>r.Date).sort()[0];
    if(metadata?.courses)state.courses=metadata.courses;
    else state.courses=[...new Set(state.rows.map(r=>r.Course))].map((name,i)=>{
      const rows=state.rows.filter(r=>r.Course===name); const dates=rows.map(r=>r.Date).sort();
      const total=sum(rows.filter(r=>r.Status!=='Missed'),r=>r['Target Hours']);
      return {name,topics:[...new Set(rows.map(r=>r.Topic))],exam_date:addDays(dates.at(-1),1),credit_hours:Math.max(0.1,Math.round(total/45*10)/10),...THEMES[i%THEMES.length]};
    }).map((c,i)=>({...c,name:[...new Set(state.rows.map(r=>r.Course))][i]}));
    state.workload=metadata?.workload||{};
    if(metadata?.start)state.start=metadata.start;
    if(metadata?.cap!=null)state.cap=metadata.cap;
    if(metadata?.hoursPerCH!=null)state.hoursPerCH=metadata.hoursPerCH;
    if(metadata?.history)state.history=metadata.history;
    if(metadata?.availability)state.availability=metadata.availability;
    if(metadata?.planId)state.planId=metadata.planId;
    for(const course of state.courses) {
      if(!Object.hasOwn(state.workload,course.name)) Object.defineProperty(state.workload,course.name,{value:Object.fromEntries(course.topics.map(topic=>[topic,
        sum(state.rows.filter(r=>r.Course===course.name&&r.Topic===topic&&r.Status!=='Missed'),r=>cents(r['Target Hours']))])),enumerable:true,writable:true,configurable:true});
    }
    return validateState(state);
  }
  function fromFlutterBackup(input) {
    if(input.version!==1||!Array.isArray(input.courses)||!Array.isArray(input.sessions))throw Error('Invalid Flutter backup.');
    const state=emptyState(String(input.start).slice(0,10));
    state.cap=number(input.daily,'Daily minutes',0,1440)/60;
    state.hoursPerCH=number(input.hours,'Hours per credit',1,100);
    const names=new Map();
    state.courses=input.courses.map(c=>{
      if(typeof c.id!=='string'||names.has(c.id))throw Error('Invalid or duplicate course identity.');
      names.set(c.id,c.name);
      const course={name:c.name,credit_hours:c.credits,exam_date:String(c.exam).slice(0,10),topics:c.topics,topicHours:{}};
      for(const [topic,minutes] of Object.entries(c.topicMinutes||{}))course.topicHours[topic]=number(minutes,'Topic minutes',0,600000)/60;
      return course;
    });
    state.courses=validateCourses(state.courses);
    state.workload=buildWorkload(state.courses,state.hoursPerCH);
    state.rows=input.sessions.map((r,i)=>{
      if(typeof r.done!=='boolean'||!names.has(r.courseId))throw Error('Invalid Flutter session.');
      return {id:String(i+1),Course:names.get(r.courseId),Topic:r.topic,Date:String(r.date).slice(0,10),
        'Target Hours':number(r.minutes,'Session minutes',1,1440)/60,Status:r.done?'Completed':'Pending','Topic Day':'',Rescheduled_From:''};
    });
    // Whole minutes need rounding when converted to the browser's hundredth-hour model.
    for(const c of state.courses)for(const t of c.topics){
      const active=sum(state.rows.filter(r=>r.Course===c.name&&r.Topic===t),r=>cents(r['Target Hours']));
      state.workload[c.name][t]=Math.max(state.workload[c.name][t],active);
    }
    const availability=input.availability||{};
    state.availability=Object.fromEntries(['weekdays','dates'].map(k=>[k,Object.fromEntries(Object.entries(availability[k]||{}).map(([d,m])=>[d,number(m,'Available minutes',0,1440)/60]))]));
    if(input.planId)state.planId=input.planId;
    return state;
  }
  function validateState(input) {
    if(input?.app==='Replan Flutter')input=fromFlutterBackup(input);
    if(!input || typeof input!=='object'||!Array.isArray(input.courses)||!Array.isArray(input.rows)||typeof input.start!=='string')throw Error('This is not a complete RePlan plan. Open the CSV together with its metadata, or choose a full JSON backup.');
    const state={...emptyState(),...clone(input)};
    state.app='Replan - Adaptive Semester Planner';
    if(typeof state.planId!=='string'||!/^[-a-zA-Z0-9]{1,100}$/.test(state.planId))throw Error('Invalid plan identity.');
    state.courses=validateCourses(state.courses); dayNumber(state.start);
    state.availability=validateAvailability(state.availability);
    state.cap=number(state.cap,'Daily limit',0,24);state.hoursPerCH=number(state.hoursPerCH,'Study hours per credit',1,100);
    if(!Array.isArray(state.rows)||state.rows.length>100000)throw Error('Invalid or oversized schedule.');
    let next=1;
    state.rows=state.rows.map(row=>{
      dayNumber(row.Date);
      const course=state.courses.find(c=>c.name===row.Course);
      if(!course||!course.topics.includes(row.Topic))throw Error('A session refers to an unknown course or topic. Import the matching metadata file.');
      if(row.Date>=course.exam_date)throw Error(`${course.name}: a session is on or after its exam.`);
      if(!STATUSES.includes(row.Status))throw Error(`Unknown status: ${row.Status}`);
      const id=String(next++);
      return {...row,id,Day:daysBetween(state.start,row.Date)+1,Weekday:weekday(row.Date),
        'Target Hours':number(row['Target Hours'],'Session hours',0,100000),Rescheduled_From:String(row.Rescheduled_From||'')};
    });
    state.nextId=next;
    if(!state.workload||typeof state.workload!=='object'||Array.isArray(state.workload))throw Error('Invalid workload metadata.');
    for(const c of state.courses) {
      const totals=Object.hasOwn(state.workload,c.name)?state.workload[c.name]:null;
      if(!totals) {Object.defineProperty(state.workload,c.name,{value:Object.fromEntries(c.topics.map(t=>[t,
        sum(state.rows.filter(r=>r.Course===c.name&&r.Topic===t&&r.Status!=='Missed'),r=>cents(r['Target Hours']))])),enumerable:true,writable:true,configurable:true});}
      else for(const topic of c.topics) number(totals[topic], 'Topic workload',0,100000000);
    }
    const knownCourses=new Set(state.courses.map(c=>c.name));
    for(const [name,topics] of Object.entries(state.workload)){
      if(!knownCourses.has(name)||!topics||typeof topics!=='object'||Array.isArray(topics))throw Error('Invalid workload course metadata.');
      const knownTopics=new Set(state.courses.find(c=>c.name===name).topics);
      for(const [topic,value] of Object.entries(topics)){
        if(!knownTopics.has(topic)||!Number.isSafeInteger(value)||value<0)throw Error('Invalid topic workload metadata.');
      }
    }
    for(const course of state.courses)for(const topic of course.topics){
      const active=sum(state.rows.filter(r=>r.Course===course.name&&r.Topic===topic&&r.Status!=='Missed'),r=>cents(r['Target Hours']));
      if(active>state.workload[course.name][topic])throw Error('Session hours exceed the topic workload.');
    }
    if(!['Off','Mild','Medium','Extra spicy'].includes(state.roast))state.roast='Medium';
    state.variation=Number.isSafeInteger(state.variation)&&state.variation>=0?state.variation:0;
    if(!Array.isArray(state.history))throw Error('Invalid replan history.');
    state.history=state.history.slice(0,100).map(entry=>{
      if(!entry||typeof entry!=='object'||!Number.isFinite(Date.parse(entry.timestamp)))throw Error('Invalid replan history entry.');
      return {...entry,reason:String(entry.reason||'Adaptive replan').slice(0,1000),
        rescheduled:number(entry.rescheduled??0,'Moved sessions',0,100000),peak:number(entry.peak??0,'Peak hours',0,100000000),
        unplaced:number(entry.unplaced??0,'Unscheduled hours',0,100000000)};
    });
    state.calendar={...emptyState().calendar,...state.calendar};
    const cal=state.calendar;
    cal.name=String(cal.name||'RePlan Roast Study Roadmap').slice(0,100);
    cal.scope=['upcoming','all','selected'].includes(cal.scope)?cal.scope:'upcoming';
    cal.allDay=!!cal.allDay;cal.clientId=String(cal.clientId||'').slice(0,300);
    cal.hour=Math.round(number(cal.hour,'Calendar hour',0,23));
    cal.reminder=number(cal.reminder,'Calendar reminder',0,40320);
    return state;
  }
  function calendarRows(state, options, on=today()) {
    const names=new Set(options.courses||state.courses.map(c=>c.name));
    return sortRows(clone(state.rows.filter(r=>names.has(r.Course)&&
      r.Status!=='Missed'&&
      (options.scope==='selected'?(options.ids||[]).includes(r.id):options.scope==='all'||(r.Date>=on&&!['Completed','Missed'].includes(r.Status))))));
  }
  function eventTimes(rows, options) {
    const offsets=new Map();const hour=number(options.hour??18,'Start hour',0,23);
    return rows.map(row=>{
      const day=row.Date; const offset=offsets.get(day)||0;
      const start=new Date(`${day}T${String(hour).padStart(2,'0')}:00:00`);
      start.setMinutes(start.getMinutes()+offset);
      const duration=Math.max(1,Math.round(row['Target Hours']*60));
      const end=new Date(start.getTime()+duration*60000);offsets.set(day,offset+duration);
      return {row,start,end};
    });
  }
  function calendarEvents(rows, options) {
    const reminder=number(options.reminder??15,'Reminder',0,40320);
    return eventTimes(rows,options).map(({row,start,end})=>({
      summary:`${row.Course}: ${row.Topic} (${row['Topic Day']})`,
      description:`Replan - Adaptive Semester Planner\nTarget: ${row['Target Hours'].toFixed(2)}h\nStatus: ${row.Status}${row.Rescheduled_From?'\nMoved from: '+row.Rescheduled_From:''}`,
      start:options.allDay?{date:row.Date}:{dateTime:start.toISOString()},
      end:options.allDay?{date:addDays(row.Date,1)}:{dateTime:end.toISOString()},
      reminders:{useDefault:false,overrides:reminder?[{method:'popup',minutes:reminder}]:[]},
      extendedProperties:{private:{replanId:row.id}}
    }));
  }
  function toICS(rows, options) {
    const esc=value=>String(value).replaceAll('\\','\\\\').replaceAll('\r','').replaceAll('\n','\\n').replaceAll(',','\\,').replaceAll(';','\\;');
    const stamp=new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
    const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Replan//Adaptive Semester Planner//EN','CALSCALE:GREGORIAN','X-WR-CALNAME:'+esc(options.name||'RePlan Roast Study Roadmap')];
    const events=calendarEvents(rows,options);
    events.forEach((event,i)=>{
      const row=rows[i];const identity=`${row.Course}|${row.Date}|${row.Topic}|${row['Topic Day']}`;
      // Encode the full identity rather than relying on a short, collision-prone hash.
      const uid=Array.from(new TextEncoder().encode(identity),b=>b.toString(16).padStart(2,'0')).join('');
      lines.push('BEGIN:VEVENT','UID:'+uid+'@replan.local','DTSTAMP:'+stamp,
        options.allDay?'DTSTART;VALUE=DATE:'+row.Date.replaceAll('-',''):'DTSTART:'+event.start.dateTime.replace(/[-:]/g,'').replace(/\.\d{3}/,''),
        options.allDay?'DTEND;VALUE=DATE:'+addDays(row.Date,1).replaceAll('-',''):'DTEND:'+event.end.dateTime.replace(/[-:]/g,'').replace(/\.\d{3}/,''),
        'SUMMARY:'+esc(event.summary),'DESCRIPTION:'+esc(event.description));
      if(Number(options.reminder)>0)lines.push('BEGIN:VALARM','ACTION:DISPLAY','DESCRIPTION:Study reminder','TRIGGER:-PT'+Number(options.reminder)+'M','END:VALARM');
      lines.push('END:VEVENT');
    });
    lines.push('END:VCALENDAR');
    return lines.map(line=>{let part='',result=[];for(const char of line){if(new TextEncoder().encode(part+char).length>75){result.push(part);part=' ';}part+=char;}result.push(part);return result.join('\r\n');}).join('\r\n')+'\r\n';
  }
  const api={STATUSES,THEMES,COLUMNS,clone,sum,cents,hours,today,dayNumber,addDays,daysBetween,weekday,number,validateCourses,
    buildWorkload,capacityOn,validateAvailability,emptyState,generate,replan,setStatus,analyze,topicPeriods,roast,toCSV,parseCSV,importCSV,validateState,calendarRows,calendarEvents,toICS};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.ReplanEngine=api;
})(typeof globalThis!=='undefined'?globalThis:this);
