"""Conservative exact timing for fixed **kern/**harm/**function spines.

Reference: https://www.humdrum.org/rep/kern.html . This is not a general
Humdrum parser. Unsupported spine paths, rhythm syntax and ambiguous timing
are rejected rather than repaired. Grace notes retain their source position
but receive no invented metrical duration.
"""
from fractions import Fraction as F
import re


def duration(token):
    if '%' in token:
        raise ValueError('unsupported_percent_rhythm')
    if 'q' in token or 'Q' in token:
        return F(0)
    match = re.search(r'(\d+)(\.*)', token)
    if not match:
        raise ValueError('missing_explicit_duration')
    digits, dots = match.groups()
    if digits == '0':
        base = F(8)
    elif int(digits) > 0 and not digits.startswith('0'):
        base = F(4, int(digits))
    else:
        raise ValueError('unsupported_zero_rhythm')
    return base * sum((F(1, 2**i) for i in range(len(dots)+1)), F(0))


def annotation_label(token):
    match = re.fullmatch(r'\d+\.*(.+)', token)
    if not match:
        raise ValueError('unsupported_annotation_token')
    return match.group(1)


def parse(text):
    header = None
    events = []
    remain = []
    now = F(0)
    barlines = []
    meters = []
    keys = []
    ended = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line or line.startswith('!!'):
            continue
        fields = line.split('\t')
        if all(t.startswith('!') for t in fields):
            continue
        if line.startswith('**'):
            if header is not None or any(t not in ('**kern','**harm','**function') for t in fields):
                raise ValueError('unsupported_exclusive_header')
            if fields.count('**kern') < 1 or fields.count('**harm') > 1 or fields.count('**function') > 1:
                raise ValueError('ambiguous_spines')
            header = fields; events = [[] for _ in fields]; remain = [F(0) for _ in fields]
            continue
        if header is None:
            raise ValueError('missing_header')
        if len(fields) != len(header):
            raise ValueError('changing_spine_count')
        if any(t in ('*^','*v','*x','*+') for t in fields):
            raise ValueError('spine_path_operation')
        if ended:
            raise ValueError('data_after_termination')
        if all(t == '*-' for t in fields):
            if any(remain):
                raise ValueError('unfinished_duration_at_termination')
            ended = True
            continue
        if any(t.startswith('*') for t in fields):
            if not all(t.startswith('*') for t in fields) or any(t == '*-' for t in fields):
                raise ValueError('mixed_interpretation_or_termination')
            ts = {t for t in fields if re.fullmatch(r'\*M\d+/\d+', t)}
            if len(ts) > 1:
                raise ValueError('conflicting_meter')
            if ts:
                token = next(iter(ts))[2:]
                if not meters and now != 0:
                    raise ValueError('missing_initial_meter')
                beats, unit = map(int, token.split('/'))
                if beats <= 0 or unit <= 0:
                    raise ValueError('invalid_meter')
                if meters and meters[-1]['value'] != token:
                    raise ValueError('changing_meter')
                if not meters:meters.append({'onset':str(now),'value':token,'line':lineno})
            for i, token in enumerate(fields):
                if re.fullmatch(r'\*[A-Ga-g][#-]?:', token):
                    keys.append({'onset':str(now),'spine':i,'raw':token,'line':lineno})
            continue
        if any(t.startswith('=') for t in fields):
            if not all(t.startswith('=') for t in fields) or len(set(fields)) != 1:
                raise ValueError('conflicting_barline')
            if not barlines or barlines[-1]['onset'] != str(now):
                barlines.append({'onset':str(now),'raw':fields[0],'line':lineno})
            continue
        grace = any(('q' in t or 'Q' in t) and kind == '**kern' and t != '.'
                    for kind,t in zip(header,fields))
        durations = []
        for i,(kind,token) in enumerate(zip(header,fields)):
            if token == '.':
                if not grace and remain[i] <= 0:
                    raise ValueError('null_without_sounding_duration')
                durations.append(None)
                continue
            if token.startswith(('!','*','=')):
                raise ValueError('mixed_data_record')
            chord = token.split(' ') if kind == '**kern' else [token]
            values = {duration(n) for n in chord}
            if len(values) != 1:
                raise ValueError('unequal_chord_durations')
            d = values.pop()
            if grace and d != 0:
                raise ValueError('mixed_grace_and_metric_attack')
            if d and remain[i] > 0:
                raise ValueError('overlapping_spine_duration')
            if kind != '**kern' and d == 0:
                raise ValueError('zero_duration_annotation')
            row = {'onset':str(now),'duration':str(d),'raw':token,'line':lineno,'grace':d==0}
            if kind != '**kern':row['label'] = annotation_label(token)
            events[i].append(row)
            durations.append(d)
        if grace:
            continue
        for i,d in enumerate(durations):
            if d is not None:remain[i] = d
        if not all(r > 0 for r in remain):
            raise ValueError('uncovered_spine')
        step = min(remain)
        now += step
        remain = [r-step for r in remain]
    if not ended or not meters or now <= 0:
        raise ValueError('incomplete_or_unmetered_score')
    beats, unit = map(int,meters[0]['value'].split('/'))
    bar_length = F(4*beats,unit)
    starts = [{'onset':'0','raw':None,'line':None}] if not barlines or F(barlines[0]['onset'])>0 else []
    starts += [b for b in barlines if F(b['onset'])<now]
    bars = []
    for i,bar in enumerate(starts):
        end = F(starts[i+1]['onset']) if i+1<len(starts) else now
        length = end-F(bar['onset'])
        if length <= 0 or length > bar_length:
            raise ValueError('invalid_bar_span')
        bars.append({**bar,'ordinal':i,'duration':str(length),'full':length==bar_length})
    return {'meter':meters[0]['value'],'span':str(now),'bars':bars,'keys':keys,
            'spines':[{'kind':kind,'events':rows} for kind,rows in zip(header,events)],
            'grace_events':sum(e['grace'] for kind,rows in zip(header,events) if kind=='**kern' for e in rows),
            'repeats':'not-expanded','timing':'exact_written_quarters'}


def validate_alignment(score, joined):
    for key in ('meter','span'):
        if score[key] != joined[key]:raise ValueError('score_annotation_'+key+'_mismatch')
    # Printed labels (e.g. an invisible initial barline or omitted numbering)
    # are preserved separately; temporal boundaries must still match exactly.
    bars = lambda p:[(b['onset'],b['duration']) for b in p['bars']]
    if bars(score) != bars(joined):raise ValueError('score_annotation_barline_mismatch')
    kern = lambda p:[[(e['onset'],e['duration'],e['raw']) for e in s['events']]
                    for s in p['spines'] if s['kind']=='**kern']
    if kern(score) != kern(joined):raise ValueError('score_annotation_note_tokens_mismatch')
    if [s['kind'] for s in joined['spines']].count('**harm') != 1 or [s['kind'] for s in joined['spines']].count('**function') != 1:
        raise ValueError('missing_annotation_spines')
    return True
