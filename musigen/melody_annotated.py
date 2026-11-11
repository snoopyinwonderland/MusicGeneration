"""Read documented monophonic MTC and Weimar records without copying lyrics.

Kept separate from the large file census so a database record is never counted
as a score file. Weimar performance seconds are explicitly not quarter notes.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

from musigen.melody_evidence import connect, line


def mtc_record(row):
    f = row['features']
    pitches, durations, iois = f['midipitch'], f['duration_frac'], f['IOI_frac']
    if not len(pitches) == len(durations) == len(iois):
        raise ValueError('MTC parallel array length mismatch')
    events, onset = [], F(0)
    for i, (pitch, duration) in enumerate(zip(pitches, durations)):
        if int(pitch) != pitch:
            raise ValueError('nonintegral MIDI pitch')
        events.append((onset, F(duration), int(pitch)))
        if i < len(pitches) - 1:
            delta = F(iois[i])
            if delta <= 0:
                raise ValueError('nonpositive MTC IOI')
            onset += delta
    item = line(str(row['id']), 'documented_melody',
                'MTC/ESSEN authored monophonic note sequence; IOI_frac in quarter notes', events)
    metadata = {k: row.get(k) for k in ('id', 'tunefamily', 'year', 'type', 'origin', 'ann_bgcorpus')}
    metadata.update(time_unit='quarter_note', phrase_boundary_status='not_used_in_this_analysis')
    return metadata, item


def weimar_record(row, notes):
    events = []
    for onset, duration, pitch in notes:
        if int(pitch) != pitch:
            raise ValueError('nonintegral Weimar pitch')
        events.append((F(str(onset)), F(str(duration)), int(pitch)))
    item = line(str(row['melid']), 'documented_melody',
                'Weimar transcribed solo; measured onset/duration in seconds', events)
    if item:
        # A second is not a quarter note. Namespacing prevents accidental
        # whole-line identity with a score using the same numeric durations.
        item['fingerprint'] = hashlib.sha256(('seconds:' + item['fingerprint']).encode()).hexdigest()
        f = item['features']
        f['rest_seconds'] = f.pop('rest_quarters')
        f['span_seconds'] = f.pop('span_quarters')
        f['time_unit'] = 'performance_seconds'
    metadata = {k: row[k] for k in ('melid', 'compid', 'performer', 'title', 'instrument', 'style', 'rhythmfeel', 'key', 'signature')}
    metadata['time_unit'] = 'performance_seconds'
    return metadata, item


def put(db, path, source, metadata, item):
    db.execute('INSERT INTO files VALUES(?,?,?,?,?,?)',
               (path, source, None, 'read', None, json.dumps(metadata, ensure_ascii=False)))
    if item:
        db.execute('INSERT OR IGNORE INTO lines VALUES(?,?,?,?,?,?,?,?)',
                   (item['fingerprint'], path, source, item['track'], item['role'], item['basis'],
                    item['events'], json.dumps(item['features'])))


def run(out, mtc=None, weimar=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'melodies.sqlite3'
    if target.exists():
        raise ValueError('Use a fresh output directory')
    db = connect(target)
    report = {'record_counts': {}, 'source_files': [], 'errors': [], 'lyrics_copied': False}
    if mtc:
        for path in sorted(Path(mtc).glob('*.jsonl.gz')):
            report['source_files'].append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            sid = 'mtc/' + path.name
            count = Counter()
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                for number, text in enumerate(stream, 1):
                    count['records'] += 1
                    try:
                        metadata, item = mtc_record(json.loads(text))
                        put(db, str(path) + '#record=' + str(number), sid, metadata, item)
                        count['read'] += 1
                        count['eligible_lines_before_dedup'] += bool(item)
                    except (ValueError, KeyError, TypeError) as exc:
                        count['errors'] += 1
                        report['errors'].append({'source': sid, 'record': number, 'reason': str(exc)})
            report['record_counts'][sid] = dict(count)
            db.commit()
    if weimar:
        path = Path(weimar).resolve()
        report['source_files'].append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        source.row_factory = sqlite3.Row
        count = Counter()
        for row in source.execute('SELECT * FROM solo_info ORDER BY melid'):
            count['records'] += 1
            try:
                notes = source.execute('SELECT onset,duration,pitch FROM melody WHERE melid=? ORDER BY onset,eventid', (row['melid'],))
                metadata, item = weimar_record(row, notes)
                put(db, str(path) + '#melid=' + str(row['melid']), 'weimar', metadata, item)
                count['read'] += 1
                count['eligible_lines_before_dedup'] += bool(item)
            except (ValueError, KeyError, TypeError) as exc:
                count['errors'] += 1
                report['errors'].append({'source': 'weimar', 'record': row['melid'], 'reason': str(exc)})
        report['record_counts']['weimar'] = dict(count)
        source.close()
    db.commit()
    report['unique_lines'] = db.execute('SELECT count(*) FROM lines').fetchone()[0]
    db.close()
    (out / 'coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MTC·Weimar의 명시된 선율 레코드 읽기')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--mtc', type=Path)
    parser.add_argument('--weimar', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.out, args.mtc, args.weimar), ensure_ascii=False))
