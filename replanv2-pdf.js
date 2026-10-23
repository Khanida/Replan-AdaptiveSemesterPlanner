/* Offline A4 wall-checklist export. Canvas preserves non-Latin course/topic text. */
(function (root) {
  'use strict';
  const E=typeof module!=='undefined'&&module.exports?require('./replanv2-engine.js'):root.ReplanEngine;
  const WIDTH=595.28,HEIGHT=841.89,LEFT=36,RIGHT=559,TOP=150,BOTTOM=730;
  const FONT='Arial, sans-serif';
  const dateText=(value,options)=>new Date(E.dayNumber(value)*86400000).toLocaleDateString(undefined,{...options,timeZone:'UTC'});
  function wrap(text,width,measure){
    const lines=[];let line='';
    // Character-level fallback also wraps long unbroken strings and CJK text.
    for(const paragraph of String(text).split(/\r?\n/)){
      for(const word of paragraph.split(/(\s+)/).filter(Boolean)){
        if(line&&measure(line+word)>width){lines.push(line.trimEnd());line='';}
        for(const char of word){
          if(line&&measure(line+char)>width){lines.push(line.trimEnd());line='';}
          line+=char;
        }
      }
      lines.push(line.trimEnd());line='';
    }
    return lines.length?lines:[''];
  }
  function layoutSchedule(state,measure=(text)=>Array.from(text).length*5.4){
    const rows=E.clone(state.rows.filter(row=>row.Status!=='Missed')).sort((a,b)=>a.Date.localeCompare(b.Date)||a.Course.localeCompare(b.Course));
    if(!rows.length)throw Error('There are no scheduled study sessions to save. Generate or replan your roadmap first.');
    const days=new Map();
    for(const row of rows){if(!days.has(row.Date))days.set(row.Date,[]);days.get(row.Date).push(row);}
    const pages=[];
    for(const [date,sessions] of days){
      let page=null,y=TOP,part=0;
      const newPage=()=>{page={date,part:++part,rows:[],dailyHours:E.sum(sessions,r=>r['Target Hours']),dailySessions:sessions.length};pages.push(page);y=TOP;};
      newPage();
      for(const row of sessions){
        const courseLines=wrap(row.Course,105,measure),topicLines=wrap(row.Topic,241,measure);
        const height=Math.max(25,Math.max(courseLines.length,topicLines.length)*13+12);
        if(height>BOTTOM-TOP)throw Error('A session label is too long to fit on one printable page. Shorten the course or topic name.');
        if(y+height>BOTTOM)newPage();
        page.rows.push({row,courseLines,topicLines,y,height});y+=height;
      }
    }
    return pages;
  }
  function pdfBytes(images){
    if(!images.length)throw Error('No PDF pages to export.');
    const encoder=new TextEncoder(),chunks=[],offsets=[0];let size=0;
    const append=data=>{const bytes=typeof data==='string'?encoder.encode(data):data;chunks.push(bytes);size+=bytes.length;};
    const object=(id,body)=>{offsets[id]=size;append(`${id} 0 obj\n`);append(body);append('\nendobj\n');};
    append('%PDF-1.4\n');append(new Uint8Array([37,226,227,207,211,10]));
    object(1,'<< /Type /Catalog /Pages 2 0 R >>');
    object(2,`<< /Type /Pages /Count ${images.length} /Kids [${images.map((_,i)=>`${3+i*3} 0 R`).join(' ')}] >>`);
    images.forEach((image,i)=>{
      const page=3+i*3,img=page+1,content=page+2;
      object(page,`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${WIDTH} ${HEIGHT}] /Resources << /XObject << /Im0 ${img} 0 R >> >> /Contents ${content} 0 R >>`);
      offsets[img]=size;append(`${img} 0 obj\n<< /Type /XObject /Subtype /Image /Width ${image.width} /Height ${image.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${image.bytes.length} >>\nstream\n`);
      append(image.bytes);append('\nendstream\nendobj\n');
      const commands=`q\n${WIDTH} 0 0 ${HEIGHT} 0 0 cm\n/Im0 Do\nQ\n`;
      object(content,`<< /Length ${encoder.encode(commands).length} >>\nstream\n${commands}endstream`);
    });
    const start=size,count=3+images.length*3;
    append(`xref\n0 ${count}\n0000000000 65535 f \n`);
    for(let id=1;id<count;id++)append(`${String(offsets[id]).padStart(10,'0')} 00000 n \n`);
    append(`trailer\n<< /Size ${count} /Root 1 0 R >>\nstartxref\n${start}\n%%EOF\n`);
    const result=new Uint8Array(size);let cursor=0;for(const chunk of chunks){result.set(chunk,cursor);cursor+=chunk.length;}return result;
  }
  function drawPage(ctx,page,index,count,state,generated){
    const text=(value,x,y,size=10,bold=false,color='#202720')=>{ctx.font=`${bold?'600':'400'} ${size}px ${FONT}`;ctx.fillStyle=color;ctx.fillText(value,x,y);};
    const line=(x1,y1,x2,y2,color='#d6dcd6',width=.6)=>{ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();};
    ctx.fillStyle='#ffffff';ctx.fillRect(0,0,WIDTH,HEIGHT);ctx.textBaseline='top';
    text('Replan - Adaptive Semester Planner',LEFT,29,9,true,'#4d6653');text('DAILY STUDY CHECKLIST',LEFT,47,22,true);
    text(`${dateText(page.date,{weekday:'long',day:'numeric',month:'short',year:'numeric'})}${page.part>1?'  / continued':''}`,LEFT,81,11,true);
    text(`${page.dailySessions} sessions  /  ${Number(page.dailyHours.toFixed(2))} study hours for this day`,LEFT,101,9,false,'#515b53');
    text('Check each box after studying. One session at a time.',LEFT,117,9,false,'#515b53');
    ctx.fillStyle='#edf0eb';ctx.fillRect(LEFT,133,RIGHT-LEFT,17);
    text('DAY',LEFT+5,138,7.5,true);text('COURSE',114,138,7.5,true);text('TOPIC / MILESTONE',231,138,7.5,true);text('TIME',487,138,7.5,true);text('DONE',532,138,7.5,true);
    page.rows.forEach(({row,courseLines,topicLines,y,height})=>{
      const completed=row.Status==='Completed';const color=completed?'#667067':'#202720';
      text(dateText(row.Date,{weekday:'short'}),LEFT+5,y+8,9,true,color);
      text(dateText(row.Date,{day:'numeric',month:'short'}),LEFT+5,y+17,7,false,'#626d64');
      courseLines.forEach((value,i)=>text(value,114,y+8+i*13,9,true,color));
      topicLines.forEach((value,i)=>text(value,231,y+8+i*13,9,false,color));
      const minutes=Math.round(row['Target Hours']*60),h=Math.floor(minutes/60),m=minutes%60;
      text(h?`${h}h${m?' '+m+'m':''}`:`${m}m`,487,y+9,8,false,color);
      const boxY=y+(height-13)/2;ctx.strokeStyle='#3e4b40';ctx.lineWidth=1;ctx.strokeRect(536,boxY,13,13);
      if(completed){ctx.strokeStyle='#3e4b40';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(538.5,boxY+6.5);ctx.lineTo(542,boxY+10);ctx.lineTo(547,boxY+3);ctx.stroke();}
      line(LEFT,y+height,RIGHT,y+height);
    });
    text('NOTES / NEXT STEPS',LEFT,747,7.5,true,'#515b53');line(LEFT,773,RIGHT,773);line(LEFT,791,RIGHT,791);
    const warning=E.analyze(state,generated).unplaced;
    text(warning>0?`${Number(warning.toFixed(1))}h is still unscheduled. Review deadlines in the app.`:'Blank boxes are yours to check. Ticks reflect work completed before export.',LEFT,804,7,false,warning>0?'#783c31':'#626d64');
    text(`Saved ${dateText(generated,{day:'numeric',month:'short',year:'numeric'})}`,LEFT,819,7,false,'#626d64');
    ctx.textAlign='right';text(`PAGE ${index+1} / ${count}`,RIGHT,819,7,true,'#515b53');ctx.textAlign='left';
  }
  async function createSchedulePDF(state,onProgress=()=>{}){
    const snapshot=E.clone(state),scale=2.5,canvas=document.createElement('canvas');
    canvas.width=Math.ceil(WIDTH*scale);canvas.height=Math.ceil(HEIGHT*scale);
    const ctx=canvas.getContext('2d');if(!ctx)throw Error('Your browser could not create the PDF canvas. Try the Print option instead.');
    ctx.scale(scale,scale);ctx.font=`600 9px ${FONT}`;
    const pages=layoutSchedule(snapshot,text=>ctx.measureText(text).width),images=[],generated=E.today();
    for(let i=0;i<pages.length;i++){
      drawPage(ctx,pages[i],i,pages.length,snapshot,generated);
      const jpeg=await new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error('Could not render a PDF page.')),'image/jpeg',.96));
      images.push({width:canvas.width,height:canvas.height,bytes:new Uint8Array(await jpeg.arrayBuffer())});
      onProgress(i+1,pages.length);await new Promise(resolve=>setTimeout(resolve,0));
    }
    return pdfBytes(images);
  }
  const api={layoutSchedule,pdfBytes,drawPage,createSchedulePDF,wrap};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ReplanPDF=api;
})(typeof globalThis!=='undefined'?globalThis:this);
