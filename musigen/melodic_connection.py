"""Descriptive boundary observations for a monophonic right-hand melody.

No thresholds, quality score, ranking, or automatic rewrite. A large interval
can be intentional; only listening can decide whether a connection works.
"""
from fractions import Fraction
from statistics import median


def connections(piece):
    notes = sorted((n for n in piece.notes if n.hand == 'rh'), key=lambda n: n.onset)
    if any(len(n.pitches) != 1 for n in notes):
        raise ValueError('연결 관찰은 단선율 오른손을 대상으로 합니다')
    if any(a.onset+a.dur > b.onset for a, b in zip(notes, notes[1:])):
        raise ValueError('겹치는 오른손 성부를 임의로 하나로 고르지 않습니다')
    rows = []
    for bar in range(2, piece.bars+1):
        boundary = piece.bar_start(bar)
        before = [n for n in notes if n.onset < boundary]
        after = [n for n in notes if boundary <= n.onset < piece.bar_end(bar)]
        prior = [n for n in before if n.onset >= piece.bar_start(bar-1)]
        row = dict(bar=bar, prior_attacks=len(prior), attacks=len(after),
                   durations=sorted({str(n.dur) for n in after}, key=Fraction))
        if before and after:
            a, b = before[-1], after[0]
            row.update(join_semitones=b.pitches[0][0]-a.pitches[0][0],
                       gap_quarters=str(b.onset-a.onset-a.dur),
                       first_pitches=[n.pitches[0][0] for n in after[:5]])
        if prior and after:
            row['median_duration_ratio'] = str(median(n.dur for n in after)/median(n.dur for n in prior))
        row['largest_internal_interval'] = max((abs(b.pitches[0][0]-a.pitches[0][0])
                                               for a, b in zip(after, after[1:])), default=0)
        rows.append(row)
    return rows


def compare_connections(a, b):
    if a.bars != b.bars or a.bar_len != b.bar_len:
        raise ValueError('같은 마디 길이와 수를 가진 두 악보가 필요합니다')
    return {'interpretation': 'descriptive_only_not_quality_or_selection',
            'a': connections(a), 'b': connections(b)}
