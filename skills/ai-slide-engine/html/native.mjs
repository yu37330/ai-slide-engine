// HTMLを入口に原典のDOM検査とDrawingML変換を実行する。外部アクセス・自動依存導入なし。
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { assemblePptx, walkItems, summarize } from './pptx/assemble.mjs';
import { checkLayout, measureSvg, checkWriting, svgFindings, inkBox } from './check/deck-check.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const ORIGIN='https://slide-engine.invalid';
const CSP="default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; script-src 'none'; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'";
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.woff2':'font/woff2','.png':'image/png','.jpeg':'image/jpeg','.jpg':'image/jpeg','.gif':'image/gif'};
const readJson=async f=>JSON.parse(await fs.readFile(f,'utf8'));
export async function browserLaunch(){
  let pw;
  try{pw=await import('playwright-core');}catch{pw=await import('playwright');}
  const options={headless:true};
  if(process.env.CHROME_PATH)options.executablePath=process.env.CHROME_PATH;
  return pw.chromium.launch(options);
}
async function bundle(dir){
  const manifest=await readJson(path.join(dir,'manifest.json'));
  const deck=await readJson(path.join(dir,'deck.json'));
  if(!['petrol','paper'].includes(manifest.theme)||!Array.isArray(deck.slides)||!deck.slides.length||
      JSON.stringify(manifest.slides)!==JSON.stringify(deck.slides.map(s=>s.id)))throw Error('manifest mismatch');
  const names=['deck.html','themes/petrol.css','themes/paper.css'];
  for(const s of deck.slides){
    if(!/^[A-Za-z0-9_-]+$/.test(s.id))throw Error('invalid slide id');
    if(s.kind==='figure')names.push('figures/'+s.id+'.svg');
  }
  if(manifest.font_mode==='approved_assets')for(const n of ['NotoSansJP-Book450.woff2','NotoSansJP-Bold.woff2','NotoSansJP-Regular.woff2'])names.push('themes/assets/'+n);
  const assets=new Map();
  const root=await fs.realpath(dir);
  for(const name of names){
    const real=await fs.realpath(path.join(root,name));
    if(!real.startsWith(root+path.sep))throw Error('asset outside bundle');
    const bytes=await fs.readFile(real);
    assets.set(ORIGIN+'/'+name,bytes);
  }
  return {manifest,deck,assets};
}
async function wire(context,assets){
  await context.route('**/*',async route=>{
    const req=route.request(),url=req.url(),bytes=assets.get(url);
    if(req.method()!=='GET'||!bytes)return route.abort('blockedbyclient');
    return route.fulfill({status:200,body:bytes,contentType:mime[path.extname(new URL(url).pathname)],headers:{'Content-Security-Policy':CSP,'X-Content-Type-Options':'nosniff'}});
  });
}
export async function ready(page){
  await page.evaluate(async()=>{
    await document.fonts.ready;
    await Promise.all([...document.images].map(i=>i.decode().catch(()=>{})));
  });
}
async function checkBundle(page, context, manifest, deck, assets, dir){
  const actual=await page.locator('section[id]').evaluateAll(es=>es.map(e=>({id:e.id,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height})));
  if(actual.length!==deck.slides.length||actual.some((e,i)=>e.id!==deck.slides[i].id||Math.abs(e.w-1280)>.5||Math.abs(e.h-720)>.5))throw Error('HTML slide ID/order/dimensions mismatch');
  const issues=await page.evaluate(checkLayout,{range:null});
  const phrases=await readJson(path.join(here,'check','phrases.json'));
  issues.push(...await page.evaluate(checkWriting,phrases));
  const figPage=await context.newPage();
  for(const [i,s] of deck.slides.entries()){
    if(s.kind!=='figure')continue;
    const src='figures/'+s.id+'.svg',url=ORIGIN+'/'+src,svg=assets.get(url).toString('utf8');
    await figPage.setViewportSize({width:s.figure.width,height:s.figure.height});
    // CSP付き同一オリジンのルートへ移動。SVGは生成済みのローカル資産のみ。
    await figPage.goto(url);
    await figPage.evaluate(()=>document.fonts.ready);
    // SVG単体文書をHTML内に配置する検査は、原典measureSvgとinkBoxのDOM契約に合わせる。
    const wrapper=ORIGIN+'/__figure_check.html';
    assets.set(wrapper,Buffer.from('<!doctype html><html><head><style>html,body{margin:0}body>svg{display:block;width:100vw;height:100vh}</style></head><body>'+svg+'</body></html>'));
    await figPage.goto(wrapper);await figPage.evaluate(()=>document.fonts.ready);
    const r=await figPage.evaluate(measureSvg),ink=await figPage.evaluate(inkBox);
    issues.push(...svgFindings(r,src,[i+1]));
    const box=await page.locator('section[id]').nth(i).locator('img').evaluate(e=>{const r=e.getBoundingClientRect(),s=e.closest('section').getBoundingClientRect();return {w:r.width,y:r.top-s.top};});
    if(!ink||ink.x1-ink.x0<1||ink.y1-ink.y0<1)issues.push({page:i+1,type:'figure-empty',level:'error',msg:src});
    else{
      const {width,height}=s.figure;
      if(ink.x0<-1||ink.y0<-1||ink.x1>width+1||ink.y1>height+1)issues.push({page:i+1,type:'svg-geometry-outside',level:'error',msg:src,ink});
      const scale=box.w/width,w=(ink.x1-ink.x0)*scale,h=(ink.y1-ink.y0)*scale,gap=668-(box.y+ink.y1*scale);
      if(w<720||(h<200&&gap>170))issues.push({page:i+1,type:'figure-small',level:'warn',msg:src,ink});
    }
  }
  assets.delete(ORIGIN+'/__figure_check.html');
  await figPage.close();
  if(manifest.font_mode!=='approved_assets')issues.push({page:0,type:'font-fallback-unverified',level:'warn',msg:'Original font files were not supplied. Font/render parity unverified.'});
  // 発表者・原典由来の配色/文言検査を残し、未実査を合格扱いしない。
  await fs.mkdir(path.join(dir,'pages'),{recursive:true});
  for(let i=0;i<actual.length;i++)await page.locator('section[id]').nth(i).screenshot({path:path.join(dir,'pages',String(i+1).padStart(3,'0')+'.png'),animations:'disabled'});
  return {issues,errors:issues.filter(x=>x.level==='error').length,warnings:issues.filter(x=>x.level==='warn').length};
}
async function imageBytes(page,it,assets){
  if(it.data)return {buf:it.data,ext:'png'};
  const src=it.src||'';
  let buf=assets.get(src);
  if(src.startsWith('data:')){
    const i=src.indexOf(',');if(i<0)throw Error('invalid data URI');
    buf=/;base64/.test(src.slice(0,i))?Buffer.from(src.slice(i+1),'base64'):Buffer.from(decodeURIComponent(src.slice(i+1)));
  }
  if(!buf)throw Error('missing/blocked image: '+src);
  const ext=buf[0]===0x89&&buf[1]===0x50?'png':buf[0]===0xff&&buf[1]===0xd8?'jpeg':buf.slice(0,3).toString()==='GIF'?'gif':null;
  if(ext)return {buf,ext};
  const b64=await page.evaluate(async s=>{
    const im=new Image();im.src=s;await im.decode();
    const c=document.createElement('canvas');c.width=im.naturalWidth;c.height=im.naturalHeight;
    c.getContext('2d').drawImage(im,0,0);
    return c.toDataURL('image/png').split(',')[1];
  },src);
  return {buf:Buffer.from(b64,'base64'),ext:'png'};
}
async function shootRaster(page, index, id, it) {
  const box = await page.evaluate(({ index, id }) => {
    const sec = document.querySelectorAll('section[id]')[index];
    const el = sec.querySelector(`[data-pptx-raster~="${id}"]`) || (sec.dataset.pptxRaster?.split(' ').includes(id) ? sec : null);
    if (!el) return null;
    const what = el.dataset[`pptxRaster${id}`];
    el.classList.add('pptx-target');
    document.body.classList.add('pptx-iso', what === 'mask' ? 'pptx-iso-mask' : 'pptx-iso-bg');
    sec.classList.add('pptx-iso-sec');
    sec.scrollIntoView();
    const b = sec.getBoundingClientRect();
    return { x: b.left, y: b.top };
  }, { index, id });
  if (!box) return null;
  const isolation=await page.addStyleTag({ content: `
    body.pptx-iso, html:has(body.pptx-iso) { background: transparent !important; }
    body.pptx-iso section.pptx-iso-sec { background: transparent !important; }
    body.pptx-iso section.pptx-iso-sec * { visibility: hidden !important; }
    body.pptx-iso section.pptx-iso-sec .pptx-target { visibility: visible !important; color: transparent !important; -webkit-text-fill-color: transparent !important; border-color: transparent !important; box-shadow: none !important; outline: none !important; }
    body.pptx-iso section.pptx-iso-sec .pptx-target * { visibility: hidden !important; }
    body.pptx-iso section.pptx-iso-sec.pptx-target { visibility: visible !important; }
  ` });
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const clip = { x: box.x + it.x, y: box.y + it.y, width: Math.max(1, it.w), height: Math.max(1, it.h) };
  const buf = await page.screenshot({ type: 'png', omitBackground: true, clip });
  await page.evaluate(() => {
    document.querySelector('.pptx-target')?.classList.remove('pptx-target');
    document.body.classList.remove('pptx-iso', 'pptx-iso-mask', 'pptx-iso-bg');
    document.querySelector('.pptx-iso-sec')?.classList.remove('pptx-iso-sec');
    window.scrollTo(0, 0);
  });
  await isolation.evaluate(el=>el.remove());
  return buf;
}

