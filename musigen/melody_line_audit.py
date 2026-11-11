"""Opt-in, bounded claims about long repetition and corpus similarity.

This detects contiguous note sequences, not semantic plagiarism or every kind of
musical similarity. Thresholds determine report coverage, not quality coefficients.
Repetition can be purposeful thematic return: counts are never rejection gates.
No score or default composer is changed by this module.
"""
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import zlib

from musigen.melody_evidence import features, unpacked


def signature(events):
    first, pitch = events[0][0], events[0][2]
    return tuple((t-first, d, p-pitch) for t, d, p in events)


def internal(events, bar_length, bars):
    """Compare complete 2/4/8-bar windows; short/single-tone cells are not phrases."""
    events = sorted(events)
    matches = []
    for width in (2, 4, 8):
        windows = []
        for start in range(bars-width+1):
            lo, hi = start*bar_length, (start+width)*bar_length
            selected = [(max(t, lo)-lo, min(t+d, hi)-max(t, lo), p)
                        for t,d,p in events if t < hi and t+d > lo]
            # Preserve leading silence and final duration, not just attacks.
            if len(selected) < 4:
                continue
            pitch = selected[0][2]
            sig = tuple((t,d,p-pitch) for t,d,p in selected)
            for old, old_sig, old_pitch in windows:
                if start-old >= width and sig == old_sig:
                    matches.append({'bars': width, 'first': old+1, 'second': start+1,
                                    'kind': 'exact' if pitch == old_pitch else 'transposed',
                                    'semitones': pitch-old_pitch})
            windows.append((start, sig, pitch))
    approximate = []
    for a in range(len(events)-15):
        first = events[a:a+16]
        if first[-1][0]+first[-1][1]-first[0][0] < 2*bar_length:
            continue
        for b in range(a+16,len(events)-15):
            second = events[b:b+16]
            if second[0][0] < first[-1][0]+first[-1][1]:
                continue
            detail = near(first,second)
            if detail is not None:
                approximate.append({'first_onset':str(first[0][0]),'second_onset':str(second[0][0]),
                                    'notes':16,**detail})
    return {'window_unit': 'notated_bars_not_inferred_phrases',
            'interpretation':'observations_for_composer_review_not_repetition_penalty',
            'long_repeats': matches,
            'near_repeats':approximate,
            'facts': features(events)}


class Matcher:
    """Aho–Corasick over signed intervals; no corpus-sized window index in RAM."""
    def __init__(self, patterns):
        self.next, self.fail, self.outputs = [{}], [0], [[]]
        for pattern, value in patterns:
            state = 0
            for token in pattern:
                if token not in self.next[state]:
                    self.next[state][token] = len(self.next)
                    self.next.append({}); self.fail.append(0); self.outputs.append([])
                state = self.next[state][token]
            self.outputs[state].append((len(pattern), value))
        queue = deque(self.next[0].values())
        while queue:
            state = queue.popleft()
            for token, child in self.next[state].items():
                queue.append(child)
                fallback = self.fail[state]
                while fallback and token not in self.next[fallback]:
                    fallback = self.fail[fallback]
                self.fail[child] = self.next[fallback].get(token, 0)
                self.outputs[child].extend(self.outputs[self.fail[child]])

    def find(self, sequence):
        state = 0
        for i, token in enumerate(sequence):
            while state and token not in self.next[state]:
                state = self.fail[state]
            state = self.next[state].get(token, 0)
            for length, value in self.outputs[state]:
                yield i-length+1, value


def rhythm_error(a, b):
    """Uniform tempo scaling allowed; both onset spacing AND note lengths tested."""
    span_a, span_b = a[-1][0]-a[0][0], b[-1][0]-b[0][0]
    if not span_a or not span_b:
        return float('inf')
    scale = span_a/span_b
    ratios = []
    for i in range(len(a)):
        da, db = a[i][1], b[i][1]*scale
        ratios.append(float(abs(da-db)/max(da, db)))
        if i:
            da, db = a[i][0]-a[i-1][0], (b[i][0]-b[i-1][0])*scale
            ratios.append(float(abs(da-db)/max(da, db)))
    return max(ratios)


def near(a, b, tolerance=.12):
    if len(a) != len(b):
        return None
    shifts = Counter(y[2]-x[2] for x,y in zip(a,b))
    shift, count = shifts.most_common(1)[0]
    edits = len(a)-count
    if edits > 1:
        return None
    error = rhythm_error(a,b)
    if error > tolerance:
        return None
    return {'changed_pitch_notes': edits, 'transposition': shift, 'max_rhythm_relative_error': error}


def _initialize_scan(patterns, windows, max_examples):
    global _matcher, _windows, _max_examples
    _matcher, _windows, _max_examples = Matcher(patterns), windows, max_examples


