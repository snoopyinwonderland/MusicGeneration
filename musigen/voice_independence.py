"""Optional written-voice observations, not a contrapuntal quality score.

Motivation: 2026-11-11 listening feedback about similar hand contours and
unprepared non-chord tones. Never forbid all similar motion or count ornaments
as a quality target. Outer envelopes are not inferred inner voices.
"""
from collections import Counter
from fractions import Fraction as F
from musigen.musical_checks import chord_at


def contour(piece, lower='bass', lower_voice=None):
    if lower not in ('bass', 'top'):
        raise ValueError('왼손 윤곽은 bass 또는 top으로 지정하세요')
    rh = [n for n in piece.notes if n.hand == 'rh' and n.voice == 1]
    lh = [n for n in piece.notes if n.hand == 'lh' and (lower_voice is None or n.voice == lower_voice)]
    notes = rh + lh
    attacks = {n.onset for n in notes}
    boundaries = sorted(attacks | {n.onset+n.dur for n in notes})
    rows, previous = [], None
    overlap = F(0)
    for i, t in enumerate(boundaries):
        upper = [m for n in rh if n.onset <= t < n.onset+n.dur for m, _ in n.pitches]
        lower_pitches = [m for n in lh if n.onset <= t < n.onset+n.dur for m, _ in n.pitches]
        if not upper or not lower_pitches:
            previous = None  # A release-only silence must break the comparison.
            continue
        if i+1 < len(boundaries):
            overlap += boundaries[i+1]-t
        current = (t, max(upper), (min if lower == 'bass' else max)(lower_pitches))
        if t not in attacks:
            if previous is not None and current[1:] != previous[1:]:
                previous = None
            continue
        if previous is not None:
            dt, a, b = previous
            du, dl = current[1]-a, current[2]-b
            # A chord release coinciding with an RH attack can expose an already
            # held bass. That envelope drop is not a new LH melodic attack.
            if dl and not any(n.onset == t and current[2] in [m for m,_ in n.pitches] for n in lh):
                previous = current
                continue
            motion = ('stationary' if du == dl == 0 else 'oblique' if du*dl == 0
                      else 'similar' if du*dl > 0 else 'contrary')
            rows.append({'from': str(dt), 'to': str(t), 'bar': piece.bar_of(t),
                         'upper_semitones': du, 'lower_semitones': dl, 'motion': motion,
                         'parallel_perfect': motion == 'similar' and
                         (a-b) % 12 in (0, 7) and (current[1]-current[2]) % 12 == (a-b) % 12})
        previous = current
    counts = Counter(r['motion'] for r in rows)
    return {'scope': 'RH voice 1 upper envelope vs LH '+lower+' envelope; rests/released extrema break runs',
            'lower_voice':lower_voice,
            'both_sounding_quarters': str(overlap), 'compared_transitions': len(rows),
            'counts': dict(counts), 'both_moving': counts['similar']+counts['contrary'],
            'parallel_perfect_count': sum(r['parallel_perfect'] for r in rows), 'events': rows}


def embellishments(piece):
    """Classify contiguous three-note gestures at RH attacks against written chords.

    No beat-strength, suspension or phrase inference. A chromatic approach may
    target the next harmony; a passing/neighbor classification requires one
    harmony throughout all three attacks. Chord extensions remain chord tones.
    """
    notes = sorted((n for n in piece.notes if n.hand == 'rh' and n.voice == 1), key=lambda n:n.onset)
    if any(len(n.pitches) != 1 for n in notes):
        raise ValueError('장식음 관찰에는 단선율 오른손 1성부가 필요합니다')
    if any(a.onset+a.dur > b.onset for a,b in zip(notes,notes[1:])):
        raise ValueError('단선율 음 사건이 겹칩니다. 붙임줄을 먼저 합치세요')
    chords = piece.analysis_chords or piece.chords
    rows = []
    for i, n in enumerate(notes):
        ch = chord_at(chords,n.onset)
        if ch is None:
            continue
        pitch = n.pitches[0][0]
        tones = {pc for pc,_ in ch.tones}
        if pitch % 12 in tones:
            continue
        a = notes[i-1] if i else None
        b = notes[i+1] if i+1 < len(notes) else None
        incoming = pitch-a.pitches[0][0] if a else None
        outgoing = b.pitches[0][0]-pitch if b else None
        contiguous = bool(a and b and a.onset+a.dur == n.onset and n.onset+n.dur == b.onset)
        same = bool(a and b and chord_at(chords,a.onset) == ch == chord_at(chords,b.onset))
        anchors = bool(a and b and a.pitches[0][0] % 12 in tones and b.pitches[0][0] % 12 in tones)
        kind = 'unclassified'
        if contiguous and same and anchors and 0 < abs(incoming) <= 2 and 0 < abs(outgoing) <= 2:
            kind = 'passing' if incoming*outgoing > 0 else 'neighbor' if incoming == -outgoing else 'unclassified'
        target = chord_at(chords,b.onset) if b else None
        if kind == 'unclassified' and b and n.onset+n.dur == b.onset and abs(outgoing) == 1 and target and b.pitches[0][0] % 12 in {pc for pc,_ in target.tones}:
            kind = 'chromatic_approach'
        rows.append({'bar':piece.bar_of(n.onset),'onset':str(n.onset),'pitch':pitch,
                     'chord':ch.symbol,'kind':kind,'contiguous_three_notes':contiguous,
                     'incoming_semitones':incoming,'outgoing_semitones':outgoing,
                     'next_onset':str(b.onset) if b else None})
    return {'scope':'RH voice 1 attacks only; written chord membership, not all sustained dissonances',
            'counts':dict(Counter(r['kind'] for r in rows)), 'events':rows}
