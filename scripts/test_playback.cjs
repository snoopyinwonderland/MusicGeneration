const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../musigen/listen_template.html'),'utf8');
const fn=source.slice(source.indexOf('function applyPerformance()'),source.indexOf('\nfunction open('));
function render(expression,instrument='piano'){
 const context={cur:{performance:{expression}},notes:[{q:0,t:0,d:1000,p:60,instrument,lh:false}],qMs:q=>q*1000};
 vm.runInNewContext(fn+';applyPerformance();',context);
 return context.notes[0];
}
test('pedal refresh damps the old note at the first boundary',()=>{
 assert.equal(render([{kind:'pedal',start:0,changes:[3,6],end:9}]).d,3000);
});
test('adjacent pedal spans do not re-sustain a released note',()=>{
 assert.equal(render([{kind:'pedal',start:0,changes:[],end:3},{kind:'pedal',start:3,changes:[],end:6}]).d,3000);
});
test('piano pedal never extends the violin',()=>{
 assert.equal(render([{kind:'pedal',start:0,changes:[],end:3}],'violin').d,950);
});
test('without pedal, existing gate duration stays unchanged',()=>{
 assert.equal(render([]).d,950);
});

for(const instrument of ['viola','cello']) test('piano pedal never extends '+instrument,()=>{
 assert.equal(render([{kind:'pedal',start:0,changes:[],end:3}],instrument).d,950);
});

test('audio and attribution each use one explicit download action',async()=>{
 const handlers={},downloads=[],elements={};
 const context={
  $:id=>elements[id]??=( {addEventListener:(event,fn)=>{handlers[id]=fn;},value:'100'} ),
  pianoReady:true,cur:{piece:'sample',design:{title:'시험곡'},info:{version:'v001'}},
  notes:[],audible:()=>true,endMs:()=>1000,sampleTone:()=>{},
  OfflineAudioContext:class{async startRendering(){return 'pcm';}},
  wavBlob:pcm=>new Blob([pcm]),Blob,download:(blob,name)=>downloads.push({blob,name})
 };
 const start=source.indexOf("$('downloadAudio').addEventListener");
 const end=source.indexOf("window.addEventListener('hashchange'",start);
 vm.runInNewContext(source.slice(start,end),context);
 await handlers.downloadAudio();
 assert.deepEqual(downloads.map(d=>d.name),['sample-v001.wav']);
 handlers.downloadAudioCredit();
 assert.deepEqual(downloads.map(d=>d.name),['sample-v001.wav','sample-v001-출처.txt']);
 assert.match(await downloads[1].blob.text(),/CC BY 3\.0 US/);
 assert.equal(elements.downloadAudio.disabled,false);
});
