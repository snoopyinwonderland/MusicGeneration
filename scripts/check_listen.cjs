const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const assert=require('node:assert/strict');
const repo=path.resolve(__dirname,'..');
const dependencyRoot=path.resolve(process.env.MUSICOMP_ROOT || path.join(repo,'../Music Composition'));
const {createRequire}=require('node:module');
const {chromium}=createRequire(path.join(dependencyRoot,'package.json'))('playwright-core');
const root=path.join(repo,'docs/listen');
const out=path.join(repo,'output/virtual-composer-release');
const mime={'.html':'text/html; charset=utf-8','.json':'application/json','.pdf':'application/pdf'};
async function main(){
 const server=http.createServer((req,res)=>{
  let file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
  if(!file.startsWith(path.resolve(root)+path.sep)&&file!==path.resolve(root)){res.writeHead(403).end();return;}
  if(fs.existsSync(file)&&fs.statSync(file).isDirectory()) file=path.join(file,'index.html');
  if(!fs.existsSync(file)){res.writeHead(404).end();return;}
  res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'text/plain'});res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const url='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || undefined});
 const report={pages:[],downloads:[],errors:[]};
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
  page.on('pageerror',e=>report.errors.push(e.message));
  await page.route('https://cdn.jsdelivr.net/**',r=>r.fulfill({body:fs.readFileSync(path.join(dependencyRoot,'node_modules/verovio/dist/verovio-toolkit-wasm.js')),contentType:'text/javascript'}));
  await page.goto(url+'/');
  await page.waitForFunction(()=>typeof pianoReady!=='undefined'&&pianoReady&&notes.length>0);
  assert.equal(await page.locator('#pick option').count(),6);
  for(let i=0;i<6;i++){
   await page.selectOption('#pick',String(i));
   const result=await page.evaluate(()=>({piece:cur.piece,version:cur.info.version,log:tk.getLog(),notes:notes.length,
    instruments:notes.reduce((o,n)=>(o[n.instrument]=(o[n.instrument]||0)+1,o),{}),
    pianoBuffers:pianoBuffers.size,violinBuffers:violinBuffers.size,pedals:document.querySelectorAll('#score g.pedal').length,
    duration:endMs(),pdfEnabled:!$('downloadPdf').disabled,
    firstNotes:notes.slice(0,4).map(n=>({p:n.p,t:n.t,d:n.d,lh:n.lh,instrument:n.instrument}))}));
   assert.equal(result.log,'');assert.equal(result.pdfEnabled,true);
   await page.click('#play');
   const sounding=await page.evaluate(()=>playing.oscs.length);
   assert(sounding>0);await page.click('#stop');
   if(result.piece==='winter_morning') assert(result.firstNotes[1].d<3000);
   report.pages.push(result);
   if(i<2){
    for(const [id,ext] of [['downloadXml','.musicxml'],['downloadPdf','.pdf'],['downloadAudio','.wav']]){
     const downloaded=page.waitForEvent('download',{predicate:d=>d.suggestedFilename().endsWith(ext)});
     await page.click('#'+id);
     const file=await downloaded;
     const target=path.join(out,file.suggestedFilename());await file.saveAs(target);
     const bytes=fs.readFileSync(target);
     if(ext==='.musicxml') assert.equal(bytes.toString(),await page.evaluate(()=>cur.xml));
     if(ext==='.pdf') assert.equal(bytes.subarray(0,5).toString(),'%PDF-');
     const entry={name:file.suggestedFilename(),bytes:bytes.length};
     if(ext==='.wav'){
      assert.equal(bytes.subarray(0,4).toString(),'RIFF');let peak=0,sum=0;
      for(let j=44;j<bytes.length;j+=2){const x=bytes.readInt16LE(j)/32768;peak=Math.max(peak,Math.abs(x));sum+=x*x;}
      entry.peak=peak;entry.rms=Math.sqrt(sum/((bytes.length-44)/2));assert(entry.rms>.005);assert(entry.peak<.99);
     }
     report.downloads.push(entry);
    }
    if(i===1){
     await page.uncheck('#violin');await page.click('#play');
     assert.equal(await page.evaluate(()=>playing.oscs.length),result.instruments.piano);
     await page.click('#stop');await page.check('#violin');
    }
    await page.screenshot({path:path.join(out,i?'duet-desktop.png':'solo-desktop.png'),fullPage:true});
   }
  }
  for(const piece of ['lingering_light','lingering_light_duet']){
   await page.goto(url+'/'+piece+'/');await page.waitForFunction(()=>pianoReady&&notes.length>0);
   assert.equal(await page.evaluate(()=>cur.piece),piece);
  }
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(700);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'duet-mobile.png'),fullPage:true});
  assert.equal(report.errors.length,0);
  fs.writeFileSync(path.join(out,'browser-check.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
 }finally{await browser.close();server.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
