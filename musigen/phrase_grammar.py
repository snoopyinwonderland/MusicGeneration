"""Opt-in eight-bar formal functions; provisional realizations, not quality claims.

Structure: Caplin (1998), Classical Form, chapters 3–5. Concrete rhythms,
voicings and technique defaults below are provisional composer choices.
"""
from __future__ import annotations
import copy
from dataclasses import replace
from fractions import Fraction as F

from musicomp.theory import name_to_tpc, tpc_name, spell
from musigen.accomp import parse_chord, parse_chords, PATTERNS, figure
from musigen.design import bar_len, beat
from musigen.motif import realise, apply
from musigen.motif_clip import read_events, pitch_name, to_clip
from musigen.notation import Ev, length, parse

DEFAULTS = {
    'sentence': {'presentation': [1,4], 'continuation': [5,6], 'cadential': [7,8]},
    'period': {'antecedent': [1,4], 'consequent': [5,8]},
    'hybrid': {'antecedent': [1,4], 'continuation': [5,6], 'cadential': [7,8]},
}
LABELS = {'sentence':'문장형', 'period':'악절형', 'hybrid':'앞악구 + 이어짐'}

def fit(events, duration):
    """Explicit phrase fragment boundary; rest-pad, do not invent new attacks."""
    out=[]; pos=F(0)
    for e in events:
        if pos >= duration: break
        d=min(e.dur,duration-pos)
        out.append(replace(e,dur=d,tie=False,slur=None)); pos+=d
    if pos<duration: out.append(Ev(duration-pos,src='phrase:breath'))
    return out

def chord_symbol(token,key):
    root=tpc_name(key.tonic_tpc)
    table={'I':root,'i':root+'m', 'IV':tpc_name(key.tonic_tpc-1), 'iv':tpc_name(key.tonic_tpc-1)+'m',
           'V':tpc_name(key.tonic_tpc+1), 'V7':tpc_name(key.tonic_tpc+1)+'7',
           'ii':tpc_name(key.tonic_tpc+2)+'m', 'ii°':tpc_name(key.tonic_tpc+2)+'dim',
           'vi':tpc_name(key.tonic_tpc+3)+'m', 'VI':tpc_name(key.tonic_tpc-4)}
    sym=table.get(token,token);parse_chord(sym);return sym

def harmony_rows(spec,key,blen,kind):
    tonic='i' if key.minor else 'I'; pre='iv' if key.minor else 'IV'
    half=blen/2
    defaults=([tonic,tonic,'V','V',f'{pre}:{half} V:{half}',f'{pre}:{half} V:{half}','V',tonic]
              if kind!='period' else [tonic,tonic,pre,'V',tonic,tonic,'V',tonic])
    if spec is None: rows=defaults
    elif isinstance(spec,list): rows=spec
    elif isinstance(spec,str): rows=spec.split('|') if spec.count('|')==7 else spec.replace('|',' ').split()
    else: raise ValueError('phrase.harmony는 8마디 문자열 목록입니다')
    if len(rows)!=8:raise ValueError('phrase.harmony는 정확히 8마디가 필요합니다. 분할 화음은 마디별 목록을 쓰세요')
    result=[]
    for row in rows:
        tokens=[]
        for token in row.split():
            sym,sep,dur=token.partition(':')
            tokens.append(chord_symbol(sym,key)+(sep+dur if sep else ''))
        text=' '.join(tokens);parsed=parse_chords(text,blen,F(1))
        if not parsed or sum(d for _,d,_ in parsed)!=blen or any(d<=0 for _,d,_ in parsed):
            raise ValueError('phrase.harmony의 각 마디는 박자를 정확히 채워야 합니다')
        result.append(text)
    return result

def align(events,harmony,key,blen,lo,hi,all_tones=False):
    chords=parse_chords(harmony,blen,F(1));position=F(0);pitches=[]
    for e in events:
        if e.pitches:
            ch=next(ch for off,d,ch in chords if off<=position<off+d)
            allowed=[m for m in range(lo,hi+1) if (not all_tones and position.denominator!=1) or m%12 in {pc for pc,t in ch.tones}]
            if not allowed:raise ValueError('프레이즈 음역에 화음 구성음이 없습니다')
            m=min(allowed,key=lambda m:(abs(m-e.pitches[0]),m))
            pitches.append(pitch_name(m,spell(m,key)))
        position+=e.dur
    return realise(events,[],key,pitches=' '.join(pitches),label='phrase:a')

