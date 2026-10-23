// Vector score PDF from the same MusicXML used by the listening page.
// Dependencies resolve from MUSICOMP_ROOT; no cloud rendering or XML rewriting.
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const dependencyRoot = path.resolve(process.env.MUSICOMP_ROOT || path.join(__dirname,'../../Music Composition'));
const requireDependency = createRequire(path.join(dependencyRoot,'package.json'));
const {chromium} = requireDependency('playwright-core');
const runtime = fs.readFileSync(path.join(dependencyRoot,'node_modules/verovio/dist/verovio-toolkit-wasm.js'));
const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function main(){
  const dirs=process.argv.slice(2).map(x=>path.resolve(x));
  if(!dirs.length) throw Error('사용법: node scripts/render_score_pdf.cjs <버전 폴더> ...');
  const options={headless:true};
  if(process.env.CHROME_PATH) options.executablePath=process.env.CHROME_PATH;
  const browser=await chromium.launch(options);
  try{
    for(const dir of dirs){
      const design=JSON.parse(fs.readFileSync(path.join(dir,'design.json'),'utf8'));
      const info=JSON.parse(fs.readFileSync(path.join(dir,'version.json'),'utf8'));
      const xml=fs.readFileSync(path.join(dir,'piece.musicxml'),'utf8');
      const page=await browser.newPage();
      try{
        await page.route('https://score.local/verovio.js',route=>route.fulfill({body:runtime,contentType:'text/javascript'}));
        await page.setContent('<!doctype html><html lang="ko"><head><meta charset="utf-8"><script src="https://score.local/verovio.js"></script></head><body></body></html>');
        await page.waitForFunction(()=>typeof verovio.module._vrvToolkit_constructor==='function');
        const result=await page.evaluate(xml=>{
          const renderer=new verovio.toolkit();
          renderer.setOptions({pageWidth:1780,pageHeight:2490,scale:40,svgViewBox:true,
            pageMarginTop:30,pageMarginBottom:30,pageMarginLeft:0,pageMarginRight:0,
            header:'none',footer:'none',adjustPageHeight:false,breaks:'auto'});
          if(!renderer.loadData(xml)) throw Error('MusicXML 렌더링 실패');
          const pages=Array.from({length:renderer.getPageCount()},(_,i)=>renderer.renderToSVG(i+1));
          return {pages,log:renderer.getLog()};
        },xml);
        if(result.log) throw Error(result.log);
        const ensemble=({violin_piano:'바이올린 · 피아노',viola_piano:'비올라 · 피아노',cello_piano:'첼로 · 피아노'})[info.ensemble] || '피아노 솔로';
        const composer=design.credits?.composer ? ` · 작곡 ${design.credits.composer}` : '';
        await page.addStyleTag({content:`@page{size:A4;margin:0}*{box-sizing:border-box}body{margin:0;color:#172d2b;font-family:'Malgun Gothic',sans-serif}.sheet{width:210mm;height:297mm;padding:12mm 16mm 10mm;break-after:page}.sheet:last-child{break-after:auto}header{height:19mm;display:flex;justify-content:space-between;align-items:start;border-bottom:.2mm solid #c7cfc6;margin-bottom:2mm}h1{font-size:17pt;margin:0 0 2mm}p{font-size:8pt;margin:0;color:#53625d}.brand{font:8pt Georgia,serif;letter-spacing:.4mm;text-align:right;padding-top:2mm}.music{height:249mm}.music svg{width:178mm;height:249mm;display:block}footer{height:5mm;font-size:8pt;color:#53625d;display:flex;justify-content:space-between}`});
        await page.evaluate(({pages,title,ensemble,composer,version,escapeStrings})=>{
          document.title=title+' | MUSICANOTE Virtual Composer';
          document.body.innerHTML=pages.map((svg,i)=>`<section class="sheet"><header><div><h1>${escapeStrings.title}</h1><p>${escapeStrings.subtitle}</p></div><div class="brand">MUSICANOTE<br>Virtual Composer</div></header><div class="music">${svg}</div><footer><span>${escapeStrings.version} · 검수용 악보</span><span>${i+1} / ${pages.length}</span></footer></section>`).join('');
        },{...result,title:design.title,ensemble,composer,version:info.version,escapeStrings:{title:esc(design.title),subtitle:esc(ensemble+composer),version:esc(info.version)}});
        await page.evaluate(()=>document.fonts.ready);
        const target=path.join(dir,'piece.pdf');
        await page.pdf({path:target,format:'A4',printBackground:true,preferCSSPageSize:true});
        console.log(JSON.stringify({path:target,pages:result.pages.length,bytes:fs.statSync(target).size}));
      }finally{ await page.close(); }
    }
  }finally{ await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
