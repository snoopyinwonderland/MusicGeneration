// P1 has no pedal or dynamics variation: identical preview mix for fair comparisons.
const $=id=>document.getElementById(id), buffers=new Map(), checked=new Set();
let audio=null, ready=false, chosen=null, timer=null, nodes=[], generation=0;
const stage=DATA.stage||'motif',isPhrase=stage==='phrase';
const storageKey='musicanote-'+stage+'-choice:'+DATA.set_id;
$('stage-title').textContent=isPhrase?'2단계 · 프레이즈를 골라 주세요':'1단계 · 주제를 골라 주세요';
$('stage-help').textContent=isPhrase?'선택한 모티프를 발전시킨 8마디 후보입니다. 구조와 쉼, 반주의 차이를 들어 보세요. 페달은 쓰지 않습니다.':'각 악보는 1마디 모티프 + 1마디 기본 응답입니다. 같은 빠르기·블록 반주·피아노 음원으로 비교합니다. 페달은 쓰지 않습니다.';
$('meter-badge').textContent=DATA.design.basics.meter+' 박자 · '+(isPhrase?'선택 모티프 '+DATA.selected_motif:'모티프 후보');
const rows=DATA.candidates, byId=new Map(rows.map(r=>[r.id,r]));
const kindNames={generator:'리듬·윤곽 생성기',composer:'작곡자가 작성',import:'가져온 모티프'};
const qpm=DATA.design.basics.tempo, seconds=q=>q*60/qpm;
$('design').textContent=`${DATA.design.title||'모티프 설계'} · ${DATA.design.basics.key} ${DATA.design.basics.mode==='minor'?'단조':'장조'} · ${DATA.design.basics.meter} 박자 · ♩=${qpm} · 후보 ${rows.length}개 (요청 ${DATA.requested}개)`;
if(DATA.design.impression?.mood)$('design').textContent+=' · '+DATA.design.impression.mood;
$('diagnostics').textContent=JSON.stringify(DATA.diagnostics,null,2);
function text(tag,value,parent){const e=document.createElement(tag);e.textContent=value;parent.append(e);return e;}
function remember(){try{localStorage.setItem(storageKey,JSON.stringify({chosen,reason:$('reason').value}));}catch{$('status').textContent='브라우저 저장을 사용할 수 없습니다. 선택 내보내기를 이용하세요.';}}
function select(id){
 chosen=id;$('selected').textContent=`선택: ${id} · ${byId.get(id).features.contour_label}`;
 $('export').disabled=false;document.querySelectorAll('article').forEach(e=>e.classList.toggle('chosen',e.dataset.id===id));remember();
}
function button(label,fn,parent){const e=text('button',label,parent);e.addEventListener('click',fn);return e;}
for(const row of rows){
 const card=document.createElement('article');card.dataset.id=row.id;$('candidates').append(card);
 text('h2',`${row.id} · ${row.features.contour_label}`,card);
 text('p',`출처: ${kindNames[row.origin.kind]||row.origin.kind}`,card).className='muted';
 const score=document.createElement('div');score.className='score';score.id='score-'+row.id;card.append(score);
 const dl=document.createElement('dl');card.append(dl);
 const f=row.features;
 for(const [k,v] of [['음 수 / 밀도',`${f.notes}음 / ${f.density}음/박`],['음역',f.range.join('–')],['최대 도약',`${f.largest_leap}반음`],['당김음 / 쉼',`${f.syncopated?'있음':'없음'} / ${f.rest_quarters}박`],['화성 함의',f.harmonic_implication]]){text('dt',k,dl);text('dd',v,dl);}
 const actions=document.createElement('div');actions.className='actions';card.append(actions);
 button('재생',()=>play([row.id],false),actions).className='play';
 button('반복 재생',()=>play([row.id],true),actions).className='play';
 button('이걸로',()=>select(row.id),actions).disabled=DATA.status==='stopped';
 const label=document.createElement('label');const box=document.createElement('input');box.type='checkbox';box.dataset.id=row.id;
 box.addEventListener('change',()=>{if(box.checked&&checked.size>=2){box.checked=false;$('status').textContent='번갈아 들을 후보는 두 개만 고르세요.';return;}box.checked?checked.add(row.id):checked.delete(row.id);$('alternate').disabled=!ready||checked.size!==2;});
 label.append(box,document.createTextNode(' 비교에 넣기'));card.append(label);
 if(row.observations){const d=document.createElement('details');card.append(d);text('summary','프레이즈 기능과 긴장 곡선',d);for(const finding of row.observations.findings)text('p',finding.message,d);text('pre',JSON.stringify(row.observations.curve,null,2),d);}
 if(row.preview.warnings.length){const d=document.createElement('details');card.append(d);text('summary','참고할 검사 관찰',d);text('p',row.preview.warnings.join(' / '),d);}
}
document.querySelectorAll('.play').forEach(e=>e.disabled=true);
$('reason').addEventListener('input',remember);
try{const old=JSON.parse(localStorage.getItem(storageKey)||'null');if(old&&byId.has(old.chosen)&&DATA.status!=='stopped'){$('reason').value=typeof old.reason==='string'?old.reason.slice(0,1000):'';select(old.chosen);}}catch{}
$('export').addEventListener('click',()=>{
 if(!chosen)return;
 const payload={format:'musicanote-selection',version:1,stage,set_id:DATA.set_id,design_sha256:DATA.design_sha256,shown:rows.map(r=>r.id),chosen,reason:$('reason').value};
 const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download=stage+'-selection.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
function stop(){generation++;clearTimeout(timer);timer=null;for(const n of nodes){try{n.stop();}catch{}}nodes=[];document.querySelectorAll('article').forEach(e=>e.removeAttribute('aria-current'));}
async function play(ids,loop){
 stop();const token=generation;if(!ready)return;
 audio??=new AudioContext();await audio.resume();if(token!==generation)return;
 let index=0;
 function next(){
  if(token!==generation)return;
  const id=ids[index],row=byId.get(id);$('status').textContent=`재생 중: ${id}${loop?' · 반복':''}`;
  document.querySelectorAll('article').forEach(e=>e.toggleAttribute('aria-current',e.dataset.id===id));
  nodes=[];const start=audio.currentTime+.06;
  for(const n of row.preview.notes)for(const pitch of n.p){
   const key=[...buffers.keys()].reduce((a,b)=>Math.abs(b-pitch)<Math.abs(a-pitch)?b:a);
   const src=audio.createBufferSource(),gain=audio.createGain();src.buffer=buffers.get(key);src.playbackRate.value=2**((pitch-key)/12);
   const on=start+seconds(n.q),end=on+seconds(n.d),level=n.hand==='rh'?.2:.1;
   gain.gain.setValueAtTime(level,on);gain.gain.setValueAtTime(level,end);gain.gain.exponentialRampToValueAtTime(.00001,end+.16);
   src.connect(gain).connect(audio.destination);src.start(on);src.stop(end+.18);nodes.push(src);
  }
  timer=setTimeout(()=>{index++;if(index<ids.length)next();else if(loop){index=0;next();}else{stop();$('status').textContent='재생 완료';}},(seconds(row.preview.quarters)+.4)*1000);
 }
 next();
}
$('stop').onclick=()=>{stop();$('status').textContent='정지됨';};
$('all').onclick=()=>play(rows.map(r=>r.id),false);
$('alternate').onclick=()=>{if(checked.size===2)play([...checked],true);};
window.addEventListener('pagehide',stop);
async function init(){
 if(typeof verovio==='undefined')throw Error('악보 엔진을 불러오지 못했습니다');
 const began=Date.now();while(typeof verovio.module?._vrvToolkit_constructor!=='function'){
  if(Date.now()-began>20000)throw Error('악보 엔진 준비 시간 초과');await new Promise(r=>setTimeout(r,50));
 }
 for(const row of rows){
  const tk=new verovio.toolkit();tk.setOptions({pageWidth:isPhrase?1000:1500,pageHeight:isPhrase?8000:900,scale:40,svgViewBox:true,breaks:isPhrase?'auto':'none',adjustPageHeight:true,header:'none',footer:'none',pageMarginLeft:20,pageMarginRight:20});
  if(!tk.loadData(row.preview.xml)||tk.getLog())throw Error(`${row.id}: ${tk.getLog()||'악보 오류'}`);
  $('score-'+row.id).innerHTML=tk.renderToSVG(1);tk.destroy();
 }
 const decoder=new OfflineAudioContext(1,1,44100);
 await Promise.all(Object.entries(BANK.notes).map(async([key,url])=>{
  const bytes=Uint8Array.from(atob(url.split(',')[1]),c=>c.charCodeAt(0));const buffer=await decoder.decodeAudioData(bytes.buffer);let peak=0;
  for(let c=0;c<buffer.numberOfChannels;c++)for(const x of buffer.getChannelData(c))peak=Math.max(peak,Math.abs(x));
  if(!peak)throw Error('무음 피아노 샘플');
  for(let c=0;c<buffer.numberOfChannels;c++){const a=buffer.getChannelData(c);for(let i=0;i<a.length;i++)a[i]*=.8/peak;}
  buffers.set(Number(key),buffer);
 }));
 ready=true;$('all').disabled=!rows.length;$('alternate').disabled=checked.size!==2;document.querySelectorAll('.play').forEach(e=>e.disabled=false);
 $('status').textContent=DATA.status==='ready'?'재생 준비됨':DATA.status==='stopped'?'다양성 조건 미달: 생성 중단. 진단을 확인하세요.':'요청 수보다 적은 후보입니다. 생성 진단을 확인하세요.';
}
init().catch(e=>{$('status').textContent=e.message;console.error(e);});
