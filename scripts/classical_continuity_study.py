"""Fit complete paths through variants of the three previously published scores."""
import argparse
from copy import deepcopy
from fractions import Fraction as F
from functools import lru_cache
from html import escape
import json
from math import log
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL

from music21 import converter, key, note, chord
from scripts.classical_bar_links import NAMES, describe, features
from scripts.mozart_miniatures import PIECES
from scripts.mozart_cadence_pairs import PLANS,collect_events


def profile(model,meter):
    tables={}
    for name in ['Mozart','DCML Mozart','Beethoven','Chopin','Schumann']:
        pair=model.get(name+'|'+meter)
        if not pair:continue
        n=sum(v for k,v in pair[0].items() if k.startswith('r:'))
        tables[name]=(pair,n)
    @lru_cache(maxsize=8192)
    def cost(k):
        # Each source is scored separately; editions shared between XML and DCML
        # cannot accumulate twice as much weight solely through file counts.
        weighted=mass=0
        for name,((real,false),n) in tables.items():
            weight=(3 if 'Mozart' in name else 1)*n/(n+500)
            a,b=real.get(k,0),false.get(k,0)
            weighted+=weight*log((b+5)/(a+5));mass+=weight
        return weighted/mass
    return lambda a,b:sum(cost(k) for k in features(a,b))


def events(m):
    return tuple((F(n.quarterLength),tuple(p.midi for p in n.pitches)) for n in m.notesAndRests)


def attacks(events):
    on=F(0)
    seq=[]
    for d,ps in events:
        seq.extend((on,p) for p in ps)
        on+=d
    return seq


def variations(rh,lh,harmony,tonality,theme,prior_lh,recall):
    active=[i for i,(_,ps) in enumerate(rh) if ps]
    pcs={p%12 for _,ps in harmony for p in ps}
    tones=[p for p in range(59,85) if p%12 in pcs]
    melodies={rh:0.}
    for idx in dict.fromkeys([active[0],active[-1]]):
        d,ps=rh[idx]
        for p in sorted(tones,key=lambda p:abs(p-ps[0])):
            if not 0<abs(p-ps[0])<=5:continue
            changed=list(rh);changed[idx]=(d,(p,))
            melodies[tuple(changed)]=.12+.035*abs(p-ps[0])
    # Reprise two-bar rhythmic gestures over the current harmony, retaining the
    # contour of the opening while letting the pitch of each bar adapt.
    if recall:
        pitches=[p for _,ps in theme for p in ps]
        scale={p.pitchClass for p in tonality.pitches}
        melodies={}
        for anchor in sorted(tones,key=lambda p:abs(p-rh[active[0]][1][0]))[:4]:
            shift=anchor-pitches[0]
            mapped=[]
            for j,(d,ps) in enumerate(theme):
                pool=tones if not any(v for _,v in mapped) or j==len(theme)-1 else [p for p in range(59,85) if p%12 in scale]
                mapped.append((d,(min(pool,key=lambda p:abs(p-ps[0]-shift)),) if ps else ()))
            melodies[tuple(mapped)]=.06*abs(anchor-rh[active[0]][1][0])
    bass={lh:0.}
    if prior_lh and len(prior_lh)!=len(lh):
        # Reuse a neighboring accompaniment rhythm. Voice it with this bar's
        # chord, respecting the original bass and keeping the harmony complete.
        source=[ps for _,ps in lh if ps]
        union=sorted({p for ps in source for p in ps})
        cursor=0;alt=[]
        for d,ps in prior_lh:
            if not ps:alt.append((d,()));continue
            q=source[0][:1] if cursor==0 else tuple(union[1:]) if len(ps)>1 and len(union)>1 else (union[cursor%len(union)],)
            alt.append((d,q));cursor+=1
        if pcs<={p%12 for _,ps in alt for p in ps}:bass[tuple(alt)]=.35
    for high,rc in melodies.items():
        for low,lc in bass.items():
            if min(p for _,ps in high for p in ps)<=max(p for _,ps in low for p in ps):continue
            yield high,low,rc+lc


def write_bar(m,seq,tonality):
    from musigen.score_io import _pitch
    from musicomp.theory import Key,name_to_tpc
    k=Key(name_to_tpc(tonality.tonic.name.replace('-','b')),tonality.mode=='minor')
    old=list(m.notesAndRests)
    for n in old:m.remove(n)
    t=F(0)
    for j,(d,ps) in enumerate(seq):
        pitches=[_pitch(p,k) for p in ps]
        n=note.Rest() if not ps else note.Note(pitches[0]) if len(ps)==1 else chord.Chord(pitches)
        if j<len(old) and not old[j].isRest and ps:n.articulations=deepcopy(old[j].articulations)
        n.quarterLength=d;m.insert(t,n);t+=d