def make_bars(phrase,motifs,key,blen):
    if set(phrase)-{'type','motif','range','harmony','functions','accompaniment','overrides'}:
        raise ValueError('지원하지 않는 phrase 설정입니다')
    kind=phrase.get('type')
    if kind not in DEFAULTS:raise ValueError('phrase.type은 sentence, period, hybrid 중 하나입니다')
    mid=phrase.get('motif')
    if mid not in motifs:raise ValueError('phrase의 모티프를 찾을 수 없습니다')
    ev=motifs[mid]
    if not ev or not any(e.pitches for e in ev) or any(len(e.pitches)>1 for e in ev) or length(ev)>blen:
        raise ValueError('phrase 기본 모티프는 한 마디 이내 단선율이어야 합니다')
    if blen not in (F(3),F(4)):raise ValueError('phrase는 현재 3/4·4/4를 지원합니다')
    bounds=phrase.get('range',[60,81])
    if not isinstance(bounds,list) or len(bounds)!=2 or any(type(x)is not int for x in bounds) or not 0<=bounds[0]<bounds[1]<=127:
        raise ValueError('phrase.range는 MIDI 음역 [낮은 음, 높은 음]입니다')
    lo,hi=bounds
    if any(not lo<=m<=hi for e in ev for m in e.pitches):raise ValueError('선택 모티프가 phrase.range를 벗어납니다')
    functions=copy.deepcopy(DEFAULTS[kind])
    supplied=phrase.get('functions',{})
    if set(supplied)-set(functions):raise ValueError('이 프레이즈 유형에 없는 기능입니다')
    for name,config in supplied.items():
        if not isinstance(config,dict):raise ValueError('기능 설정은 객체입니다')
        if config.get('bars',functions[name])!=functions[name]:raise ValueError('첫 버전은 기본 8마디 기능 경계를 유지합니다')
        allowed={'bars','technique','harmonic_rhythm','cadence','basic_idea','repetition'}
        if set(config)-allowed:raise ValueError('지원하지 않는 기능 설정입니다')
        if config.get('cadence','authentic')!='authentic':raise ValueError('마지막 종지는 authentic만 지원합니다')
        if config.get('basic_idea',[1,2])!=[1,2]:raise ValueError('기본 악상은 1–2마디입니다')
        if config.get('repetition','dominant') not in ('dominant','tonic'):raise ValueError('반복은 tonic 또는 dominant입니다')
        if config.get('harmonic_rhythm','faster')!='faster':raise ValueError('화성 리듬 옵션은 faster입니다')
    technique=supplied.get('continuation',{}).get('technique',['fragment','sequence:+1'])
    if technique not in (['fragment','sequence:+1'],['diminution']):raise ValueError('이어짐 기법은 fragment+sequence:+1 또는 diminution입니다')
    for name,config in supplied.items():
        if name!='continuation' and config.get('technique',['augment_end'])!=['augment_end']:
            raise ValueError('종지 기법은 augment_end입니다')
    harmony=harmony_rows(phrase.get('harmony'),key,blen,kind)
    basic=fit(realise(ev,[],key,label=mid),blen)
    # A two-bar basic idea comprises the selected one-bar motif and a breathing answer.
    answer=align(apply(basic,'step:-1',key),harmony[1],key,blen,lo,hi)
    answer=fit(answer,blen-F(1,2))+[Ev(F(1,2),src='phrase:breath')]
    bars=[basic,answer]
    if kind=='sentence':
        repetition=supplied.get('presentation',{}).get('repetition','dominant')
        if repetition=='tonic' and phrase.get('harmony') is None:
            harmony[2:4]=harmony[:2]
        bars += [align(basic,harmony[2],key,blen,lo,hi,True),align(answer,harmony[3],key,blen,lo,hi,True)]
    else:
        contrast=apply(apply(basic,'frag:0:3',key),'aug:2',key)
        bars += [align(fit(contrast,blen),harmony[2],key,blen,lo,hi),None]
    units=[]
    if kind=='period':bars += [copy.deepcopy(basic),copy.deepcopy(answer)]
    else:
        for j in range(2):
            if technique==['diminution']:
                unit=apply(basic,'dim:2',key)
            else:
                unit=fit(apply(basic,'frag:0:3',key),blen/2)
            unit=fit(unit,blen/2)
            line=apply(unit,f'step:{j+1}',key)+apply(unit,f'step:{j+2}',key)
            bars.append(align(line,harmony[4+j],key,blen,lo,hi))
            units.extend([{'bar':5+j,'offset':str(k*blen/2),'duration':str(blen/2)} for k in range(2)])
    bars += [None,None]
    # Cadential material: longer values, dominant-to-tonic root and bass closure.
    def cadence(index,authentic):
        final_ch=parse_chords(harmony[index],blen,F(1))[-1][2]
        target_pc=(key.tonic_tpc*7)%12 if authentic else final_ch.bass_pc
        prev=next((e.pitches[0] for row in reversed(bars[:index]) if row for e in reversed(row) if e.pitches),72)
        targets=[m for m in range(lo,hi+1) if m%12==target_pc]
        if not targets:raise ValueError('종지음이 지정 음역에 없습니다')
        target=min(targets,key=lambda m:abs(m-prev))
        if authentic:
            approach=target+2 if target+2<=hi else target-1
            line=[Ev(F(1),(approach,),(spell(approach,key),)),Ev(blen-1,(target,),(spell(target,key),))]
        else:
            line=[Ev(blen-F(1,2),(target,),(spell(target,key),)),Ev(F(1,2))]
        return [replace(e,src='phrase:cadential') for e in line]
    if kind!='sentence':bars[3]=cadence(3,False)
    bars[6]=align(fit(apply(basic,'aug:2',key),blen),harmony[6],key,blen,lo,hi,True)
    bars[7]=cadence(7,True)
    accompaniment=phrase.get('accompaniment',{})
    if not isinstance(accompaniment,dict) or set(accompaniment)-set(functions):raise ValueError('반주 설정의 기능 이름을 확인하세요')
    defaults={name:('broken' if name in ('presentation','antecedent','consequent') else 'block' if name=='continuation' else 'bass') for name in functions}
    defaults.update(accompaniment)
    if any(p not in PATTERNS for p in defaults.values()):raise ValueError('지원하지 않는 반주 패턴입니다')
    material=[]
    for i,line in enumerate(bars,1):
        name=next(n for n,(a,z) in functions.items() if a<=i<=z)
        left={'pattern':defaults[name],'chords':harmony[i-1]}
        extra={}
        if defaults[name]=='block':
            # Existing figure, then octave-compact its simultaneous pitches.
            # A one-octave voicing is provisional; it avoids the existing open
            # figure's tenth without changing the shared accompaniment engine.
            evs=figure('block',parse_chords(harmony[i-1],blen,F(1)),F(1))
            compact=[]
            for e in evs:
                bass=min(e.pitches);tones={}
                for m,t in zip(e.pitches,e.tpcs):
                    while m>bass+12:m-=12
                    tones[m]=t
                compact.append(replace(e,pitches=tuple(sorted(tones)),tpcs=tuple(tones[m] for m in sorted(tones))))
            left=to_clip(compact,'phrase:block');extra={'chords':harmony[i-1]}
        material.append({'bars':str(i),'rh':to_clip(line,f'{mid}|phrase:{name}:{i}'),'lh':left,**extra,'dyn':'mp' if i==1 else 'mf' if i==5 and kind!='period' else 'p' if i==8 else 'mp'})
    plan={'type':kind,'functions':functions,'units':units,'basic_unit_bars':2,'harmony':harmony,
          'technique':technique,'cadences':[{'bar':4,'kind':'half'}] if kind!='sentence' else []}
    plan['cadences'].append({'bar':8,'kind':'authentic'})
    return material,plan

