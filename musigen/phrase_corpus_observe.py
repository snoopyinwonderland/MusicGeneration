"""Observe phrase shapes on the indexed corpus and on explicit annotations.

Heuristic cuts are observations. Explicit phrase annotations form a separate
report. Neither path saves melodies, lyrics or source phrases in its result.
"""
import argparse
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import gzip
import json
from pathlib import Path
import sqlite3
from statistics import median
import time
import zlib

@lru_cache(maxsize=8192)
def number(text):
    n, sep, d = text.partition('/')
    return float(n) / int(d) if sep else float(n)


def observe(notes, segments):
    """Count contour, endings and opening-cell relationships in eligible phrases."""
    counts = Counter()
    first_cells = None
    for start, end in segments:
        if not 4 <= end - start <= 32:
            counts['outside_length_window'] += 1
            continue
        phrase = notes[start:end]
        durs = [d for _,d,_ in phrase]
        steps = [b[2] - a[2] for a,b in zip(phrase, phrase[1:])]
        counts['phrases'] += 1
        counts['contains_repeated_pitch'] += 0 in steps
        counts['contains_leap_ge_five'] += any(abs(step) >= 5 for step in steps)
        counts['long_ending'] += durs[-1] >= 1.5 * median(durs[:-1])
        if end < len(notes):
            counts['internal_endings'] += 1
            silence = notes[end][0] - phrase[-1][0] - durs[-1]
            counts['audible_space_after_end'] += silence >= median(durs) * .5
        directional = [step > 0 for step in steps if step]
        turns = sum(a != b for a,b in zip(directional, directional[1:]))
        if len(directional) == 0:
            counts['stationary'] += 1
        elif turns == 0:
            counts['one_direction'] += 1
        elif turns == 1:
            counts['one_turn'] += 1
        else:
            counts['multiple_turns'] += 1
        intervals = tuple(steps[:3])
        onset_gaps = [phrase[i+1][0]-phrase[i][0] for i in range(3)]
        width = sum(onset_gaps)
        rhythm = tuple(round(24 * gap / width) for gap in onset_gaps)
        if first_cells is None:
            first_cells = (intervals, rhythm)
        else:
            counts['later_openings'] += 1
            same_pitch, same_rhythm = intervals == first_cells[0], rhythm == first_cells[1]
            if same_pitch and same_rhythm:
                counts['same_opening_cell'] += 1
            elif same_rhythm:
                counts['same_opening_rhythm_new_intervals'] += 1
            elif same_pitch:
                counts['same_opening_intervals_new_rhythm'] += 1
    return counts


def unpack(raw):
    return [(number(on), number(dur), pitch) for on, dur, pitch in raw]


def observe_batch(batch):
    groups = defaultdict(Counter)
    for source, role, basis, blob in batch:
        seconds = source == 'weimar' or 'seconds' in basis.lower()
        group = groups[(source, role, 'seconds' if seconds else 'quarter_notes')]
        group['lines'] += 1
        notes = unpack(json.loads(zlib.decompress(blob)))
        group['attacks'] += len(notes)
        middle = median(d for _,d,_ in notes)
        pause = max(.12 if seconds else .5, .75 * middle)
        long_note = 2.5 * middle
        cuts = [0]
        for i, ((on, duration, pitch), (following, _, target)) in enumerate(zip(notes, notes[1:]), 1):
            gap = following - on - duration
            if gap >= pause or (duration >= long_note and abs(target - pitch) >= 3 and gap >= -.01):
                cuts.append(i)
        cuts.append(len(notes))
        group['internal_cut_candidates'] += len(cuts) - 2
        group.update(observe(notes, zip(cuts, cuts[1:])))
    return dict(groups)


def indexed(databases, workers, progress):
    seen, snapshots = set(), []
    totals = defaultdict(Counter)
    started = time.monotonic()
    lines = 0

    def batches():
        for path in databases:
            with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
                snapshots.append({'name': str(path), 'rows': db.execute('SELECT count(*) FROM lines').fetchone()[0]})
                batch = []
                for fingerprint, *row in db.execute('SELECT fingerprint,source,role,basis,events FROM lines'):
                    if fingerprint in seen:
                        continue
                    seen.add(fingerprint)
                    batch.append(row)
                    if len(batch) == 256:
                        yield batch
                        batch = []
                if batch:
                    yield batch

    def merge(groups):
        nonlocal lines
        before = lines
        for key, row in groups.items():
            totals[key].update(row)
            lines += row['lines']
        if before // 10000 != lines // 10000:
            progress.write_text(json.dumps({'lines': lines, 'seconds': round(time.monotonic()-started)}), encoding='utf8')

    if workers == 1:
        for batch in batches():
            merge(observe_batch(batch))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            source = iter(batches())
            pending = deque(pool.submit(observe_batch, batch)
                            for _, batch in zip(range(workers * 2), source))
            while pending:
                merge(pending.popleft().result())
                batch = next(source, None)
                if batch is not None:
                    pending.append(pool.submit(observe_batch, batch))
    return {'snapshots': snapshots, 'unique_lines': len(seen), 'seconds': round(time.monotonic()-started),
            'groups': [{'source': k[0], 'role': k[1], 'time_unit': k[2], **v} for k,v in sorted(totals.items())]}


def mtc_annotations(path):
    counts = Counter()
    with gzip.open(path, 'rt', encoding='utf8') as handle:
        for line in handle:
            f = json.loads(line)['features']
            ends = f['phrase_end']
            lengths = [number(v) for v in f['duration_frac']]
            ioi = f['IOI_frac']
            notes, q = [], 0.0
            for index, (pitch, dur) in enumerate(zip(f['midipitch'], lengths)):
                notes.append((q, dur, pitch))
                if index < len(lengths)-1:
                    q += number(ioi[index])
            boundaries = [0, *(i+1 for i,v in enumerate(ends) if v)]
            assert boundaries[-1] == len(notes)
            counts['songs'] += 1
            counts['annotated_phrases'] += len(boundaries)-1
            counts.update(observe(notes, zip(boundaries, boundaries[1:])))
    return counts


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--database', type=Path, action='append', required=True)
    cli.add_argument('--mtc', type=Path, required=True)
    cli.add_argument('--out', type=Path, required=True)
    cli.add_argument('--workers', type=int, default=8)
    args = cli.parse_args()
    if args.workers < 1:
        cli.error('--workers must be positive')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    annotated = mtc_annotations(args.mtc)
    report = {'mtc_annotations': annotated, 'indexed': indexed(args.database, args.workers, args.out.with_suffix('.progress.json'))}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'mtc': annotated, 'lines': report['indexed']['unique_lines'], 'seconds': report['indexed']['seconds']}))


if __name__ == '__main__':
    main()