export async function run(dir,{checkOnly=false}={}){
  dir=path.resolve(dir);
  const {manifest,deck,assets}=await bundle(dir);
  const browser=await browserLaunch();
  try{
    const context=await browser.newContext({viewport:{width:1280,height:720},deviceScaleFactor:1,serviceWorkers:'block',colorScheme:manifest.theme==='paper'?'dark':'light'});
    await wire(context,assets);
    const page=await context.newPage();
    await page.exposeFunction('pptxReadText',async url=>{
      if(!assets.has(url)||!url.endsWith('.svg'))throw Error('blocked SVG read');
      return assets.get(url).toString('utf8');
    });
    await page.goto(ORIGIN+'/deck.html');await ready(page);
    const report=await checkBundle(page,context,manifest,deck,assets,dir);
    const result={...report,status:report.errors?'LAYOUT_FAILED':'REVIEW_REQUIRED',checks:{browser_layout:'RUN',svg_geometry:'RUN',native_export:'NOT_RUN',office_render:'NOT_RUN',fact_verification:'NOT_RUN',tenant:'NOT_RUN',credits:'NOT_RUN'},font_mode:manifest.font_mode};
    const save=()=>fs.writeFile(path.join(dir,'review-html.json'),JSON.stringify(result,null,2)+'\n');
    await save();
    if(report.errors||checkOnly)return result;
    // 原典extract.jsを同じHTMLに適用する。参照コード自体は変更しない。
    await page.addScriptTag({path:path.join(here,'pptx','extract.js')});
    const scenes=await page.evaluate(()=>window.__pptxExtract());
    if(scenes.length!==deck.slides.length)throw Error('scene count mismatch');
    for(const sc of scenes)for(const it of walkItems(sc.items)){
      if(it.k==='raster'){
        const buf=await shootRaster(page,sc.index,it.id,it);
        if(!buf)throw Error('raster fallback failed');
        Object.assign(it,{k:'image',data:buf,crop:null,rot:0});
      }
      if(it.k==='skip')throw Error('unsupported skipped item');
    }
    await fs.writeFile(path.join(dir,'scenes.json'),JSON.stringify(scenes,(k,v)=>k==='data'||k==='_bytes'?undefined:v,2)+'\n');
    const md='title: '+deck.title.replace(/[\r\n]+/g,' ')+'\nauthor: '+deck.author.replace(/[\r\n]+/g,' ');
    const notes=deck.slides.map(s=>[s.notes,...s.source_ids.map(id=>{const src=deck.sources.find(x=>x.id===id);return src.label+': '+src.locator;})]);
    const buf=await assemblePptx(md,notes,scenes,async it=>{
      const img=await imageBytes(page,it,assets);return {...img,hash:crypto.createHash('sha1').update(img.buf).digest('hex')};
    },'nodebuffer');
    await fs.writeFile(path.join(dir,'deck-native.pptx'),buf);
    result.checks.native_export='PASS';result.stats=summarize(scenes);
    await save();
    return result;
  }finally{await browser.close();}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const result=await run(process.argv[2],{checkOnly:process.argv.includes('--check-only')});console.log(JSON.stringify(result,null,2));if(result.errors)process.exitCode=1;}
  catch(e){console.error(e);process.exitCode=1;}
}
