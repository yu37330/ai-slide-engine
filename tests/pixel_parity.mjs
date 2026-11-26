// 正解は上流の固定Marpを再実行したHTML。候補は固定catalogをPythonでレンダリングする。
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {chromium} from 'playwright-core';
import {PNG} from 'pngjs';
import {original,NAMES,THEMES,shell} from '../scripts/compile_templates.mjs';
const up=path.resolve(process.argv[2]),catalog=path.resolve(process.argv[3]);
const script=path.resolve(process.env.SKILL_ROOT||'skills/ai-slide-engine','scripts/template_render.py'),fontDir=path.join(up,'marp/themes/assets');
const HOST='https://pixel-test.invalid/';
const mime={'.html':'text/html','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2'};
const PY=process.env.PYTHON||'python';
const browser=await chromium.launch({headless:true});
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'pixel-parity-'));
let rows=[],errors=[];
async function open(context,files){
  const page=await context.newPage();
  await page.route('**/*',async route=>{
    const url=route.request().url(),name=url.startsWith(HOST)?url.slice(HOST.length):null;
    if(!name||!files.has(name))return route.abort();
    return route.fulfill({body:files.get(name),contentType:mime[path.extname(name)]});
  });
  await page.goto(HOST+'deck.html');
  await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(x=>x.decode()));});
  return page;
}
function compare(a,b){
  a=PNG.sync.read(a);b=PNG.sync.read(b);
  assert.equal(a.width,1280);assert.equal(a.height,720);assert.equal(a.width,b.width);assert.equal(a.height,b.height);
  let different=0,abs=0,max=0;
  for(let p=0;p<a.data.length;p+=4){
    let delta=0;
    for(let j=0;j<4;j++){const d=Math.abs(a.data[p+j]-b.data[p+j]);abs+=d;delta=Math.max(delta,d);max=Math.max(max,d);}
    if(delta)different++;
  }
  return {different,total:a.width*a.height,mae:abs/a.data.length,max};
}
try{
  for(const name of NAMES)for(const theme of THEMES){
    const key=name+'-'+theme,ref=await original(up,name,theme),dir=path.join(temp,key),sp=path.join(temp,key+'.json');
    execFileSync(PY,[script,'--catalog',catalog,'spec',name,theme,sp]);
    execFileSync(PY,[script,'--catalog',catalog,'render',sp,dir,'--fonts',fontDir]);
    const manifest=JSON.parse(await fs.readFile(path.join(dir,'manifest.json'),'utf8'));
    const baseline=new Map(Object.entries(ref.assets));
    baseline.set('deck.html',Buffer.from('<!doctype html><html><head><meta charset="utf-8"><style>'+ref.css+'\n'+shell+'</style></head><body>'+ref.html+'</body></html>'));
    const candidate=new Map();
    for(const asset of manifest.assets)candidate.set(asset,await fs.readFile(path.join(dir,asset)));
    const context=await browser.newContext({viewport:{width:1280,height:720},deviceScaleFactor:1,colorScheme:theme==='paper'?'dark':'light',serviceWorkers:'block'});
    const a=await open(context,baseline),b=await open(context,candidate);
    const al=a.locator('section[id]'),bl=b.locator('section[id]');
    assert.equal(await al.count(),await bl.count(),key);
    const pageRows=[];
    for(let i=0;i<await al.count();i++){
      const A=await al.nth(i).screenshot({animations:'disabled'}),B=await bl.nth(i).screenshot({animations:'disabled'});
      const r=compare(A,B);pageRows.push({...r,page:i+1});
      if(r.different)errors.push({key,page:i+1,...r});
    }
    const different=pageRows.reduce((x,r)=>x+r.different,0),total=pageRows.reduce((x,r)=>x+r.total,0);
    rows.push({key,pages:pageRows.length,exact:pageRows.filter(r=>r.different===0).length,different,total,details:pageRows});
    console.log('PIXEL',key,JSON.stringify({pages:pageRows.length,exact:pageRows.filter(r=>!r.different).length,different,total,match:1-different/total}));
    await context.close();
  }
  const result={variants:rows.length,pages:rows.reduce((n,x)=>n+x.pages,0),exact:rows.reduce((n,x)=>n+x.exact,0),errors,rows};
  console.log('PIXEL_SUMMARY',JSON.stringify({variants:result.variants,pages:result.pages,exact:result.exact,errors:errors.length}));
  if(process.env.PIXEL_REPORT)await fs.writeFile(process.env.PIXEL_REPORT,JSON.stringify(result,null,2));
  assert.equal(errors.length,0,JSON.stringify(errors.slice(0,20)));
}finally{await browser.close();await fs.rm(temp,{recursive:true,force:true});}
