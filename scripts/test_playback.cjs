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
