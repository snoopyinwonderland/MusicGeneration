/* Rendered score timing and the arranger's local per-instrument sample banks. */
const WorkshopAudio = (() => {
  const cache=new Map();
  let audio,manifest,nodes=[],generation=0,timer;
  function stop(){
    generation++;clearTimeout(timer);
    for(const node of nodes){try{node.stop()}catch{}}
    nodes=[];
  }
  function events(engine,xml){
    const parse=text=>new DOMParser().parseFromString(text,'application/xml');
    const doc=parse(xml), mei=parse(engine.getMEI()),routes=[],byId=new Map();
    const programs={25:'guitar',41:'violin',42:'viola',43:'cello',108:'gayageum'};
    for(const part of doc.querySelectorAll('score-part')){
      const id=part.getAttribute('id');
      const source=Array.from(doc.querySelectorAll('score-partwise > part')).find(el=>el.getAttribute('id')===id);
      const count=Number(source?.querySelector('attributes > staves')?.textContent||1);
      const instrument=programs[Number(part.querySelector('midi-program')?.textContent)]||'piano';
      const tabs=new Set(Array.from(source?.querySelectorAll('attributes > clef')||[])
        .filter(c=>c.querySelector('sign')?.textContent==='TAB').map(c=>Number(c.getAttribute('number')||1)));
      for(let i=0;i<count;i++)routes.push(tabs.has(i+1)?null:instrument);
    }
    for(const staff of mei.getElementsByTagName('staff')){
      for(const note of staff.getElementsByTagName('note'))byId.set(note.getAttribute('xml:id'),routes[Number(staff.getAttribute('n'))-1]);
    }
    const next=new Map(),ends=new Set();
    for(const tie of mei.getElementsByTagName('tie')){
      const a=tie.getAttribute('startid')?.slice(1), b=tie.getAttribute('endid')?.slice(1);
      if(a&&b){next.set(a,b);ends.add(b)}
    }
    const result=[];
    for(const group of engine.renderToTimemap())for(const id of group.on||[]){
      if(ends.has(id)||byId.get(id)===null)continue;
      const n=engine.getMIDIValuesForElement(id);
      if(!(n.duration>0))continue;
      let end=n.time+n.duration,current=id;
      const seen=new Set();
      while(next.has(current)&&!seen.has(current)){
        seen.add(current);current=next.get(current);
        const tied=engine.getMIDIValuesForElement(current);
        if(tied)end=Math.max(end,tied.time+tied.duration);
      }
      result.push({start:n.time/1000,end:end/1000,pitch:n.pitch,bank:byId.get(id)||'piano'});
    }
    return result;
  }
  async function play(notes,done){
    stop();const token=generation;
    if(!notes.length)throw Error('재생할 음이 없습니다.');
    audio||=new AudioContext();await audio.resume();
    if(!manifest){
      const r=await fetch('assets/samples/manifest.json');
      if(!r.ok)throw Error('편곡기 샘플 음원을 읽지 못했습니다.');
      manifest=(await r.json()).instruments;
    }
    const voices=notes.map(n=>{
      const tone=manifest[n.bank].reduce((a,b)=>Math.abs(a-n.pitch)<=Math.abs(b-n.pitch)?a:b);
      return {...n,tone,url:'assets/samples/'+n.bank+'/'+tone+'.mp3'};
    });
    await Promise.all([...new Set(voices.map(n=>n.url))].map(async url=>{
      if(cache.has(url))return;
      const r=await fetch(url);if(!r.ok)throw Error('악기 음원을 불러오지 못했습니다.');
      cache.set(url,await audio.decodeAudioData(await r.arrayBuffer()));
    }));
    if(token!==generation)return;
    const start=audio.currentTime+.09;
    for(const n of voices){
      const source=audio.createBufferSource(),gain=audio.createGain(),end=start+n.end;
      source.buffer=cache.get(n.url);source.playbackRate.value=2**((n.pitch-n.tone)/12);
      source.connect(gain).connect(audio.destination);gain.gain.setValueAtTime(.30,start+n.start);
      gain.gain.setValueAtTime(.30,end);gain.gain.exponentialRampToValueAtTime(.0001,end+.12);
      source.start(start+n.start);source.stop(end+.14);nodes.push(source);
    }
    timer=setTimeout(()=>{if(token===generation){stop();done()}},1000*Math.max(...voices.map(v=>v.end))+260);
  }
  return {events,play,stop};
})();
