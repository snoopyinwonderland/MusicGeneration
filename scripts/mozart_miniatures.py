"""Three reproducible Mozart-inspired piano miniatures for the listening workshop."""
import argparse
from collections import Counter
from fractions import Fraction as F
import gzip
import json
from pathlib import Path
from random import Random
from uuid import NAMESPACE_URL, uuid5

from music21 import articulations, chord, clef, dynamics, layout, metadata, meter, note, stream, tempo, key
from musigen.composer_reference import index_rows, source_path
from musigen.harmony import make_chord
from musigen.score_io import write_leadsheet, _key, _pitch
from musigen.spec import Spec, Section

# Quarter-note units; negative values are rests. Cells are varied at phrase returns.
PIECES = [
    ('햇살 아래 미뉴에트','G','major','3/4',108,714832,
     [(1,.5,.5,1),(.5,.5,1.5,-.5),(1.5,.5,.5,.5),(.5,.5,.5,.5,1)]),
    ('작은 극장의 메아리','D','minor','4/4',92,368271,
     [(-.5,.5,1,.5,.5,1),(1.5,.5,1,-1),(.5,.5,1,1.5,.5),(1,.25,.25,.25,.25,1,.5,.5)]),
    ('정원을 도는 제비','D','major','6/8',132,921457,
     [(.5,.5,.5,1,.5),(1,.5,.5,.5,-.5),(.75,.25,.5,.5,.5,.5),(.5,.5,.5,.75,.25,.5)]),
]


