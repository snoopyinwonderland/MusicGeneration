"""Observe written attacks, holds and gaps without prescribing their frequency.

Input times are quarter-note units. Sustained ties must already be merged.
Gaps describe the supplied notes, not pedal/reverb or inferred phrase boundaries.
"""
from fractions import Fraction as F


def gaps(events, end):
    """Complement of sounding intervals, including leading/trailing written rest."""
    end = F(end)
    if end <= 0:
        raise ValueError('악보 길이는 양수여야 합니다')
    intervals = sorted((F(t), F(t)+F(d)) for t,d,*_ in events)
    if any(a < 0 or b <= a or b > end for a,b in intervals):
        raise ValueError('음이 악보 범위를 벗어나거나 음가가 양수가 아닙니다')
    result, cursor = [], F(0)
    for a,b in intervals:
        if a > cursor:
            result.append((cursor,a-cursor))
        cursor = max(cursor,b)
    if cursor < end:
        result.append((cursor,end-cursor))
    return result


def observe(events, bar_length, bars):
    bar = F(bar_length)
    if bar <= 0 or type(bars) is not int or bars < 1:
        raise ValueError('양의 마디 길이와 마디 수가 필요합니다')
    notes = sorted((F(t),F(d),int(p)) for t,d,p in events)
    rests = gaps(notes,bar*bars)
    rows=[]
    for i in range(bars):
        lo,hi=i*bar,(i+1)*bar
        overlap=[(max(t,lo),min(t+d,hi)) for t,d,p in notes if t<hi and t+d>lo]
        local_gaps=gaps([(a-lo,b-a,0) for a,b in overlap],bar)
        silent=sum((d for t,d in local_gaps),F(0))
        rows.append({'bar':i+1,'attacks':sum(lo<=t<hi for t,d,p in notes),
                     'held_from_previous_bar':any(t<lo<t+d for t,d,p in notes),
                     'rest_quarters':str(silent),'occupied_quarters':str(bar-silent)})
    def location(t,d):
        return {'bar':int(t//bar)+1,'offset':str(t%bar),'duration_quarters':str(d)}
    return {'time_unit':'quarter_note','interpretation':'observations_not_a_quality_or_repetition_score',
            'attacks':len(notes),'bars':rows,
            'note_duration_counts':{str(d):sum(n[1]==d for n in notes) for d in sorted({n[1] for n in notes})},
            'longest_note_quarters':str(max((d for t,d,p in notes),default=F(0))),
            'longest_rest_quarters':str(max((d for t,d in rests),default=F(0))),
            'rests':[location(t,d) for t,d in rests],
            'held_across_barline':[location(t,d) for t,d,p in notes if t+d>(int(t//bar)+1)*bar],
            'longest_notes':[{**location(t,d),'midi':p} for t,d,p in sorted(notes,key=lambda n:-n[1])[:5]]}