def expand(blocks,motifs,key,blen):
    """Expand only explicit phrase blocks; existing blocks pass through untouched."""
    result=[];plans=[]
    for block in blocks:
        if 'phrase' not in block: result.append(block);continue
        if set(block)-{'bars','phrase','key','dyn','text'}:raise ValueError('phrase 블록의 직접 성부는 phrase.overrides로 지정하세요')
        a,_,z=str(block['bars']).partition('-');a=int(a);z=int(z or a)
        if z-a!=7:raise ValueError('phrase 블록은 정확히 8마디입니다')
        from musigen.piece import parse_key
        localkey=parse_key(block['key']) if block.get('key') else key
        rows,plan=make_bars(block['phrase'],motifs,localkey,blen)
        overrides=block['phrase'].get('overrides',[])
        touched=set()
        for override in overrides:
            n=int(override['bars'])
            if not 1<=n<=8 or n in touched:raise ValueError('phrase.overrides는 중복 없는 상대 마디 1–8입니다')
            if set(override)-{'bars','rh','rh2','lh','lh2','chords','dyn','text'}:raise ValueError('override에는 기존 블록 성부·화음·표현만 쓸 수 있습니다')
            rows[n-1].update(copy.deepcopy(override));touched.add(n)
        for row in rows:
            row['bars']=str(int(row['bars'])+a-1)
            if block.get('key'):row['key']=block['key']
        for k in ('dyn','text'):
            if k in block:rows[0][k]=block[k]
        plan.update({'start':a,'end':z,'overrides':sorted(touched)})
        result+=rows;plans.append(plan)
    return result,plans

