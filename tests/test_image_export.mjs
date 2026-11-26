import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import JSZip from 'jszip';
import {run} from '../skills/ai-slide-engine/html/native.mjs';
const py=process.env.PYTHON||'python';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
test('approved PNG/JPEG survive native PPTX export unchanged; static SVG is extracted',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'image-export-'));
  try{
    const src=path.join(dir,'deck.json'),assets=path.join(dir,'assets'),out=path.join(dir,'out');
    execFileSync(py,['tests/test_visual_assets.py',assets,src]);
    execFileSync(py,['skills/ai-slide-engine/scripts/render_html.py',src,out,'--theme','paper','--assets-dir',assets]);
    const report=await run(out);
    assert.equal(report.errors,0,JSON.stringify(report.issues));
    assert.equal(report.checks.native_export,'PASS');
    assert.ok(report.stats.image>=2,JSON.stringify(report.stats));
    const zip=await JSZip.loadAsync(await fs.readFile(path.join(out,'deck-native.pptx')));
    const media=Object.keys(zip.files).filter(n=>/^ppt\/media\/.+\.(png|jpeg|jpg)$/i.test(n));
    const hashes=await Promise.all(media.map(async n=>sha(await zip.file(n).async('nodebuffer'))));
    for(const filename of ['screen.png','photo.jpg'])assert.ok(hashes.includes(sha(await fs.readFile(path.join(assets,filename)))),filename+' bytes changed or missing');
    console.log('VISUAL_ASSET_NATIVE_EXPORT',JSON.stringify(report.stats));
  }finally{await fs.rm(dir,{recursive:true,force:true});}
});
