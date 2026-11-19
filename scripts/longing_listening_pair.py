"""Publish the eight-bar controlled listening study into a built local workshop."""
import argparse
from fractions import Fraction as F
from html import escape
import json
from pathlib import Path

from music21 import converter
import verovio

from musigen.harmony import make_chord
from musigen.score_io import write_leadsheet
from musigen.spec import Spec, Section


# Durations are in quarter notes. Bars 4 and 8 are phrase arrivals.
BARS = [
    [(None,.5),(66,.5),(69,.5),(71,.5),(69,2)],
    [(73,1.5),(71,.5),(69,1),(None,1)],
    [(66,.5),(69,.5),(74,1.5),(73,.5),(71,1)],
    [(69,1),(71,3)],
    [(None,.5),(67,.5),(71,.5),(74,.5),(73,1),(71,1)],
    [(76,1.5),(74,.5),(71,1),(67,1)],
    [(69,.5),(71,.5),(73,.5),(76,.5),(74,1),(73,1)],
    [(64,1),(62,3)],
]
HARMONY = ['I','V','vi7','IV','IV','ii7','V7','I']


def build(statistics, root):
    patterns=json.loads(statistics.read_text('utf8'))['patterns']['ko/longing']
    # Verify the common four-note gesture and the two selected harmonic links.
    references=[('timed_shape','++- sss'),('harmony','major +7 major'),('harmony','dominant7 +5 major')]
    evidence=[f"{code} ({patterns[name]['counts'][code]:,}/{patterns[name]['total']:,})" for name,code in references]
    dest=root/'longing-pair'
    dest.mkdir(parents=True,exist_ok=True)
    spec=Spec(title='창가에 두고 온 말',key='D',tempo=80,form=[Section('A',8,'authentic')])
    chords=[make_chord(spec,i,token) for i,token in enumerate(HARMONY,1)]
    events={}
    cards=[]
    for label in ('A','B'):
        time=F(0)
        melody=[]
        for i,bar in enumerate(BARS,1):
            if label=='B' and i in (4,8):
                bar=[bar[0],(None,1),(bar[1][0],2)]
            assert sum(d for _,d in bar)==4
            for pitch,d in bar:
                melody.append((time,F(d),pitch))
                time+=F(d)
        path=dest/f'{label}.musicxml'
        write_leadsheet(spec,chords,melody,path)
        score=converter.parse(path)
        events[label]=[]
        for part in score.parts:
            for item in part.flatten().notes:
                for pitch in item.pitches:
                    events[label].append(dict(start=float(item.offset)*.75,
                        end=float(item.offset+item.quarterLength)*.75,pitch=pitch.midi,bank='piano'))
        tk=verovio.toolkit()
        tk.setOptions(dict(pageWidth=2000,pageHeight=2800,scale=38,adjustPageHeight=True,svgViewBox=True,
                           header='none',footer='none',breaks='auto'))
        if not tk.loadFile(str(path.resolve())):raise ValueError('악보를 그릴 수 없습니다.')
        images=[]
        for n in range(1,tk.getPageCount()+1):
            image=dest/f'{label}-{n}.svg'
            image.write_text(tk.renderToSVG(n),encoding='utf8')
            images.append(f'<img src="longing-pair/{image.name}" alt="후보 {label} 악보 {n}쪽">')
        cards.append(f'<details><summary>후보 {label} 악보</summary>'+''.join(images)+
                     f'<a download href="longing-pair/{path.name}">MusicXML 받기</a></details>')
    template=Path(__file__).with_name('longing_listening_pair.html').read_text('utf8')
    (root/'longing-pair.html').write_text(template.replace('<!-- SCORES -->',''.join(cards))
        .replace('/* EVENTS */',json.dumps(events)).replace('<!-- EVIDENCE -->',escape(' · '.join(evidence))),encoding='utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('statistics',type=Path)
    parser.add_argument('workshop',type=Path)
    args=parser.parse_args()
    build(args.statistics,args.workshop)
