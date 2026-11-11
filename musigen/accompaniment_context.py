"""Explicit phrase requirements and observations of the realised LH, not a quality score."""
import copy
from fractions import Fraction as F
from musigen.piece import ScoreError


def requirements(design,piece):
    result={};last_bar=piece if type(piece)is int else piece.bars
    plan=design.get('accompaniment_plan',[])
    if not isinstance(plan,list):raise ScoreError('반주 계획은 구간 목록이어야 합니다')
    for row in plan:
        if not isinstance(row,dict):raise ScoreError('반주 계획 구간은 객체여야 합니다')
        if set(row)-{'bars','role','decision','required_degrees','entry_bass_range','repair_voicing'}:raise ScoreError('알 수 없는 반주 계획 항목')
        if 'repair_voicing' in row and type(row['repair_voicing']) is not bool:raise ScoreError('반주 음 배치 수정은 true/false로 지정하세요')
        span=row.get('bars');degrees=row.get('required_degrees',[])
        if not isinstance(span,list) or len(span)!=2 or any(type(b)is not int for b in span) or not 1<=span[0]<=span[1]<=last_bar:
            raise ScoreError('반주 계획의 마디 범위 오류')
        if any(not isinstance(row.get(k),str) or not row[k].strip() for k in ('role','decision')) or not isinstance(degrees,list) or any(type(d)is not int or d not in (3,7) for d in degrees) or len(set(degrees))!=len(degrees):
            raise ScoreError('반주 역할·작성 결정·요구 구성음(3/7)을 확인하세요')
        row={**row,'required_degrees':degrees}
        register=row.get('entry_bass_range')
        if register is not None and (not isinstance(register,list) or len(register)!=2 or any(type(n)is not int for n in register) or not 28<=register[0]<=register[1]<=69):
            raise ScoreError('반주 첫 발음 최저음 범위는 MIDI 28–69 안에서 지정하세요')
        for b in range(span[0],span[1]+1):
            if b in result:raise ScoreError('반주 계획 구간이 겹칩니다')
            result[b]=copy.deepcopy(row)
    return result


def chord_degrees(chord,degrees):
    # Degree comes from spelling, not pitch-class distance: diminished sevenths
    # and enharmonic notes retain their declared harmonic role.
    from musicomp.theory import tpc_step
    letters='CDEFGAB';root=letters.index(tpc_step(chord.root_tpc))
    return {t for _,t in chord.tones if (letters.index(tpc_step(t))-root)%7+1 in degrees}


def missing_requirements(notes,piece,bar,policy):
    missing=[];lo,hi=piece.bar_start(bar),piece.bar_end(bar)
    chords=piece.analysis_chords
    for i,(on,ch) in enumerate(chords):
        end=chords[i+1][0] if i+1<len(chords) else piece.bar_end(piece.bars)
        start,stop=max(lo,on),min(hi,end)
        if ch is None or start>=stop:continue
        # A required pitch must sound within this chord span, not elsewhere in the bar.
        actual={t for n in notes if n.onset<stop and n.onset+n.dur>start for _,t in n.pitches}
        absent=chord_degrees(ch,policy['required_degrees'])-actual
        if absent:missing.append({'onset':str(start),'missing_tpcs':sorted(absent)})
    return missing


def entry_in_range(notes,policy):
    bounds=policy.get('entry_bass_range')
    if bounds is None:return True
    if not notes:return False
    at=min(n.onset for n in notes);bass=min(m for n in notes if n.onset==at for m,t in n.pitches)
    return bounds[0]<=bass<=bounds[1]


def source_has_degrees(target,source,degrees):
    from musicomp.realize.retrieval import SEVENTH
    for c in target.chords:
        # '3' in the arranger's role map includes a suspended tone. Such chords
        # have no spelled third, so only ordinary major/minor thirds are required.
        requested={str(d) for d in degrees if (d==3 and c['quality'] not in ('sus2','sus4','7sus4')) or (d==7 and c['quality'] in SEVENTH)}
        roles={str(n.get('role')) for e in source['lh'] if c['on']<=F(e['on'])<c['end'] for n in e['notes']}
        if not requested<=roles:return False
    return True


