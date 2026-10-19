const test=require('node:test');
const assert=require('node:assert/strict');
const E=require('./replanv2-engine.js');
const PDF=require('./replanv2-pdf.js');
const ON='2026-10-19';
function plan(){
  const s=E.emptyState(ON);s.courses=[{name:'Programming',credit_hours:3,exam_date:E.addDays(ON,35),topics:['Functions','Recursion','Project']}];
  return E.generate(s);
}
test('The wall checklist groups every active session by week without missing or duplicate rows',()=>{
  const s=plan();s.rows[0].Status='Missed';s.rows[1].Status='Completed';
  const pages=PDF.layoutSchedule(s),printed=pages.flatMap(p=>p.rows.map(r=>r.row));
  assert.equal(printed.length,s.rows.length-1);assert.equal(new Set(printed.map(r=>r.id)).size,printed.length);
  assert.ok(printed.some(r=>r.Status==='Completed'));assert.ok(printed.every(r=>r.Status!=='Missed'));
  for(const p of pages){assert.equal(new Date(p.week+'T00:00:00Z').getUTCDay(),1);for(const r of p.rows){assert.ok(r.y>=150);assert.ok(r.y+r.height<=730);}}
});
test('Long course and topic names wrap and paginate before overlapping notes or footers',()=>{
  const s=plan();s.rows=Array.from({length:60},(_,i)=>({...s.rows[0],id:String(i),Course:'A very long course title '.repeat(4),Topic:'A long topic that must wrap neatly '.repeat(8)}));
  const pages=PDF.layoutSchedule(s);assert.ok(pages.length>1);assert.equal(pages.flatMap(p=>p.rows).length,60);
  for(const p of pages){let bottom=150;for(const r of p.rows){assert.ok(r.y>=bottom);bottom=r.y+r.height;assert.ok(bottom<=730);assert.ok(r.topicLines.length>1);}}
});
test('Unicode, multiline text, and unbroken words retain every character when wrapping',()=>{
  const text='دراسة الرياضيات\n'+ 'verylongword'.repeat(20);
  const lines=PDF.wrap(text,30,t=>Array.from(t).length*5);
  assert.equal(lines.join('').replaceAll(' ',''),text.replace(/[\n ]/g,''));
  assert.ok(lines.every(line=>Array.from(line).length<=6));
});
test('Drawing emits one large manual checkbox per row and marks only completed sessions',()=>{
  const s=plan();s.rows[0].Status='Completed';const page=PDF.layoutSchedule(s)[0];
  let boxes=0;const text=[];
  const ctx={fillRect(){},fillText(value){text.push(value);},beginPath(){},moveTo(){},lineTo(){},stroke(){},strokeRect(x,y,w,h){assert.equal(w,13);assert.equal(h,13);boxes++;}};
  PDF.drawPage(ctx,page,0,1,s,ON);
  assert.equal(boxes,page.rows.length);assert.ok(text.includes('STUDY CHECKLIST'));assert.ok(text.includes('NOTES / NEXT WEEK'));assert.ok(text.includes('PAGE 1 / 1'));
});
test('PDF page tree, image streams, lengths, and cross-reference offsets are consistent',()=>{
  const image={width:1,height:1,bytes:new Uint8Array([0xff,0xd8,0xff,0xd9])};
  const bytes=PDF.pdfBytes([image,image]),buffer=Buffer.from(bytes),text=buffer.toString('latin1');
  assert.ok(text.startsWith('%PDF-1.4'));assert.match(text,/\/Count 2/);assert.match(text,/\/MediaBox \[0 0 595\.28 841\.89\]/);
  const xref=Number(text.match(/startxref\n(\d+)/)[1]);assert.equal(buffer.subarray(xref,xref+4).toString(),'xref');
  const entries=text.slice(xref).split('\n');const count=Number(entries[1].split(' ')[1]);
  for(let i=1;i<count;i++){const offset=Number(entries[i+2].slice(0,10));assert.equal(buffer.subarray(offset,offset+`${i} 0 obj`.length).toString(),`${i} 0 obj`);}
  assert.equal((text.match(/\/Subtype \/Image/g)||[]).length,2);
});
test('An empty or missed-only plan cannot download a misleading blank checklist',()=>{
  assert.throws(()=>PDF.layoutSchedule(E.emptyState(ON)),/no scheduled study sessions/i);
  const s=plan();s.rows.forEach(r=>r.Status='Missed');assert.throws(()=>PDF.layoutSchedule(s));
});

test('A normal three-course week fits on one A4 sheet',()=>{
  const s=plan();s.rows=Array.from({length:21},(_,i)=>({...s.rows[0],id:String(i),Date:E.addDays(ON,Math.floor(i/3)),Course:['Calculus','Networks','Programming'][i%3],Topic:'Practice'}));
  const pages=PDF.layoutSchedule(s);assert.equal(pages.length,1);assert.equal(pages[0].rows.length,21);
});
