"""Opt-in AMT diagnostics; frozen protocol, raw outputs, no automatic selection.

The provisional notation tolerance is declared BEFORE sampling. It is an adapter
constraint, not an estimate of musical quality or of the model's general ability.
"""
from collections import Counter

MODEL = 'stanford-crfm/music-small-800k'
REVISION = 'fa800530aa1126dd6b58b38f3bdb8fcec9c9d4f5'
SOURCE_REVISION = 'af37397922665a0fb8d474d7988b0f3755a38d45'


def protocol():
    return dict(version=1, samples=16, seeds=list(range(16)), top_p=.98,
                quarter_ticks=60, ticks_per_second=100, start_tick=480,
                end_tick=1920, grid_ticks=15, tolerance_ticks=2,
                allowed_pitch_classes=[0, 2, 4, 5, 7, 9, 11],
                pitch_range=[60, 84], program=0, max_events=384,
                seconds_per_candidate=120, min_eligible=4,
                basis='잠정: 100 BPM, 4/4, C장조, 16분음표 격자 ±20ms. '
                      '음 변경·성부 추출·후속 재시도 없이 직접 기보 가능성을 검사한다.',
                user_selected_phrase=False, input_role='author_designated_diagnostic',
                selection=None)


def assess(events, spec, completed=True):
    """events are raw {tick,duration,program,pitch}; never modify them in place."""
    errors = Counter()
    if not completed:
        errors['generation_incomplete'] += 1
    if not events:
        errors['empty_continuation'] += 1
    notation = []
    grid, tolerance = spec['grid_ticks'], spec['tolerance_ticks']
    for event in events:
        onset, duration = event['tick'], event['duration']
        start = ((onset + grid // 2) // grid) * grid
        length = ((duration + grid // 2) // grid) * grid
        if abs(start-onset) > tolerance or abs(length-duration) > tolerance:
            errors['outside_notation_grid'] += 1
        if duration <= 0 or length <= 0:
            errors['nonpositive_duration'] += 1
        if onset < spec['start_tick'] or onset+duration > spec['end_tick']+tolerance:
            errors['outside_six_bar_window'] += 1
        if start < spec['start_tick'] or start+length > spec['end_tick']:
            errors['notation_outside_window'] += 1
        if event['pitch'] % 12 not in spec['allowed_pitch_classes']:
            errors['outside_declared_key'] += 1
        if not spec['pitch_range'][0] <= event['pitch'] <= spec['pitch_range'][1]:
            errors['outside_melody_register'] += 1
        if event['program'] != spec['program']:
            errors['non_piano_program'] += 1
        notation.append({**event, 'tick': start, 'duration': length})
    ordered = sorted(notation, key=lambda e: e['tick'])
    end = spec['start_tick']
    for event in ordered:
        if event['tick'] < end:
            errors['polyphonic_continuation'] += 1
        end = max(end, event['tick']+event['duration'])
    missing = [bar for bar in range(3, 9) if not any(
        (bar-1)*240 <= e['tick'] < bar*240 for e in ordered)]
    if missing:
        errors['empty_continuation_bar'] = len(missing)
    meter_key = not any(errors[k] for k in (
        'generation_incomplete', 'empty_continuation', 'outside_notation_grid',
        'nonpositive_duration', 'outside_six_bar_window', 'notation_outside_window',
        'outside_declared_key', 'empty_continuation_bar'))
    return {'meter_key_eligible': meter_key, 'score_eligible': not errors,
            'reasons': dict(errors), 'raw_note_count': len(events),
            'quantized_events': ordered if not errors else None,
            'missing_bars': missing}


def summarize(rows, spec):
    if len(rows) != spec['samples'] or sorted(r['seed'] for r in rows) != spec['seeds']:
        raise ValueError('16개의 서로 다른 사전 지정 seed 결과가 필요합니다')
    valid = sum(r['assessment']['meter_key_eligible'] for r in rows)
    score_valid = sum(r['assessment']['score_eligible'] for r in rows)
    return {'attempted': len(rows), 'meter_key_eligible': valid,
            'score_eligible': score_valid, 'rejected_for_score': len(rows)-score_valid,
            'stop_gate_reached': valid < spec['min_eligible'],
            'status': 'stopped_below_four' if valid < spec['min_eligible'] else
                      'needs_score_review' if score_valid < 4 else 'needs_p2_checks',
            'user_choice': None, 'automatic_selection': False,
            'reason_candidates': dict(Counter(k for r in rows for k in r['assessment']['reasons']))}
