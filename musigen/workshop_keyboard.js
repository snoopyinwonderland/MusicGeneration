/* Same C2–E6 span and accidental choice as the MusicSearch query keyboard. */
function workshopKeyboard({append,edit,audition}){
  const $=id=>document.getElementById(id);
  const sharp=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
  const flat=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'];
  const lengths=[['4','𝅝','온음표'],['2','𝅗𝅥','2분음표'],['1','♩','4분음표'],['1/2','♪','8분음표'],['1/4','♬','16분음표'],['1/3','⅓','8분 셋잇단음표']];
  let preferFlat=false,base='1',dotted=false;
  function duration(){
    const f=MotifTools.F.read(base);
    return dotted?new MotifTools.F(f.n*3,f.d*2).toString():base;
  }
  function mark(){
    for(const button of $('durations').children)button.setAttribute('aria-pressed',String(button.value===base));
    $('dot').setAttribute('aria-pressed',String(dotted));
  }
  function apply(){
    mark();
    if($('editNote').value!=='')edit(Number($('editNote').value),duration());
  }
  for(const [value,symbol,label] of lengths){
    const button=document.createElement('button');
    button.value=value;button.textContent=symbol;button.title=label;button.setAttribute('aria-label',label);
    button.onclick=()=>{base=value;apply()};$('durations').append(button);
  }
  $('dot').onclick=()=>{dotted=!dotted;apply()};mark();
  function keys(){
    const strip=$('keys');strip.replaceChildren();let whites=0;
    for(let midi=36;midi<=88;midi++){
      const pc=midi%12,black=sharp[pc].length===2,octave=Math.floor(midi/12)-1;
      const name=(preferFlat?flat:sharp)[pc]+octave;
      const key=document.createElement('button');
      key.className=black?'piano-black':'piano-white';
      if(black)key.style.left='calc('+whites+' * 100% / 31 - 100% / 104)';
      else whites++;
      key.title=name;key.setAttribute('aria-label',name);
      if(pc===0)key.textContent=name;
      key.onclick=()=>{if(append(name,duration()))audition(midi)};
      strip.append(key);
    }
    $('sharp').setAttribute('aria-pressed',String(!preferFlat));$('flat').setAttribute('aria-pressed',String(preferFlat));
  }
  $('sharp').onclick=()=>{preferFlat=false;keys()};$('flat').onclick=()=>{preferFlat=true;keys()};
  $('rest').onclick=()=>append(null,duration());
  keys();
  const scroller=$('keys').parentElement;
  scroller.scrollLeft=(scroller.scrollWidth-scroller.clientWidth)/2;
  let notes=[];
  $('editNote').onchange=()=>{
    const selection=$('editNote').value;
    if(selection==='')return;
    const selected=MotifTools.F.read(notes[Number(selection)].duration).toString();
    for(const [value] of lengths){
      const f=MotifTools.F.read(value);
      if(f.toString()===selected||new MotifTools.F(f.n*3,f.d*2).toString()===selected){
        base=value;dotted=f.toString()!==selected;mark();return;
      }
    }
  };
  return function update(events,selected=''){
    notes=events;
    const select=$('editNote');select.replaceChildren(new Option('다음 입력음',''));
    events.forEach((e,i)=>select.add(new Option((i+1)+'. '+(e.pitches[0]||'쉼')+' · '+e.duration+'박',String(i))));
    select.value=selected;
  };
}
