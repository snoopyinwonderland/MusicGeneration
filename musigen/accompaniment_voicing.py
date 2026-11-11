"""Conservative, opt-in pitch substitutions after corpus selection.

No inferred harmony, learned weights or work-specific exceptions. A monotone local
search retains attack timing, rests, first basses and protected authored material.
Unsolvable constraints remain explicit; this is not a complete voicing solver.
"""
from dataclasses import replace
from fractions import Fraction

from musigen.accompaniment_context import missing_requirements, entry_in_range
from musigen.musical_checks import parallel_events


def _missing(notes,piece,bar,policy):
    return {(r['onset'],t) for r in missing_requirements(notes,piece,bar,policy) for t in r['missing_tpcs']}


def _spans(piece,bar):
    lo,hi=piece.bar_start(bar),piece.bar_end(bar)
    chords=piece.analysis_chords or piece.chords
    for i,(on,ch) in enumerate(chords):
        end=chords[i+1][0] if i+1<len(chords) else piece.bar_end(piece.bars)
        start,stop=max(lo,on),min(hi,end)
        if start<stop:yield start,stop,ch


def _edits(notes,piece,bar,policy,prof):
    """One chord-tone substitution, within one octave of its current pitch.

    Keep the exact lowest pitch of the first LH attack in every harmony span.
    Do not rewrite existing non-chord tones or tones held over unknown harmony.
    """
    from musigen.corpus_accomp import _reject
    spans=list(_spans(piece,bar));anchors={}
    for start,stop,ch in spans:
        ns=[(i,n) for i,n in enumerate(notes) if start<=n.onset<stop]
        if ns:
            at=min(n.onset for i,n in ns)
            anchors[at]=min(m for i,n in ns if n.onset==at for m,t in n.pitches)
    for i,n in enumerate(notes):
        covering=[(start,stop,ch) for start,stop,ch in spans if n.onset<stop and n.onset+n.dur>start]
        if sum(min(stop,n.onset+n.dur)-max(start,n.onset) for start,stop,ch in covering)!=n.dur:continue
        overlapping=[ch for start,stop,ch in covering]
        if not overlapping or any(ch is None for ch in overlapping):continue
        allowed=set(overlapping[0].tones)
        for ch in overlapping[1:]:allowed.intersection_update(ch.tones)
        for j,(old,tpc) in enumerate(n.pitches):
            if old==anchors.get(n.onset) or (old%12,tpc) not in allowed:continue
            for pc,t in sorted(allowed):
                for m in range(max(28,old-12),min(69,old+12)+1):
                    if m%12!=pc or (m,t)==(old,tpc):continue
                    pitches=list(n.pitches);pitches[j]=(m,t);pitches=tuple(sorted(pitches))
                    if len({x for x,t in pitches})!=len(pitches):continue
                    if n.onset in anchors and min(x for x,t in pitches)<anchors[n.onset]:continue
                    candidate=list(notes);candidate[i]=replace(n,pitches=pitches)
                    if _reject(candidate,piece,bar,prof) or not entry_in_range(candidate,policy):continue
                    yield candidate,{'bar':bar,'onset':str(n.onset),'from':list(n.pitches),'to':list(pitches),'source':n.src},abs(m-old)


def repair(piece,notes,policies,grade):
    """Return LH and an audit; eligibility is based on the authored pre-search piece."""
    from musigen.corpus_accomp import _protected
    from musicomp.realize.grades import profile
    prof=profile(grade);rh=[n for n in piece.notes if n.hand!='lh']
    current=sorted(notes,key=lambda n:(n.onset,n.voice));original=list(current);requested={b:p for b,p in policies.items() if p.get('repair_voicing',False)}
    eligible={b:p for b,p in requested.items() if _protected(piece,b) is None}
    protected={str(b):_protected(piece,b) for b in requested if b not in eligible}
    def group(ns,b):return [n for n in ns if piece.bar_of(n.onset)==b]
    def substitute(ns,b,new):return sorted([n for n in ns if piece.bar_of(n.onset)!=b]+new,key=lambda n:(n.onset,n.voice))
    def parallels(ns):return set(parallel_events(replace(piece,notes=rh+ns)))
    before_parallel=parallels(current);steps=[];tested=0
    # Each accepted edit strictly reduces a finite set. No fitted cost coefficients.
    for phase in ('required_tones','outer_parallels'):
        while True:
            old_parallel=parallels(current);best=None
            for b,policy in sorted(eligible.items()):
                old=group(current,b);missing=_missing(old,piece,b,policy)
                core=_missing(old,piece,b,{'required_degrees':[3,7]})
                if phase=='required_tones' and not missing:continue
                if phase=='outer_parallels' and not any(piece.bar_start(b)<=t<piece.bar_end(b) for e in old_parallel for t in e[:2]):continue
                for candidate,edit,distance in _edits(old,piece,b,policy,prof):
                    tested+=1;absent=_missing(candidate,piece,b,policy)
                    if not absent<=missing or not _missing(candidate,piece,b,{'required_degrees':[3,7]})<=core:continue
                    if phase=='required_tones' and not absent<missing:continue
                    merged=substitute(current,b,candidate);ps=parallels(merged)
                    if not ps<=old_parallel:continue
                    if phase=='outer_parallels' and not ps<old_parallel:continue
                    key=(len(absent)-len(missing),len(ps),distance,b,Fraction(edit['onset']),edit['to'])
                    if best is None or key<best[0]:best=(key,merged,{**edit,'phase':phase})
            if best is None:break
            _,current,edit=best;steps.append(edit)
    changed=[];corpus=[];fallback=[]
    for b in sorted(eligible):
        if [n.pitches for n in group(original,b)]!=[n.pitches for n in group(current,b)]:
            changed.append(b)
            (corpus if any(n.src.startswith('corpus:') for n in group(original,b)) else fallback).append(b)
    # Keep provenance, marking only pitches actually changed in the frozen snapshot.
    for i,(a,b) in enumerate(zip(original,current)):
        if a.pitches!=b.pitches:current[i]=replace(b,src=b.src+'|voicing')
    def event_rows(events):
        return [{'from_onset':str(a),'to_onset':str(b),'from_bar':piece.bar_of(a),'to_bar':piece.bar_of(b),'interval':8 if iv==0 else 5} for a,b,iv in sorted(events)]
    unresolved=[{'bar':b,'missing':missing_requirements(current,piece,b,p),'entry_in_range':entry_in_range(group(current,b),p)} for b,p in sorted(requested.items())]
    unresolved=[r for r in unresolved if r['missing'] or not r['entry_in_range']]
    return current,{'version':1,'status':'실험 옵션 · 청취 검수 전','requested_bars':sorted(requested),'eligible_bars':sorted(eligible),
        'protected_bars':protected,'changed_bars':changed,'changed_corpus_bars':corpus,'changed_fallback_bars':fallback,
        'steps':steps,'tested_edits':tested,'unresolved_requirements':unresolved,
        'parallel_before':event_rows(before_parallel),'parallel_after':event_rows(parallels(current)),
        'scope':'기존 외성 발음 시각 검사만 사용. 내성 진행·전체 대위법·청취 품질 보장 아님.',
        'search':'한 음씩 ±12반음 이내. 요구 구성음 감소 후 병행 사건 감소. 새 생략·병행 사건 금지. 남은 후보는 변화량·마디·음순으로 결정.',
        'preserved':'음가·발음 시각·쉼·동시음 수·각 화성 구간 첫 최저음·직접 작성 왼손·오른손·화성·표현'}
