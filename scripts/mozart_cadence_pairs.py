"""Publish separate cadence revisions of the three existing piano miniatures."""
import argparse
from bisect import bisect_right
from fractions import Fraction as F
import gzip
from html import escape
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from music21 import chord, converter, key, note, roman, stream
from musigen.composer_reference import source_path
from scripts.mozart_miniatures import PIECES

# Printed measures differ from the library bar IDs. Target pitches are newly
# authored continuations of the miniature; source time and harmonic anchors are read below.
PLANS = [
    ('K280-1',12,3, [['G5','B5','A5','G5'],['E5','C5','F#4']]),
    ('K309-1',57,2, [['F4','G4','A4','F4','F4','E4','D4','F4',
                        'G4','A4','B-4','G4','E4','F4','E4','C#4']]),
    ('K311-3',56,3, [['A4','C#5','E5','F#5','D5','C5'],['B4','D5','G5','E5','B4','C#5']]),
]


def eligible_windows(db,meter,length,size):
    for (song,n),last in db.items():
        if last['meter']!=meter or not any(a['kind']=='PAC' and F(a['on'])==0 for a in last['cadence_annotations']):
            continue
        window=[db.get((song,i)) for i in range(n-size+1,n+1)]
        if not all(r and r['meter']==meter and F(r['bar_len'])==length and r['melody'] and r['lh'] and r['chords'] for r in window):
            continue
        harmonies=[c for r in window[:-1] for c in r['chords']]+last['chords'][:1]
        if all(c['annotation']['localkey']==harmonies[-1]['annotation']['localkey'] for c in harmonies):
            yield window


def low_voicing(symbol, tonality):
    rn=roman.RomanNumeral(symbol,tonality)
    bass=rn.bass().pitchClass+48
    if bass>54:bass-=12
    offsets=sorted({(p.pitchClass-bass)%12 for p in rn.pitches})
    return [bass+i for i in offsets]


def put(measure,on,duration,pitches):
    obj=note.Rest() if not pitches else note.Note(pitches[0]) if len(pitches)==1 else chord.Chord(pitches)
    obj.quarterLength=duration
    measure.insert(on,obj)


def clear_bar(part,i):
    m=part.measure(i)
    for element in list(m.notesAndRests):m.remove(element)
    return m


def collect_events(score):
    events=[]
    bpm=score.metronomeMarkBoundaries()[0][2].getQuarterBPM()
    for part in score.parts:
        for obj in part.flatten().notes:
            start=float(obj.offset)*60/bpm
            events.extend(dict(start=start,end=start+float(obj.quarterLength)*60/bpm,pitch=p.midi,bank='piano') for p in obj.pitches)
    return events


