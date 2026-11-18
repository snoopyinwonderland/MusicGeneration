import {mount} from './motif-input/motif-input.js';

(() => {
  const $=id=>document.getElementById(id);
  const buttons=['auto','complete','compose','arrange','original','preview'];
  let engine,piece,sourceClip,activeNotes=[],busy=false;
  const status=(text,error=false)=>{ $('status').textContent=text;$('status').classList.toggle('error',error); };
  const link=(label,href)=>{const a=document.createElement('a');a.textContent=label;a.href=href;return a};
  function stop(){WorkshopAudio.stop();$('stop').disabled=true}
  function readClip(){
    const raw=$('tokens').value.trim();
    if(!raw)throw Error('음을 하나 이상 입력하거나 자동 모티프 생성을 눌러 주세요.');
    let clip;
    if(raw.startsWith('{'))clip=JSON.parse(raw);
    else if(sourceClip && raw===notation(sourceClip))clip=sourceClip;
    else{
      const events=raw.split(/[\s,]+/).map(token=>{
        const match=token.match(/^([a-gA-G](?:#{1,2}|b{1,2})?-?\d|쉼|R)(?::(\d+(?:\/\d+)?))?$/);
        if(!match)throw Error('음을 C4:1, 반음은 F#4:1/2, 쉼은 쉼:1처럼 입력하세요.');
        const pitch=match[1][0].toUpperCase()+match[1].slice(1);
        return {duration:match[2]||'1',pitches:['쉼','R'].includes(pitch)?[]:[pitch]};
      });
      clip={format:'musicanote-motif',version:1,name:'나의 모티프',source:{kind:'user'},events};
    }
    MotifTools.validate(clip);
    if(clip.events.some(e=>e.pitches.length>1))throw Error('한 성부의 선율을 입력하세요.');
    return clip;
  }
  function notation(c){return c.events.map(e=>(e.pitches[0]||'쉼')+':'+e.duration).join(' ')}
  function setClip(c){sourceClip=c;$('tokens').value=notation(c);editor.replace(c)}
  function settings(){return {title:$('title').value,key:$('keySpelling').value,meter:$('meter').value,tempo:Number($('tempo').value),bars:Number($('bars').value)}}
  async function json(url,data){
    const res=await fetch(url,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{cache:'no-store'});
    if(!res.ok){const problem=await res.json().catch(()=>({}));throw Error(problem.error||'작곡 서버에 연결할 수 없습니다.')}
    return res.json();
  }
  async function run(task){
    if(busy)return;busy=true;stop();$('motifEditor').inert=true;
    const controls=[...document.querySelectorAll('.controls button,.controls input,.controls select,.controls textarea'),...buttons.map($)];
    for(const el of controls)el.disabled=true;
    try{await task()}catch(e){status(e.message,true)}
    finally{busy=false;$('motifEditor').inert=false;for(const el of controls)el.disabled=false}
  }
  function drawScore(xml){
    if(!engine){try{engine=new verovio.toolkit()}catch{throw Error('악보를 준비하고 있습니다. 잠시 후 다시 눌러 주세요.')}}
    engine.setOptions({pageWidth:1900,pageHeight:2700,scale:40,svgViewBox:true,breaks:'auto',adjustPageHeight:true,header:'none',footer:'none'});
    if(!engine.loadData(xml))throw Error('악보를 표시할 수 없습니다.');
    $('score').innerHTML=Array.from({length:engine.getPageCount()},(_,i)=>engine.renderToSVG(i+1)).join('');
  }
  function render(xml){
    drawScore(xml);
    activeNotes=WorkshopAudio.events(engine,xml);
    $('play').disabled=!activeNotes.length;
  }
  function clear(){
    $('nativePane').hidden=true;
    stop();piece=null;activeNotes=[];$('play').disabled=true;
    $('arranger').hidden=$('download').hidden=$('print').hidden=true;
    $('score').hidden=true;$('score').replaceChildren();$('scoreKind').textContent='모티프 재생';$('scoreTitle').textContent='나의 모티프';
    history.replaceState(null,'','compose.html');
    status('입력 악보를 보거나 이 모티프로 곡을 만들어 주세요.');
  }
  function preview(){
    const clip=readClip();editor.replace(clip);clear();
    editor.configure($('meter').value,$('keySpelling').value);
    activeNotes=editor.performance(Number($('tempo').value));
    $('play').disabled=!activeNotes.length;
    status(clip.events.length+'개의 음·쉼 · '+MotifTools.validate(clip)+'박');
  }
  async function showScore(work,kind){
    let xmlPath='compositions/'+work.id+'/melody.musicxml';
    if(kind!=='melody'){
      if(!Array.from($('instrument').options).some(o=>o.value===kind))throw Error('알 수 없는 편성입니다.');
      $('instrument').value=kind;
      status('같은 선율과 화성으로 편곡 악보를 준비하고 있습니다…');
      xmlPath=(await json('api/arrange',{id:work.id,instrument:kind})).xml;
    }
    const r=await fetch(xmlPath);if(!r.ok)throw Error('저장된 악보를 열 수 없습니다.');
    const xml=await r.text();$('score').hidden=false;render(xml);
    piece=work;setClip(work.clip);
    for(const k of ['title','meter','tempo','bars'])$(k).value=work[k];
    KeyPicker.restore(work.key);
    $('development').value=work.development||'classic';
    editor.configure(work.meter,work.key);$('scoreTitle').textContent=work.title;
    $('scoreKind').textContent=kind==='melody'?'원 선율 + 화성':$('instrument').selectedOptions[0].text;
    $('download').href=xmlPath;$('download').hidden=$('print').hidden=$('arranger').hidden=false;
    const url='compose.html?piece='+work.id+'&voice='+kind;
    history.replaceState(null,'',url);$('permalink').href=url;
    status(work.key+' · '+work.meter+' · ♩ '+work.tempo+' · '+work.bars+'마디');
  }
  async function library(){
    const {works}=await json('api/compositions');
    $('works').replaceChildren(...works.map(w=>link(w.title+' · '+w.bars+'마디', 'compose.html?piece='+w.id)));
    if(!works.length)$('works').textContent='아직 저장한 곡이 없습니다.';
  }

  const editor=mount($('motifEditor'),{
    onChange(clip,meter){
      sourceClip=clip;$('meter').value=meter;$('tokens').value=notation(clip);clear();
      activeNotes=editor.performance(Number($('tempo').value));
      $('play').disabled=!activeNotes.length;
      status(clip.events.length?'모티프를 수정했습니다.':'건반을 눌러 모티프를 시작하세요.');
    },
    preview(){
      const notes=editor.performance(Number($('tempo').value));
      if(!notes.length){status('먼저 소리 나는 음을 입력하세요.');return}
      $('stop').disabled=false;
      WorkshopAudio.play(notes,stop).catch(e=>{stop();status(e.message,true)});
    },
    audition(midi){WorkshopAudio.play([{start:0,end:.35,pitch:midi,bank:'piano'}],()=>{}).catch(e=>status(e.message,true))},
    error(message){status(message,true)}
  });
  workshopImport(json,c=>{setClip(c);preview();status('선택 구간을 모티프로 가져왔습니다. '+(c.warnings||[]).join(' '))});
  $('tokens').oninput=()=>{sourceClip=null;clear();
    if(!$('tokens').value.trim()){editor.replace({format:'musicanote-motif',version:1,events:[]});return}
    try{preview()}catch(e){status(e.message+' 악보에는 마지막으로 읽은 입력을 표시합니다.',true)}
  };
  $('tokens').addEventListener('paste',event=>{
    const raw=event.clipboardData?.getData('text/plain')?.trim();
    if(!raw?.startsWith('{'))return;
    let clip;try{clip=JSON.parse(raw)}catch{return}
    if(clip?.format!=='musicanote-motif')return;
    event.preventDefault();
    try{
      MotifTools.validate(clip);
      if(clip.events.some(e=>e.pitches.length>1))throw Error('한 성부의 선율을 붙여넣으세요.');
      sourceClip=clip;$('tokens').value=raw;preview();
      status('모티프를 붙여넣었습니다. '+clip.events.length+'개 음·쉼 · '+MotifTools.validate(clip)+'박');
    }catch(e){status(e.message,true)}
  });
  for(const id of ['title','key','keySpelling','meter','tempo','bars'])$(id).onchange=()=>{
    clear();editor.configure($('meter').value,$('keySpelling').value);
    if($('tokens').value.trim())try{preview()}catch(e){status(e.message,true)}
  };
  $('randomRhythm').onclick=()=>run(async()=>{
    const clip=await json('api/rhythm',{clip:readClip()});setClip(clip);preview();
    status(clip.rhythm_variation.same_length?'음높이와 전체 길이를 유지해 새 리듬을 만들었습니다.':'새 리듬을 만들었습니다. 이 입력은 전체 길이도 함께 바뀝니다.');
  });
  $('preview').onclick=()=>run(()=>{preview();$('score').hidden=false;drawScore(editor.score())});
  for(const mode of ['auto','complete'])$(mode).onclick=()=>run(async()=>{
    const clip=mode==='complete'?readClip():null;
    const generated=await json('api/motif',{...settings(),mode,clip});
    setClip(generated);preview();
    status(mode==='auto'?'두 마디 모티프를 만들었습니다. 듣고 음을 수정할 수 있습니다.':'입력한 앞부분을 보존해 두 마디를 완성했습니다.');
  });
  $('compose').onclick=()=>run(async()=>{
    const clip=readClip();status('구절을 발전시키고 화성을 붙이고 있습니다…');
    const work=await json('api/compose',{...settings(),clip,development:$('development').value});await showScore(work,'melody');await library();
  });
  $('arrange').onclick=()=>run(()=>showScore(piece,$('instrument').value));
  async function openWorkbench(){
    const {url}=await json('api/workbench',{id:piece.id});
    if($('nativeFrame').src!==url)$('nativeFrame').src=url;
    $('nativeTab').href=url;$('nativePane').hidden=false;$('nativePane').scrollIntoView();
    const link=new URL(location.href);link.searchParams.set('workspace','arranger');
    history.replaceState(null,'',link);$('permalink').href=link.href;
  }
  $('openWorkbench').onclick=()=>run(openWorkbench);
  $('original').onclick=()=>run(()=>showScore(piece,'melody'));
  $('print').onclick=()=>window.print();
  $('play').onclick=async()=>{try{$('stop').disabled=false;await WorkshopAudio.play(activeNotes,stop)}catch(e){stop();status(e.message,true)}};
  $('stop').onclick=stop;window.addEventListener('pagehide',e=>{stop();if(!e.persisted)editor.destroy()});
  const params=new URLSearchParams(location.search);
  async function init(){
    await library();
    const id=params.get('piece');
    if(id){
      if(!/^[a-f0-9]{32}$/.test(id))throw Error('작품 주소를 확인하세요.');
      await showScore(await json('compositions/'+id+'/piece.json'),params.get('voice')||'melody');
      if(params.get('workspace')==='arranger')await openWorkbench();
    }else if(params.get('import')==='clip'){
      const raw=sessionStorage.getItem('workshop-input');
      if(!raw)throw Error('가져올 구간이 없습니다. 모티프 입력에서 구간을 선택해 주세요.');
      setClip(JSON.parse(raw));preview();sessionStorage.removeItem('workshop-input');
    }
  }
  let initialized=false;
  function ready(){
    if(initialized)return;
    try{engine=new verovio.toolkit();engine.getVersion()}catch{engine=null;return}
    initialized=true;run(init);
  }
  if(typeof verovio!=='undefined'){verovio.module.onRuntimeInitialized=ready;ready()}
  else status('악보 엔진을 불러오지 못했습니다.',true);
})();
