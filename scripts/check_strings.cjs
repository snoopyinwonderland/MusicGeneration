const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {createRequire}=require('node:module');
const {chromium}=createRequire(path.join(process.env.MUSICOMP_ROOT||'K:/Music Composition','package.json'))('playwright-core');
const root=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
(async()=>{
 const server=http.createServer((req,res)=>{let f=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));if(f!==root&&!f.startsWith(root+path.sep))return res.writeHead(403).end();if(fs.existsSync(f)&&fs.statSync(f).isDirectory())f=path.join(f,'index.html');if(!fs.existsSync(f))return res.writeHead(404).end();res.setHeader('Content-Type',f.endsWith('.json')?'application/json':'text/html; charset=utf-8');res.end(fs.readFileSync(f));});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||undefined});const report={pages:[],downloads:[],errors:[]};
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.on('pageerror',e=>report.errors.push(e.message));
 const catalog=JSON.parse(fs.readFileSync(path.join(root,'catalog.json'),'utf8'));
 for(const item of catalog){
  await page.goto('http://127.0.0.1:'+server.address().port+'/'+item.url);await page.waitForFunction(()=>pianoReady&&notes.length>0);
  const result=await page.evaluate(()=>({piece:cur.piece,log:tk.getLog(),instruments:cur.instrumentation.instruments,label:ensembleLabel(cur),counts:notes.reduce((a,n)=>(a[n.instrument]=(a[n.instrument]||0)+1,a),{}),duration:endMs(),banks:{piano:pianoBuffers.size,violin:violinBuffers.size,viola:violaBuffers.size,cello:celloBuffers.size}}));
  assert.equal(result.log,'');assert(result.duration>0);
  for(const name of result.instruments)assert(result.banks[name]>0);
  for(const name of ['violin','viola','cello'])assert.equal(await page.locator('#'+name+'Control').isVisible(),result.instruments.includes(name));
  const sig=await page.evaluate(()=>JSON.stringify(notes.map(n=>[n.id,n.t,n.d,n.p,n.instrument])));
  await page.click('#play');assert(await page.evaluate(()=>playing.oscs.length>0));
  await page.click('#romanAnalysis');assert.equal(await page.evaluate(()=>JSON.stringify(notes.map(n=>[n.id,n.t,n.d,n.p,n.instrument]))),sig);
  assert(await page.evaluate(()=>!!playing));assert.deepEqual(await page.evaluate(()=>[...document.querySelectorAll('#score g.harm text')].map(n=>n.textContent)),await page.evaluate(()=>cur.harmony.map(h=>h.display)));
  await page.click('#stop');await page.click('#chordSymbols');
  const strings=result.instruments.filter(i=>i!=='piano');
  for(const name of strings){await page.uncheck('#'+name);await page.click('#play');assert.equal(await page.evaluate(()=>playing.oscs.length),Object.entries(result.counts).filter(([i])=>i!==name).reduce((a,[,n])=>a+n,0));await page.click('#stop');await page.check('#'+name);}
  const files=[['downloadXml','.musicxml']];if(await page.locator('#downloadPdf').isEnabled())files.push(['downloadPdf','.pdf']);files.push(['downloadAudio','.wav']);
  for(const [id,ext] of files){const pending=page.waitForEvent('download',{predicate:d=>d.suggestedFilename().endsWith(ext),timeout:60000});let notice;
   if(ext==='.wav')notice=page.waitForEvent('download',{predicate:d=>d.suggestedFilename().endsWith('.txt'),timeout:60000});
   await page.click('#'+id);const d=await pending;const f=path.join(out,item.piece+ext);await d.saveAs(f);if(notice)await(await notice).saveAs(path.join(out,item.piece+'-출처.txt'));
   const bytes=fs.readFileSync(f);const entry={piece:item.piece,ext,bytes:bytes.length};
   if(ext==='.musicxml')assert.equal(bytes.toString(),await page.evaluate(()=>cur.xml));
   if(ext==='.pdf')assert.equal(bytes.subarray(0,5).toString(),'%PDF-');
   if(ext==='.wav'){let peak=0,sum=0;for(let j=44;j<bytes.length;j+=2){const x=bytes.readInt16LE(j)/32768;peak=Math.max(peak,Math.abs(x));sum+=x*x;}entry.peak=peak;entry.rms=Math.sqrt(sum/((bytes.length-44)/2));assert(entry.rms>.005);assert(peak<.99);}
   report.downloads.push(entry);
  }
  // Isolate the new string samples: a healthy piano mix must not hide a silent string bank.
  if(strings.length){await page.uncheck('#rh');await page.uncheck('#lh');await page.click('#play');assert.equal(await page.evaluate(()=>playing.oscs.length),strings.reduce((n,i)=>n+result.counts[i],0));await page.click('#stop');
   result.stringAudio=await page.evaluate(async()=>{const audio=new OfflineAudioContext(1,44100*3,44100);for(const n of notes.filter(n=>audible(n)&&n.t<2500))sampleTone(audio,n.t/1000,Math.min(n.d/1000,2),n);const b=await audio.startRendering();let peak=0,sum=0;for(const x of b.getChannelData(0)){peak=Math.max(peak,Math.abs(x));sum+=x*x;}return{peak,rms:Math.sqrt(sum/b.length)};});assert(result.stringAudio.rms>.005);assert(result.stringAudio.peak<.99);await page.check('#rh');await page.check('#lh');}
  await page.screenshot({path:path.join(out,item.piece+'-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(250);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(out,item.piece+'-mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1000});
  report.pages.push(result);
 }
 assert.equal(report.errors.length,0);fs.writeFileSync(path.join(out,'browser-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
