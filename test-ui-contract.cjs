const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('replanv2.html','utf8');
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
test('browser UI has unique control IDs and every referenced static control exists',()=>{
  assert.equal(new Set(ids).size,ids.length);
  const source=fs.readFileSync('replanv2.js','utf8');
  for(const match of source.matchAll(/\$\('([^']+)'\)/g))assert.ok(ids.includes(match[1]),'Missing UI control: '+match[1]);
  for(let i=0;i<7;i++)assert.ok(ids.includes('weekday-'+i));
});
test('browser script dependencies exist and calendar helper loads before the UI',()=>{
  const scripts=[...html.matchAll(/<script\b[^>]*src="([^"]+)"/g)].map(m=>m[1]);
  for(const source of scripts)assert.ok(fs.existsSync(source),'Missing browser asset: '+source);
  assert.ok(scripts.indexOf('replanv2-calendar.js')<scripts.indexOf('replanv2.js'));
  assert.ok(scripts.indexOf('replanv2-engine.js')<scripts.indexOf('replanv2.js'));
});
test('web v2 makes daily PDF the primary export and keeps backups in recovery tools',()=>{
  assert.ok((html.match(/data-action="save"/g)||[]).length>=2);
  assert.match(html,/data-action="save"[^>]*>↓ Download PDF/);
  const recovery=html.match(/<details class="backup-tools">([\s\S]*?)<\/details>/)?.[1];
  assert.ok(recovery);assert.match(recovery,/Plan backup and recovery/);
  assert.match(recovery,/data-action="backup"/);assert.match(recovery,/data-action="export-original"/);
  assert.match(html,/Continue with Google/);assert.doesNotMatch(html,/Continue with Apple/);
});
test('browser app has a restrictive script policy and bounds imported files',()=>{
  assert.match(html,/Content-Security-Policy[^>]*default-src 'self'/);
  assert.match(html,/object-src 'none'/);assert.match(html,/script-src 'self'/);
  assert.match(html,/name="referrer" content="no-referrer"/);
  const source=fs.readFileSync('replanv2.js','utf8');
  assert.match(source,/files\.length>2/);
  assert.match(source,/reduce\(\(total,file\)=>total\+file\.size,0\)>maxImportBytes/);
});
