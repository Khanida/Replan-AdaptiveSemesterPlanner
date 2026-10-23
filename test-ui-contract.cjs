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
