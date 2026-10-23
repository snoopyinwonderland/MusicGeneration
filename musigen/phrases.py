"""Optional melodic phrase observations using the existing musicomp analyser unchanged."""
from fractions import Fraction as F
from musicomp.analysis.motif import analyze_motifs
from musicomp.analysis.phrase import segment_layers
from musicomp.core.score import Melody, Measure, Note


def melody(piece):
    lead = sorted((n for n in piece.notes if n.hand == 'rh' and n.voice == 1), key=lambda n:n.onset)
    if any(len(n.pitches) != 1 for n in lead):
        raise ValueError('프레이즈 분석은 단선율 오른손 첫 성부를 대상으로 합니다')
    if any(a.onset+a.dur > b.onset for a,b in zip(lead,lead[1:])):
        raise ValueError('프레이즈 분석 대상 선율의 음이 겹칩니다')
    notes = [Note(n.onset,n.dur,*n.pitches[0],idx=i) for i,n in enumerate(lead)]
    bars = range(0 if piece.pickup else 1,piece.bars+1)
    measures = [Measure(i,str(b),piece.bar_start(b),piece.bar_end(b)-piece.bar_start(b),piece.bar_len,piece.meter)
                for i,b in enumerate(bars)]
    beats,beat_type = map(int,piece.meter.split('/'))
    return Melody(piece.title,notes,measures,beats,beat_type,piece.key.sharps,
                  'minor' if piece.key.minor else 'major',tempo_qpm=piece.qpm,
                  key_changes=[(piece.bar_start(b),k.sharps) for b,k in sorted(piece.bar_keys.items())])


def analyze(piece, plan=()):
    mel = melody(piece)
    motifs = analyze_motifs(mel,cross_check=False)
    phrases,gaps = segment_layers(mel,piece.key,motifs)  # Melody only: no inferred harmony feedback.
    def printed(index):return int(mel.measures[index].number)
    rows = [{'id':p.id,'bars':[printed(p.first_bar),printed(p.last_bar)],
             'start':float(p.start),'end':float(p.end),'boundary':p.boundary,
             'subphrases':[{'bars':[piece.bar_of(mel.notes[a].onset),piece.bar_of(mel.notes[b].onset)],
                           'start':float(mel.notes[a].onset),'end':float(mel.notes[b].end)} for a,b in p.subphrases]}
            for p in phrases]
    rests=[]
    cursor=F(0)
    for n in mel.notes:
        if n.onset>cursor:rests.append({'start':float(cursor),'end':float(n.onset),'bar':piece.bar_of(cursor)})
        cursor=n.end
    if cursor<mel.total:rests.append({'start':float(cursor),'end':float(mel.total),'bar':piece.bar_of(cursor)})
    boundaries={p['bars'][1] for p in rows}
    planned=[dict(p,detected_end=p['bars'][1] in boundaries) for p in plan]
    result = {'engine':'musicomp.analysis.phrase.segment_layers (melody-only, defaults)',
            'status':'자동 관찰 · 작곡 설계 및 청취 판단과 구분',
            'phrases':rows,'rests':rests,'rest_quarters':sum(r['end']-r['start'] for r in rests),
            'plan':planned,'motifs':motifs.to_json()}

    def plain(value):
        if isinstance(value,F):return float(value)
        if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
        if isinstance(value,(tuple,list)):return [plain(v) for v in value]
        return value
    return plain(result)
