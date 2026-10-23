"""Local musical observations; ROUND1 thresholds are provisional, not style laws."""
from fractions import Fraction as F
from statistics import mean
from musigen.design import beat
from musigen.motif import _index, _ladder

def top(n): return max(m for m,_ in n.pitches)
def bottom(n): return min(m for m,_ in n.pitches)
def degree(m,key): return _index(_ladder(key),m)
def chord_at(chords,t):
    return next((c for on,c in reversed(chords) if on<=t),None)
def active(notes,t): return [n for n in notes if n.onset<=t<n.onset+n.dur]
def evaluate(p,d):
    warnings=[]; notes=[]; events=[]; sections=[]
    chords=p.analysis_chords or p.chords
    rh=[n for n in p.notes if n.hand=="rh" and n.voice==1]
    def emit(kind,bar,hand,msg,warning=False):
        text=f"{bar}마디 {hand}: {msg}"
        (warnings if warning else notes).append(text)
        events.append({'kind':kind,'bar':bar,'hand':hand,'level':'warnings' if warning else 'notes','message':text})
    # Evaluate beat starts, including notes held across a chord change.
    seen=set(); bt=beat(p.meter)
    for bar in range(0 if p.pickup else 1,p.bars+1):
        if chord_at(chords,p.bar_start(bar)) is None:
            emit("harmony_unknown",bar,"양손","화음 기호가 없어 화성·병행 검사를 일부 생략")
        t=p.bar_start(bar)
        while t<p.bar_end(bar):
            ch=chord_at(chords,t)
            for n in active(rh,t):
                pitch=top(n)
                if not ch or (n.onset,ch.symbol) in seen: continue
                seen.add((n.onset,ch.symbol))
                allowed={pc for pc,_ in ch.tones}
                if ch.quality in ('','m'): allowed.add((ch.tones[0][0]+2)%12)
                if pitch%12 in allowed: continue
                i=rh.index(n); prev=rh[i-1] if i else None; nxt=rh[i+1] if i+1<len(rh) else None
                key=p.bar_keys.get(bar,p.key); out=degree(top(nxt),key)-degree(pitch,key) if nxt else None
                incoming=degree(pitch,key)-degree(top(prev),key) if prev else None
                # Resolution must be a chord tone, not merely a coincidental step.
                resolves=nxt is not None and top(nxt)%12 in {pc for pc,_ in ch.tones}
                old=chord_at(chords,n.onset)
                label=None
                if n.onset<t and old and pitch%12 in {pc for pc,_ in old.tones} and out==-1 and resolves: label='계류음'
                elif incoming is not None and abs(incoming)>1 and out is not None and abs(out)==1 and resolves: label='전타음'
                elif incoming in (-1,1) and out==incoming and resolves: label='경과음'
                emit('nonchord',bar,'오른손',f"강박 비화성음 {pitch} / {ch.symbol}: {label or '해결 형태 미분류'}",label is None)
            t+=bt
    # Outer voices at consecutive attacks; held notes participate until their release.
    outer=[]
    for t in sorted({n.onset for n in p.notes}):
        rr=active([n for n in p.notes if n.hand=='rh'],t)
        ll=active([n for n in p.notes if n.hand=='lh'],t)
        if rr and ll: outer.append((t,max(top(n) for n in rr),min(bottom(n) for n in ll),chord_at(chords,t)))
        else: outer.append((t,None,None,None))
    for a,b in zip(outer,outer[1:]):
        if a[1] is None or b[1] is None or not a[3] or not b[3] or a[3].symbol==b[3].symbol: continue
        up,down=b[1]-a[1],b[2]-a[2]
        iv=(a[1]-a[2])%12
        if up*down>0 and iv in (0,7) and (b[1]-b[2])%12==iv:
            emit('parallel',p.bar_of(b[0]),'양손',f"병행 {'8' if iv==0 else '5'}도 ({p.bar_of(a[0])}→{p.bar_of(b[0])}마디)",True)
    rhythms=[]
    for bar in range(1,p.bars+1):
        ns=[n for n in rh if n.onset<p.bar_end(bar) and n.onset+n.dur>p.bar_start(bar)]
        excluded=any(n.src.startswith('copy:') or '|seq:' in n.src for n in ns)
        sig=tuple((max(n.onset,p.bar_start(bar))-p.bar_start(bar),min(n.onset+n.dur,p.bar_end(bar))-max(n.onset,p.bar_start(bar))) for n in ns)
        rhythms.append(None if excluded or not ns else sig)
    i=0
    while i<len(rhythms):
        j=i+1
        while j<len(rhythms) and rhythms[i] is not None and rhythms[j]==rhythms[i]: j+=1
        if j-i>=4: emit('rhythm',i+1,'오른손',f"{i+1}–{j}마디의 리듬이 같음(반복 의도 확인, 잠정)")
        i=j
    for s in d['form']:
        a,z=s['bars']; ns=[n for n in rh if a<=p.bar_of(n.onset)<=z]
        pitches=[top(n) for n in ns]
        cs=[]
        first=chord_at(chords,p.bar_start(a))
        if first: cs.append(first)
        for on,ch in chords:
            if ch and p.bar_start(a)<on<p.bar_end(z) and (not cs or cs[-1].symbol!=ch.symbol): cs.append(ch)
        keys=sorted({str(p.bar_keys.get(b,p.key)) for b in range(a,z+1)})
        row={'label':s.get('label'),'bars':[a,z],'mean_pitch':round(mean(pitches),3) if pitches else None,
             'range':[min(pitches),max(pitches)] if pitches else None,'density':len(ns)/(z-a+1),
             'chord_changes_per_bar':max(0,len(cs)-1)/(z-a+1),'keys':keys}
        if s['function']=='contrast' and sections:
            prev=sections[-1]
            if pitches and prev['mean_pitch'] is not None and abs(row['mean_pitch']-prev['mean_pitch'])<2 and abs(row['density']-prev['density'])/max(prev['density'],1e-9)<.15 and row['keys']==prev['keys']:
                emit('contrast',a,'오른손',f"{a}–{z}마디 대조 구간의 음역·밀도·조성이 앞 구간과 유사(2반음/15% 잠정)",True)
        cadence=s.get('cadence','none')
        if cadence!='none':
            key=p.bar_keys.get(z,p.key); tonic=key.tonic_pc
            roots=[(c.tones[0][0]-tonic)%12 for c in cs]
            pair=roots[-2:]
            tonic_tones={tonic,(tonic+(3 if key.minor else 4))%12,(tonic+7)%12}
            ok=(bool(roots) and roots[-1]==7) if cadence=='half' else pair==([7,0] if cadence=='authentic' else [5,0] if cadence=='plagal' else [7,8 if key.minor else 9])
            if cadence=='authentic': ok=ok and bool(pitches) and pitches[-1]%12 in tonic_tones
            if chord_at(chords,p.bar_end(z)-F(1,10000)) is None:
                emit('cadence_unknown',z,'양손','마지막 화음 기호가 없어 종지 의도 미평가')
                sections.append(row)
                continue
            if not ok: emit('cadence',z,'양손',f"구간 끝이 설계한 { {'authentic':'정격','half':'반','plagal':'변격','deceptive':'위장'}[cadence]}종지와 다름",True)
        sections.append(row)
    return {'warnings':warnings,'notes':notes,'events':events,'sections':sections}