def build(root,model_path):
    model=json.loads(model_path.read_text('utf8'));cards=[];audio=[];report={}
    for row,(_,_,tail,_) in zip(PIECES,PLANS,strict=True):
        title,tonic,mode,meter,bpm,seed,_=row
        ids=[uuid5(NAMESPACE_URL,'musicanote/mozart-miniatures/'+v+'/'+str(seed)).hex for v in ('cadence-v2','continuity-v3')]
        src,dst=[root/'compositions'/i for i in ids]
        dst.mkdir(exist_ok=True,parents=True)
        piano,lead=[converter.parse(src/(s+'.musicxml')) for s in ('piano','melody')]
        info=json.loads((src/'piece.json').read_text('utf8'));tonality=key.Key(tonic,mode)
        prev=collect_events(piano)
        bars=[(events(piano.parts[0].measure(i)),events(piano.parts[1].measure(i))) for i in range(1,17)]
        learned_cost=profile(model['counts'],meter)
        def transition(a,b):
            leap=abs(b[1][0]-a[1][1])
            return learned_cost(a,b)+.45*max(0,leap-7)
        layers=[]
        for i,(r,l) in enumerate(bars):
            options=[(r,l,0)] if i<2 or i>=16-tail else list(variations(r,l,events(lead.parts[1].measure(i+1)),tonality,
                        bars[i%2][0],bars[i-1][1],i in (4,5,12)))
            layers.append([(h,b,c,describe(meter,attacks(h),attacks(b))) for h,b,c in options] or [(r,l,0,describe(meter,attacks(r),attacks(l)))])
        paths=[(0,[0])]
        for i in range(1,16):
            paths=[min((prior+transition(layers[i-1][path[-1]][3],target[3])+target[2],path+[j])
                       for prior,path in paths) for j,target in enumerate(layers[i])]
        _,chosen=min(paths)
        changed=[];pairs=[]
        for i,j in enumerate(chosen):
            h,b,_,sig=layers[i][j]
            if i:
                old_a,old_b=bars[i-1],bars[i]
                a=describe(meter,*(attacks(x) for x in old_a));z=describe(meter,*(attacks(x) for x in old_b))
                pairs.append([i,i+1,round(transition(a,z),3),round(transition(layers[i-1][chosen[i-1]][3],sig),3),
                              z[1][0]-a[1][1],sig[1][0]-layers[i-1][chosen[i-1]][3][1][1]])
            r,l=bars[i]
            if h!=r or b!=l:changed.append(i+1)
            if h!=r:
                for score in (piano,lead):write_bar(score.parts[0].measure(i+1),h,tonality)
            if b!=l:write_bar(piano.parts[1].measure(i+1),b,tonality)
        for score,name in [(piano,'piano'),(lead,'melody')]:
            score.metadata.title=title+' · 악구 연결판'
            score.write('musicxml',fp=dst/(name+'.musicxml'))
        info.update(id=ids[1],title=title+' · 악구 연결판')
        (dst/'piece.json').write_text(json.dumps(info,ensure_ascii=False),encoding='utf8')
        audio.append({'A':prev,'B':collect_events(converter.parse(dst/'piano.musicxml')),
                      'barSeconds':float(F(meter)*4)*60/bpm})
        report[title]=dict(ids=ids,changed=changed,boundaries=pairs)
        cards.append(f'<section class="paper"><h2>{escape(title)}</h2><p>수정 마디 · {", ".join(map(str,changed))}</p>'
            '<select aria-label="재생 구간"><option value="1-16">전곡</option><option value="3-8">3–8마디 · 주제 응답</option><option value="11-16">11–16마디 · 재현과 종지</option></select><div class="actions"><button data-v="A">이전 종지판 듣기</button>'
            '<button data-v="B">악구 연결판 듣기</button><button data-stop>정지</button></div>'
            f'<a href="compose.html?piece={ids[0]}">이전 악보</a> · <a href="compose.html?piece={ids[1]}">악구 연결 악보</a></section>')
    template=Path(__file__).with_suffix('.html').read_text('utf8')
    stats=[]
    for name in (*NAMES,'DCML Mozart'):
        paired=[v for k,v in model['counts'].items() if k.split('|')[0]==name]
        total=model['inventory'][name+' boundaries']
        small=[sum(t for group in paired for k,t in group[i].items()
                   if k.startswith('r:') and abs(int(k[2:]))<=2) for i in range(2)]
        stats.append(f'<tr><td>{name}</td><td>{model["inventory"][name+" scores"]}</td><td>{total:,}</td>'
                     f'<td>{100*small[0]/total:.1f}%</td><td>{100*small[1]/total:.1f}%</td></tr>')
    validation=model['dcml_holdout']
    page=template.replace('<!-- CARDS -->',''.join(cards)).replace('/* AUDIO */',json.dumps(audio))
    page=page.replace('<!-- COUNTS -->',''.join(stats)).replace('<!-- VALIDATION -->',
        f'DCML 모차르트 {validation["works"]}개 작품 묶음을 하나씩 제외하고 다시 계산했다. 제외한 작품에서 실제 이웃 마디가 '
        f'{validation["win"]:,}번, 떨어진 마디가 {validation["loss"]:,}번 높은 점수를 받았고 동점은 {validation["tie"]}번이었다.')
    (root/'classical-continuity.html').write_text(page,encoding='utf8')
    (model_path.parent/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print({k:v['changed'] for k,v in report.items()})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workshop',type=Path);p.add_argument('model',type=Path)
    args=p.parse_args();build(args.workshop,args.model)