def observe(piece,design):
    """Exact coverage/rests and boundary snapshots; no inferred inner voice IDs."""
    from musicomp.theory import tpc_name
    policies=requirements(design,piece);bars=[];boundaries=[]
    rh=[n for n in piece.notes if n.hand=='rh'];lh=[n for n in piece.notes if n.hand=='lh']
    def edges(notes,lo,hi):
        times=sorted({n.onset for n in notes if lo<=n.onset<hi})
        if not times:return None,None
        def event(at):
            pitches=sorted(m for n in notes if n.onset==at for m,t in n.pitches)
            return {'onset':str(at),'bass':min(pitches),'top':max(pitches)}
        return event(times[0]),event(times[-1])
    for b in range(1,piece.bars+1):
        lo,hi=piece.bar_start(b),piece.bar_end(b);ns=[n for n in lh if n.onset<hi and n.onset+n.dur>lo]
        first,last=edges(lh,lo,hi)
        activity=sorted({n.onset for n in ns if lo<=n.onset<hi})
        rest_attacks=[at for at in activity if not any(r.onset<=at<r.onset+r.dur for r in rh)]
        sounding_end=max((min(n.onset+n.dur,hi) for n in ns),default=lo)
        harmony=[]
        for i,(on,ch) in enumerate(piece.analysis_chords):
            end=piece.analysis_chords[i+1][0] if i+1<len(piece.analysis_chords) else piece.bar_end(piece.bars)
            start,stop=max(lo,on),min(hi,end)
            if ch is None or start>=stop:continue
            actual={t for n in ns if n.onset<stop and n.onset+n.dur>start for _,t in n.pitches}
            important=chord_degrees(ch,[3,7])
            harmony.append({'onset':str(start),'symbol':ch.symbol,'core_tones':[tpc_name(t) for t in sorted(important)],
                'missing_core_tones':[tpc_name(t) for t in sorted(important-actual)],
                'scope':'LH pitches across the chord span, not simultaneous voicing or whole-score omission'})
        bars.append({'bar':b,'first_attack':first,'last_attack':last,'attacks':len(activity),
            'attacks_during_melody_rest':[str(t-lo) for t in rest_attacks],'trailing_rest':str(hi-sounding_end),
            'range':[min(m for n in ns for m,t in n.pitches),max(m for n in ns for m,t in n.pitches)] if ns else None,
            'harmony':harmony,'plan':policies.get(b),'unmet_plan':missing_requirements(ns,piece,b,policies[b]) if b in policies else [],
            'entry_in_planned_range':entry_in_range([n for n in ns if lo<=n.onset<hi],policies[b]) if b in policies else None})
    starts={row['bars'][0] for row in design.get('phrase_plan',[])}
    for a,b in zip(bars,bars[1:]):
        x,y=a['last_attack'],b['first_attack']
        boundaries.append({'from_bar':a['bar'],'to_bar':b['bar'],'phrase_boundary':b['bar'] in starts,
            'entry_bass_semitones':b['first_attack']['bass']-a['first_attack']['bass'] if a['first_attack'] and b['first_attack'] else None,
            'last_attack_to_first_bass_semitones':y['bass']-x['bass'] if x and y else None,
            'last_attack_to_first_top_semitones':y['top']-x['top'] if x and y else None,
            'scope':'boundary attack extremes; not a traced bass/inner voice in arpeggios'})
    return {'status':'observations_not_quality_ranking','bars':bars,'boundaries':boundaries,
            'summary':{'harmony_spans':sum(len(b['harmony']) for b in bars),
                'spans_missing_core_tones':sum(bool(h['missing_core_tones']) for b in bars for h in b['harmony']),
                'unmet_plan_bars':[b['bar'] for b in bars if b['unmet_plan'] or b['entry_in_planned_range'] is False]}}