def melody_for(rng, library, spec, harmonies, rhythms):
    length=sum(abs(d) for d in rhythms[0])
    relative=[0,2,3,5,7,8,10] if spec.mode=='minor' else [0,2,4,5,7,9,11]
    tonic=_key(spec).tonic_pc
    scale=[p for p in range(62,87) if (p-tonic)%12 in relative]
    weights=Counter(i for row in library for i in row['melody_features']['intervals'] if 0<abs(i)<=9)
    rhythms=list(rhythms)
    rng.shuffle(rhythms)
    themes={}
    bars=[]
    previous=scale[len(scale)//2]
    for i,h in enumerate(harmonies):
        role=i%4
        pitches=[p for p in range(62,87) if p%12 in h.pcs]
        if role==3:
            rhythm=([1,length-1] if i==15 else [.5,.5,length-1.5,-.5])
        else:
            rhythm=rhythms[(role+(1 if 8<=i<12 else 0))%4]
        bar=[]
        for j,d in enumerate(rhythm):
            if d<0:
                bar.append((None,-d))
                continue
            offset=sum(n for _,n in bar)
            pool=pitches if j==0 or offset in (0,1.5,2) else scale
            if i==15:
                target=(tonic+(2 if j==0 else 0))%12
                pool=[p for p in range(62,81) if p%12==target]
                aim=previous
            elif i in (4,12) and j<len(themes[0]) and themes[0][j][0] is not None:
                aim=themes[0][j][0]+(0 if i==12 else 2)
            else:
                step=rng.choices(list(weights),weights=list(weights.values()))[0]
                aim=previous+step
                if aim<63 or aim>82:aim=previous-step
            pitch=min(pool,key=lambda p:(abs(p-aim),abs(p-previous)))
            bar.append((pitch,d))
            previous=pitch
        if i==0:themes[0]=bar
        bars.append(bar)
    return bars


def left_hand(h, length, texture, ceiling):
    bass=48+h.root_pc
    while bass+12>=ceiling:bass-=12
    tones=[bass+(pc-h.root_pc)%12 for pc in h.pcs]
    upper=tones[1:3]
    if texture=='close':return [(tones,length)]
    if texture=='pulse':return [([bass],length/2),(upper,length/4),(None,length/4)]
    if texture=='answer':return [([bass],1),(None,length-2),(upper,1)]
    if texture=='alberti':
        order=[0,2,1,2]
    else:
        order=[0,1,2,1,2,0]
    return [([tones[order[i%len(order)]]],.5) for i in range(int(length*2))]


def build(root):
    with gzip.open(source_path(),'rt',encoding='utf8') as f:
        library=index_rows((json.loads(line) for line in f),'mozart')
    for title,tonic,mode,signature,bpm,seed,rhythms in PIECES:
        rng=Random(seed)
        length=sum(abs(d) for d in rhythms[0])
        rows=[r for r in library if r['meter']==signature and F(r['bar_len'])==length]
        spec=Spec(title=title,key=tonic,mode=mode,meter=signature,tempo=bpm,genre='classical',
                  form=[Section('A',8,'half'),Section('B',8,'authentic')],seed=seed)
        I,ii,IV,vi=('i','iv','iv','VI') if mode=='minor' else ('I','ii','IV','vi')
        progression=[I,'V',IV,'V',I,vi,ii,'V',vi,IV,ii,'V',I,IV,'V7',I]
        hs=[make_chord(spec,i,t) for i,t in enumerate(progression,1)]
        bars=melody_for(rng,rows,spec,hs,rhythms)
        textures=Counter(r['figure_candidate'] for r in rows if r['figure_candidate'] in ('alberti','pulse','arpeggio'))
        identity=uuid5(NAMESPACE_URL,'musicanote/mozart-miniatures/v1/'+str(seed)).hex
        dest=root/'compositions'/identity
        dest.mkdir(exist_ok=True,parents=True)
        score=stream.Score()
        score.metadata=metadata.Metadata(title=title,composer='MUSICANOTE Virtual Composer')
        hands=[stream.PartStaff(id='RH'),stream.PartStaff(id='LH')]
        for hand,sign in zip(hands,[clef.TrebleClef(),clef.BassClef()]):
            hand.partName='Piano'
            hand.insert(0,sign)
            hand.insert(0,key.Key(tonic,mode))
            hand.insert(0,meter.TimeSignature(signature))
            score.insert(0,hand)
        score.insert(0,layout.StaffGroup(hands,symbol='brace',barTogether=True))
        hands[0].insert(0,tempo.MetronomeMark(number=bpm,referent=note.Note(quarterLength=1)))
        timeline=[]
        clip=[]
        for i,(bar,h) in enumerate(zip(bars,hs)):
            if i in (0,4,8,12):hands[0].insert(i*length,dynamics.Dynamic({0:'mp',4:'p',8:'f',12:'mp'}[i]))
            texture=rng.choices(list(textures),weights=list(textures.values()))[0]
            if i%4==1:texture='pulse'
            if i%4==3:texture='answer'
            if i==15:texture='close'
            low=left_hand(h,length,texture,min(p for p,d in bar if p is not None))
            for staff,events in enumerate([bar,low]):
                cursor=F(i)*F(length)
                for p,d in events:
                    if p is None:n=note.Rest()
                    elif staff==0:n=note.Note(_pitch(p,_key(spec)))
                    else:n=chord.Chord([_pitch(x,_key(spec)) for x in p])
                    n.quarterLength=d
                    if staff==0:
                        timeline.append((cursor,F(d),p))
                        if i<2:clip.append({'duration':str(F(d)),'pitches':[v.nameWithOctave.replace('-','b') for v in n.pitches]})
                        if p is not None and d==.5 and i%4==1:n.articulations.append(articulations.Staccato())
                    hands[staff].insert(cursor,n)
                    cursor+=F(d)
                assert cursor==(i+1)*length
        score.write('musicxml',fp=dest/'piano.musicxml')
        write_leadsheet(spec,hs,timeline,dest/'melody.musicxml')
        info=dict(id=identity,title=title,key=f'{tonic} {mode}',meter=signature,tempo=bpm,bars=16,seed=seed,
                  development='neighbors',authored_piano=True,chords=progression,
                  clip=dict(format='musicanote-motif',version=1,name='첫 두 마디',events=clip))
        (dest/'piece.json').write_text(json.dumps(info,ensure_ascii=False),encoding='utf8')
        print(identity,signature,len(rows),textures)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('workshop',type=Path)
    build(parser.parse_args().workshop)