def build(root):
    with gzip.open(source_path(),'rt',encoding='utf8') as f:
        db={(r['song'],r['bar']):r for r in map(json.loads,f)
            if r['composer']=='Mozart' and r['corpus']=='mozart-sonatas' and r['split']=='train'
            and r['license']=='CC-BY-NC-SA-4.0' and r['library_assessment']['eligible']}
    cards=[]
    audio=[]
    for row,(movement,end,size,new_pitches) in zip(PIECES,PLANS,strict=True):
        title,tonic,mode,meter,bpm,seed,_=row
        old=uuid5(NAMESPACE_URL,'musicanote/mozart-miniatures/v1/'+str(seed)).hex
        new=uuid5(NAMESPACE_URL,'musicanote/mozart-miniatures/cadence-v2/'+str(seed)).hex
        source=root/'compositions'/old
        dest=root/'compositions'/new
        dest.mkdir(parents=True,exist_ok=True)
        piano=converter.parse(source/'piano.musicxml')
        lead=converter.parse(source/'melody.musicxml')
        initial=collect_events(piano)
        info=json.loads((source/'piece.json').read_text('utf8'))
        tonality=key.Key(tonic,mode)
        length=F(4)*F(meter)
        windows=list(eligible_windows(db,meter,length,size))
        donor=next(w for w in windows if w[-1]['song'].endswith('::'+movement) and w[-1]['bar']==end)
        first=17-size
        details=[]
        for j,r in enumerate(donor):
            i=first+j
            pr,pl=(clear_bar(p,i) for p in piano.parts)
            mr,ml=(clear_bar(p,i) for p in lead.parts)
            def right(on,d,pitches):
                for m in (pr,mr):put(m,on,d,pitches)
            chords=r['chords'] if i<16 else r['chords'][:1]
            symbols=[c['annotation']['chord'].replace('viio6','vii°6').replace('V2','V42') for c in chords]
            if mode=='minor':
                symbols=[{'I':'i','vi':'VI','ii6':'ii°6'}.get(s,s) for s in symbols]
            starts=[F(c['on']) for c in chords]
            blocks=[low_voicing(s,tonality) for s in symbols]
            for on,stop,tones in zip(starts,starts[1:]+[length],blocks):
                put(ml,on,stop-on,tones)
            if i<16:
                cursor=F(0)
                for n,p in zip(r['melody'],new_pitches[j],strict=True):
                    on,d=F(n['on']),F(n['dur'])
                    assert cursor<=on and on+d<=length
                    if on>cursor:right(cursor,on-cursor,[])
                    right(on,d,[p])
                    cursor=on+d
                if cursor<length:right(cursor,length-cursor,[])
                attacks=[F(x['on']) for x in r['lh']]
                for k,(on,stop) in enumerate(zip(attacks,attacks[1:]+[length])):
                    block=blocks[bisect_right(starts,on)-1]
                    if len(r['lh'][k]['notes'])>1:
                        pitches=block
                    elif on in starts:
                        pitches=block[:1]
                    else:
                        pitches=[block[(k%3)%len(block)]]
                    put(pl,on,stop-on,pitches)
            else:
                # Hold the tonic at the PAC; in 6/8 let the accompaniment finish the gesture.
                last_pitch=note.Note(new_pitches[-1][-1]).pitch.midi
                pitch=min((note.Note(tonic+str(o)).pitch for o in (4,5)),key=lambda p:abs(p.midi-last_pitch))
                right(0,length,[pitch])
                if meter=='6/8':
                    for k in range(6):
                        put(pl,F(k,4),F(1,4),[blocks[0][[0,1,2,1,2,1][k]]])
                    put(pl,F(3,2),F(3,2),blocks[0])
                else:put(pl,0,length,blocks[0])
            info['chords'][i-1]=' → '.join(symbols)
            details.append(f"<tr><td>{r['source']['mn']} → {i}</td><td>{len(r['melody'])} / {len(r['lh'])}</td><td>{escape(' → '.join(c['annotation']['chord'] for c in r['chords']))}</td><td>{len(pr.notes)} / {len(pl.notes)}</td><td>{escape(info['chords'][i-1])}</td></tr>")
        info.update(id=new,title=title+' · 종지 연결판')
        for score,name in [(piano,'piano'),(lead,'melody')]:
            score.metadata.title=info['title']
            score.write('musicxml',fp=dest/(name+'.musicxml'))
        (dest/'piece.json').write_text(json.dumps(info,ensure_ascii=False),encoding='utf8')
        audio.append({'A':initial,'B':collect_events(converter.parse(dest/'piano.musicxml')),
                      'start':float((first-2)*length)*60/bpm})
        count=len(windows)
        cards.append(f'<section class="paper"><h2>{escape(title)}</h2><p>{meter} · {movement} · 같은 박자의 적격 {size}마디 연결 {count}건에서 선택</p>'
                     f'<select aria-label="재생 구간"><option>{first-1}–16마디</option><option>전곡</option></select>'
                     '<div class="actions"><button data-v="A">이전판 듣기</button><button data-v="B">종지 연결판 듣기</button><button data-stop>정지</button></div>'
                     f'<a href="compose.html?piece={old}">이전 악보</a> · <a href="compose.html?piece={new}">수정 악보</a>'
                     '<details><summary>원자료와 적용 마디</summary><table><tr><th>원본 → 수정 마디</th><th>원본 오른손 / 왼손 발음점</th><th>원본 화성</th><th>수정 오른손 / 왼손 발음점</th><th>수정 화성</th></tr>'
                     +''.join(details)+'</table></details></section>')
        print(movement,count,old,new)
    template=Path(__file__).with_suffix('.html').read_text('utf8')
    (root/'mozart-cadences.html').write_text(template.replace('<!-- CARDS -->',''.join(cards)).replace('/* AUDIO */',json.dumps(audio)),encoding='utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('workshop',type=Path)
    build(parser.parse_args().workshop)
