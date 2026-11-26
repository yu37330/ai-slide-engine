// 実際の変換エンジンとブラウザを起動。追加導入・外部通信なし。
const report={node:process.version,modules:{},browser:false,status:'BLOCKED'};
let browser;
try{
  for(const name of ['pptxgenjs','jszip']){
    try{await import(name);report.modules[name]=true;}catch(e){report.modules[name]=false;report.modules[name+'_reason']=String(e.message).slice(0,200);}
  }
  let browserModule=false;
  for(const name of ['playwright-core','playwright']){
    try{await import(name);report.modules[name]=true;browserModule=true;}catch{report.modules[name]=false;}
  }
  if(!report.modules.pptxgenjs||!report.modules.jszip||!browserModule)throw Error('required preinstalled Node packages unavailable');
  const {browserLaunch}=await import('../html/native.mjs');
  browser=await browserLaunch();
  const context=await browser.newContext({serviceWorkers:'block'});
  await context.route('**/*',r=>r.abort());
  const page=await context.newPage();
  await page.setContent('<html><body><svg width="16" height="16"><rect width="16" height="16" fill="red"/></svg></body></html>');
  if((await page.screenshot({type:'png'})).length<50)throw Error('browser screenshot failed');
  report.browser=true;report.status='READY';
}catch(e){report.reason=String(e.message||e).slice(0,350);}
finally{
  if(browser)try{await browser.close();}catch{}
  console.log(JSON.stringify(report));if(report.status!=='READY')process.exitCode=2;
}
