"""Fit real-versus-displaced bar-boundary histograms from notated keyboard parts."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction as F
import gzip
from hashlib import sha256
from math import log
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from musigen.composer_reference import source_path
from musigen.corpus_features import read_xml

NAMES=('Mozart','Beethoven','Chopin','Schumann')
STEPS={'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}


def hand(events,upper):
    if not events:return None
    by_time=defaultdict(list)
    for t,p in events:by_time[t].append(p)
    points=[(t,(max if upper else min)(ps)) for t,ps in sorted(by_time.items())]
    a,z=points[0],points[-1]
    return (a[1],z[1],points[1][1]-a[1] if len(points)>1 else 0,
            z[1]-points[-2][1] if len(points)>1 else 0,len(points),float(a[0]),float(z[0]))


def describe(meter,upper,lower):
    rh,lh=hand(upper,True),hand(lower,False)
    return (meter,rh,lh) if rh and lh else None


def part_bars(part,split):
    div=1
    meter=None
    for m in part.findall('measure'):
        groups=[[],[]]
        t=last=extent=F(0)
        for el in m:
            if el.tag=='attributes':
                div=int(el.findtext('divisions',str(div)))
                tm=el.find('time')
                if tm is not None:meter=tm.findtext('beats','')+'/'+tm.findtext('beat-type','')
            if el.tag in ('backup','forward'):
                t+=F(int(el.findtext('duration')),div)*(1 if el.tag=='forward' else -1)
            if el.tag!='note' or el.find('grace') is not None:continue
            d=F(int(el.findtext('duration','0')),div)
            on=last if el.find('chord') is not None else t
            if el.find('chord') is None:last,t=on,on+d
            extent=max(extent,on+d)
            step=el.findtext('pitch/step')
            if step is None or el.find("tie[@type='stop']") is not None:continue
            staff=int(el.findtext('staff','1')) if split else 1
            if staff in (1,2):
                pitch=12*(1+int(el.findtext('pitch/octave')))+STEPS[step]+int(el.findtext('pitch/alter','0'))
                groups[staff-1].append((on,pitch))
        valid=(meter and re.fullmatch(r'\d+/\d+',meter) and extent==4*F(meter) and
               m.find('.//repeat') is None and m.find('.//ending') is None)
        yield (meter,groups) if valid else None


def extract(root):
    parts=root.findall('part')
    descriptions=root.findall('part-list/score-part')
    if len(parts) not in (1,2) or len(descriptions)!=len(parts):return []
    for desc in descriptions:
        name=(desc.findtext('part-name','')+' '+desc.findtext('.//instrument-name','')).lower()
        if not (any(s in name for s in ('piano','klavier')) or desc.findtext('.//midi-program')=='1'):return []
    if len(parts)==1:
        return [describe(m,*g) if row else None for row in part_bars(parts[0],True)
                for m,g in [row or ('',[[],[]])]]
    if [p.findtext('.//clef/sign') for p in parts]!=['G','F'] or any(
            p.findtext('.//staves','1')!='1' for p in parts):return []
    bars=[]
    for a,b in zip(part_bars(parts[0],False),part_bars(parts[1],False),strict=True):
        bars.append(describe(a[0],a[1][0],b[1][0]) if a and b and a[0]==b[0] else None)
    return bars


def interval(d):
    return (1 if d>0 else -1 if d<0 else 0)*(abs(d) if abs(d)<=2 else 3 if abs(d)<=4 else 5 if abs(d)<=7 else 8)


def features(a,b):
    _,ar,al=a
    meter,br,bl=b
    d=interval(br[0]-ar[1])
    bass=interval(bl[0]-al[1])
    gap=4*float(F(meter))-ar[6]+br[5]
    return [f'r:{d}',f'direction:{interval(ar[3])},{d},{interval(br[2])}',
            f'hands:{d},{bass}',f'bass:{bass}',
            f'pacing:{min(7,ar[4])},{min(7,br[4])},{round(gap*2)}',
            f'texture:{min(5,al[4])},{min(5,bl[4])}']


def comparisons(bars):
    for i,(a,b) in enumerate(zip(bars,bars[1:])):
        if not a or not b or a[0]!=b[0]:continue
        # Contrast with a nonadjacent bar from this score in the same meter.
        j=next((j for j in ((i+7+k)%len(bars) for k in range(12))
                if abs(j-i)>2 and bars[j] and bars[j][0]==a[0]),None)
        if j is not None:yield a,b,bars[j]


def validate_works(groups):
    results=Counter()
    for held,tests in groups.items():
        tables=defaultdict(lambda:[Counter(),Counter()])
        for work,examples in groups.items():
            if work==held:continue
            for a,b,c in examples:
                for i,target in enumerate((b,c)):
                    tables[a[0]][i].update(features(a,target))
        for a,b,c in tests:
            if a[0] not in tables:
                results['no_meter']+=1
                continue
            real,other=tables[a[0]]
            def score(target):
                return sum(log((real[f]+5)/(other[f]+5)) for f in features(a,target))
            margin=score(b)-score(c)
            results['win' if margin>1e-8 else 'loss' if margin< -1e-8 else 'tie']+=1
    return {'works':len(groups),**results}


def learn(folder,out):
    counts=defaultdict(lambda:[Counter(),Counter()])
    inventory=Counter()
    seen=set()
    def observe(group,bars):
        used=0
        for a,b,other in comparisons(bars):
            for idx,target in enumerate((b,other)):
                counts[group+'|'+a[0]][idx].update(features(a,target))
            used+=1
        if used:
            inventory[group+' scores']+=1
            inventory[group+' boundaries']+=used
    for p in sorted(folder.rglob('*')):
        if p.suffix.lower() not in ('.xml','.musicxml','.mxl'):continue
        inventory['utf8 inventory']+=1
        name=p.stem.split(',')[0]
        if name not in NAMES:continue
        inventory[name+' candidates']+=1
        try:bars=extract(read_xml(p))
        except (ET.ParseError,ValueError,KeyError,TypeError) as exc:
            inventory[name+' invalid '+type(exc).__name__]+=1
            continue
        if not any(bars):continue
        digest=sha256(repr(bars).encode()).digest()
        if digest in seen:continue
        seen.add(digest)
        observe(name,bars)
    with gzip.open(source_path(),'rt',encoding='utf8') as f:
        songs=defaultdict(dict)
        for r in map(json.loads,f):
            if r['corpus']!='mozart-sonatas' or r['split']!='train' or not r['library_assessment']['eligible'] or F(r['bar_len'])!=4*F(r['meter']):continue
            songs[r['work_group'],r['song']][r['bar']]=describe(r['meter'],[(F(n['on']),n['midi']) for n in r['melody']],
                 [(F(e['on']),n['midi']) for e in r['lh'] for n in e['notes']])
        groups=defaultdict(list)
        for (work,_),bars in songs.items():
            sequence=[bars.get(i) for i in range(min(bars),max(bars)+1)]
            observe('DCML Mozart',sequence)
            groups[work].extend(comparisons(sequence))
    out.parent.mkdir(exist_ok=True,parents=True)
    out.write_text(json.dumps({'inventory':inventory,'counts':dict(counts),'dcml_holdout':validate_works(groups)}),encoding='utf8')
    print(dict(inventory))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('folder',type=Path)
    p.add_argument('out',type=Path)
    a=p.parse_args()
    learn(a.folder,a.out)