def _scan_rows(rows):
    counts, results = Counter(), {}
    for path, source, track, role, raw in rows:
        counts['lines_scanned'] += 1
        counts['role/' + role] += 1
        data = json.loads(zlib.decompress(raw))
        pitches = [n[2] for n in data]
        counts['attacks_scanned'] += len(pitches)
        verified, decoded = set(), {}
        for pos, (index, offset) in _matcher.find(b-a for a,b in zip(pitches,pitches[1:])):
            start = pos-offset
            name, at, query, length = _windows[index]
            if start < 0 or start+length > len(data) or (index,start) in verified:
                continue
            verified.add((index,start))
            counts['seed_candidates_verified'] += 1
            shifts = Counter(pitches[start+i]-query[i][2] for i in range(length))
            if max(shifts.values()) < length-(length==16):
                continue
            key = (start,length)
            if key not in decoded:
                decoded[key] = unpacked(data[start:start+length])
            detail = near(query,decoded[key], tolerance=0 if length==12 else .12)
            if detail is None:
                continue
            result = results.setdefault(name, {'match_count':0, 'matches':[]})
            result['match_count'] += 1
            if len(result['matches']) < _max_examples:
                result['matches'].append({'query_note':at, 'query_onset':str(query[0][0]),
                    'source_note':start, 'notes':length, 'path':path, 'source':source,
                    'track':track, 'role':role, **detail})
    return counts, results


def scan(queries, databases, target, max_examples=50, workers=1):
    """12-note exact/transposed + 16-note single-pitch-change, ≥2 query bars.

    Three disjoint 5-interval seeds guarantee a candidate for one changed pitch
    in a 16-note passage. Insertions/deletions and arbitrary ornamentation are
    outside this detector. Performance timing tolerance is explicitly reported.
    """
    if workers < 1:
        raise ValueError('workers must be positive')
    started=time.monotonic()
    query_hash=hashlib.sha256(json.dumps(queries,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    progress=Path(target).with_suffix('.progress.json')
    progress.write_text(json.dumps({'status':'running','queries_sha256':query_hash}),encoding='utf-8')
    patterns, windows = [], []
    reports = {}
    for name, query in queries.items():
        events, bar = unpacked(query['events']), F(query['bar_length'])
        reports[name] = {'internal': internal(events, bar, query['bars']), 'matches': [], 'match_count': 0}
        for length in (12,16):
            for at in range(len(events)-length+1):
                notes = events[at:at+length]
                if notes[-1][0]+notes[-1][1]-notes[0][0] < 2*bar:
                    continue
                intervals = [b[2]-a[2] for a,b in zip(notes,notes[1:])]
                index = len(windows)
                windows.append((name, at, notes, length))
                if length == 12:
                    patterns.append((intervals, (index,0)))
                else:
                    for offset in (0,5,10):
                        patterns.append((intervals[offset:offset+5], (index,offset)))
    seen, counts, snapshots = set(), Counter(), []
    def batches():
        for database in databases:
            db = sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)
            try:
                db.execute('BEGIN')
                snapshots.append({'path':str(Path(database).resolve()),
                    'indexed_lines':db.execute('SELECT count(*) FROM lines').fetchone()[0],
                    'files_statuses':dict(db.execute('SELECT status,count(*) FROM files GROUP BY status'))})
                batch = []
                for fp,*row in db.execute('SELECT fingerprint,path,source,track,role,events FROM lines'):
                    if fp in seen:
                        counts['duplicate_lines_across_databases'] += 1
                        continue
                    seen.add(fp)
                    batch.append(row)
                    if len(batch) == 128:
                        yield batch
                        batch = []
                if batch:
                    yield batch
            finally:
                db.close()

    def merge(result):
        batch_counts, batch_results = result
        counts.update(batch_counts)
        for name, row in batch_results.items():
            target_row = reports[name]
            target_row['match_count'] += row['match_count']
            target_row['matches'].extend(row['matches'][:max_examples-len(target_row['matches'])])
        progress.write_text(json.dumps({'status':'running','queries_sha256':query_hash,
            'lines_scanned':counts['lines_scanned'],'seconds':round(time.monotonic()-started)}),encoding='utf-8')

    if workers == 1:
        _initialize_scan(patterns, windows, max_examples)
        for batch in batches():
            merge(_scan_rows(batch))
    else:
        # Bounded FIFO preserves example order and avoids materializing the corpus.
        with ProcessPoolExecutor(max_workers=workers, initializer=_initialize_scan,
                                 initargs=(patterns,windows,max_examples)) as pool:
            iterator, pending = iter(batches()), deque()
            for _ in range(workers*2):
                batch = next(iterator,None)
                if batch is not None:
                    pending.append(pool.submit(_scan_rows,batch))
            while pending:
                merge(pending.popleft().result())
                batch = next(iterator,None)
                if batch is not None:
                    pending.append(pool.submit(_scan_rows,batch))
    report = {'format': 'musicanote-melody-audit', 'version': 1,
              'queries_sha256':query_hash,'database_snapshots':snapshots,
              'scope': 'contiguous symbolic windows; not universal originality or legal clearance',
              'criteria': {'exact_notes':12,'near_notes':16,'near_changed_pitch_notes':1,
                           'near_max_rhythm_relative_error':.12,'minimum_query_bars':2,
                           'uniform_tempo_scale':True,'report_example_cap_per_piece':max_examples},
              'coverage': dict(counts), 'pieces': reports}
    Path(target).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    progress.write_text(json.dumps({'status':'complete','queries_sha256':query_hash,
        'lines_scanned':counts['lines_scanned'],'seconds':round(time.monotonic()-started)}),encoding='utf-8')
    return {'coverage':dict(counts),'matches':{k:v['match_count'] for k,v in reports.items()}}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description='새 선율의 긴 반복과 보유 자료의 연속 음형 비교')
    p.add_argument('--queries',type=Path,required=True)
    p.add_argument('--database',type=Path,action='append',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=1)
    a=p.parse_args()
    print(json.dumps(scan(json.loads(a.queries.read_text(encoding='utf-8')),a.database,a.out,workers=a.workers)))