def observations(piece,design=None):
    """Read actual built notes/chords, including composer overrides."""
    rows=[]
    for bar in range(1,piece.bars+1):
        notes=[n for n in piece.in_bars(bar,bar,'rh') if n.voice==1]
        rows.append({'bar':bar,'mean_pitch':round(sum(n.pitches[-1][0] for n in notes)/len(notes),3) if notes else None,
                     'density':round(len(notes)/float(piece.bar_len),3),
                     'harmony_changes':len({on for on,ch in piece.analysis_chords if piece.bar_start(bar)<=on<piece.bar_end(bar) and ch})})
    findings=[]
    def signature(a,z):
        start=piece.bar_start(a)
        return [(n.onset-start,n.dur,n.pitches) for n in piece.in_bars(a,z,'rh') if n.voice==1]
    def chord_at(on):return next((ch for t,ch in reversed(piece.analysis_chords) if t<=on),None)
    for plan in piece.phrase_plans:
        start=plan['start'];offset=start-1
        if 'continuation' in plan['functions']:
            cont=rows[offset+4:offset+6];pres=rows[offset:offset+4]
            acceleration=sum(r['density'] for r in cont)/2>sum(r['density'] for r in pres)/4 or sum(r['harmony_changes'] for r in cont)/2>sum(r['harmony_changes'] for r in pres)/4
            findings.append({'bars':[offset+5,offset+6],'check':'acceleration','ok':acceleration,'message':f'{offset+5}–{offset+6}마디: 실제 음 밀도 또는 화성 변화 수 증가 '+('확인' if acceleration else '없음')})
            # Unit lengths are the explicit construction spans. Overrides invalidate that evidence.
            valid=not(set(plan['overrides']) & {5,6}) and all(F(u['duration'])<2*piece.bar_len for u in plan['units'])
            findings.append({'bars':[offset+5,offset+6],'check':'shorter_units','ok':valid,'message':f'{offset+5}–{offset+6}마디: 2마디 악상 → 반 마디 구성 단위 '+('확인' if valid else '덮어쓰기 후 확인 필요')})
        if plan['type']=='period':
            ok=signature(start,start+1)==signature(start+4,start+5)
            findings.append({'bars':[start+4,start+5],'check':'consequent_return','ok':ok,'message':f'{start+4}–{start+5}마디: 앞악구 첫 2마디의 실제 음·리듬 반복 '+('일치' if ok else '불일치')})
        for cadence in plan['cadences']:
            bar=offset+cadence['bar'];notes=piece.in_bars(bar,bar,'rh');end=piece.bar_end(bar)
            ch=chord_at(end-F(1,1000));key=piece.bar_keys[bar];tonic=(key.tonic_tpc*7)%12
            authentic=cadence['kind']=='authentic';target=tonic if authentic else (tonic+7)%12
            ok=bool(ch and notes and ch.bass_pc==target and (ch.root_tpc*7)%12==target and notes[-1].pitches[-1][0]%12==target)
            if authentic:
                prior=chord_at(piece.bar_start(bar)-F(1,1000))
                ok=ok and bool(prior and (prior.root_tpc*7)%12==(tonic+7)%12)
            findings.append({'bars':[bar],'check':cadence['kind']+'_cadence','ok':ok,'message':f'{bar}마디: '+('정격' if authentic else '반')+'종지 화음·선율 끝음 '+('일치' if ok else '확인 필요')})
    planned=(design or {}).get('climax',{}).get('bar')
    available=[r for r in rows if r['mean_pitch'] is not None]
    maximum=max((r['mean_pitch'] for r in available),default=None)
    peaks=[r['bar'] for r in available if r['mean_pitch']==maximum]
    climax={'planned_bar':planned,'mean_pitch_peak_bars':peaks,
            'within_one_bar':min((abs(planned-b) for b in peaks),default=999)<=1 if type(planned)is int else None,
            'basis':'평균 음높이 정점과 1마디 이내는 잠정. 밀도·화성 곡선과 별개로 관찰.'}
    return {'climax':climax,'basis':'구조는 Caplin(1998) 3–5장. 수치와 단위 길이는 잠정·참고 검사이며 청취 품질 점수가 아님.',
            'unit_method':'생성 구성 단위 길이; 자동 청각적 분절 판정 아님. 덮어쓴 이어짐은 판정 보류.',
            'curve':rows,'findings':findings}
