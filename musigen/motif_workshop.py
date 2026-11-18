"""Local motif composition using document support from the karaoke phrase census."""
import json
import os
import random
import re
import secrets
import subprocess
import sys
import tempfile
import uuid
from fractions import Fraction as F
from pathlib import Path
from threading import Lock
from xml.etree import ElementTree as ET

from musicomp.theory import spell
from musigen import MUSICOMP_ROOT
from musigen.harmony import make_chord, progression, tonic_pc
from musigen.motif_clip import pitch_name, read_events
from musigen.score_io import _key, write_leadsheet
from musigen.spec import Section, Spec
from musigen.studio import KEYS

PROFILE = json.loads(Path(__file__).with_name('data').joinpath('karaoke_gestures.json').read_text('utf8'))
STAGES = {'piano':'stage1_piano_solo','guitar':'stage1_guitar_solo','gayageum':'stage1_gayageum_solo',
          'duet':'stage2_duet','trio':'stage3_trio','quartet':'stage4_piano_quartet'}
ARRANGING = Lock()


def settings(data):
    key, meter, tempo, bars = (data.get(k) for k in ('key','meter','tempo','bars'))
    if key not in KEYS or meter not in ('3/4','4/4','6/8'):
        raise ValueError('조성과 박자를 확인하세요.')
    if type(tempo) is not int or not 40 <= tempo <= 180 or type(bars) is not int or bars not in (8,16):
        raise ValueError('빠르기 40–180, 길이 8 또는 16마디를 선택하세요.')
    title = data.get('title','')
    if not isinstance(title,str) or len(title)>80:
        raise ValueError('곡 제목은 80자 이내로 입력하세요.')
    tonic, mode = key.split()
    return Spec(key=tonic,mode=mode,meter=meter,tempo=tempo,title=title.strip() or '모티프 습작',
                form=[Section('제시',bars//2,'half'),Section('응답',bars//2,'authentic')],seed=secrets.randbits(32))


def bar_length(spec):
    beats, unit = map(int,spec.meter.split('/'))
    return F(4*beats,unit)


def unpack(clip):
    events=read_events(clip)
    if any(len(e.pitches)>1 for e in events):
        raise ValueError('모티프에는 한 성부의 선율을 입력하세요.')
    return [(e.dur,e.pitches[0] if e.pitches else None) for e in events]


def scale(spec):
    degrees=(0,2,3,5,7,8,10) if spec.mode=='minor' else (0,2,4,5,7,9,11)
    return [n for n in range(128) if (n-tonic_pc(spec))%12 in degrees]


def nearest(midi, candidates):
    return min(candidates,key=lambda n:abs(n-midi))


def draw(family,rng):
    weights=PROFILE[family]
    return rng.choices(list(weights),weights=weights.values())[0]


def fit(events,duration):
    result=[]
    for length,note in events:
        if duration<=0:break
        take=min(length,duration)
        if 0<duration-take<F(1,12):take=duration
        result.append((take,note))
        duration-=take
    return result


def motif(data):
    spec=settings(data)
    mode=data.get('mode')
    if mode not in ('auto','complete'):raise ValueError('모티프 생성 방식을 선택하세요.')
    clip=data.get('clip') if mode=='complete' else None
    if mode=='complete':unpack(clip)
    return extend_motif(spec,clip)


def extend_motif(spec,clip):
    before=unpack(clip) if clip else []
    length=bar_length(spec)*2
    left=length-sum(d for d,_ in before)
    if left<F(1,12):raise ValueError('이어쓰려면 두 마디보다 짧은 앞부분이 필요합니다.')
    rng=random.Random(spec.seed)
    notes=scale(spec)
    pitch=next((n for _,n in reversed(before) if n is not None),60+tonic_pc(spec))
    pitch=nearest(max(55,min(78,pitch)),notes)
    addition=[]
    while left:
        steps=list(map(int,draw('interval_pattern_4',rng).split(',')))
        rhythm=draw('rhythm_4',rng)
        gaps,durations=([F(x) for x in s.split(',')] for s in rhythm.split('|'))
        # Choose a new entrance between gestures, including a leap or a repeated landing.
        pitch=nearest(max(53,min(81,pitch+rng.choice([-5,-2,0,0,2,4,7]))),notes)
        gesture=[]
        for i,duration in enumerate(durations):
            if i:pitch=nearest(max(51,min(83,pitch+steps[i-1])),notes)
            gesture.append((duration,pitch))
            if i<len(gaps) and gaps[i]>duration:gesture.append((gaps[i]-duration,None))
        chunk=fit(gesture,left)
        addition.extend(chunk)
        left-=sum(d for d,_ in chunk)
    key=_key(spec)
    rows=list(clip['events']) if clip else []
    rows += [dict(duration=str(d),pitches=[] if n is None else [pitch_name(n,spell(n,key))]) for d,n in addition]
    value={'format':'musicanote-motif','version':1,'name':clip.get('name','나의 모티프') if clip else '생성 모티프',
           'events':rows,'source':{'kind':'complete' if before else 'auto','seed':spec.seed,'preserved_events':len(before)}}
    if clip:value['source']['input']=clip.get('source',{})
    unpack(value)
    return value


def develop(spec,theme):
    length=bar_length(spec)
    end=length*spec.total_bars
    used=sum(d for d,_ in theme)
    if used>end-length:raise ValueError('마지막 발전·종결을 위해 모티프는 완성곡보다 한 마디 이상 짧게 입력하세요.')
    result=list(theme)
    cell=fit(theme,min(2*length,used))
    if not any(n is not None for _,n in cell):
        cell=theme[next(i for i,x in enumerate(theme) if x[1] is not None):]
    notes=scale(spec)
    moves=(2,5,-2,0,4,-3)
    index=0
    while used<end-length:
        shift=moves[index%len(moves)]
        answer=[(d,None if n is None else nearest(max(0,min(127,n+shift)),notes)) for d,n in cell]
        if index%3==1 and len(answer)>2:
            # A held landing and a breath use time from the tail of this answer.
            tail=sum(d for d,_ in answer[-2:])
            landing=next(n for _,n in reversed(answer) if n is not None)
            breath=min(F(1,2),tail/2)
            answer[-2:]=[(tail-breath,landing),(breath,None)]
        chunk=fit(answer,end-length-used)
        result.extend(chunk)
        used+=sum(d for d,_ in chunk)
        index+=1
    last=next(n for _,n in reversed(result) if n is not None)
    tonic=nearest(last,[n for n in notes if n%12==tonic_pc(spec)])
    result.extend([(length-F(1,2),tonic),(F(1,2),None)])
    return result


def harmonize(spec,timeline):
    initial=progression(spec)
    length=bar_length(spec)
    palette=('i','iv','V','bVI','bIII','bVII') if spec.mode=='minor' else ('I','ii','iii','IV','V','vi')
    for i,base in enumerate(initial[:-1]):
        start=i*length
        evidence=[(n,float(min(t+d,start+length)-max(t,start))*(1.35 if t==start else 1))
                  for t,d,n in timeline if n is not None and t<start+length and t+d>start]
        candidates=[base]+[make_chord(spec,i+1,tok) for tok in palette]
        def score(chord):
            support=sum(weight for n,weight in evidence if n%12 in chord.pcs)
            return support+(.45 if chord==base else 0)-(.35 if i and chord.token==initial[i-1].token else 0)
        initial[i]=max(candidates,key=score)
    return initial


def compose(root,data):
    spec=settings(data)
    clip=data.get('clip')
    theme=unpack(clip)
    # A very short incipit needs enough material for the ensuing phrase variations.
    if sum(d for d,_ in theme)<bar_length(spec):
        theme=unpack(extend_motif(spec,clip))
    events=develop(spec,theme)
    time=F(0)
    timeline=[]
    for duration,pitch in events:
        timeline.append((time,duration,pitch))
        time+=duration
    chords=harmonize(spec,timeline)
    works=Path(root)/'compositions'
    works.mkdir(exist_ok=True)
    identity=uuid.uuid4().hex
    metadata={'id':identity,'title':spec.title,'key':data['key'],'meter':spec.meter,'tempo':spec.tempo,
              'bars':spec.total_bars,'seed':spec.seed,'clip':clip,'chords':[c.token for c in chords]}
    with tempfile.TemporaryDirectory(dir=works) as tmp:
        stage=Path(tmp)/'score'
        write_leadsheet(spec,chords,timeline,stage/'melody.musicxml')
        (stage/'piece.json').write_text(json.dumps(metadata,ensure_ascii=False),encoding='utf8')
        stage.rename(works/identity)
    return metadata


def arrangements(root,data):
    identity=data.get('id')
    kind=data.get('instrument')
    if not isinstance(identity,str) or not re.fullmatch('[a-f0-9]{32}',identity) or kind not in STAGES:
        raise ValueError('곡과 편성을 다시 선택하세요.')
    work=Path(root)/'compositions'/identity
    lead=work/'melody.musicxml'
    if not lead.is_file():raise ValueError('저장한 선율을 찾을 수 없습니다.')
    with ARRANGING:
        dest=work/'arrangements'
        if not (dest/(STAGES[kind]+'.musicxml')).is_file():
            if dest.exists():raise ValueError('현재 선율은 편곡기의 해당 악기 조건을 충족하지 않습니다.')
            with tempfile.TemporaryDirectory(dir=work) as tmp:
                stage=Path(tmp)/'stages'
                cmd=[sys.executable,'-m','musicomp.pipeline','arrange',str(lead.resolve()),'--out',str(stage.resolve()),
                     '--harmony','given','--piano','retrieval','--grade','8','--style-plan','[{"from_bar":1,"style":"lyrical"}]',
                     '--guitar-solo','--gayageum','octave']
                try:
                    proc=subprocess.run(cmd,cwd=MUSICOMP_ROOT,env={**os.environ,'PYTHONIOENCODING':'utf-8'},
                                        capture_output=True,timeout=240)
                except subprocess.TimeoutExpired:
                    raise RuntimeError('편곡 시간이 4분을 넘었습니다. 다시 시도해 주세요.') from None
                if proc.returncode:
                    print(proc.stderr.decode('utf8','replace')[-2000:],file=sys.stderr)
                    raise RuntimeError('편곡기가 악보를 완성하지 못했습니다. 다시 시도해 주세요.')
                if not (stage/(STAGES['piano']+'.musicxml')).is_file():raise RuntimeError('편곡 파일이 누락됐습니다.')
                publish=Path(tmp)/'publish'
                publish.mkdir()
                for name in STAGES.values():
                    xml=stage/(name+'.musicxml')
                    if xml.is_file():
                        score=ET.parse(xml)
                        title=score.find('./work/work-title')
                        if title is not None:title.text=json.loads((work/'piece.json').read_text('utf8'))['title']
                        score.write(publish/xml.name,encoding='utf-8',xml_declaration=True)
                publish.rename(dest)
        if not (dest/(STAGES[kind]+'.musicxml')).is_file():raise ValueError('현재 선율은 편곡기의 해당 악기 조건을 충족하지 않습니다.')
    return {'xml':f'compositions/{identity}/arrangements/{STAGES[kind]}.musicxml'}
