// 開発専用。固定された上流MarpからHTML雛形を一度だけ生成する。
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {Marp} from '@marp-team/marp-core';
import {chromium} from 'playwright-core';
import JSZip from 'jszip';
export const PIN='b5814e92b1c4bcc6d78f1c357ebe05de9030f5e2';
export const NAMES=['lightning','release','talk','update','webinar'];
export const THEMES=['petrol','paper'];
export const FONTS=['NotoSansJP-Book450.woff2','NotoSansJP-Bold.woff2','NotoSansJP-Regular.woff2'];
export const shell='html,body{margin:0;padding:0;background:#888}\nsvg[data-marpit-svg]{display:block;width:1280px;height:720px;margin:0 0 8px}';
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
export async function original(up,name,theme){
  const dir=path.join(up,'marp','templates',name);
  const meta=JSON.parse(await fs.readFile(path.join(dir,'template.json'),'utf8'));
  const md=(await fs.readFile(path.join(dir,'slides.md'),'utf8')).replaceAll('{{TITLE}}',meta.defaultTitle).replaceAll('Your Name','Sample Author').replace(/^theme:\s*\S+/m,'theme: '+theme);
  const {default:engine}=await import(pathToFileURL(path.join(up,'marp','engine.mjs')).href);
  const marp=engine({marp:new Marp({html:true,emoji:{shortcode:false,unicode:false},math:false,minifyCSS:false,script:false})});
  const {html,css,comments}=marp.render(md);
  const assets={};
  for(const name of await fs.readdir(path.join(dir,'figs'))){
    if(!/^[A-Za-z0-9_-]+\.svg$/.test(name))continue;
    assets['figs/'+name]=await fs.readFile(path.join(dir,'figs',name));
  }
  const fonts={};
  for(const name of FONTS)fonts[name]=await fs.readFile(path.join(up,'marp','themes','assets',name));
  return {html,css,comments,assets,fonts,title:meta.defaultTitle.replace(/<br\s*\/?>/g,' '),author:'Sample Author'};
}
function externalizeFonts(css,fonts){
  for(const [name,raw] of Object.entries(fonts)){
    const data='data:font/woff2;base64,'+raw.toString('base64');
    if(!css.includes(data))throw Error('original embedded font missing: '+name);
    css=css.replaceAll(data,'themes/assets/'+name);
  }
  if(/data:font\//i.test(css)||/data:application\/(?:font|x-font)/i.test(css))throw Error('unremoved embedded font');
  return css;
}
export async function compile(up,output){
  const zip=new JSZip(),browser=await chromium.launch({headless:true});
  const manifest={version:1,upstream:PIN,variants:[],fonts:{}};
  try{
    const page=await browser.newPage();
    for(const name of NAMES)for(const theme of THEMES){
      const r=await original(up,name,theme),key=name+'-'+theme;
      // テキストノードだけをJSONスロット化する。DOMのclass、SVG、配置、CSSは維持。
      const compiled=await page.evaluate(raw=>{
        const doc=new DOMParser().parseFromString('<!doctype html><html><body>'+raw+'</body></html>','text/html');
        const sections=[...doc.querySelectorAll('section[id]')],slots={},slides=[];
        let next=0;
        for(const sec of sections){
          const id=sec.id;
          const kind=sec.classList.contains('cover')?'cover':sec.classList.contains('closing')?'closing':sec.classList.contains('divider')?'section':sec.querySelector('img[src$=".svg"]')?'figure':sec.querySelector('table')?'table':'text';
          const walker=doc.createTreeWalker(sec,NodeFilter.SHOW_TEXT);
          const ids=[];
          for(let n;(n=walker.nextNode());){
            if(!n.nodeValue.trim()||n.parentElement.closest('svg,style,script'))continue;
            const k='S'+String(++next).padStart(5,'0');
            if(raw.includes('__JINNO_'+k+'__'))throw Error('slot marker collision');
            const el=n.parentElement,role=el.closest('h1')?'title':el.closest('.lead')?'lead':el.closest('.kicker')?'kicker':el.closest('.sub')?'subtitle':el.closest('.who')?'author':'body';
            slots[k]={slide:id,role,default:n.nodeValue};ids.push(k);
            n.nodeValue='__JINNO_'+k+'__';
          }
          slides.push({id,kind,classes:sec.className,slots:ids,images:[...sec.querySelectorAll('img')].map(x=>x.getAttribute('src'))});
        }
        return {body:doc.body.innerHTML,slots,slides};
      },r.html);
      if(!compiled.slides.length||!compiled.slots||!compiled.slides.every(x=>x.id))throw Error('empty template: '+key);
      const css=externalizeFonts(r.css,r.fonts);
      const index={version:1,key,name,theme,title:r.title,author:r.author,slides:compiled.slides,slots:compiled.slots,comments:r.comments,assets:Object.keys(r.assets).sort()};
      zip.file(key+'/body.html',compiled.body);
      zip.file(key+'/theme.css',css);
      zip.file(key+'/index.json',JSON.stringify(index));
      for(const [p,data] of Object.entries(r.assets))zip.file(key+'/'+p,data);
      manifest.variants.push({key,name,theme,pages:index.slides.length,slots:Object.keys(index.slots).length});
      for(const [n,raw] of Object.entries(r.fonts))manifest.fonts[n]=sha(raw);
      console.log('TEMPLATE_COMPILED',key,index.slides.length,Object.keys(index.slots).length);
    }
    zip.file('catalog.json',JSON.stringify(manifest,null,2));
    const buf=await zip.generateAsync({type:'nodebuffer',compression:'DEFLATE',compressionOptions:{level:9}});
    await fs.writeFile(output,buf);
    console.log('CATALOG',JSON.stringify(manifest.variants),buf.length,sha(buf));
  }finally{await browser.close();}
}
if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(new URL(import.meta.url).pathname)){
  await compile(path.resolve(process.argv[2]),path.resolve(process.argv[3]));
}
