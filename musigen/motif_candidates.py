"""Opt-in P1: finite motif search, measured diversity, no quality score.

Rhythm cells/contours and the 320-attempt cap are provisional authored materials,
not corpus statistics. The stop threshold (six) comes from the 2026-10-24 handoff.
"""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
import random
import re
import shutil
from collections import Counter
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

from musicomp.theory import Key, name_to_tpc, spell, tpc_name
from musicomp.realize.grades import profile
from musigen.accomp import parse_chord
from musigen.design import bar_len, beat, qpm
from musigen.motif import realise, _ladder
from musigen.motif_clip import read_events, to_clip, pitch_name
from musigen.notation import Ev, parse_pitch
from musigen.piece import build
from musigen.piano_io import write_musicxml
from musigen.checks import check

MAX_ATTEMPTS = 320
CONTOURS = ('ascending','descending','arch','valley','repeat_up','repeat_down',
            'up_repeat','down_repeat','zigzag_up','zigzag_down')
LABELS = dict(zip(CONTOURS, ('상행','하행','아치','골짜기','반복 뒤 상행','반복 뒤 하행',
                           '상행 뒤 반복','하행 뒤 반복','오르내리며 상승','오르내리며 하강')))
# Durations in quarter beats. A negative cell is an explicit rest.
CELLS = ((F(1),), (F(1,2),F(1,2)), (F(3,4),F(1,4)),
         (F(1,4),F(3,4)), (F(1,2),F(1),F(1,2)),
         (-F(1,2),F(1,2)), (F(1,2),-F(1,2)))

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def dump(path, value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def settings(design):
    if not isinstance(design,dict) or not isinstance(design.get('basics'),dict) or not isinstance(design.get('theme',{}),dict):
        raise ValueError('설계에는 basics 객체와 선택적인 theme 객체가 필요합니다')
    b=design.get('basics',{}); c=design.get('theme',{}).get('constraints',{})
    if not isinstance(c,dict): raise ValueError('theme.constraints는 객체여야 합니다')
    if b.get('meter') not in ('3/4','4/4'):
        raise ValueError('P1은 현재 3/4·4/4의 한 마디 모티프를 지원합니다')
    if type(c.get('bars',1)) is not int or c.get('bars',1)!=1:
        raise ValueError('P1 모티프는 한 마디입니다. 긴 클립은 작업실에서 구간을 선택하세요')
    if b.get('pickup',0) or b.get('swing',False):
        raise ValueError('P1 비교는 온마디·기보 음가 그대로 재생합니다. pickup/swing 설계는 아직 지원하지 않습니다')
    if set(c)-{'bars','range','start_on_beat','rhythm'}:
        raise ValueError('지원하지 않는 theme.constraints 항목입니다')
    if 'start_on_beat' in c and type(c['start_on_beat']) is not bool:
        raise ValueError('start_on_beat는 true 또는 false여야 합니다')
    if c.get('rhythm','lyrical') not in ('lyrical','syncopated'):
        raise ValueError('rhythm은 lyrical 또는 syncopated입니다')
    match=re.fullmatch(r'([A-G](?:#|b)?\d)-([A-G](?:#|b)?\d)',c.get('range','C4-A5'))
    if not match: raise ValueError('음역은 C4-A5처럼 적습니다')
    lo,hi=(parse_pitch(x)[0] for x in match.groups())
    if not 53<=lo<=hi<=100: raise ValueError('P1 오른손 음역은 F3–E7 안에 있어야 합니다')
    if b.get('mode') not in ('major','minor'): raise ValueError('mode는 major/minor입니다')
    if type(b.get('grade',6)) is not int or not 1<=b.get('grade',6)<=10:
        raise ValueError('grade는 1–10 정수입니다')
    if type(b.get('tempo')) not in (int,float) or not 30<=b['tempo']<=240:
        raise ValueError('tempo는 30–240입니다')
    if not re.fullmatch(r'[A-G](?:#|b)?',str(b.get('key',''))): raise ValueError('조성을 확인하세요')
    key=Key(name_to_tpc(b['key']),b['mode']=='minor'); prof=profile(b.get('grade',6))
    if abs(key.sharps)>prof['accidentals']:
        raise ValueError('조표가 선택 급수의 기존 기준을 넘습니다. 조성 또는 급수를 명시적으로 바꾸세요')
    return b,c,key,prof,lo,hi

def contour(pitches):
    signs=[(b>a)-(b<a) for a,b in zip(pitches,pitches[1:])]
    runs=[s for s,_ in itertools.groupby(signs)]
    known={(1,):'ascending',(-1,):'descending',(1,-1):'arch',(-1,1):'valley',
           (0,1):'repeat_up',(0,-1):'repeat_down',(1,0):'up_repeat',(-1,0):'down_repeat'}
    if tuple(runs) in known: return known[tuple(runs)]
    if 0 not in runs and len(runs)>=3:
        return 'zigzag_up' if pitches[-1]>pitches[0] else 'zigzag_down' if pitches[-1]<pitches[0] else 'oscillating'
    return 'mixed:'+','.join(map(str,runs))

def features(events, blen, harmonic='I → V (맛보기 화성 제안)'):
    pos=F(0); onsets=[]; pitches=[]; sync=False
    for e in events:
        if e.pitches:
            onsets.append(str(pos)); pitches.append(e.pitches[0])
            # Offbeat attack held strictly across the next quarter beat (provisional).
            sync |= pos.denominator!=1 and pos+e.dur>int(pos)+1
        pos+=e.dur
    kind=contour(pitches)
    direction_names={'-1':'하행','0':'동음','1':'상행'}
    label=LABELS[kind] if kind in LABELS else '오르내림' if kind=='oscillating' else ' → '.join(direction_names[x] for x in kind.removeprefix('mixed:').split(',') if x)
    named={m:pitch_name(m,t) for e in events for m,t in zip(e.pitches,e.tpcs)}
    return {'notes':len(pitches),'range_midi':[min(pitches),max(pitches)],
            'range':[named[min(pitches)],named[max(pitches)]],
            'largest_leap':max((abs(b-a) for a,b in zip(pitches,pitches[1:])),default=0),
            'density':round(len(pitches)/float(blen),3),'syncopated':sync,
            'rhythm_fingerprint':onsets,'contour_type':kind,'contour_label':label,
            'harmonic_implication':harmonic,'rest_quarters':float(sum(e.dur for e in events if e.rest))}

def rhythms(blen, constraints):
    rows=[]
    def visit(evs,total):
        if total==blen:
            if 4<=sum(x>0 for x in evs)<=8: rows.append(evs)
            return
        for cell in CELLS:
            size=sum(abs(x) for x in cell)
            if total+size<=blen: visit(evs+cell,total+size)
    visit((),F(0))
    if 'start_on_beat' in constraints:
        rows=[r for r in rows if (r[0]>0)==constraints['start_on_beat']]
    if constraints.get('rhythm')=='syncopated':
        def syncopated(row):
            pos=F(0)
            for dur in row:
                if dur>0 and pos.denominator!=1 and pos+dur>int(pos)+1: return True
                pos+=abs(dur)
            return False
        rows=[r for r in rows if syncopated(r)]
    return rows

def targets(kind,n):
    up=list(range(n)); down=up[::-1]
    if kind=='ascending': return up
    if kind=='descending': return down
    if kind=='arch': return [min(i,n-1-i) for i in up]
    if kind=='valley': return [-min(i,n-1-i) for i in up]
    if kind=='repeat_up': return [0]+list(range(n-1))
    if kind=='repeat_down': return [0]+[-i for i in range(n-1)]
    if kind=='up_repeat': return list(range(n-1))+[n-2]
    if kind=='down_repeat': return [-i for i in range(n-1)]+[2-n]
    zig=[i//2+(2 if i%2 else 0) for i in up]
    return zig if kind=='zigzag_up' else [-i for i in zig]

def generated(rhythm,kind,key,lo,hi,rng):
    ladder=[m for m in _ladder(key) if lo<=m<=hi]
    if not ladder: return None
    target=targets(kind,sum(x>0 for x in rhythm)); width=max(target)-min(target)
    if width>=len(ladder): return None
    base=rng.randrange(len(ladder)-width)-min(target)
    pos=F(0); result=[]; j=0
    tonic={key.tonic_pc,(key.tonic_pc+(3 if key.minor else 4))%12,(key.tonic_pc+7)%12}
    for dur in rhythm:
        if dur<0: result.append(Ev(-dur))
        else:
            ideal=ladder[base+target[j]]; j+=1
            pool=[m for m in ladder if pos.denominator!=1 or m%12 in tonic]
            if not pool: return None
            m=min(pool,key=lambda m:(abs(m-ideal),m))
            result.append(Ev(dur,(m,),(spell(m,key),)))
        pos+=abs(dur)
    return result

def preview(design,clip):
    b,c,key,prof,lo,hi=settings(design); blen=bar_len(b['meter'])
    ev=read_events(clip,'a'); span=sum(e.dur for e in ev)
    if span>blen or any(len(e.pitches)>1 for e in ev):
        raise ValueError('P1에는 한 마디 이내의 단선율 모티프를 넣으세요. 자동 자르기·최상성부 추출은 하지 않습니다')
    if any(not lo<=m<=hi for e in ev for m in e.pitches): raise ValueError('모티프 음역이 설계 범위를 벗어납니다')
    f=features(ev,blen)
    first=next(i for i,e in enumerate(ev) if not e.rest)
    onset=sum(e.dur for e in ev[:first])
    if 'start_on_beat' in c and (onset.denominator==1)!=c['start_on_beat']:
        raise ValueError('모티프의 시작 박이 start_on_beat 조건과 다릅니다')
    if c.get('rhythm')=='syncopated' and not f['syncopated']:
        raise ValueError('syncopated 조건에는 박을 가로지르는 당김음이 필요합니다')
    # Same harmonic support for every candidate. Response re-pitches the original
    # rhythm through realise; no candidate-specific accompaniment advantage.
    tonic=b['key']+('m' if key.minor else '')
    dominant=tpc_name(name_to_tpc(b['key'])+1)
    chs=[parse_chord(tonic),parse_chord(dominant)]
    dominant_pool=[m for m in range(lo,hi+1) if m%12 in {pc for pc,t in chs[1].tones}]
    if not dominant_pool: raise ValueError('설계 음역에 딸림화음 응답음이 없습니다')
    ps=[min(dominant_pool,key=lambda m:(abs(m-e.pitches[0]),m)) for e in ev if e.pitches]
    response=realise(ev,[],key,pitches=' '.join(pitch_name(m,spell(m,key)) for m in ps),label='a')
    response_clip=to_clip(response,'answer')
    pad=[{'duration':str(blen-span),'pitches':[]}] if span<blen else []
    padded=copy.deepcopy(clip); padded['events']=clip['events']+pad
    answer=copy.deepcopy(response_clip); answer['events']+=pad
    left=[]
    for ch in chs:
        pool=[m for m in range(max(24,prof['lh_range'][0]),min(lo,prof['lh_range'][1]+1)) if m%12 in {pc for pc,t in ch.tones}]
        roots=[m for m in pool if m%12==ch.bass_pc]
        if not roots: raise ValueError('음역·급수에 맞는 낮은 블록 화음을 놓을 수 없습니다')
        bass=min(roots,key=lambda m:abs(m-45)); tones=[m for m in pool if bass<=m<=bass+prof['span_lh']][:prof['notes_lh']]
        left.append({'format':'musicanote-motif','version':1,'name':'lh','events':[{'duration':str(blen),'pitches':[pitch_name(m,dict(ch.tones)[m%12]) for m in tones]}]})
    pd={'title':clip.get('id','모티프 후보'),'basics':b,
        'theme':{'motifs':{'a':{'hand':'rh'}}},
        'form':[{'label':'맛보기','bars':[1,2],'function':'statement','motifs':['a']}], 'analysis':{'phrases':True}}
    score={'motifs':{'a':padded,'answer':answer,'left1':left[0],'left2':left[1]},
           'blocks':[{'bars':'1','rh':{'motif':'a'},'lh':{'motif':'left1'},'chords':tonic,'dyn':'mp'},
                     {'bars':'2','rh':{'motif':'answer'},'lh':{'motif':'left2'},'chords':dominant}]}
    piece=build(pd,score); checked=check(piece,pd)
    if checked['errors']: raise ValueError('; '.join(checked['errors']))
    return piece,pd,score,checked

def generate(design,count=8,seed=0,includes=(),max_attempts=MAX_ATTEMPTS):
    if type(count) is not int or not 6<=count<=10: raise ValueError('후보 수는 6–10개입니다')
    b,c,key,prof,lo,hi=settings(design); blen=bar_len(b['meter'])
    selected=[]; prints=set(); shapes=set(); rejected=Counter(); previews={}
    def accept(clip,origin):
        ev=read_events(clip,'a'); f=features(ev,blen,('i' if key.minor else 'I')+' → V (맛보기 화성 제안)')
        piece,pd,score,checked=preview(design,clip)
        fingerprint=tuple(f['rhythm_fingerprint']); shape=f['contour_type']
        if fingerprint in prints: rejected['리듬 지문 중복']+=1; return False
        if shape in shapes: rejected['실제 윤곽 유형 중복']+=1; return False
        cid=f'm{len(selected)+1}'
        row={**copy.deepcopy(clip),'id':cid,'origin':origin,'features':f,
             'preview':{'bars':2,'response':'realise: 리듬 유지, 딸림화음 음으로 응답','warnings':checked['warnings']}}
        pd['title']=cid; piece.title=cid
        selected.append(row);prints.add(fingerprint);shapes.add(shape);previews[cid]=(piece,pd,score,checked)
        return True
    if len(includes)>count: raise ValueError('--include 수가 전체 후보 수보다 많습니다')
    for source in includes:
        clip=read_json(source)
        origin={'kind':'composer' if clip.get('origin')=='composer' else 'import','file':Path(source).name,'sha256':digest(clip)}
        accept(clip,origin)  # Invalid imports fail explicitly; duplicates are reported.
    rng=random.Random(seed)
    pool=[(r,k) for r in rhythms(blen,c) for k in CONTOURS]; rng.shuffle(pool)
    attempts=0
    for r,k in pool:
        if len(selected)>=count or attempts>=max_attempts: break
        attempts+=1; ev=generated(r,k,key,lo,hi,rng)
        if ev is None: rejected['음역 내 윤곽 실현 불가']+=1;continue
        try: accept(to_clip(ev,'a'),{'kind':'generator','rhythm_cells':'authored-v1','planned_contour':k})
        except ValueError as e: rejected[str(e)]+=1
    status='ready' if len(selected)==count else 'stopped' if len(selected)<6 else 'partial'
    data={'format':'musicanote-candidates','version':1,'stage':'motif','design_sha256':digest(design),
          'design':design,'seed':seed,'requested':count,'status':status,'candidates':selected,
          'diagnostics':{'attempts':attempts,'max_attempts':max_attempts,'rejected':dict(rejected),
                         'available_rhythms':len(rhythms(blen,c)),'actual_contours':sorted(shapes),
                         'missing_contours':sorted(set(CONTOURS)-shapes),
                         'basis':'리듬 세포·윤곽·시도 상한은 잠정. 6개 미만 중단은 인수인계 요구. 점수는 음악적 품질을 뜻하지 않음.'}}
    data['set_id']=digest(data)
    return data,previews

def run(work,count=8,seed=0,includes=()):
    work=Path(work); design=read_json(work/'design.json')
    data,previews=generate(design,count,seed,includes)
    stage=work/'stage1_motifs'; archive=stage/'runs'/data['set_id']; archive.mkdir(parents=True,exist_ok=True)
    for row in data['candidates']:
        folder=archive/row['id'];folder.mkdir(exist_ok=True)
        piece,pd,score,checked=previews[row['id']]
        xml=write_musicxml(piece,folder/'preview.musicxml')
        dump(folder/'design.json',pd);dump(folder/'score.json',score);dump(folder/'checks.json',checked)
        row['preview'].update({'xml':xml.read_text(encoding='utf-8'),
                              'notes':[{'q':float(n.onset),'d':float(n.dur),'p':[m for m,t in n.pitches],'hand':n.hand} for n in piece.notes],
                              'quarters':float(2*piece.bar_len)})
    # The set id binds musical input/content; renderer output is supplementary.
    dump(archive/'candidates.json',data);dump(stage/'candidates.json',data)
    from musigen.candidate_page import write_page
    write_page(data,stage/'index.html')
    return {'path':str(stage/'index.html'),'status':data['status'],'count':len(data['candidates']),
            'set_id':data['set_id'],'diagnostics':data['diagnostics']}
