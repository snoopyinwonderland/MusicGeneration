const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const dependencyRoot = process.env.MUSICOMP_ROOT || path.resolve(root, '../Music Composition');
const {chromium} = createRequire(path.join(dependencyRoot, 'package.json'))('playwright-core');
const out = path.join(root, 'output/motif-import');
fs.mkdirSync(out, {recursive:true});
const example = `<?xml version="1.0"?><score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list><part id="P1">
<measure number="0" implicit="yes"><attributes><divisions>6</divisions><key><fifths>0</fifths></key><time><beats>3</beats><beat-type>4</beat-type></time><staves>2</staves><clef number="1"><sign>G</sign><line>2</line></clef><clef number="2"><sign>F</sign><line>4</line></clef></attributes>
<note><pitch><step>F</step><alter>1</alter><octave>4</octave></pitch><duration>3</duration><voice>1</voice><type>eighth</type><staff>1</staff></note></measure>
<measure number="1"><note><rest/><duration>3</duration><voice>1</voice><type>eighth</type><staff>1</staff></note>
<note><pitch><step>G</step><octave>4</octave></pitch><duration>3</duration><voice>1</voice><type>eighth</type><staff>1</staff></note>
<note><pitch><step>A</step><octave>4</octave></pitch><duration>12</duration><tie type="start"/><voice>1</voice><type>half</type><staff>1</staff></note>
<backup><duration>18</duration></backup><note><pitch><step>C</step><octave>3</octave></pitch><duration>18</duration><voice>1</voice><type>half</type><dot/><staff>2</staff></note></measure>
<measure number="2"><note><pitch><step>A</step><octave>4</octave></pitch><duration>6</duration><tie type="stop"/><voice>1</voice><type>quarter</type><staff>1</staff></note>
<note><pitch><step>B</step><alter>-1</alter><octave>4</octave></pitch><duration>2</duration><voice>1</voice><type>eighth</type><time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification><staff>1</staff></note>
<note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type><time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification><staff>1</staff></note>
<note><rest/><duration>6</duration><voice>1</voice><type>quarter</type><staff>1</staff></note></measure></part></score-partwise>`;
async function main() {
 const server = http.createServer((req,res) => {
  const publicRoot = path.join(root, 'docs/listen');
  const file = path.resolve(publicRoot, '.' + decodeURIComponent(new URL(req.url,'http://localhost').pathname));
  if (!file.startsWith(publicRoot + path.sep)) return res.writeHead(403).end();
  if (!fs.existsSync(file)) return res.writeHead(404).end();
  res.setHeader('Content-Type',file.endsWith('.html')?'text/html; charset=utf-8':'application/json');
  res.end(fs.readFileSync(file));
 });
 await new Promise(r => server.listen(0,'127.0.0.1',r));
 const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH});
 const report = {errors:[]};
 try {
  const context = await browser.newContext({viewport:{width:1440,height:1100},permissions:['clipboard-read','clipboard-write'],acceptDownloads:true});
  const page = await context.newPage();
  page.on('pageerror', e => report.errors.push(e.message));
  await page.route('https://cdn.jsdelivr.net/**',r => r.fulfill({body:fs.readFileSync(path.join(dependencyRoot,'node_modules/verovio/dist/verovio-toolkit-wasm.js')),contentType:'text/javascript'}));
  await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
  await page.waitForFunction(() => pianoReady && notes.length > 0);
  const placement = await page.evaluate(() => {
    const mei = new DOMParser().parseFromString(tk.getMEI(),'application/xml');
    return [...mei.querySelectorAll('harm')].map(h => [h.getAttribute('place'),h.getAttribute('staff')]);
  });
  assert(placement.length > 0 && placement.every(([p,s]) => p === 'below' && s === '2'));
  const musical = await page.evaluate(() => notes.map(n => [n.p,n.t,n.d,n.instrument]));
  await page.selectOption('#harmonyPlacement','original');
  assert.deepEqual(await page.evaluate(() => notes.map(n => [n.p,n.t,n.d,n.instrument])),musical);
  await page.selectOption('#harmonyPlacement','below');
  await page.click('#romanAnalysis');
  await page.screenshot({path:path.join(out,'harmony-below.png'),fullPage:true});
  await page.locator('#motifStudio summary').click();
  await page.click('#motifCurrent');
  assert.equal(await page.locator('#motifVoice option').count(),3);
  assert(await page.locator('#motifScore g.note[id^="motif-note-"]').count() > 0);
  // Select actual notes with the mouse, not just controls.
  await page.locator('#motifScore #motif-note-1').scrollIntoViewIfNeeded();
  await page.locator('#motifScore #motif-note-1').click();
  const next = await page.evaluate(() => {
    const score = MotifTools.parseMusicXML(cur.xml);
    return score.voices[0].events[3].ids[0];
  });
  await page.locator('#motifScore [id="'+next+'"]').click();
  await page.click('#motifExtract');
  let clip = JSON.parse(await page.inputValue('#motifText'));
  assert.deepEqual(clip.events.map(e => e.pitches[0]),['F#4','A4','B4','A4']);
  assert.deepEqual(clip.events.map(e => e.duration),['1','1/2','1/2','1']);
  await page.click('#motifListen');
  assert.equal(await page.isDisabled('#motifSilence'),false);
  await page.click('#motifSilence');
  await page.click('#motifCopy');
  assert.equal(JSON.parse(await page.evaluate(() => navigator.clipboard.readText())).events.length,4);
  await page.fill('#motifText','');
  await page.click('#motifPaste');
  await page.waitForFunction(() => document.querySelector('#motifText').value.length > 0);
  assert.equal(JSON.parse(await page.inputValue('#motifText')).events.length,4);
  await page.evaluate(() => { window.readClip = navigator.clipboard.readText; navigator.clipboard.readText = async () => { throw Error('denied'); }; });
  await page.click('#motifPaste');
  await page.waitForFunction(() => document.querySelector('#motifStatus').textContent.includes('Ctrl+V'));
  await page.evaluate(() => { navigator.clipboard.readText = window.readClip; });
  const download = page.waitForEvent('download');
  await page.click('#motifSave');
  await (await download).saveAs(path.join(out,'a.motif.json'));
  const withSource = JSON.parse(fs.readFileSync(path.join(out,'a.motif.json')));
  assert.equal(withSource.source.staff,'1');
  assert.equal(withSource.source.voice,'1');
  await page.locator('#motifFile').setInputFiles({name:'timing.musicxml',mimeType:'application/xml',buffer:Buffer.from(example)});
  await page.waitForFunction(() => document.querySelector('#motifStart option')?.textContent.startsWith('0마디'));
  await page.selectOption('#motifEnd','7');
  await page.click('#motifExtract');
  clip = JSON.parse(await page.inputValue('#motifText'));
  assert.deepEqual(clip.events.map(e => e.duration),['1/2','1/2','1/2','3','1/3','2/3','1']);
  assert.deepEqual(clip.events.map(e => e.pitches),[['F#4'],[],['G4'],['A4'],['Bb4'],['C5'],[]]);
  fs.writeFileSync(path.join(out,'timing.motif.json'),JSON.stringify(clip,null,2));
  await page.selectOption('#motifStart','4');
  await page.selectOption('#motifEnd','4');
  await page.click('#motifExtract');
  assert.match(await page.textContent('#motifStatus'),/구간 밖 붙임줄/);
  const invalid = await page.evaluate(xml => {
    const s = MotifTools.parseMusicXML(xml);
    try { MotifTools.clipRange(s,s.voices[0],3,1); return false; } catch { return true; }
  },example);
  assert(invalid);
  await page.fill('#motifText','<not-a-score/>');
  await page.click('#motifLoadText');
  assert.match(await page.textContent('#motifStatus'),/score-partwise/);
  await page.locator('#motifFile').setInputFiles(path.join(out,'a.motif.json'));
  await page.waitForFunction(() => document.querySelector('#motifStatus').textContent.includes('4개 사건'));
  await page.screenshot({path:path.join(out,'motif-studio.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(500);
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({path:path.join(out,'motif-mobile.png'),fullPage:true});
  assert.deepEqual(report.errors,[]);
  report.status='passed';
  report.checks=['harmony below/original with same notes','actual note selection','clipboard copy/paste','JSON download/open','part/staff/voice isolation','pickup/rest/tie/triplets','boundary tie crop','invalid inputs','mobile width'];
  fs.writeFileSync(path.join(out,'browser-check.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
 } finally { await browser.close(); server.close(); }
}
main().catch(e => { console.error(e); process.exitCode=1; });
