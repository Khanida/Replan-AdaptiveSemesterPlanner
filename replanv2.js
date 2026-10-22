/* Replan - Adaptive Semester Planner — local browser application. No build step required. */
(function () {
  'use strict';
  const E=window.ReplanEngine, $=id=>document.getElementById(id), KEY='no-replan-semester-v2';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=value=>Number(value).toLocaleString(undefined,{maximumFractionDigits:1});
  const displayDate=value=>value ? new Date(E.dayNumber(value)*86400000).toLocaleDateString(undefined,{month:'short',day:'numeric',timeZone:'UTC'}) : 'Not scheduled';
  const longDate=value=>new Date(E.dayNumber(value)*86400000).toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric',year:'numeric',timeZone:'UTC'});
  const badge=status=>`<span class="status-badge ${status.toLowerCase()}">${esc(status)}</span>`;
  const courseFor=name=>state.courses.find(c=>c.name===name);
  const dot=course=>`<span style="color:color-mix(in srgb, ${esc(course?.color||'#ff8799')} 38%, var(--green))">●</span>`;
  let state=E.emptyState(), view='today', page=0, dailyPage=0, sortKey='Date',ascending=true,selected=new Set(), visible=[],editing=null;
  let toastTimer,lastDay=E.today(),syncing=false,contextIds=[];
  let accountSession=null,googleSession=null,authBusy=false,authVersion=0;
  let storageAvailable=true,startupError='';
  try {const saved=localStorage.getItem(KEY);if(saved)state=E.validateState(JSON.parse(saved));}
  catch(error){startupError='Could not restore browser storage. Your saved data has not been overwritten. Open a JSON backup, or save a new plan.';storageAvailable=false;}
  function notify(message,error=false){
    $('status-line').textContent=message;$('toast').textContent=message;$('toast').hidden=false;
    $('toast').style.background=error?'var(--danger-bg)':'';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,5500);
  }
  function persist(){
    try { if(!storageAvailable)return;localStorage.setItem(KEY,JSON.stringify(state));document.querySelector('.local-badge').innerHTML='<i></i> Saved on this device'; }
    catch(error){storageAvailable=false;document.querySelector('.local-badge').textContent='Save a JSON backup';notify('Browser storage is unavailable or full. Use JSON backup in Study roadmap to download a backup.',true);}
  }
  function commit(next,message){state=next;selected.clear();persist();render();if(message)notify(message);}
  function confirmAction(title,message,yes='Continue') {
    return new Promise(resolve=>{
      $('confirm-title').textContent=title;$('confirm-message').textContent=message;$('confirm-yes').textContent=yes;
      const dialog=$('confirm-dialog');dialog.returnValue='cancel';
      dialog.addEventListener('close',()=>resolve(dialog.returnValue==='confirm'),{once:true});dialog.showModal();
    });
  }
  function safe(action){return async (...args)=>{try{await action(...args);}catch(error){notify(error.message||'That action could not be completed.',true);}};}
  const titles={today:['Less planning.<br><span>More showing up.</span>','Your semester, broken into things you can actually do.'],schedule:['The plan.<br><span>With receipts.</span>','Every milestone between here and your exam dates.'],courses:['Know the scope.<br><span>Then do the work.</span>','Give every course a real outline and a real deadline.'],daily:['Meet your calendar.<br><span>It has limits.</span>','A combined view of what each study day asks of you.'],insights:['Numbers first.<br><span>Excuses later.</span>','Your workload, progress, and the evidence behind the roast.']};
  function switchView(name){
    if(!titles[name])name='today';view=name;
    document.querySelectorAll('[data-tab]').forEach(b=>{const active=b.dataset.tab===view;b.classList.toggle('active',active);b.setAttribute('aria-current',active?'page':'false');});
    document.querySelectorAll('.view').forEach(section=>section.hidden=section.id!=='view-'+view);
    $('page-title').innerHTML=titles[view][0];$('page-description').textContent=titles[view][1];
    if(location.hash!=='#'+name)history.replaceState(null,'','#'+name);
  }
  function empty(title,description,actions=true){return `<div class="empty-state"><span class="empty-icon" aria-hidden="true">▱</span><h3>${esc(title)}</h3><p>${esc(description)}</p>${actions?'<div class="button-row"><button data-action="add-course" class="button primary">+ Add a course</button><button data-action="demo" class="button">Try the demo</button></div>':''}</div>`;}
  function renderMetrics(m){
    const next=m.upcoming[0];const days=next?E.daysBetween(E.today(),next.exam_date):null;
    const metrics=[['COURSES',String(state.courses.length),`${fmt(E.sum(state.courses,c=>c.credit_hours))} credit hours`],
      ['NEXT EXAM',next?`${days}d`:'—',next?next.name:'No upcoming exam'],
      ['TOTAL WORK',`${fmt(m.total)}h`,'Estimated study workload'],['LEFT TODAY',`${fmt(m.leftToday)}h`,'Time to show up'],
      ['ACTUAL PROGRESS',`${Math.round(m.progress)}%`,`${fmt(m.done)}h completed`],
      ['DAILY LIMIT',`${fmt(state.cap)}h`,m.overDays.length?`${m.overDays.length} overloaded days`:'Your capacity ceiling']];
    $('metrics').innerHTML=metrics.map(([title,value,caption])=>`<article class="metric"><h2 class="eyebrow">${esc(title)}</h2><strong class="metric-value">${esc(value)}</strong><p class="metric-caption">${esc(caption)}</p></article>`).join('');
  }
  function feasibility(m){
    if(!state.rows.length)return '';
    if(m.unplaced>0.005)return `<div class="notice danger"><strong>Deadline problem: ${fmt(m.unplaced)}h remains unscheduled.</strong>There are no available slots for some unfinished work before its exam. Review course scope or deadlines. Increasing the daily limit alone will not add calendar days.</div>`;
    if(m.overdue)return `<div class="notice warning"><strong>${m.overdue} overdue session${m.overdue===1?'':'s'} need a new home.</strong>Use Adaptive Replan to redistribute unfinished work before each exam.</div>`;
    if(m.overDays.length)return `<div class="notice warning"><strong>Your calendar declined the optimism.</strong>Required pace peaks at ${fmt(m.peak)}h/day, above your ${fmt(state.cap)}h daily limit on ${m.overDays.length} day${m.overDays.length===1?'':'s'}. Adjust available study time, workload estimates, or course scope.</div>`;
    return `<div class="notice"><strong>Room to work. No miracle required.</strong>Peak workload is ${fmt(m.peak)}h/day within your ${fmt(state.cap)}h limit. Completed work counts toward each day’s load.</div>`;
  }
  function progressPanel(){
    if(!state.courses.length)return '<p class="muted small">Your course progress will appear here.</p>';
    return state.courses.map(c=>{
      const topics=E.topicPeriods(state,c.name);const total=E.sum(topics,t=>t.total),done=E.sum(topics,t=>t.done);const pct=total?Math.min(100,100*done/total):0;
      return `<div class="progress-item"><div class="progress-line"><strong>${dot(c)} ${esc(c.name)}</strong><span>${Math.round(pct)}%</span></div><div class="progress-track" role="progressbar" aria-label="${esc(c.name)} progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct)}"><div class="progress-fill" style="--progress:${pct}%;background:color-mix(in srgb, ${c.color} 38%, var(--green))"></div></div><div class="progress-detail"><span>${fmt(done)} / ${fmt(total)}h</span><span>Exam ${displayDate(c.exam_date)}</span></div></div>`;
    }).join('');
  }
  function renderToday(m){
    let sessions='';const rows=m.todayRows;
    if(!state.rows.length)sessions=empty('A clean slate. Suspiciously clean.','Add your courses and outlines, then generate a roadmap. Or try the demo to see a complete semester.');
    else if(!rows.length)sessions=empty('A calendar-approved breather.','There are no study sessions scheduled today. Check your roadmap for the next one.',false);
    else sessions=rows.map(row=>{
      const completed=row.Status==='Completed';const c=courseFor(row.Course);
      return `<article class="today-session"><button class="session-status ${completed?'complete':''}" data-toggle="${row.id}" aria-label="${completed?'Reset':'Complete'} ${esc(row.Course+': '+row.Topic)}">${completed?'✓':'○'}</button><div class="session-copy"><div class="session-course">${dot(c)} ${esc(row.Course)} ${badge(row.Status)}</div><h3 class="session-topic">${esc(row.Topic)}</h3><p class="session-meta">Session ${esc(row['Topic Day'])}${row.Rescheduled_From?' · Moved from '+esc(row.Rescheduled_From):''}</p></div><span class="session-time">${fmt(row['Target Hours'])}h</span><label class="sr-only" for="task-${row.id}">Status for ${esc(row.Topic)}</label><select id="task-${row.id}" data-session-status="${row.id}">${E.STATUSES.map(s=>`<option ${row.Status===s?'selected':''}>${s}</option>`).join('')}</select></article>`;
    }).join('');
    const active=rows.filter(r=>!['Completed','Missed'].includes(r.Status));
    const actions=rows.length?`<div class="today-actions"><button data-action="finish-today" class="button primary compact" ${!active.length?'disabled':''}>✓ Finish today</button><button data-action="miss-today" class="button compact" ${!active.length?'disabled':''}>Missed today · Replan</button><button data-action="reset-today" class="button ghost compact">Reset today</button></div>`:'';
    $('view-today').innerHTML=`<div class="today-layout"><section class="panel"><div class="section-heading"><div><p class="section-kicker">THE NEXT RIGHT THING</p><h2>Today’s accountability check</h2></div><span class="count-pill">${active.length} to do</span></div>${sessions}${actions}</section><section class="panel"><div class="section-heading"><div><p class="section-kicker">SMALL WINS, ADDED UP</p><h2>Semester progress</h2></div><button class="text-button" data-action="view-courses">View all ↗</button></div>${progressPanel()}</section></div>${feasibility(m)}`;
    $('today-count').textContent=active.length;
  }
  function filteredRows(){
    const course=$('filter-course').value,status=$('filter-status').value,query=$('filter-search').value.trim().toLocaleLowerCase();
    const rows=state.rows.filter(r=>(!course||r.Course===course)&&(!status||r.Status===status)&&(!query||`${r.Course} ${r.Topic}`.toLocaleLowerCase().includes(query)));
    return rows.sort((a,b)=>{const first=a[sortKey],second=b[sortKey];const comparison=typeof first==='number'?first-second:String(first).localeCompare(String(second));return (ascending?1:-1)*comparison||a.Date.localeCompare(b.Date)||a.Course.localeCompare(b.Course);});
  }
  function renderSelection(){
    const count=selected.size;$('selection-summary').textContent=count?`${count} session${count===1?'':'s'} selected`:'Select sessions to update their status';
    ['batch-done','batch-missed','batch-pending'].forEach(action=>document.querySelector(`[data-action="${action}"]`).disabled=!count);
    const checked=visible.filter(r=>selected.has(r.id)).length;$('select-all').checked=visible.length>0&&checked===visible.length;$('select-all').indeterminate=checked>0&&checked<visible.length;
  }
  function pagination(id,total,current,scope){
    const pages=Math.max(1,Math.ceil(total/75));
    $(id).innerHTML=`<span>${total?`${current*75+1}–${Math.min(total,(current+1)*75)} of ${total}`:'0'} ${scope==='schedule'?'sessions':'days'}</span><div class="button-row"><button class="button compact" data-page="${scope}" data-direction="-1" ${current===0?'disabled':''}>← Previous</button><span>${current+1} / ${pages}</span><button class="button compact" data-page="${scope}" data-direction="1" ${current>=pages-1?'disabled':''}>Next →</button></div>`;
  }
  function renderSchedule(){
    const filtered=filteredRows();page=Math.max(0,Math.min(page,Math.ceil(filtered.length/75)-1));visible=filtered.slice(page*75,(page+1)*75);
    $('schedule-body').innerHTML=visible.length?visible.map(row=>`<tr data-row-id="${row.id}" class="${row.Date===E.today()?'today-row ':''}${selected.has(row.id)?'selected-row ':''}${row.Status==='Missed'?'missed-row':''}"><td><input type="checkbox" data-select="${row.id}" aria-label="Select ${esc(row.Course+' / '+row.Topic+' / '+row.Date)}" ${selected.has(row.id)?'checked':''}></td><td>${row.Day}</td><td class="nowrap">${displayDate(row.Date)}<span class="subline">${esc(row.Weekday)}</span></td><td class="nowrap">${dot(courseFor(row.Course))} ${esc(row.Course)}</td><td class="topic-cell">${esc(row.Topic)}${row.Rescheduled_From?'<span class="subline">↻ '+esc(row.Rescheduled_From)+'</span>':''}</td><td class="nowrap">${esc(row['Topic Day'])}</td><td>${fmt(row['Target Hours'])}</td><td>${badge(row.Status)}</td></tr>`).join(''):'<tr><td colspan="8">No sessions match. Add courses and generate a plan, or clear the filters.</td></tr>';
    document.querySelectorAll('[data-sort]').forEach(b=>b.closest('th').setAttribute('aria-sort',b.dataset.sort===sortKey?(ascending?'ascending':'descending'):'none'));
    pagination('schedule-pagination',filtered.length,page,'schedule');renderSelection();
  }
  function updateCourseSelectors(){
    const filter=$('filter-course').value,timeline=$('timeline-course').value;
    const options=state.courses.map(c=>`<option value="${esc(c.name)}">${esc(c.icon+' '+c.name)}</option>`).join('');
    $('filter-course').innerHTML='<option value="">All courses</option>'+options;
    if(state.courses.some(c=>c.name===filter))$('filter-course').value=filter;
    $('timeline-course').innerHTML=options;
    if(state.courses.some(c=>c.name===timeline))$('timeline-course').value=timeline;
    $('timeline-course').disabled=!state.courses.length;
  }
  function renderCourses(){
    $('course-count').textContent=state.courses.length;
    $('course-cards').innerHTML=state.courses.length?state.courses.map((c,index)=>{
      const topics=E.topicPeriods(state,c.name),total=E.sum(topics,t=>t.total),done=E.sum(topics,t=>t.done),pct=total?Math.min(100,100*done/total):0;
      const upcoming=state.rows.filter(r=>r.Course===c.name&&r.Date>=E.today()&&!['Completed','Missed'].includes(r.Status));
      const next=upcoming[0];
      return `<article class="course-card"><div class="course-top"><span class="course-icon">${esc(c.icon)}</span><div><h3>${esc(c.name)}</h3><p>${fmt(c.credit_hours)} credits · ${c.topics.length} topics</p></div></div><dl class="course-stats"><div><dt>EXAM DATE</dt><dd>${displayDate(c.exam_date)}</dd></div><div><dt>TIME LEFT</dt><dd>${E.daysBetween(E.today(),c.exam_date)<0?'Exam passed':E.daysBetween(E.today(),c.exam_date)+' days'}</dd></div><div><dt>WORKLOAD</dt><dd>${fmt(total||c.credit_hours*state.hoursPerCH)}h</dd></div><div><dt>NEXT SESSION</dt><dd>${next?displayDate(next.Date):'—'}</dd></div></dl><div class="progress-line"><span>${fmt(done)}h completed</span><strong>${Math.round(pct)}%</strong></div><div class="progress-track"><div class="progress-fill" style="--progress:${pct}%;background:color-mix(in srgb, ${c.color} 38%, var(--green))"></div></div><div class="button-row"><button class="button compact" data-edit-course="${index}">Edit outline</button><button class="button ghost compact" data-delete-course="${index}">Remove</button></div></article>`;
    }).join(''):empty('No courses. No excuses yet.','Add a course with its exam date and outline to build your semester.');
    renderTimeline();
  }
  function renderTimeline(){
    const name=$('timeline-course').value,periods=E.topicPeriods(state,name);
    $('topic-timeline').innerHTML=periods.length?periods.map(t=>`<div class="timeline-row"><div><h3>${esc(t.topic)}</h3><p>${t.start?displayDate(t.start)+' – '+displayDate(t.end):'Generate a roadmap to assign dates'} · ${t.sessions} sessions</p></div><div><div class="progress-track"><div class="progress-fill" style="--progress:${t.progress}%"></div></div><p>${Math.round(t.progress)}% completed</p></div><div class="timeline-numbers">${fmt(t.done)} / ${fmt(t.total)}h</div></div>`).join(''):'<p class="muted small">Add a course to see its topic timeline.</p>';
  }
  function renderDaily(m){
    const days=m.daily.filter(d=>$('daily-scope').value==='all'||d.date>=E.today());dailyPage=Math.max(0,Math.min(dailyPage,Math.ceil(days.length/75)-1));
    const chart=days.slice(0,14),peak=Math.max(state.cap,...chart.map(d=>d.hours),1);
    $('workload-chart').innerHTML=chart.length?`<div class="chart-heading"><span>FIRST ${chart.length} ${$('daily-scope').value==='all'?'STUDY':'UPCOMING STUDY'} DAYS</span><span>Daily limit ${fmt(state.cap)}h · <span style="color:var(--amber)">Amber = over limit</span></span></div><div class="chart-days">${chart.map(d=>`<div class="chart-day ${d.hours>state.cap?'over':''} ${d.date===E.today()?'today':''}" aria-label="${esc(d.date)}: ${fmt(d.hours)} hours"><span>${fmt(d.hours)}h</span><div class="chart-column" style="--height:${Math.max(2,d.hours/peak*100)}px"></div><span>${displayDate(d.date)}</span></div>`).join('')}</div>`:empty('No workload here yet.','Generate a plan or switch to All days to see past sessions.',false);
    $('daily-body').innerHTML=days.length?days.slice(dailyPage*75,(dailyPage+1)*75).map(d=>`<tr class="${d.date===E.today()?'today-row':''}"><td class="nowrap">${displayDate(d.date)}<span class="subline">${E.weekday(d.date)}</span></td><td>${esc([...new Set(d.rows.map(r=>r.Course))].join(', '))}</td><td>${fmt(d.hours)}h</td><td>${fmt(d.completed)}h</td><td>${d.pending} / ${d.rescheduled}</td><td>${d.missed}</td><td>${d.hours>state.cap?'<span class="status-badge missed">Over by '+fmt(d.hours-state.cap)+'h</span>':'<span class="status-badge completed">Within limit</span>'}</td></tr>`).join(''):'<tr><td colspan="7">No study days to display.</td></tr>';
    pagination('daily-pagination',days.length,dailyPage,'daily');
  }
  function renderInsights(m){
    if(!state.rows.length){$('insights-content').innerHTML=empty('I need evidence before I roast the numbers.','Generate or import a plan to see your progress, workload diagnostics, and replan history.');return;}
    const buffer=Math.max(0,state.cap-m.peak);
    const actions=m.unplaced?['Some unfinished work has no available date before its exam. Review those course deadlines and topic scope.','A higher daily limit will only change warnings; edit the workload or deadline to change the plan.']:m.overDays.length?['Review your daily limit against the peak required pace. Only raise it if you have that time.','Reduce workload estimates or narrow course outlines where appropriate.','Prioritize the nearest exam. Keep breaks in your actual study routine.']:['Follow today’s check-in. Mark completed sessions so the plan stays honest.',`Your peak-day buffer is ${fmt(buffer)}h below the daily limit.`,'If you miss a session, use Adaptive Replan to bring unfinished work forward.'];
    $('insights-content').innerHTML=`${feasibility(m)}<div class="insight-grid"><section class="panel"><p class="eyebrow">THE NUMBERS</p><h2>Semester diagnostic</h2><ul class="insight-list"><li>Estimated workload <strong>${fmt(m.total)}h</strong></li><li>Completed <strong>${fmt(m.done)}h · ${Math.round(m.progress)}%</strong></li><li>Remaining <strong>${fmt(m.remaining)}h</strong></li><li>Unscheduled <strong>${fmt(m.unplaced)}h</strong></li><li>Peak combined pace <strong>${fmt(m.peak)}h/day</strong></li><li>Average study-day pace <strong>${fmt(m.average)}h/day</strong></li><li>Over daily limit <strong>${m.overDays.length} days</strong></li></ul></section><section class="panel"><p class="eyebrow">DAMAGE CONTROL</p><h2>What to do next</h2><ol class="guide-list">${actions.map(a=>'<li>'+esc(a)+'</li>').join('')}</ol>${m.overDays.length?'<ul class="insight-list">'+m.overDays.slice(0,5).map(d=>`<li>${displayDate(d.date)}: <strong>${fmt(d.hours)}h</strong> (+${fmt(d.hours-state.cap)}h over)</li>`).join('')+'</ul>':''}</section></div><section class="panel timeline-panel"><p class="eyebrow">COURSE BY COURSE</p><h2>Roadmap breakdown</h2>${progressPanel()}</section><section class="panel timeline-panel"><p class="eyebrow">THE REPLANNING RECEIPTS</p><h2>Adaptive replan history</h2>${state.history.length?'<ol class="history-list">'+state.history.map(h=>`<li>${esc(h.reason)}<small>${esc(new Date(h.timestamp).toLocaleString())} · ${Number(h.rescheduled)||0} moved sessions · peak ${fmt(h.peak)}h/day${h.unplaced?' · '+fmt(h.unplaced)+'h unscheduled':''}</small></li>`).join('')+'</ol>':'<p class="muted small" style="margin-top:14px">No replanning events yet. Keep showing up.</p>'}</section>`;
  }
  function applyTheme(){
    document.documentElement.dataset.roast=state.roast;
    document.querySelector('meta[name="theme-color"]').content=
      getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
  }
  function render(){
    applyTheme();
    const m=E.analyze(state);$('current-date').textContent=longDate(E.today()).toUpperCase();$('roast-message').textContent=E.roast(state);
    $('roast-level').value=state.roast;$('plan-start').value=state.start;$('daily-cap').value=state.cap;$('hours-per-credit').value=state.hoursPerCH;
    updateCourseSelectors();renderMetrics(m);renderToday(m);renderSchedule();renderCourses();renderDaily(m);renderInsights(m);switchView(view);
  }
  async function download(name,content,type){
    const blob=new Blob([content],{type});
    if(window.pywebview?.api?.save_file){
      const encoded=await new Promise((resolve,reject)=>{
        const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);
        reader.onerror=()=>reject(Error('Could not prepare the desktop export.'));reader.readAsDataURL(blob);
      });
      const result=await window.pywebview.api.save_file(name,encoded);
      return !!result.saved;
    }
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;
    document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);return true;
  }
  async function backup(){if(await download('replan-semester.json',JSON.stringify(state,null,2),'application/json'))notify('JSON backup saved, including courses, progress, settings, and history.');}
  let savingPDF=false;
  async function save(){
    if(savingPDF)return;
    if(!state.rows.some(row=>row.Status!=='Missed'))throw Error('Generate or replan a schedule before saving its PDF.');
    savingPDF=true;const button=document.querySelector('[data-action="save"]'),label=button.textContent;
    button.disabled=true;button.textContent='Preparing PDF…';
    try{
      const content=await window.ReplanPDF.createSchedulePDF(state,(page,total)=>{button.textContent=`PDF ${page}/${total}…`;});
      if(!await download(`replan-checklist-${E.today()}.pdf`,content,'application/pdf'))return;
      notify('PDF checklist downloaded. Print the A4 pages and check off each study session by hand.');
    }finally{savingPDF=false;button.disabled=false;button.textContent=label;}
  }
  function metadata(){return {version:2,courses:state.courses,workload:state.workload,history:state.history,start:state.start,cap:state.cap,hoursPerCH:state.hoursPerCH};}
  function readSettings(){return {start:$('plan-start').value,cap:E.number($('daily-cap').value,'Daily limit',0,24),hoursPerCH:E.number($('hours-per-credit').value,'Hours per credit',1,100)};}
  async function generate(){
    const settings=readSettings();E.dayNumber(settings.start);
    if(state.rows.length&&!await confirmAction('Regenerate the roadmap?','This replaces the existing schedule and clears recorded progress and replan history. Use Adaptive Replan to preserve completed work. Save a JSON backup first if needed.','Regenerate'))return;
    commit(E.generate({...state,...settings}),'Roadmap generated. Your calendar has done its part.');switchView('today');
  }
  async function adaptiveReplan(reason='Manual adaptive replan'){
    state.cap=E.number($('daily-cap').value,'Daily limit',0,24);
    commit(E.replan(state,E.today(),reason),'Plan rebuilt. Completed work preserved; unfinished topics moved before their exams.');
  }
  function openCourse(index=null){
    editing=index;const c=index===null?null:state.courses[index];$('course-form').reset();$('course-error').textContent='';
    $('course-dialog-title').textContent=c?'Edit course':'Add a course';$('course-name').value=c?.name||'';$('course-credit').value=c?.credit_hours||3;
    $('course-exam').value=c?.exam_date||E.addDays(E.today(),60);$('course-topics').value=c?.topics.join('\n')||'';
    const theme=c?E.THEMES.findIndex(t=>t.icon===c.icon&&t.color===c.color):-1;
    $('course-theme').innerHTML=E.THEMES.map((t,i)=>`<option value="${i}">${t.icon} ${t.name}</option>`).join('')+(c&&theme<0?'<option value="custom">Keep current badge</option>':'');
    $('course-theme').value=c&&theme<0?'custom':String(theme>=0?theme:state.courses.length%E.THEMES.length);
    $('course-dialog').showModal();$('course-name').focus();
  }
  async function saveCourse(event){
    event.preventDefault();$('course-error').textContent='';
    try{
      const old=editing===null?null:state.courses[editing];
      const theme=$('course-theme').value==='custom'?old:E.THEMES[Number($('course-theme').value)];
      const candidate={name:$('course-name').value.trim(),credit_hours:Number($('course-credit').value),exam_date:$('course-exam').value,
        topics:$('course-topics').value.split('\n').map(t=>t.trim()).filter(Boolean),icon:theme.icon,color:theme.color};
      const courses=E.clone(state.courses);if(editing===null)courses.push(candidate);else courses[editing]=candidate;
      E.validateCourses(courses);
      if(candidate.exam_date<=E.today())throw Error('Choose a future exam date for a new or edited course.');
      if(E.daysBetween(state.start,candidate.exam_date)>1827)throw Error('Choose an exam within five years of the plan start.');
      const affected=old?state.rows.filter(r=>r.Course===old.name):[];
      if(affected.some(r=>r.Status==='Completed')&&old.topics.some(t=>!candidate.topics.includes(t)&&affected.some(r=>r.Topic===t&&r.Status==='Completed')))throw Error('A removed or renamed topic has completed work. Keep that topic name to preserve its progress, or regenerate the roadmap first.');
      const hasPlan=state.rows.length>0;
      if(hasPlan&&candidate.exam_date<=(state.start>E.today()?state.start:E.today()))throw Error('The exam must leave at least one future study day.');
      if(affected.some(r=>r.Status==='Completed'&&r.Date>=candidate.exam_date))throw Error('The new exam date is before recorded completed work. Choose a later exam date.');
      const next=E.clone(state);next.courses=courses;
      if(hasPlan){
        const work=Object.fromEntries(candidate.topics.map(t=>[t,0]));const total=E.cents(candidate.credit_hours*state.hoursPerCH);
        const completed=Object.fromEntries(candidate.topics.map(t=>[t,E.sum(affected.filter(r=>r.Topic===t&&r.Status==='Completed'),r=>E.cents(r['Target Hours']))]));
        const already=E.sum(Object.values(completed),n=>n);if(already>total)throw Error('The new estimated workload is below already completed hours. Keep a higher credit estimate.');
        const remaining=total-already,base=Math.floor(remaining/candidate.topics.length),extra=remaining%candidate.topics.length;
        candidate.topics.forEach((t,i)=>work[t]=completed[t]+base+(i<extra?1:0));
        if(old&&old.name!==candidate.name)delete next.workload[old.name];Object.defineProperty(next.workload,candidate.name,{value:work,enumerable:true,writable:true,configurable:true});
        next.rows=next.rows.filter(r=>!old||r.Course!==old.name||candidate.topics.includes(r.Topic)).map(r=>old&&r.Course===old.name?{...r,Course:candidate.name}:r);
      }
      $('course-dialog').close();
      commit(hasPlan?E.replan(next,E.today(),`Updated course: ${candidate.name}`):next,`${candidate.name} saved${hasPlan?' and roadmap updated':'. Add more courses or generate the roadmap'}.`);
    }catch(error){$('course-error').textContent=error.message;}
  }
  async function deleteCourse(index){
    const course=state.courses[index];if(!course)return;
    if(!await confirmAction('Remove this course?',`Remove ${course.name}, its milestones, and all recorded progress? Other courses will be retained.`,'Remove course'))return;
    const next=E.clone(state);next.courses.splice(index,1);next.rows=next.rows.filter(r=>r.Course!==course.name);delete next.workload[course.name];
    commit(next,`${course.name} removed.`);
  }
  async function loadDemo(){
    if((state.courses.length||state.rows.length)&&!await confirmAction('Load the demo?','This replaces the current plan. Download a JSON backup first if you want to keep it.','Load demo'))return;
    const today=E.today(),demo=E.emptyState(today);demo.roast=state.roast;
    demo.courses=[{name:'Programming',credit_hours:4,exam_date:E.addDays(today,90),topics:['Syntax & control flow','Functions & recursion','Data structures','Object-oriented programming','Final project'],...E.THEMES[0]},
      {name:'Calculus',credit_hours:3,exam_date:E.addDays(today,75),topics:['Limits & continuity','Derivatives','Integration','Applications of integration'],...E.THEMES[1]},
      {name:'Networks',credit_hours:3,exam_date:E.addDays(today,85),topics:['OSI model','TCP/IP','Routing','Subnetting'],...E.THEMES[2]}];
    // Theme labels describe the badge; course names remain the academic names.
    ['Programming','Calculus','Networks'].forEach((name,i)=>demo.courses[i].name=name);
    commit(E.generate(demo),'Demo loaded: 3 courses with individual outlines and exam dates.');switchView('today');
  }
  async function importFiles(files){
    if(!files.length)return;
    try{
      if(files.some(file=>file.size>15*1024*1024))throw Error('Choose plan files smaller than 15 MB.');
      const csvFile=files.find(f=>/\.csv$/i.test(f.name));const jsonFiles=files.filter(f=>/\.json$/i.test(f.name));let next,inferred=false;
      if(csvFile){const companion=jsonFiles.find(f=>f.name===csvFile.name+'.meta.json')||jsonFiles.find(f=>/\.meta\.json$/i.test(f.name));
        const meta=companion?JSON.parse(await companion.text()):null;
        next=E.importCSV(await csvFile.text(),meta);inferred=!companion;
      }else{
        if(jsonFiles.length!==1)throw Error('Choose one JSON plan, or a CSV with its matching metadata file.');
        next=E.validateState(JSON.parse(await jsonFiles[0].text()));
      }
      if((state.courses.length||state.rows.length)&&!await confirmAction('Open a different plan?','This replaces the current browser plan. Save a JSON backup first if you need the current version.','Open plan'))return;
      const overdue=next.rows.some(r=>r.Date<E.today()&&['Pending','Rescheduled'].includes(r.Status));
      if(overdue)next=E.replan(next,E.today(),'Caught up imported overdue sessions');
      storageAvailable=true;commit(next,inferred?'CSV imported. Credits and exam dates were inferred; review Courses & topics.':'Plan opened, including course details and recorded progress.');switchView(inferred?'courses':'today');
    }catch(error){notify('Could not open plan: '+error.message,true);}
    $('open-file').value='';
  }
  function mark(ids,status){
    if(!ids.length){notify('Select at least one session first.');return;}
    commit(E.setStatus(state,ids,status),`${ids.length} session${ids.length===1?'':'s'} marked ${status.toLowerCase()}${status==='Missed'?' and the roadmap rebuilt':''}.`);
  }
  function todayIds(includeCompleted=false){return state.rows.filter(r=>r.Date===E.today()&&(includeCompleted||!['Completed','Missed'].includes(r.Status))).map(r=>r.id);}
  function calendarOptions(){
    const options={...state.calendar,name:$('calendar-name').value.trim(),scope:$('calendar-scope').value,
      allDay:$('calendar-allday').checked,hour:Number($('calendar-hour').value),reminder:Number($('calendar-reminder').value),
      courses:[...$('calendar-courses').querySelectorAll('input:checked')].map(input=>state.courses[Number(input.value)].name),ids:[...selected]};
    if(!options.name)throw Error('Give the calendar a name.');
    return options;
  }
  function updateCalendarPreview(){
    try{const options=calendarOptions(),rows=E.calendarRows(state,options);$('calendar-preview').textContent=`${rows.length} session${rows.length===1?'':'s'} from ${options.courses.length} course${options.courses.length===1?'':'s'} will be included. ${options.allDay?'All-day events.':'Timed sessions follow your local time zone: '+Intl.DateTimeFormat().resolvedOptions().timeZone+'.'}`;
      document.querySelector('[data-action="export-ics"]').disabled=!rows.length;$('google-sync').disabled=!rows.length||syncing;
    }catch(error){$('calendar-preview').textContent=error.message;}
  }
  function openCalendar(){
    if(!state.rows.length){notify('Generate or import a roadmap before exporting calendar sessions.');return;}
    $('calendar-error').textContent='';$('sync-progress').textContent='';
    const options=state.calendar;
    $('calendar-courses').innerHTML=state.courses.map((c,i)=>`<label><input type="checkbox" value="${i}" checked> ${esc(c.icon+' '+c.name)}</label>`).join('');
    $('calendar-name').value=options.name;$('calendar-scope').value=options.scope;$('calendar-hour').value=String(options.hour);
    $('calendar-reminder').value=String(options.reminder);$('calendar-allday').checked=options.allDay;$('calendar-hour').disabled=options.allDay;
    $('calendar-dialog').showModal();updateGoogleAccount();updateCalendarPreview();

  }
  function keepCalendarOptions(options){state.calendar={name:options.name,scope:options.scope,allDay:options.allDay,hour:options.hour,reminder:options.reminder};persist();}
  async function exportICS(){
    try{const options=calendarOptions(),rows=E.calendarRows(state,options);if(!rows.length)throw Error('Choose at least one course with matching sessions.');
      if(!await download('replan-roadmap.ics',E.toICS(rows,options),'text/calendar;charset=utf-8'))return;keepCalendarOptions(options);notify(`${rows.length} calendar sessions exported. Import the .ics file in your calendar app.`);
    }catch(error){$('calendar-error').textContent=error.message;}
  }
  function updateGoogleAccount(){
    const account=accountSession?.profile;
    $('google-account').textContent=account ? (account.name||account.email||'Account') : 'Sign in';
    $('google-profile').hidden=!account;
    $('google-profile').textContent=account ? `Signed in with ${accountSession.provider==='apple'?'Apple':'Google'} as ${account.email||account.name||'your account'}.` : '';
    $('google-signout').hidden=!accountSession;
    $('google-sync').textContent='Add tasks to Google Calendar';
  }
  function openGoogleLogin(){
    $('google-login-error').textContent='';$('google-login-status').textContent='';
    updateGoogleAccount();$('google-dialog').showModal();
  }
  async function signInProvider(provider){
    if(authBusy||syncing)return;
    const attempt=++authVersion;
    authBusy=true;$('google-login-error').textContent='';
    $('google-signin').disabled=true;$('apple-signin').disabled=true;
    $('google-login-status').textContent='Complete sign-in in the secure browser window…';
    try{
      const session=await window.ReplanAuth.signIn(provider);
      if(attempt!==authVersion)return;
      accountSession=session;googleSession=null;updateGoogleAccount();
      $('google-login-status').textContent='Signed in. Your plan is still saved on this device.';
    }catch(error){if(attempt===authVersion){$('google-login-status').textContent='';$('google-login-error').textContent=error.message;}}
    finally{authBusy=false;$('google-signin').disabled=false;$('apple-signin').disabled=false;}
  }
  function signOutGoogle(){
    if(syncing)return;
    authVersion++;accountSession=null;googleSession=null;updateGoogleAccount();
    $('google-login-status').textContent='Signed out of Replan. Your local plan is still available.';
  }
  async function calendarToken(){
    if(googleSession&&googleSession.expires>Date.now())return googleSession.calendarToken;
    const session=await window.ReplanAuth.signIn('google',true);
    googleSession={...session,expires:Date.now()+45*60*1000};
    if(!accountSession)accountSession={provider:session.provider,profile:session.profile};
    updateGoogleAccount();return session.calendarToken;
  }
  async function api(token,path,method='GET',body){
    const response=await fetch('https://www.googleapis.com/calendar/v3'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
    let data={};try{data=await response.json();}catch(error){/* Some successful responses have no body. */}
    if(!response.ok){const error=Error(data.error?.message||`Calendar request failed (${response.status}).`);error.status=response.status;throw error;}return data;
  }
  async function googleEventId(row){
    const key=`no-replan-v2|${row.Course}|${row.Date}|${row.Topic}|${row['Topic Day']}`;
    const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(key));
    return Array.from(new Uint8Array(digest),n=>n.toString(16).padStart(2,'0')).join('');
  }
  async function syncCalendar(event){
    event.preventDefault();$('calendar-error').textContent='';let added=0;
    try{
      const options=calendarOptions(),rows=E.calendarRows(state,options);if(!rows.length)throw Error('No matching sessions to sync.');
      keepCalendarOptions(options);syncing=true;updateCalendarPreview();$('sync-progress').textContent='Waiting for Google sign-in and calendar permission…';
      const token=await calendarToken();
      $('sync-progress').textContent='Finding your study calendar…';
      let calendar=null,pageToken='';
      do{const list=await api(token,'/users/me/calendarList?maxResults=250'+(pageToken?'&pageToken='+encodeURIComponent(pageToken):''));calendar=(list.items||[]).find(c=>c.summary===options.name&&['owner','writer'].includes(c.accessRole));pageToken=list.nextPageToken||'';}while(!calendar&&pageToken);
      if(!calendar)calendar=await api(token,'/calendars','POST',{summary:options.name,description:'Study milestones from Replan - Adaptive Semester Planner',timeZone:Intl.DateTimeFormat().resolvedOptions().timeZone});
      const events=E.calendarEvents(rows,options),path='/calendars/'+encodeURIComponent(calendar.id)+'/events';
      for(let i=0;i<events.length;i++){
        const id=await googleEventId(rows[i]);
        try{await api(token,path,'POST',{...events[i],id});}
        catch(error){if(error.status===409)await api(token,path+'/'+id,'PUT',events[i]);else throw error;}
        added++;$('sync-progress').textContent=`Synced ${added} of ${events.length} sessions…`;
      }
      $('sync-progress').textContent=`Synced ${added} sessions to “${options.name}”. Matching sessions are updated on repeat sync.`;notify(`${added} Google Calendar sessions synced.`);
    }catch(error){if(error.status===401)googleSession=null;$('calendar-error').textContent=(added?`${added} sessions were synced before this stopped. `:'')+error.message;}
    finally{syncing=false;updateCalendarPreview();}
  }
  function printReport(){
    const m=E.analyze(state),rows=view==='schedule'?filteredRows():state.rows;
    $('print-report').innerHTML=`<h1>Replan - Adaptive Semester Planner</h1><p>Semester roadmap · ${esc(longDate(E.today()))}</p><p>${esc(E.roast(state))}</p><p>${state.courses.length} courses · ${fmt(m.done)} / ${fmt(m.total)}h completed · ${fmt(m.remaining)}h remaining · daily limit ${fmt(state.cap)}h</p><p>Peak ${fmt(m.peak)}h/day · ${m.overDays.length} days over limit · ${fmt(m.unplaced)}h unscheduled</p><h2>Course outlines</h2>${state.courses.map(c=>`<p><strong>${esc(c.name)}</strong> · ${fmt(c.credit_hours)} credits · exam ${esc(c.exam_date)}<br>${c.topics.map(esc).join(' / ')}</p>`).join('')}<h2>${view==='schedule'?'Filtered study roadmap':'Study roadmap'}</h2><table><thead><tr><th>Date</th><th>Course</th><th>Topic</th><th>Hours</th><th>Status</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.Date)}</td><td>${esc(r.Course)}</td><td>${esc(r.Topic)}</td><td>${fmt(r['Target Hours'])}</td><td>${esc(r.Status)}</td></tr>`).join('')}</tbody></table>`;
    window.print();
  }
  function jumpToday(){
    $('filter-course').value='';$('filter-status').value='';$('filter-search').value='';sortKey='Date';ascending=true;
    const index=filteredRows().findIndex(r=>r.Date===E.today());if(index<0){notify('No sessions are scheduled today.');return;}
    page=Math.floor(index/75);renderSchedule();switchView('schedule');
    const target=$('schedule-body').querySelector('.today-row');if(target)target.scrollIntoView({block:'center',behavior:'smooth'});
  }
  const actions={'google-login':openGoogleLogin,'continue-guest':()=>{signOutGoogle();$('google-dialog').close();},backup,open:()=>$('open-file').click(),save,calendar:openCalendar,'add-course':()=>openCourse(),demo:loadDemo,
    replan:()=>adaptiveReplan(),roast:()=>{state.variation++;persist();$('roast-message').textContent=E.roast(state);},guide:()=>$('guide-dialog').showModal(),
    'view-courses':()=>switchView('courses'),'export-csv':async()=>{if(!state.rows.length)throw Error('Generate a plan before exporting.');if(!await download('replan-semester.csv',E.toCSV(state),'text/csv;charset=utf-8'))return;notify('CSV exported. Download CSV metadata too to preserve exact course details.');},
    'export-meta':async()=>{if(!await download('replan-semester.csv.meta.json',JSON.stringify(metadata(),null,2),'application/json'))return;notify('Metadata exported. Keep it beside the matching CSV, or use JSON backup for one complete plan file.');},
    print:printReport,'export-ics':exportICS,'jump-today':jumpToday,
    'batch-done':()=>mark([...selected],'Completed'),'batch-missed':()=>mark([...selected],'Missed'),'batch-pending':()=>mark([...selected],'Pending'),
    'finish-today':()=>mark(todayIds(),'Completed'),'miss-today':()=>mark(todayIds(),'Missed'),'reset-today':()=>mark(todayIds(true),'Pending')};
  document.addEventListener('click',safe(async event=>{
    const menu=$('row-menu');
    const context=event.target.closest('[data-context-status]');if(context){mark(contextIds,context.dataset.contextStatus);menu.hidden=true;return;}
    if(!event.target.closest('#row-menu'))menu.hidden=true;
    const close=event.target.closest('[data-close]');if(close){if(syncing&&close.dataset.close==='calendar-dialog')return;$(close.dataset.close).close();return;}
    const tab=event.target.closest('[data-tab]');if(tab){switchView(tab.dataset.tab);return;}
    const action=event.target.closest('[data-action]');if(action){await actions[action.dataset.action]?.();return;}
    const edit=event.target.closest('[data-edit-course]');if(edit){openCourse(Number(edit.dataset.editCourse));return;}
    const remove=event.target.closest('[data-delete-course]');if(remove){await deleteCourse(Number(remove.dataset.deleteCourse));return;}
    const preset=event.target.closest('[data-exam-days]');if(preset){$('course-exam').value=E.addDays(E.today(),Number(preset.dataset.examDays));return;}
    const toggle=event.target.closest('[data-toggle]');if(toggle){const row=state.rows.find(r=>r.id===toggle.dataset.toggle);mark([row.id],row.Status==='Completed'?'Pending':'Completed');return;}
    const sort=event.target.closest('[data-sort]');if(sort){ascending=sortKey===sort.dataset.sort?!ascending:true;sortKey=sort.dataset.sort;page=0;renderSchedule();return;}
    const pager=event.target.closest('[data-page]');if(pager){if(pager.dataset.page==='schedule'){page+=Number(pager.dataset.direction);renderSchedule();}else{dailyPage+=Number(pager.dataset.direction);renderDaily(E.analyze(state));}}
  }));
  document.addEventListener('change',safe(event=>{
    const select=event.target.closest('[data-select]');if(select){if(select.checked)selected.add(select.dataset.select);else selected.delete(select.dataset.select);select.closest('tr').classList.toggle('selected-row',select.checked);renderSelection();return;}
    const status=event.target.closest('[data-session-status]');if(status){mark([status.dataset.sessionStatus],status.value);return;}
  }));
  $('settings-form').addEventListener('submit',safe(event=>{event.preventDefault();return generate();}));
  $('course-form').addEventListener('submit',saveCourse);
  $('open-file').addEventListener('change',event=>importFiles([...event.target.files]));
  $('roast-level').addEventListener('change',()=>{state.roast=$('roast-level').value;applyTheme();persist();$('roast-message').textContent=E.roast(state);});
  ['filter-course','filter-status'].forEach(id=>$(id).addEventListener('change',()=>{page=0;renderSchedule();}));
  $('filter-search').addEventListener('input',()=>{page=0;renderSchedule();});
  $('timeline-course').addEventListener('change',renderTimeline);
  $('daily-cap').addEventListener('change',safe(()=>{
    state.cap=E.number($('daily-cap').value,'Daily limit',0,24);persist();
    const m=E.analyze(state);renderMetrics(m);renderToday(m);renderDaily(m);renderInsights(m);$('roast-message').textContent=E.roast(state);
    notify('Daily limit updated. Workload warnings now use '+fmt(state.cap)+'h/day.');
  }));
  $('daily-scope').addEventListener('change',()=>{dailyPage=0;renderDaily(E.analyze(state));});
  $('select-all').addEventListener('change',()=>{visible.forEach(r=>$('select-all').checked?selected.add(r.id):selected.delete(r.id));renderSchedule();});
  $('schedule-body').addEventListener('dblclick',safe(event=>{if(event.target.closest('input,button'))return;const tr=event.target.closest('[data-row-id]');if(!tr)return;const row=state.rows.find(r=>r.id===tr.dataset.rowId);mark([row.id],row.Status==='Completed'?'Pending':'Completed');}));
  $('schedule-body').addEventListener('contextmenu',event=>{
    const row=event.target.closest('[data-row-id]');if(!row)return;event.preventDefault();if(!selected.has(row.dataset.rowId)){selected=new Set([row.dataset.rowId]);renderSchedule();}contextIds=[...selected];
    const menu=$('row-menu');menu.hidden=false;menu.style.left=Math.min(event.clientX,window.innerWidth-205)+'px';menu.style.top=Math.min(event.clientY,window.innerHeight-140)+'px';menu.querySelector('button').focus();
  });
  document.addEventListener('keydown',event=>{if(event.key==='Escape')$('row-menu').hidden=true;if((event.metaKey||event.ctrlKey)&&['s','o'].includes(event.key.toLowerCase())){event.preventDefault();event.key.toLowerCase()==='s'?safe(save)():$('open-file').click();}});
  $('google-signin').addEventListener('click',()=>signInProvider('google'));
  $('apple-signin').addEventListener('click',()=>signInProvider('apple'));
  $('google-signout').addEventListener('click',signOutGoogle);
  updateGoogleAccount();
  $('calendar-hour').innerHTML=Array.from({length:24},(_,hour)=>`<option value="${hour}">${String(hour).padStart(2,'0')}:00</option>`).join('');
  $('calendar-form').addEventListener('input',updateCalendarPreview);$('calendar-form').addEventListener('change',updateCalendarPreview);$('calendar-form').addEventListener('submit',syncCalendar);
  $('calendar-allday').addEventListener('change',()=>$('calendar-hour').disabled=$('calendar-allday').checked);
  $('calendar-dialog').addEventListener('cancel',event=>{if(syncing)event.preventDefault();});
  function checkDay(){
    if(document.hidden)return;const on=E.today();if(on!==lastDay){lastDay=on;if(state.rows.some(r=>r.Date<on&&['Pending','Rescheduled'].includes(r.Status)))commit(E.replan(state,on,'Calendar day changed'),'New day: unfinished sessions replanned.');else render();}
  }
  document.addEventListener('visibilitychange',safe(checkDay));setInterval(safe(checkDay),60000);
  window.addEventListener('hashchange',()=>switchView(location.hash.slice(1)));
  if(state.rows.some(r=>r.Date<E.today()&&['Pending','Rescheduled'].includes(r.Status))){state=E.replan(state,E.today(),'Caught up overdue sessions on open');persist();}
  const systemAppearance=window.matchMedia('(prefers-color-scheme: light)');
  if(systemAppearance.addEventListener)systemAppearance.addEventListener('change',applyTheme);
  else systemAppearance.addListener(applyTheme);
  view=location.hash.slice(1)||'today';render();
  if(startupError){document.querySelector('.local-badge').textContent='Open a backup to restore';notify(startupError,true);}
})();
