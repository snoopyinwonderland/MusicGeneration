"""ROUND1 P2: score similarity, not a perceptual recognition claim.
Weights .6/.4 and thresholds .5/.75/.85 are provisional, specified in the handoff.
All windows (denominator) are reported; no repeated threshold fitting to the example pieces.
"""
from collections import Counter
from statistics import mean
from musigen.motif import _ladder, _index
from musigen.notation import length
from musigen.checks import motif_of, _hand

def score_window(ref, notes, piece, invert=False):
    # Each realised note uses its own block's key, so a key change does not invent
    # a large chromatic jump in an otherwise diatonic transposition.
    ri=[_index(_ladder(piece.key),e.pitches[-1]) for e in ref if not e.rest]
    ni=[_index(_ladder(piece.bar_keys.get(piece.bar_of(n.onset),piece.key)),
               n.pitches[0 if n.hand=="lh" else -1][0]) for n in notes]
    rd=[b-a for a,b in zip(ri,ri[1:])]; nd=[b-a for a,b in zip(ni,ni[1:])]
    pitch=1-mean(min(abs(a-b),3)/3 for a,b in zip(rd,nd))
    inverted=1-mean(min(abs(a+b),3)/3 for a,b in zip(rd,nd))
    is_inverted=invert and inverted>pitch
    if is_inverted: pitch=inverted
    ref_len=float(length(ref)); win_len=float(notes[-1].onset+notes[-1].dur-notes[0].onset)
    r=[float(e.dur)/ref_len for e in ref if not e.rest]
    v=[float(n.dur)/win_len for n in notes]
    rhythm=max(0,1-.5*sum(abs(a-b) for a,b in zip(r,v)))
    return {"pitch":round(pitch,4),"rhythm":round(rhythm,4),"score":round(.6*pitch+.4*rhythm,4),
            "inverted":is_inverted}

def measure(piece, design):
    result={"thresholds":{"low":.5,"heard":.75,"hidden":.85,"status":"잠정"},
            "occurrences":[],"hidden":[],"distributions":{},"sections":[]}
    for mid,ref in piece.motifs.items():
        count=sum(not e.rest for e in ref)
        if count<3: continue
        all_scores=[]
        for vn in (1,2,5,6):
            voice=[n for n in piece.notes if n.voice==vn]
            # Explicit appearances are maximal provenance runs, chunked for a
            # directly repeated identical motif. Short fragments stay unscored.
            starts={}; i=0
            while i<len(voice):
                if motif_of(voice[i].src)!=mid:
                    i+=1; continue
                j=i+1
                while j<len(voice) and voice[j].src==voice[i].src and voice[j].onset==voice[j-1].onset+voice[j-1].dur: j+=1
                for k in range(i,j,count): starts[k]=min(count,j-k)
                i=j
            for i in range(max(0,len(voice)-count+1)):
                window=voice[i:i+count]
                inv=any("|invert" in n.src for n in window)
                metric=score_window(ref,window,piece,inv)
                all_scores.append(metric["score"])
                base={"motif":mid,"bar":piece.bar_of(window[0].onset),"hand":window[0].hand,
                      "voice":vn,"onset":str(window[0].onset),"how":window[0].src,
                      "bars":sorted({piece.bar_of(n.onset) for n in window}),**metric}
                if starts.get(i)==count:
                    result["occurrences"].append(base)
                if all(motif_of(n.src) is None and n.src.split("|")[0]=="lit" for n in window) and metric["score"]>=.85:
                    result["hidden"].append(base)
            for i,n in starts.items():
                if n<count:
                    result["occurrences"].append({"motif":mid,"bar":piece.bar_of(voice[i].onset),
                        "hand":voice[i].hand,"voice":vn,"how":voice[i].src,"score":None,
                        "bars":sorted({piece.bar_of(x.onset) for x in voice[i:i+n]}),
                        "reason":"동기의 일부만 있어 전체 길이 점수는 미평가"})
        hist=Counter("0-.5" if s<.5 else ".5-.75" if s<.75 else ".75-.85" if s<.85 else ".85-1" for s in all_scores)
        result["distributions"][mid]={"windows":len(all_scores),"histogram":{k:hist[k] for k in ("0-.5",".5-.75",".75-.85",".85-1")},
                                      "min":min(all_scores,default=None),"max":max(all_scores,default=None)}
    for sec in design["form"]:
        a,z=sec["bars"]; a=0 if a==1 and piece.pickup else a
        source={piece.bar_of(n.onset) for n in piece.notes if a<=piece.bar_of(n.onset)<=z and motif_of(n.src) in piece.motifs}
        # Include all qualifying windows, not only tagged/hidden ones.
        heard=set()
        for ref in piece.motifs.values():
            size=sum(not e.rest for e in ref)
            if size<3: continue
            for vn in (1,2,5,6):
                voice=[n for n in piece.notes if n.voice==vn]
                for i in range(len(voice)-size+1):
                    w=voice[i:i+size]
                    if score_window(ref,w,piece,any("|invert" in n.src for n in w))["score"]>=.75:
                        heard.update(piece.bar_of(n.onset) for n in w if a<=piece.bar_of(n.onset)<=z)
        result["sections"].append({"label":sec["label"],"bars":[a,z],"source_bars":len(source),"score_bars":len(heard)})
    return result
