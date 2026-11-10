/* Local input UI. Reuses MotifTools for MusicXML timing and clip validation. */
(() => {
  const $=id=>document.getElementById(id), F=MotifTools.F;
  let clip=null, source=null, stream=null, engine=null, sourceEngine=null, pickEnd=false;
  let audio=null, nodes=[], timer=null, sampleBank=null, playbackToken=0;
  const buffers=new Map();
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  const status=(message,error=false)=>{$('inputStatus').textContent=message;$('inputStatus').classList.toggle('error',error);};
  const run=fn=>async()=>{try{await fn();}catch(e){status(e.message,true);}};
  const option=(v,t)=>{const o=document.createElement('option');o.value=v;o.textContent=t;return o;};
  function enable(value){for(const id of ['listenMotif','downloadMotif','saveRequest','downloadRequest'])$(id).disabled=!value;}
  function dirty(){ $('savedLink').hidden=true; $('saveStatus').textContent=clip?'조건을 정한 뒤 작곡 요청을 저장해 주세요.':'모티프를 먼저 입력해 주세요.'; }
  function stop(){playbackToken++;clearTimeout(timer);for(const n of nodes)try{n.stop();}catch{}nodes=[];$('stopMotif').disabled=true;}
  function invalidate(){stop();clip=null;enable(false);$('motifPreview').replaceChildren();dirty();}
  function getEngine(){if(!engine)throw Error('악보 엔진 준비 중입니다. 잠시 뒤 다시 눌러 주세요.');return engine;}
  function render(target,xml,renderer){
    renderer.setOptions({pageWidth:1500,pageHeight:60000,scale:40,svgViewBox:true,breaks:'auto',adjustPageHeight:true,header:'none',footer:'none'});
    if(!renderer.loadData(xml))throw Error('악보를 표시하지 못했습니다.');
    $(target).innerHTML=Array.from({length:renderer.getPageCount()},(_,i)=>renderer.renderToSVG(i+1)).join('');
  }
  function previewXML(value){
    const [b,u]=$('meter').value.split('/').map(Number), bar=b*4/u*24;
    let used=0, measure=1, xml='', row='';
    const close=()=>{xml+=`<measure number="${measure}">${measure===1?`<attributes><divisions>24</divisions><time><beats>${b}</beats><beat-type>${u}</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>`:''}${row}</measure>`;measure++;row='';used=0;};
    for(const e of value.events){
      const d=F.read(e.duration);let left=d.n*24/d.d, tied=false;
      while(left>0){const take=Math.min(left,bar-used), continues=left>take;
        let pitch='<rest/>';
        if(e.pitches.length){const [,step,acc='',oct]=e.pitches[0].match(/^([A-G])(#{1,2}|b{1,2})?(-?\d)$/);pitch=`<pitch><step>${step}</step><alter>${acc.includes('#')?acc.length:-acc.length}</alter><octave>${oct}</octave></pitch>`;}
        const ties=e.pitches.length?(tied?'<tie type="stop"/>':'')+(continues?'<tie type="start"/>':''):'';
        row+=`<note>${pitch}<duration>${take}</duration>${ties}</note>`;
        left-=take;used+=take;tied=true;if(used===bar)close();
      }
    }
    if(used){row+=`<note><rest/><duration>${bar-used}</duration></note>`;close();}
    return `<score-partwise version="4.0"><work><work-title>${esc(value.name||'모티프')}</work-title></work><part-list><score-part id="P1"><part-name>피아노</part-name></score-part></part-list><part id="P1">${xml}</part></score-partwise>`;
  }
  function accept(value){
    const total=MotifTools.validate(value);
    if(value.events.some(e=>e.pitches.length>1))throw Error('멜로디 성부의 단선율을 골라 주세요. 화음 입력은 아직 지원하지 않습니다.');
    // Render first, so an unavailable engine cannot leave a stale accepted input.
    render('motifPreview',previewXML(value),getEngine());
    clip=structuredClone(value);$('motifName').value=value.name||'나의 모티프';
    $('inputText').value=JSON.stringify(value,null,2);enable(true);dirty();
    status(`${clip.events.length}개 음·쉼 · 4분음표 ${total}개 길이. ${(clip.warnings||[]).join(' ')}`);
  }
  function selectRange(){
    const a=+$('rangeStart').value,z=+$('rangeEnd').value;
    for(const n of $('sourceScore').querySelectorAll('.chosen'))n.classList.remove('chosen');
    if(!stream||z<a)return;
    for(const e of stream.events.slice(a,z+1))for(const id of e.ids){const el=document.getElementById(id);if(el)el.classList.add('chosen');}
    status(`${z-a+1}개 음·쉼 선택. ‘선택 구간 가져오기’를 눌러 확정하세요.`);
  }
  function chooseVoice(){
    stream=source.voices[+$('voice').value];pickEnd=false;
    for(const id of ['rangeStart','rangeEnd'])$(id).replaceChildren(...stream.events.map((e,i)=>option(i,`${e.measure}마디 +${e.offset} · ${e.pitches.join('+')||'쉼'}`)));
    $('rangeEnd').value=String(stream.events.findLastIndex(e=>e.measureIndex===stream.events[0].measureIndex));selectRange();
  }
  async function read(text,filename){
    invalidate();source=null;$('xmlSelection').hidden=true;
    if(text.trimStart().startsWith('<')){
      const parsed=MotifTools.parseMusicXML(text,filename);getEngine();sourceEngine||=new verovio.toolkit();
      render('sourceScore',parsed.xml,sourceEngine);source=parsed;
      $('voice').replaceChildren(...parsed.voices.map((s,i)=>option(i,`${s.name} · 보표 ${s.staff} · 성부 ${s.voice}`)));
      $('xmlSelection').hidden=false;chooseVoice();
    }else{
      let value;
      try{value=JSON.parse(text);}catch{throw Error('모티프 JSON 형식을 확인해 주세요. 중괄호·따옴표·쉼표가 빠졌거나 불필요한 글자가 있을 수 있습니다.');}
      if(value.format==='musicanote-composition-request'){
        const p=value.preferences;
        $('composer').value=p.composer||'none';
        for(const id of ['prompt','key','meter','tempo','bars'])$(id).value=p[id];
        for(const id of ['secondary','modulation'])$(id).checked=!!p[id];
        $('augmentedSixth').checked=!!p.augmented_sixth;$('solo').checked=p.outputs.includes('piano_solo');accept(value.motif);
      }else accept(value);
    }
  }
  function request(){
    if(!clip)throw Error('모티프를 먼저 입력해 주세요.');
    const tempo=+$('tempo').value;
    if(!Number.isInteger(tempo)||tempo<40||tempo>180)throw Error('빠르기는 40–180 사이 정수로 지정해 주세요.');
    const motif=structuredClone(clip);motif.name=$('motifName').value.trim()||'나의 모티프';
    return {format:'musicanote-composition-request',version:1,motif,preferences:{prompt:$('prompt').value,composer:$('composer').value,key:$('key').value,meter:$('meter').value,tempo,bars:+$('bars').value,
      secondary:$('secondary').checked,augmented_sixth:$('augmentedSixth').checked,modulation:$('modulation').checked,
      outputs:$('solo').checked?['melody_harmony','piano_solo']:['melody_harmony']}};
  }
  function download(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  $('readInput').addEventListener('click',run(()=>read($('inputText').value,'붙여넣은 악보')));
  $('inputText').addEventListener('input',()=>{invalidate();source=null;$('xmlSelection').hidden=true;status('내용이 바뀌었습니다. ‘입력 읽기’를 눌러 확인해 주세요.');});
  $('inputFile').addEventListener('change',run(async()=>{const f=$('inputFile').files[0];if(!f)return;if(f.size>10*1024*1024)throw Error('10MB 이하 파일을 열어 주세요.');await read(await f.text(),f.name);}));
  $('pasteInput').addEventListener('click',run(async()=>{try{await read(await navigator.clipboard.readText(),'클립보드 악보');}catch(e){throw Error('아래 입력란에 Ctrl+V로 붙여넣고 입력 읽기를 눌러 주세요. '+e.message);}}));
  $('sampleInput').addEventListener('click',run(()=>read(JSON.stringify({format:'musicanote-motif',version:1,name:'쉼이 있는 작은 주제',events:[{duration:'1/2',pitches:[]},{duration:'1/2',pitches:['E4']},{duration:'1',pitches:['G4']},{duration:'1',pitches:['F4']},{duration:'1',pitches:['E4']}],source:{kind:'original_ui_example'}}),'예시')));
  $('voice').addEventListener('change',chooseVoice);
  for(const id of ['rangeStart','rangeEnd'])$(id).addEventListener('change',selectRange);
  $('sourceScore').addEventListener('click',e=>{const n=e.target.closest('g.note,g.rest,g.mRest');if(!n||!stream)return;const i=stream.events.findIndex(v=>v.ids.includes(n.id));if(i<0){status('선택한 성부의 음을 눌러 주세요.');return;}$(pickEnd?'rangeEnd':'rangeStart').value=String(i);if(!pickEnd&&+$('rangeEnd').value<i)$('rangeEnd').value=String(i);pickEnd=!pickEnd;selectRange();});
  $('extract').addEventListener('click',run(()=>{invalidate();accept(MotifTools.clipRange(source,stream,+$('rangeStart').value,+$('rangeEnd').value,$('motifName').value));}));
  for(const id of ['prompt','composer','key','meter','tempo','bars','secondary','augmentedSixth','modulation','solo','motifName'])$(id).addEventListener('change',dirty);
  $('meter').addEventListener('change',run(()=>{stop();if(clip)render('motifPreview',previewXML(clip),getEngine());}));
  $('downloadMotif').addEventListener('click',run(()=>download(request().motif,'motif.json')));
  $('downloadRequest').addEventListener('click',run(()=>download(request(),'composition-request.json')));
  $('saveRequest').addEventListener('click',run(async()=>{
    const data=request();$('saveRequest').disabled=true;$('saveStatus').textContent='요청을 저장하고 선택한 참고 자료를 준비하고 있습니다…';
    try{
      const response=await fetch('api/requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
      if(response.status===404||response.status===501)throw Error('이 화면은 저장 서버 없이 열렸습니다. 요청 파일 받기를 이용해 주세요.');
      const result=await response.json();if(!response.ok)throw Error(result.error||'저장하지 못했습니다.');
      $('saveStatus').textContent=`저장했습니다 · ${result.id.slice(-8)} · 작곡 설계 대기 중`;
      if(result.reference_bars!=null)$('saveStatus').textContent+=` · 같은 박자 참고 ${result.reference_bars}마디`;
      if(result.reference_error)$('saveStatus').textContent+=' · 참고 자료를 준비하지 못했습니다. 요청은 저장했습니다.';
      $('savedLink').href=result.url;$('savedLink').hidden=false;
    }finally{$('saveRequest').disabled=!clip;}
  }));
  $('stopMotif').addEventListener('click',stop);window.addEventListener('pagehide',stop);
  $('listenMotif').addEventListener('click',run(async()=>{
    const data=request();stop();const token=playbackToken;$('stopMotif').disabled=false;status('피아노 음원을 준비하고 있습니다…');audio||=new AudioContext();await audio.resume();
    sampleBank||=fetch('assets/piano.json').then(r=>{if(!r.ok)throw Error('피아노 음원 읽기 실패');return r.json();});
    const bank=await sampleBank, pitches=Object.keys(bank.notes).map(Number), startNotes=[];
    let time=0;
    for(const e of data.motif.events){const d=F.read(e.duration),seconds=d.n/d.d*60/data.preferences.tempo;
      for(const name of e.pitches){const [,step,acc='',oct]=name.match(/^([A-G])(#{1,2}|b{1,2})?(-?\d)$/),midi=12*(+oct+1)+{C:0,D:2,E:4,F:5,G:7,A:9,B:11}[step]+(acc.includes('#')?acc.length:-acc.length);
        const nearest=pitches.reduce((a,b)=>Math.abs(b-midi)<Math.abs(a-midi)?b:a);
        if(!buffers.has(nearest)){const bytes=Uint8Array.from(atob(bank.notes[nearest].split(',')[1]),c=>c.charCodeAt(0));buffers.set(nearest,await audio.decodeAudioData(bytes.buffer));}
        startNotes.push({time,seconds,midi,nearest});
      }time+=seconds;
    }
    if(token!==playbackToken)return;
    const beginning=audio.currentTime+.08;
    for(const n of startNotes){const src=audio.createBufferSource(),gain=audio.createGain();src.buffer=buffers.get(n.nearest);src.playbackRate.value=2**((n.midi-n.nearest)/12);src.connect(gain).connect(audio.destination);const a=beginning+n.time,z=a+n.seconds*.95;gain.gain.setValueAtTime(.5,a);gain.gain.setValueAtTime(.5,z);gain.gain.exponentialRampToValueAtTime(.00001,z+.15);src.start(a);src.stop(z+.17);nodes.push(src);}
    $('stopMotif').disabled=false;status('모티프를 피아노로 재생 중입니다. 페달은 사용하지 않습니다.');timer=setTimeout(()=>{stop();status('모티프 재생을 마쳤습니다.');},(time+.4)*1000);
  }));
  function init(){if(engine)return;try{engine=new verovio.toolkit();engine.getVersion();}catch{engine=null;}}
  if(typeof verovio!=='undefined'){verovio.module.onRuntimeInitialized=init;init();}
})();
