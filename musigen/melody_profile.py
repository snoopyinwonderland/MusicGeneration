"""Descriptive source/cohort observations, never a fitted quality score."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import statistics


def summarize(rows):
    counts = Counter()
    ranges, climaxes = [], []
    for facts in rows:
        counts['lines'] += 1
        for key in ('attacks', 'interval_pairs', 'step_pairs', 'repeated_pitch_pairs',
                    'rest_gaps', 'overlap_pairs', 'leaps_with_successor', 'leaps_then_opposite_direction'):
            counts[key] += facts[key]
        ranges.append(facts['pitch_range'])
        if facts['climax_position'] is not None:
            climaxes.append(facts['climax_position'])
    result = dict(counts)
    for key in ('step_pairs', 'repeated_pitch_pairs', 'rest_gaps', 'overlap_pairs'):
        result[key + '_fraction'] = counts[key] / counts['interval_pairs'] if counts['interval_pairs'] else None
    result['leap_reversal_fraction'] = counts['leaps_then_opposite_direction'] / counts['leaps_with_successor'] if counts['leaps_with_successor'] else None
    result['median_pitch_range_semitones'] = statistics.median(ranges) if ranges else None
    result['median_first_climax_relative_onset'] = statistics.median(climaxes) if climaxes else None
    return result


def run(databases, target):
    groups = defaultdict(lambda: {'counts': Counter(), 'ranges': [], 'climaxes': []})
    seen = set()
    # Prefer documented roles over an unknown duplicate from another database.
    for preferred_role in ('documented_melody','named_melody','lyric_voice','single_line_score','unknown_voice'):
        for path in databases:
            db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
            for fingerprint, source, role, features in db.execute('SELECT fingerprint,source,role,features FROM lines WHERE role=?',(preferred_role,)):
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                facts = json.loads(features)
                group = groups[source + ' / ' + role]
                group['counts']['lines'] += 1
                for key in ('attacks', 'interval_pairs', 'step_pairs', 'repeated_pitch_pairs',
                            'rest_gaps', 'overlap_pairs', 'leaps_with_successor', 'leaps_then_opposite_direction'):
                    group['counts'][key] += facts[key]
                group['ranges'].append(facts['pitch_range'])
                if facts['climax_position'] is not None:
                    group['climaxes'].append(facts['climax_position'])
            db.close()
    aggregates = {}
    for key, group in sorted(groups.items()):
        c = group['counts']; row = dict(c)
        for name in ('step_pairs', 'repeated_pitch_pairs', 'rest_gaps', 'overlap_pairs'):
            row[name + '_fraction'] = c[name] / c['interval_pairs'] if c['interval_pairs'] else None
        row['leap_reversal_fraction'] = c['leaps_then_opposite_direction'] / c['leaps_with_successor'] if c['leaps_with_successor'] else None
        row['median_pitch_range_semitones'] = statistics.median(group['ranges'])
        row['median_first_climax_relative_onset'] = statistics.median(group['climaxes']) if group['climaxes'] else None
        aggregates[key] = row
    report = {'scope': 'descriptive line-level aggregates; roles separate; no phrase or quality inference',
              'deduplication':'whole-line transposition/time-shift invariant, exact durations; documented roles first, then database argument order',
              'unique_lines_across_databases': len(seen),
              'groups': aggregates}
    Path(target).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'groups': len(groups), 'lines': len(seen)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='주선율 자료의 출처·역할별 관찰 집계')
    p.add_argument('--database', type=Path, action='append', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.database, a.out)))
