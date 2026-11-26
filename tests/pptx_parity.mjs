// 実際の上流Marp→PPTXと、新しいHTML→PPTXの独立比較。原典は固定公開資料だけ。
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {chromium} from 'playwright-core';
import {NAMES,THEMES} from '../scripts/compile_templates.mjs';

const up=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
const root=path.resolve(process.env.SKILL_ROOT||'skills/ai-slide-engine'),catalog=path.join(root,'templates/catalog.zip');
const {run}=await import(pathToFileURL(path.join(root,'html/native.mjs')).href);
const fontDir=path.join(up,'marp/themes/assets'),py=process.env.PYTHON||'python';
process.env.CHROME_PATH=chromium.executablePath();
const {exportPptx}=await import(pathToFileURL(path.join(up,'marp/pptx/index.mjs')).href);
await fs.mkdir(out,{recursive:true});
const results=[];
for(const name of NAMES)for(const theme of THEMES){
  const key=name+'-'+theme,work=path.join(out,key);
  await fs.mkdir(work,{recursive:true});
  const refDir=path.join(work,'upstream'),cand=path.join(work,'candidate');
  await fs.mkdir(refDir);
  const src=path.join(up,'marp/templates',name);
  const meta=JSON.parse(await fs.readFile(path.join(src,'template.json'),'utf8'));
  const md=(await fs.readFile(path.join(src,'slides.md'),'utf8')).replaceAll('{{TITLE}}',meta.defaultTitle).replaceAll('Your Name','Sample Author').replace(/^theme:\s*\S+/m,'theme: '+theme);
  const input=path.join(refDir,'slides.md'),baseline=path.join(refDir,'original.pptx');
  await fs.writeFile(input,md);
  await fs.cp(path.join(src,'figs'),path.join(refDir,'figs'),{recursive:true});
  const spec=path.join(work,'spec.json');
  const r={key};
  try{
    // 原典の変換実装はコピーや改変をせずにそのまま実行する。
    await exportPptx(input,baseline);
    execFileSync(py,[path.join(root,'scripts/template_render.py'),'--catalog',catalog,'spec',name,theme,spec],{stdio:'pipe'});
    execFileSync(py,[path.join(root,'scripts/template_render.py'),'--catalog',catalog,'render',spec,cand,'--fonts',fontDir],{stdio:'pipe'});
    const qa=await run(cand);
    r.qa={errors:qa.errors,warnings:qa.warnings,issues:qa.issues};
    if(qa.errors||qa.checks.native_export!=='PASS')throw Error('candidate quality gate blocked: '+JSON.stringify(qa.issues.filter(x=>x.level==='error')));
    const review=path.join(work,'render-review');
    execFileSync(py,[path.join(root,'scripts/pptx_render_review.py'),path.join(cand,'deck-native.pptx'),path.join(cand,'pages'),review,'--baseline',baseline],{stdio:'pipe',timeout:300000});
    const data=JSON.parse(await fs.readFile(path.join(review,'review-pptx.json'),'utf8'));
    r.pages=data.pages.map(p=>({page:p.page,html_candidate:p.html_candidate,html_baseline:p.html_baseline,baseline_candidate:p.baseline_candidate,native_equal:p.native_equal,geometry_diff:p.geometry_diff}));
    const s=r.pages;
    console.log('PPTX_VARIANT',key,JSON.stringify({pages:s.length,exact:s.filter(x=>x.baseline_candidate.different===0).length,mean_relative_mae:s.reduce((n,x)=>n+x.baseline_candidate.mae,0)/s.length,mean_html_mae:s.reduce((n,x)=>n+x.html_candidate.mae,0)/s.length,mean_original_html_mae:s.reduce((n,x)=>n+x.html_baseline.mae,0)/s.length,native_equal:s.filter(x=>Object.values(x.native_equal).every(Boolean)).length,warnings:qa.warnings}));
  }catch(e){r.error=String(e.stderr||e.message||e).slice(0,5000);console.error('PPTX_VARIANT_ERROR',key,r.error);}
  results.push(r);
}
const pages=results.flatMap(x=>(x.pages||[]).map(p=>({variant:x.key,...p})));
const blocked=results.filter(x=>x.error);
const total=pages.reduce((n,x)=>n+x.baseline_candidate.pixels,0),different=pages.reduce((n,x)=>n+x.baseline_candidate.different,0);
// 相対差0を最終目標とする。初期監査は測定結果を記録し、閾値を後から都合よく緩めない。
// 下の回帰条件は明示した各ページの劣化幅（RGB平均0.1/255、SSIM8 0.001）に限定。
// 原典を超える絶対一致の判定は別に記録し、回帰合格を100%同一と混同しない。
const regressions=pages.filter(p=>p.html_candidate.mae>p.html_baseline.mae+.1||
  p.html_candidate.ssim8<p.html_baseline.ssim8-.001||
  ['shapes','text_runs','tables','images','groups','text'].some(k=>!p.native_equal[k]));
const mean=k=>pages.length?pages.reduce((n,p)=>n+p[k].mae,0)/pages.length:null;
const avgSsim=k=>pages.length?pages.reduce((n,p)=>n+p[k].ssim8,0)/pages.length:null;
const summary={variants:results.length,pages:pages.length,blocked:blocked.map(r=>({key:r.key,error:r.error})),
  exact_relative_pages:pages.filter(p=>p.baseline_candidate.different===0).length,relative_pixels:total,relative_different:different,
  relative_mae:mean('baseline_candidate'),html_candidate_mae:mean('html_candidate'),html_baseline_mae:mean('html_baseline'),
  html_candidate_ssim8:avgSsim('html_candidate'),html_baseline_ssim8:avgSsim('html_baseline'),
  exact_html_pages:pages.filter(p=>p.html_candidate.different===0).length,
  native_geometry_equal_pages:pages.filter(p=>p.native_equal.geometry).length,
  regressions:regressions.map(p=>({variant:p.variant,page:p.page,relative:p.baseline_candidate,html_candidate:p.html_candidate,html_baseline:p.html_baseline,native_equal:p.native_equal,geometry_diff:p.geometry_diff})),
  renderer:'LibreOffice/Poppler, not Microsoft PowerPoint'};
await fs.writeFile(path.join(out,'summary.json'),JSON.stringify({summary,results},null,2));
console.log('PPTX_AUDIT_SUMMARY',JSON.stringify({...summary,regressions:summary.regressions.length}));
for(const r of summary.regressions)console.error('PPTX_REGRESSION',JSON.stringify(r));
for(const p of pages.filter(p=>p.geometry_diff))console.log('PPTX_GEOMETRY_DIFF',JSON.stringify({variant:p.variant,page:p.page,...p.geometry_diff}));
if(blocked.length||pages.length!==96||regressions.length)process.exitCode=1;
