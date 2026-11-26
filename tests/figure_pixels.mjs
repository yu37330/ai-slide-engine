import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';
import {PNG} from 'pngjs';
const dir=path.resolve(process.argv[2]),manifest=JSON.parse(await fs.readFile(path.join(dir,'manifest.json')));
const browser=await chromium.launch({headless:true});
let pixels=0,count=0;
try{
  const page=await browser.newPage({deviceScaleFactor:1});
  for(const c of manifest.cases){
    await page.setViewportSize({width:c.width,height:c.height});
    await page.emulateMedia({colorScheme:c.id.endsWith('-paper')?'dark':'light'});
    const imgs=[];
    for(const which of ['original','candidate']){
      const svg=await fs.readFile(path.join(dir,c.id,which+'.svg'));
      await page.setContent('<style>html,body{margin:0}img{display:block;width:100vw;height:100vh}</style><img src="data:image/svg+xml;base64,'+svg.toString('base64')+'">');
      await page.evaluate(async()=>{await document.fonts.ready;await document.querySelector('img').decode()});
      imgs.push(PNG.sync.read(await page.screenshot({animations:'disabled'})));
    }
    const [a,b]=imgs;
    assert.equal(a.width,b.width);assert.equal(a.height,b.height);
    let changed=0;for(let i=0;i<a.data.length;i+=4)if(a.data[i]!==b.data[i]||a.data[i+1]!==b.data[i+1]||a.data[i+2]!==b.data[i+2]||a.data[i+3]!==b.data[i+3])changed++;
    assert.equal(changed,0,c.id);
    pixels+=a.width*a.height;count++;
  }
  console.log('FIGURE_PIXEL_SUMMARY',JSON.stringify({cases:count,pixels,different:0}));
}finally{await browser.close();}
