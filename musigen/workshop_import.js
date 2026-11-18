function workshopImport(request,accept){
  const $=id=>document.getElementById(id);
  const dialog=$('xmlDialog'),view=$('xmlScore');
  let xml='',title='',dbId=null,score,voice,engine,page=1,anchor=null,loadId=0,searchId=0,limited=false,format='musicxml';
  const message=text=>{$('importStatus').textContent=text};
  const populate=(id,rows)=>$(id).replaceChildren(...rows.map(([v,label])=>new Option(label,String(v))));
  function reset(){
    score=null;voice=null;anchor=null;$('rangePane').hidden=true;$('manualCopy').hidden=true;view.replaceChildren();
  }
  function selectPart(preferred){
    score=null;voice=null;view.replaceChildren();
    score=MotifTools.parseMusicXML(xml,title,$('xmlPart').value);
    populate('xmlVoice',score.voices.map((v,i)=>[i,v.staff+' · '+v.voice]));
    const vi=score.voices.findIndex(v=>[v.part,v.staff,v.voice].join(':')===preferred);
    $('xmlVoice').value=String(Math.max(0,vi));
    engine||=new verovio.toolkit();
    engine.setOptions({pageWidth:1750,pageHeight:2100,scale:42,svgViewBox:true,adjustPageHeight:true,header:'none',footer:'none',breaks:'auto'});
    if(!engine.loadData(score.xml))throw Error('선택한 파트를 악보로 표시하지 못했습니다.');
    page=1;chooseVoice();display();
    message(title+(format==='midi'?' · 16분음표·셋잇단음표 기준으로 기보한 MIDI':'')+(limited?' · DB 제공 미리보기 구간':''));
  }
  function chooseVoice(){
    voice=score.voices[Number($('xmlVoice').value)];
    const bars=$('rangeMode').value==='measure';
    const rows=bars?score.measures.map((m,i)=>[i,m.number+'마디']):
      voice.events.map((e,i)=>[i,e.measure+'마디 +'+e.offset+' · '+(e.pitches.join('+')||'쉼')]);
    populate('rangeA',rows);populate('rangeB',rows);
    anchor=null;highlight();
  }
  function highlight(){
    $('manualCopy').hidden=true;
    view.querySelectorAll('.range-picked').forEach(el=>el.classList.remove('range-picked'));
    if(!voice)return;
    const a=+$('rangeA').value,b=+$('rangeB').value;
    const byBar=$('rangeMode').value==='measure';
    voice.events.forEach((e,i)=>{
      const pos=byBar?e.measureIndex:i;
      if(pos>=a&&pos<=b)for(const id of e.ids)view.querySelector('#'+CSS.escape(id))?.classList.add('range-picked');
    });
  }
  function display(){
    view.innerHTML=engine.renderToSVG(page);
    // Unpainted space around a stem or inside a measure is also a click target.
    for(const group of view.querySelectorAll('g.measure,g.note,g.rest,g.mRest')){
      const box=group.getBBox();
      const hit=document.createElementNS('http://www.w3.org/2000/svg','rect');
      const pad=group.classList.contains('measure')?0:20;
      for(const [k,v] of Object.entries({x:box.x-pad,y:box.y-pad,width:box.width+2*pad,height:box.height+2*pad,
        fill:'transparent',stroke:'none','pointer-events':'all'}))hit.setAttribute(k,v);
      group.prepend(hit);
    }
    highlight();
    $('xmlPage').textContent=page+' / '+engine.getPageCount();
    $('prevXml').disabled=page<=1;$('nextXml').disabled=page>=engine.getPageCount();
  }
  function load(text,name,preferred='',identity=null,restricted=false,kind='musicxml'){
    reset();
    const doc=new DOMParser().parseFromString(text,'application/xml');
    if(doc.documentElement.localName!=='score-partwise')throw Error('MusicXML(.xml, .musicxml) 파일을 선택하세요.');
    const parts=[...doc.querySelectorAll('score-partwise > part')].filter(p=>p.querySelector('note > pitch'));
    if(!parts.length)throw Error('선율이 있는 파트가 없습니다.');
    xml=text;title=name;dbId=identity;limited=restricted;format=kind;
    const names=new Map([...doc.querySelectorAll('score-part')].map(p=>[p.id,p.querySelector('part-name')?.textContent]));
    populate('xmlPart',parts.map(p=>[p.id,names.get(p.id)||p.id]));
    if(parts.some(p=>p.id===preferred.split(':')[0]))$('xmlPart').value=preferred.split(':')[0];
    $('rangePane').hidden=false;selectPart(preferred);
  }
  function extract(){
    if(!score||!voice)throw Error('악보와 선율 성부를 선택하세요.');
    let a=+$('rangeA').value,b=+$('rangeB').value;
    const bars=$('rangeMode').value==='measure';
    if(a>b)throw Error('시작 위치 뒤에 있는 끝 위치를 선택하세요.');
    const firstBar=a,lastBar=b;
    if(bars){
      a=voice.events.findIndex(e=>e.measureIndex>=firstBar);
      b=voice.events.findLastIndex(e=>e.measureIndex<=lastBar);
      if(a<0||b<a)throw Error('선택한 마디에 선율이 없습니다.');
    }
    const policy=$('chordMode').value;
    let selected=voice;
    if(policy==='one'&&voice.events.slice(a,b+1).some(e=>e.pitches.length>1))
      throw Error('선택 구간에 화음이 있습니다. 동시 화음에서 윗음 또는 아랫음을 선택하세요.');
    if(policy!=='one'){
      const pitch=name=>{
        const [,step,acc,oct]=name.match(/^([A-G])([#b]*)(-?\d+)$/);
        return Number(oct)*12+({C:0,D:2,E:4,F:5,G:7,A:9,B:11})[step]+(acc.includes('b')?-acc.length:acc.length);
      };
      selected={...voice,events:voice.events.map(e=>{
        if(e.pitches.length<=1)return e;
        const values=e.pitches.map(pitch),which=values.indexOf(policy==='high'?Math.max(...values):Math.min(...values));
        return {...e,pitches:[e.pitches[which]],tieStarts:[e.tieStarts[which]],tieStops:[e.tieStops[which]]};
      })};
    }
    const clip=MotifTools.clipRange(score,selected,a,b,title.slice(0,64));
    clip.source.chord_selection=policy;
    if(bars){
      const begin=score.measures[firstBar],end=score.measures[lastBar],last=voice.events[b];
      const before=voice.events[a].on.sub(begin.start),after=end.end.sub(last.on.add(last.dur));
      if(before.n>0)clip.events.unshift({duration:before.toString(),pitches:[]});
      if(after.n>0)clip.events.push({duration:after.toString(),pitches:[]});
      clip.source.start={measure:begin.number,offset:'0'};
      clip.source.end={measure:end.number,offset:end.end.sub(end.start).toString()};
    }
    if(dbId)clip.source.workId=dbId;
    clip.source.format=format;
    clip.source.part_name=voice.name;
    if(format==='midi'){
      clip.source.quantization='sixteenth-and-eighth-triplet';
      clip.warnings.push('MIDI 연주 시각을 16분음표·셋잇단음표 기준으로 기보했습니다.');
    }
    MotifTools.validate(clip);return clip;
  }
  function action(fn){return async()=>{try{await fn()}catch(e){message(e.message)}}}
  $('openImport').onclick=()=>dialog.showModal();$('closeImport').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{loadId++;searchId++});
  $('xmlFile').onchange=action(async()=>{
    const file=$('xmlFile').files[0];if(!file)return;
    const ticket=++loadId;reset();message('파일을 여는 중입니다…');
    if(file.size>16*1024*1024)throw Error('16MB 이하의 악보 파일을 열어 주세요.');
    const kind=/\.midi?$/i.test(file.name)?'midi':/\.mxl$/i.test(file.name)?'mxl':'musicxml';
    let text;
    if(kind==='musicxml')text=await file.text();
    else{
      const res=await fetch('api/import-'+kind,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});
      const result=await res.json().catch(()=>({}));if(ticket!==loadId)return;
      if(!res.ok)throw Error(result.error||'악보를 불러오지 못했습니다.');
      text=result.xml;
    }
    if(ticket===loadId)load(text,file.name,'',null,false,kind);
  });
  $('catalogForm').onsubmit=async e=>{
    e.preventDefault();const ticket=++searchId;$('dbItems').replaceChildren();message('DB에서 검색 중입니다…');
    try{
      const result=await request('api/catalog',{query:$('dbQuery').value});
      if(ticket!==searchId)return;
      for(const item of result.items){
        const button=document.createElement('button');button.textContent=[item.title,item.composer].filter(Boolean).join(' · ');
        button.onclick=action(async()=>{
          const n=++loadId;reset();message('DB 악보를 여는 중입니다…');
          try{const work=await request('api/score',{workId:item.workId});
            if(n===loadId)load(work.xml,work.title,work.streamId||'',work.workId,work.restrictedPreviewActive);
          }catch(e){if(n===loadId)throw e}
        });$('dbItems').append(button);
      }
      message(result.items.length?'검색 결과에서 악보를 선택하세요.':'검색 결과가 없습니다.');
    }catch(e){if(ticket===searchId)message(e.message)}
  };
  $('xmlPart').onchange=action(()=>selectPart());
  $('xmlVoice').onchange=$('rangeMode').onchange=action(chooseVoice);
  for(const id of ['rangeA','rangeB'])$(id).onchange=()=>{
    if(+ $('rangeA').value>+$('rangeB').value)$(id==='rangeA'?'rangeB':'rangeA').value=$(id).value;
    anchor=null;highlight();
  };
  view.onclick=e=>{
    if(!voice)return;
    const note=e.target.closest('g.note,g.rest,g.mRest');
    const i=note?voice.events.findIndex(v=>v.ids.includes(note.id)):-1;
    const measure=e.target.closest('g.measure');
    const index=$('rangeMode').value==='note'?i:i>=0?voice.events[i].measureIndex:score.measures.findIndex(m=>m.id===measure?.id);
    if(index<0){message('선택한 성부의 음표 또는 마디를 눌러 주세요.');return}
    const first=anchor??index;
    $('rangeA').value=String(Math.min(first,index));$('rangeB').value=String(Math.max(first,index));
    anchor=anchor===null?index:null;highlight();message(anchor===null?'구간을 선택했습니다.':'끝 위치를 눌러 주세요.');
  };
  $('prevXml').onclick=()=>{page--;display()};$('nextXml').onclick=()=>{page++;display()};
  $('useRange').onclick=action(()=>{accept(extract());dialog.close()});
  $('copyRange').onclick=action(async()=>{
    const json=JSON.stringify(extract(),null,2);
    try{
      await navigator.clipboard.writeText(json);
      message('선택 구간을 복사했습니다. 창을 닫고 모티프 입력 칸에 붙여넣으세요.');
    }catch{
      $('manualCopy').hidden=false;$('copyText').value=json;$('copyText').focus();$('copyText').select();
      message('선택된 JSON을 Ctrl+C로 복사한 뒤 모티프 입력 칸에 붙여넣으세요.');
    }
  });
}
