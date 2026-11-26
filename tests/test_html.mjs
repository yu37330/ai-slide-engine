import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import JSZip from 'jszip';
import { run } from '../skills/ai-slide-engine/html/native.mjs';
const root=path.resolve('skills/ai-slide-engine');
const sample=JSON.parse(await fs.readFile(path.join(root,'examples/sample.json'),'utf8'));
const python=process.env.PYTHON||'python';
function render(src,out,theme='petrol'){
  execFileSync(python,[path.join(root,'scripts/render_html.py'),src,out,'--theme',theme],{stdio:'pipe'});
}
test('original CSS + native editable output (Petrol and Paper)',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'html-parity-'));
  try{
    const src=path.join(dir,'deck.json');await fs.writeFile(src,JSON.stringify(sample));
    for(const theme of ['petrol','paper']){
      const out=path.join(dir,theme);render(src,out,theme);
      const report=await run(out);
      assert.equal(report.errors,0,JSON.stringify(report.issues));
      assert.equal(report.checks.native_export,'PASS');
      assert.ok(report.stats.shape>10,JSON.stringify(report.stats));
      assert.ok(report.stats.text>10,JSON.stringify(report.stats));
      const z=await JSZip.loadAsync(await fs.readFile(path.join(out,'deck-native.pptx')));
      const xml=await z.file('ppt/slides/slide2.xml').async('string');
      assert.ok((xml.match(/<p:sp[\s>]/g)||[]).length>5,'individual native shapes');
      const nativeTexts=[...xml.matchAll(/<p:sp(?:\s[^>]*)?>[\s\S]*?<\/p:sp>/g)].map(m=>[...m[0].matchAll(/<a:t(?:\s[^>]*)?>([\s\S]*?)<\/a:t>/g)].map(t=>t[1]).join(''));
      assert.ok(nativeTexts.some(t=>t.includes('数理最適化')), 'figure text must be native within one shape; actual '+JSON.stringify(nativeTexts));
      assert.ok((await fs.stat(path.join(out,'pages/002.png'))).size>0);
      console.log(theme,JSON.stringify(report.stats),JSON.stringify(report.issues.map(x=>x.type)));
    }
  }finally{await fs.rm(dir,{recursive:true,force:true});}
});
test('actual browser rejects geometry outside; flags overlap and tiny figure',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'html-negative-'));
  try{
    const fixtures=[
      ['overlap',[{component:'T',args:[500,180,'alpha']},{component:'T',args:[500,180,'beta']}],'svg-text-overlap'],
      ['outside',[{component:'A',args:[20,100,1350,100]}],'svg-geometry-outside'],
      ['icon',[{component:'icon',args:[1150,390,'user']}],'svg-geometry-outside'],
      ['tiny',[{component:'R',args:[20,20,3,3]}],'figure-small']
    ];
    for(const [id,ops,expected] of fixtures){
      const d=structuredClone(sample);d.slides[1].figure.operations=ops;
      const src=path.join(dir,id+'.json'),out=path.join(dir,id);
      await fs.writeFile(src,JSON.stringify(d));render(src,out);
      const report=await run(out,{checkOnly:true});
      assert.ok(report.issues.some(x=>x.type===expected),JSON.stringify(report.issues));
      if(expected==='svg-geometry-outside')assert.ok(report.errors>0);
      console.log(id,expected);
    }
  }finally{await fs.rm(dir,{recursive:true,force:true});}
});
