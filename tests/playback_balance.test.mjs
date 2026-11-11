// Execute the actual player performance function, including dynamics and pedal.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const template=fs.readFileSync(new URL('../musigen/listen_template.html',import.meta.url),'utf8');
const source=template.slice(template.indexOf('function applyPerformance(){'),template.indexOf('function open(i,'));
const note=(p,lh,q=0,instrument='piano')=>({p,lh,q,instrument,t:q*1000,d:1000});
const initial=[note(72,false),...Array.from({length:4},(_,i)=>note(48+i,true)),note(76,false,0,'violin'),note(50,true,4)];
function run(balance){
  const ctx={cur:{performance:{dynamics:[{q:0,level:.8}],...(balance?{balance}: {})}},notes:structuredClone(initial),qMs:q=>q*1000};
  vm.runInNewContext(source+';applyPerformance();',ctx);return ctx.notes;
}
const before=run(),after=run([{start:0,end:4,rh:1.1,lh:.8,reduce_lh_chords:true}]);
assert.ok(before.every(n=>n.level===.8));
assert.ok(Math.abs(after[0].level-.88)<1e-12);
for(const n of after.slice(1,5)) assert.ok(Math.abs(n.level-.32)<1e-12);
assert.equal(after[5].level,.8); // A violin on the same onset is unaffected.
assert.equal(after[6].level,.8); // End is exclusive, unmatched spans use legacy gain.
assert.deepEqual(after.map(n=>[n.p,n.t,n.d,n.q]),before.map(n=>[n.p,n.t,n.d,n.q]));
const neutral=run([{start:0,end:4,rh:1,lh:1,reduce_lh_chords:false}]);
assert.deepEqual(neutral.map(n=>n.level),before.map(n=>n.level));
const muted=run([{start:0,end:4,rh:1,lh:0,reduce_lh_chords:true}]);
const audibleSource=template.slice(template.indexOf('const audible='),template.indexOf('function sampleTone('));
const audibility={$:()=>({checked:true}),notes:muted};
vm.runInNewContext(audibleSource+';result=notes.map(audible);',audibility);
assert.deepEqual(Array.from(audibility.result),[true,false,false,false,false,true,true]);
console.log('Playback balance: legacy, chord count, hand/instrument, boundary and timing checks passed.');
