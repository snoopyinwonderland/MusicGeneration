"""Opt-in census of documented karaoke vocal lines and explicit chord labels.

No melody guessing, pitch snapping, harmony inference, or generator changes.
Raw events and exact motif keys are written only to the requested local output.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
import hashlib
from itertools import groupby
import json
from pathlib import Path
import re
import sqlite3
import time
import zlib

from musigen import MUSICOMP_ROOT
from musigen.corpus_features import midi_features
from kysing_leadsheet.kysing_leadsheet import read_smf, track_name, dec, parse_label

VERSION = 2


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def sha(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def qstr(ticks, ppq):
    return str(F(ticks, ppq))


def sign(x):
    return (x > 0) - (x < 0)


def ambiguous_vocal_overlap(notes):
    ends = {}
    for start, end, pitch in notes:
        if start < ends.get(pitch, start):
            return True
        ends[pitch] = end
    return False


def rap_mask(notes, minimum=8):
    """Source-converter heuristic, not a verified genre or vocal-technique label."""
    masked = set()
    for pitch, group in groupby(enumerate(notes), key=lambda x: x[1][2]):
        indices = [i for i, _ in group]
        if pitch == 69 and len(indices) >= minimum:
            masked.update(indices)
    return masked


def split_runs(notes, masked, ppq, gap_beats=1):
    """Never bridge removed notes, overlaps, or rests at/above the chosen threshold."""
    runs, current = [], []
    for i, n in enumerate(notes):
        if i in masked:
            if current:
                runs.append(current)
                current = []
            continue
        if current and (n[0] < current[-1][1] or n[0]-current[-1][1] >= gap_beats*ppq):
            runs.append(current)
            current = []
        current.append(n)
    if current:
        runs.append(current)
    return runs


def interval_class(n):
    if n == 0:
        return 'repeat'
    if abs(n) <= 2:
        return 'step_1_2'
    if abs(n) <= 4:
        return 'third_3_4'
    return 'leap_5_plus'


def rhythm_class(ticks, ppq):
    x = ticks / ppq
    return 'short' if x <= .5 else 'medium' if x < 2 else 'long'


def bar_grid(meters, end, ppq):
    """Only complete measures under explicit meters; changes restart the grid."""
    bars = []
    for i, (start, num, den) in enumerate(meters):
        stop = meters[i+1][0] if i+1 < len(meters) else end
        length = F(ppq*4*num, den)
        if length <= 0 or length.denominator != 1:
            continue
        length = int(length)
        for at in range(start, stop-length+1, length):
            bars.append((at, at+length, f'{num}/{den}', i))
    return bars


def key_at(keys, tick):
    i = bisect_right([k[0] for k in keys], tick)-1
    if i < 0:
        return None
    _, fifths, minor = keys[i]
    return ((7*fifths + (9 if minor else 0)) % 12, minor)


def chord_quality(chord):
    iv = set(chord['ivs'])
    if {0, 3, 6, 10} <= iv: return 'half_dim7'
    if {0, 3, 6, 9} <= iv: return 'dim7'
    if {0, 3, 6} <= iv: return 'dim'
    if {0, 4, 8} <= iv: return 'aug'
    if 3 in iv: return 'minor_maj7' if 11 in iv else 'minor7' if 10 in iv else 'minor'
    if 4 in iv: return 'major7' if 11 in iv else 'dominant7' if 10 in iv else 'major'
    if 5 in iv: return 'sus4'
    if 2 in iv: return 'sus2'
    return 'other'


def degree(chord, key):
    if key is None or chord is None:
        return None
    tonic, minor = key
    return f'{"minor" if minor else "major"}:{(chord["root"]-tonic)%12}:{chord_quality(chord)}'


def extract(path):
    path = Path(path)
    before = path.stat()
    data = midi_features(path, include_notes=True)  # validates SMF before the shared annotation parser
    vocal = [t for t in data['tracks'] if t['name'].strip().upper() == 'S1']
    if len(vocal) != 1:
        raise ValueError(f'ambiguous/missing S1: {len(vocal)}')
    notes = [(a, b, p) for a, b, channel, p, _ in vocal[0]['note_events'] if channel == 3]
    if len(notes) < 8 or any(b <= a for a, b, _ in notes):
        raise ValueError('short or nonpositive vocal notes')
    if len({a for a, _, _ in notes}) != len(notes):
        raise ValueError('simultaneous vocal onsets; no top-note selection')
    if ambiguous_vocal_overlap(notes):
        raise ValueError('ambiguous same-pitch vocal overlap')
    fmt, div, tracks = read_smf(str(path))
    if div != data['ppq'] or fmt != data['format']:
        raise ValueError('MIDI readers disagree on header')
    keys, markers, line_ends, labels = set(), set(), set(), []
    for track in tracks:
        name = track_name(track).strip().upper()
        for tick, kind, typ, payload in track:
            if kind != 'meta':
                continue
            if typ == 0x59 and len(payload) == 2:
                fifths = int.from_bytes(payload[:1], 'big', signed=True)
                if -7 <= fifths <= 7 and payload[1] in (0, 1):
                    keys.add((tick, fifths, payload[1]))
            if typ == 6:
                label = dec(payload).strip()
                # Do not retain the title marker or lyrics in the statistics store.
                if re.fullmatch(r"[A-Z][A-Z0-9'′ -]{0,7}", label):
                    markers.add((tick, label))
            if name == 'S1' and typ == 5 and (b'\r' in payload or b'\n' in payload):
                line_ends.add(tick)
            if name == 'CHORD' and typ in (1, 5):
                label = dec(payload).strip()
                if label:
                    chord = parse_label(label)
                    if chord:
                        chord = {k: chord[k] for k in ('root', 'bass', 'ivs')}
                        chord['bass'] = chord['root'] if chord['bass'] is None else chord['bass']
                        chord['ivs'] = sorted(chord['ivs'])
                    labels.append((tick, label, chord))
    # A conflict at one tick is unknown, not silently resolved by track order.
    chords, conflicts = [], 0
    for tick, group in groupby(sorted(labels, key=lambda x: x[0]), key=lambda x: x[0]):
        rows = list(group)
        if len({encoded(c) for _, _, c in rows}) > 1:
            conflicts += 1
            chords.append((tick, None))
        else:
            chords.append((tick, rows[0][2]))
    keys = sorted(keys)
    if len({t for t, _, _ in keys}) != len(keys):
        raise ValueError('conflicting key signatures')
    if len({t for t, _, _ in data['meters']}) != len(data['meters']):
        raise ValueError('conflicting meters')
    # Consecutive equivalent chord labels are one sustained harmonic event.
    reduced = []
    for tick, chord in chords:
        if not reduced or chord != reduced[-1][1]:
            reduced.append((tick, chord))
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('source changed during read')
    ppq = data['ppq']
    first, root_pitch = notes[0][0], notes[0][2]
    normalized = [[qstr(a-first, ppq), qstr(b-a, ppq), p-root_pitch] for a, b, p in notes]
    harmonic = [[qstr(t-first, ppq), None if c is None else
                 [(c['root']-root_pitch)%12, (c['bass']-root_pitch)%12, c['ivs']]] for t, c in reduced]
    return {'id': path.stem, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size': after.st_size, 'mtime_ns': after.st_mtime_ns, 'ppq': ppq,
            'melody_fingerprint': sha(normalized),
            'combined_fingerprint': sha([normalized, harmonic, keys, data['meters']]),
            'notes': notes, 'chords': reduced, 'keys': keys, 'meters': data['meters'],
            'markers': sorted(markers), 'screen_line_ends': sorted(line_ends),
            'unknown_labels': dict(Counter(s for _, s, c in labels if c is None)),
            'chord_conflicts': conflicts, 'midi_warnings': data['warnings'],
            'tempos': data['tempos']}


def analyze(record):
    notes, ppq = record['notes'], record['ppq']
    if ambiguous_vocal_overlap(notes):
        raise ValueError('ambiguous same-pitch vocal overlap')
    mask = rap_mask(notes)
    runs = split_runs(notes, mask, ppq)
    kept = [n for i, n in enumerate(notes) if i not in mask]
    melody, harmony = defaultdict(Counter), defaultdict(Counter)
    metrics = {'raw_attacks': len(notes), 'excluded_rap_suspect': len(mask), 'attacks': len(kept),
               'runs_gap1': len(runs), 'runs_gap_half': len(split_runs(notes, mask, ppq, .5)),
               'runs_gap2': len(split_runs(notes, mask, ppq, 2)),
               'markers': len(record['markers']), 'screen_line_ends': len(record['screen_line_ends'])}
    # Raw reference is diagnostic only; the main patterns below exclude rap suspects.
    melody['raw_interval'].update(str(b[2]-a[2]) for a, b in zip(notes, notes[1:]))
    for i, (a, b) in enumerate(zip(notes, notes[1:])):
        if i in mask or i+1 in mask:
            continue
        gap = b[0]-a[1]
        melody['gap_quarters'][qstr(gap, ppq)] += 1
        if gap >= 0:
            melody['interval_all_gaps'][str(b[2]-a[2])] += 1
    for run in runs:
        ints = [b[2]-a[2] for a, b in zip(run, run[1:])]
        melody['interval'].update(map(str, ints))
        melody['interval_transition'].update(f'{a},{b}' for a, b in zip(ints, ints[1:]))
        for a, b in zip(ints, ints[1:]):
            melody['direction_after_interval'][f'{interval_class(a)}:{"opposite" if a*b<0 else "same" if a*b>0 else "zero"}'] += 1
        for _, group in groupby(ints, key=sign):
            steps = list(group)
            melody['direction_run'][f'{sign(steps[0])}:{len(steps)}'] += 1
        for _, group in groupby(run, key=lambda n: n[2]):
            melody['repeated_pitch_run'][str(len(list(group)))] += 1
        for size in (4, 6, 8):
            for start in range(len(run)-size+1):
                window = run[start:start+size]
                iv = [b[2]-a[2] for a, b in zip(window, window[1:])]
                melody[f'interval_pattern_{size}'][','.join(map(str, iv))] += 1
                melody[f'contour_{size}'][''.join('U' if x>0 else 'D' if x<0 else '=' for x in iv)] += 1
                # Joint gesture retains the location of holds and short notes, not just a contour histogram.
                shape = ''.join('U' if x>0 else 'D' if x<0 else '=' for x in iv)
                lengths = ','.join(rhythm_class(b-a, ppq) for a, b, _ in window)
                melody[f'gesture_{size}'][shape+'|'+lengths] += 1
                if size == 4:
                    onset_shape = ','.join(qstr(b[0]-a[0], ppq) for a, b in zip(window, window[1:]))
                    durations = ','.join(qstr(b-a, ppq) for a, b, _ in window)
                    melody['rhythm_4'][onset_shape+'|'+durations] += 1
        melody['run_attacks'][str(len(run))] += 1
        melody['run_span_quarters'][qstr(run[-1][1]-run[0][0], ppq)] += 1
        if len(run) >= 4:
            terminal = run[-1][1]-run[-1][0]
            before = sorted(b-a for a, b, _ in run[:-1])
            typical = before[len(before)//2]
            ratio = terminal/typical
            melody['run_end_length_ratio']['>=2' if ratio>=2 else '>1' if ratio>1 else '=1' if ratio==1 else '<1'] += 1
            melody['run_end_contour'][','.join(str(x) for x in ints[-3:])] += 1
    grids = bar_grid(record['meters'], max(b for _, b, _ in notes), ppq)
    starts = [a for a, _, _, _ in grids]
    by_bar = defaultdict(list)
    for a, b, pitch in kept:
        melody['duration_quarters'][qstr(b-a, ppq)] += 1
        idx = bisect_right(starts, a)-1
        if idx < 0 or a >= grids[idx][1]:
            melody['meter_coverage']['outside_complete_explicit_bar'] += 1
            continue
        start, stop, met, _ = grids[idx]
        melody['meter_coverage'][met] += 1
        by_bar[idx].append((a, b, pitch))
        # 6/8 and 9/8 use dotted-quarter pulse; other meters use the denominator unit.
        num, den = map(int, met.split('/'))
        pulse = F(ppq*4, den)*(3 if den==8 and num>=6 and num%3==0 else 1)
        phase = F(a-start, 1) % pulse
        melody['beat_phase'][f'{met}:{phase/pulse}'] += 1
        location = 'bar_start' if a==start else 'beat' if phase==0 else 'offbeat'
        melody['duration_by_position'][location+':'+rhythm_class(b-a,ppq)] += 1
        if phase:
            melody['offbeat_sustain']['crosses_next_pulse' if a+(pulse-phase)<b else 'ends_by_next_pulse'] += 1
    for idx, (start, stop, met, _) in enumerate(grids):
        if start < notes[0][0] or start >= notes[-1][1]:
            continue
        if any(start <= notes[i][0] < stop for i in mask):
            continue
        melody['bar_attack_density'][f'{met}:{len(by_bar[idx])}'] += 1
    block_examples = []
    masked_onsets = [notes[i][0] for i in sorted(mask)]
    onsets = [n[0] for n in kept]
    for size in (2, 4, 8):
        seen_pitch, seen_rhythm, seen_exact = Counter(), Counter(), Counter()
        blocks = []
        # Non-overlapping blocks, aligned to each explicit-meter segment (not claimed phrases).
        for meter_id in sorted({g[3] for g in grids}):
            indices = [i for i, g in enumerate(grids) if g[3] == meter_id]
            for j in range(0, len(indices)-size+1, size):
                idx = indices[j]
                start, end = grids[idx][0], grids[indices[j+size-1]][1]
                lo, hi = bisect_right(onsets,start-1), bisect_right(onsets,end-1)
                window = kept[lo:hi]
                if (len(window)<4 or any(start<=x<end for x in masked_onsets)
                        or (lo and kept[lo-1][1]>start) or any(b>end for _,b,_ in window)
                        or any(a[1]>b[0] for a,b in zip(window,window[1:]))):
                    continue
                pitches = tuple(p-window[0][2] for _,_,p in window)
                rhythm = tuple((qstr(a-start,ppq),qstr(b-a,ppq)) for a,b,_ in window)
                seen_pitch[pitches] += 1
                seen_rhythm[rhythm] += 1
                seen_exact[(pitches,rhythm)] += 1
                high = max(p for _,_,p in window)
                peak = next(a for a,_,p in window if p==high)
                phase = min(3,int(4*(peak-start)/(end-start)))
                net = window[-1][2]-window[0][2]
                endgap = end-window[-1][1]
                descriptor = f'{"up" if net>2 else "down" if net<-2 else "level"}:peak{phase+1}:n{len(window)}'
                melody[f'block_{size}_profile'][descriptor] += 1
                blocks.append((start,end,pitches,rhythm,window[0][2],descriptor))
                if size in (2,4):
                    block_examples.append({'start':start,'end':end,'bars':size,'attacks':len(window),
                                           'first':window[0][2],'last':window[-1][2],
                                           'range':high-min(p for _,_,p in window),'peak_quartile':phase+1,
                                           'trailing_rest':qstr(endgap,ppq)})
            # Do not pair blocks across a meter boundary.
        for kind, counts in (('pitch',seen_pitch),('rhythm',seen_rhythm),('joint',seen_exact)):
            melody[f'block_{size}_repetition'][f'{kind}_blocks'] += sum(counts.values())
            melody[f'block_{size}_repetition'][f'{kind}_unique'] += len(counts)
            melody[f'block_{size}_repetition'][f'{kind}_reused_occurrences'] += sum(n-1 for n in counts.values())
        for left,right in zip(blocks,blocks[1:]):
            if left[1]!=right[0]:
                continue
            same_pitch, same_rhythm = left[2]==right[2],left[3]==right[3]
            if same_pitch and same_rhythm:
                relation='exact' if left[4]==right[4] else 'transposed'
            elif same_rhythm: relation='same_rhythm_changed_pitch'
            elif same_pitch: relation='same_intervals_changed_rhythm'
            else: relation='both_changed'
            melody[f'block_{size}_adjacent_relation'][relation] += 1
            if len(left[2])==len(right[2]):
                differences=[i for i,(a,b) in enumerate(zip(left[2],right[2])) if a!=b]
                if differences and min(differences)>=len(left[2])//2:
                    melody[f'block_{size}_ending_variant']['same_relative_first_half'] += 1
                melody[f'block_{size}_ending_variant']['equal_attack_count_pairs'] += 1
    # Actual label times, no guessed harmony. Unknown labels break the timeline.
    chords, keys = record['chords'], record['keys']
    times = [t for t,_ in chords]
    harmonic_spans = []
    first_on,last_off=notes[0][0],max(b for _,b,_ in notes)
    for i,(tick,c) in enumerate(chords):
        end=chords[i+1][0] if i+1<len(chords) else last_off
        if end<=first_on or tick>=last_off:
            continue
        harmonic_spans.append((tick,end,c))
        if c is None:
            harmony['chord_status']['unknown_span'] += 1
            continue
        quality=chord_quality(c)
        harmony['chord_quality'][quality]+=1
        harmony['chord_intervals'][','.join(map(str,c['ivs']))]+=1
        harmony['chord_duration_quarters'][qstr(min(end,last_off)-max(tick,first_on),ppq)]+=1
        harmony['inversion']['root' if c['bass']==c['root'] else 'slash']+=1
        d=degree(c,key_at(keys,max(tick,first_on)))
        harmony['degree'][d or 'unknown_key']+=1
    for left,right in zip(harmonic_spans,harmonic_spans[1:]):
        a,b=left[2],right[2]
        if a is None or b is None: continue
        harmony['root_motion'][str((b['root']-a['root'])%12)]+=1
        harmony['quality_transition'][chord_quality(a)+'>'+chord_quality(b)]+=1
        ka,kb=key_at(keys,max(left[0],first_on)),key_at(keys,right[0])
        if ka is not None and ka==kb:
            harmony['degree_transition'][degree(a,ka)+'>'+degree(b,kb)]+=1
    for size in (3,4):
        for i in range(len(harmonic_spans)-size+1):
            group=harmonic_spans[i:i+size]
            kk=[key_at(keys,max(t,first_on)) for t,_,_ in group]
            if kk[0] is not None and len(set(kk))==1 and all(c for _,_,c in group):
                harmony[f'degree_progression_{size}']['>'.join(degree(c,kk[0]) for _,_,c in group)]+=1
    for a,b,p in kept:
        i=bisect_right(times,a)-1
        c=chords[i][1] if i>=0 else None
        if c is None:
            harmony['melody_alignment']['unlabelled_attack']+=1
            continue
        delta=(p-c['root'])%12
        member=delta in c['ivs']
        harmony['melody_alignment']['chord_tone' if member else 'nonchord_tone']+=1
        harmony['melody_chord_degree'][chord_quality(c)+':'+str(delta)]+=1
        position='quarter_grid' if a%ppq==0 else 'off_quarter_grid'
        harmony['membership_position'][position+':'+str(member)]+=1
        harmony['membership_duration'][rhythm_class(b-a,ppq)+':'+str(member)]+=1
    for idx,(start,end,met,_) in enumerate(grids):
        if not by_bar[idx]: continue
        changes=sum(start<=t<end and c is not None for t,c in chords)
        harmony['chord_changes_per_vocal_bar'][f'{met}:{changes}']+=1
    for run in runs:
        for a,b,c in zip(run,run[1:],run[2:]):
            indices=[bisect_right(times,n[0])-1 for n in (a,b,c)]
            if indices[0]<0 or len(set(indices))!=1: continue
            chord=chords[indices[0]][1]
            if chord is None: continue
            members=[(n[2]-chord['root'])%12 in chord['ivs'] for n in (a,b,c)]
            if members != [True,False,True]: continue
            x,y=b[2]-a[2],c[2]-b[2]
            harmony['nonchord_triples']['chord_nonchord_chord']+=1
            if 0<abs(x)<=2 and 0<abs(y)<=2:
                harmony['nonchord_triples']['passing_like' if x*y>0 else 'neighbor_like']+=1
    for run in runs:
        if len(run)<4: continue
        at=run[-1][0]; i=bisect_right(times,at)-1
        c=chords[i][1] if i>=0 else None
        harmony['run_final_membership']['unknown' if c is None else 'chord_tone' if (run[-1][2]-c['root'])%12 in c['ivs'] else 'nonchord_tone']+=1
    changes=[]
    for a,b in zip(keys,keys[1:]):
        if a[1:]!=b[1:]:
            changes.append(b)
            harmony['explicit_key_change'][f'{a[2]}>{b[2]}:{(7*(b[1]-a[1])+9*(b[2]-a[2]))%12}']+=1
    metrics.update(key_changes=len(changes),chord_labels=sum(c is not None for _,c in chords),
                   unknown_chord_labels=sum(record['unknown_labels'].values()),
                   pitch_range=max((p for _,_,p in kept),default=0)-min((p for _,_,p in kept),default=0))
    if kept:
        high=max(p for _,_,p in kept)
        metrics['first_high_position']=(next(a for a,_,p in kept if p==high)-kept[0][0])/max(1,kept[-1][1]-kept[0][0])
    return {'metrics':metrics,'melody':dict(melody),'harmony':dict(harmony),'blocks':block_examples}


def inspect(path):
    try:
        record=extract(path)
        result=analyze(record)
        return str(path),'ok',record['sha256'],zlib.compress(encoded({'record':record,'analysis':result}).encode()),None
    except Exception as exc:
        return str(path),'error',None,None,f'{type(exc).__name__}: {str(exc)[:300]}'


def connect(path):
    db=sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=NORMAL')
    db.execute('PRAGMA cache_size=-262144')
    db.execute('PRAGMA temp_store=MEMORY')
    db.executescript('''CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,status TEXT,sha256 TEXT,payload BLOB,error TEXT);
        CREATE TABLE IF NOT EXISTS patterns(family TEXT,pattern TEXT,occurrences INTEGER,documents INTEGER,example_id TEXT,
        PRIMARY KEY(family,pattern)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS blocks(song_id TEXT,start INTEGER,end INTEGER,bars INTEGER,features TEXT);
        CREATE INDEX IF NOT EXISTS block_song ON blocks(song_id);
        CREATE TABLE IF NOT EXISTS song_metrics(song_id TEXT PRIMARY KEY,metrics TEXT);''')
    return db


def aggregate(db,out):
    # Revalidate already-extracted v1 records without rereading or modifying the sources.
    excluded=[]
    for path,payload in db.execute("SELECT path,payload FROM files WHERE status='ok'"):
        record=json.loads(zlib.decompress(payload))['record']
        if ambiguous_vocal_overlap(record['notes']):excluded.append(path)
    db.executemany("UPDATE files SET status='error',error='ValueError: ambiguous same-pitch vocal overlap' WHERE path=?",[(p,) for p in excluded])
    db.execute('DELETE FROM patterns');db.execute('DELETE FROM blocks');db.execute('DELETE FROM song_metrics');db.commit()
    seen_melody,seen_harmony=set(),set()
    buffer={}
    totals=Counter(); metric_values=defaultdict(list); per_song=defaultdict(list)
    def flush():
        db.executemany('INSERT INTO patterns VALUES(?,?,?,?,?) ON CONFLICT(family,pattern) DO UPDATE SET occurrences=occurrences+excluded.occurrences,documents=documents+excluded.documents',
                       ((family,key,*values) for (family,key),values in sorted(buffer.items())))
        buffer.clear();db.commit()
    for index,(path,payload) in enumerate(db.execute("SELECT path,payload FROM files WHERE status='ok' ORDER BY path"),1):
        value=json.loads(zlib.decompress(payload));record=value['record'];analysis=value['analysis'];ident=record['id']
        for domain,seen,fingerprint in [('melody',seen_melody,record['melody_fingerprint']),('harmony',seen_harmony,record['combined_fingerprint'])]:
            if fingerprint in seen:
                totals[domain+'_duplicates']+=1
                continue
            seen.add(fingerprint);totals[domain+'_unique_files']+=1
            for family,counter in analysis[domain].items():
                family=domain+'.'+family
                for key,count in counter.items():
                    if not count:continue
                    bkey=(family,key)
                    if bkey not in buffer: buffer[bkey]=[0,0,ident]
                    buffer[bkey][0]+=count;buffer[bkey][1]+=1
            if domain=='melody':
                m=analysis['metrics']
                for key,n in m.items():metric_values[key].append(n)
                for family,desired in [('interval','step'),('raw_interval','step')]:
                    c=analysis['melody'].get(family,{})
                    den=sum(c.values())
                    if den:
                        per_song[family+'_step_fraction'].append(sum(v for k,v in c.items() if 0<abs(int(k))<=2)/den)
                        per_song[family+'_repeat_fraction'].append(c.get('0',0)/den)
                        per_song[family+'_leap_fraction'].append(sum(v for k,v in c.items() if abs(int(k))>=5)/den)
                db.execute('INSERT INTO song_metrics VALUES(?,?)',(ident,encoded(m)))
                db.executemany('INSERT INTO blocks VALUES(?,?,?,?,?)',((ident,b['start'],b['end'],b['bars'],encoded(b)) for b in analysis['blocks']))
        if len(buffer)>160_000:flush()
        if index%2000==0:
            (out/'progress.json').write_text(encoded({'phase':'aggregate','processed':index,'totals':dict(totals)}),encoding='utf8')
    flush()
    def describe(values):
        s=sorted(values);n=len(s)
        return {'n':n,'sum':sum(s),'mean':sum(s)/n if n else None,
                'p10':s[int((n-1)*.1)] if n else None,'median':s[(n-1)//2] if n else None,
                'p90':s[int((n-1)*.9)] if n else None}
    families={}
    for family,occs,n in db.execute('SELECT family,SUM(occurrences),COUNT(*) FROM patterns GROUP BY family'):
        top=[{'pattern':p,'occurrences':c,'documents':d,'example_id':e} for p,c,d,e in db.execute(
            'SELECT pattern,occurrences,documents,example_id FROM patterns WHERE family=? ORDER BY occurrences DESC,pattern LIMIT 40',(family,))]
        by_docs=[{'pattern':p,'occurrences':c,'documents':d,'example_id':e} for p,c,d,e in db.execute(
            'SELECT pattern,occurrences,documents,example_id FROM patterns WHERE family=? ORDER BY documents DESC,pattern LIMIT 20',(family,))]
        families[family]={'occurrences':occs,'distinct_patterns':n,'top':top,'top_document_support':by_docs}
    coverage=dict(db.execute('SELECT status,COUNT(*) FROM files GROUP BY status'))
    report={'version':VERSION,'coverage':coverage,'deduplication':dict(totals),
            'song_metrics':{k:describe(v) for k,v in metric_values.items()},
            'equal_song_weight':{k:describe(v) for k,v in per_song.items()},'families':families}
    (out/'statistics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return report


def run(root,out,workers=6,limit=0,reaggregate=False):
    out.mkdir(parents=True,exist_ok=True)
    files=sorted(p for p in root.rglob('*') if p.suffix.lower() in ('.mid','.midi','.kar'))
    if limit:files=files[:limit]
    manifest={'version':VERSION,'root':str(root.resolve()),'files':len(files),'partial_limit':limit,
              'source_parser':str(MUSICOMP_ROOT/'kysing_leadsheet/kysing_leadsheet.py'),
              'source_parser_sha256':hashlib.sha256((MUSICOMP_ROOT/'kysing_leadsheet/kysing_leadsheet.py').read_bytes()).hexdigest(),
              'inventory':[{'path':str(p),'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in files]}
    old=out/'manifest.json'
    if old.exists():
        prior=json.loads(old.read_text(encoding='utf8'))
        if reaggregate and prior.get('version')==1:
            prior['version']=VERSION  # v2 only excludes ambiguous vocal-note pairs; other features are unchanged.
        if prior!=manifest:
            raise ValueError('Inventory/parser changed; use a new output directory')
    old.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    db=connect(out/'statistics.sqlite3')
    done={p for p, in db.execute('SELECT path FROM files')};pending=[p for p in files if str(p) not in done]
    start=time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i,result in enumerate(pool.map(inspect,pending,chunksize=16),1):
            db.execute('INSERT INTO files VALUES(?,?,?,?,?)',result)
            if i%200==0:
                db.commit()
                progress={'phase':'extract','processed':len(done)+i,'total':len(files),'elapsed_seconds':round(time.monotonic()-start,1)}
                (out/'progress.json').write_text(encoded(progress),encoding='utf8')
                if i%2000==0:print(encoded(progress),flush=True)
    db.commit()
    report=aggregate(db,out)
    errors=[{'path':p,'error':e} for p,e in db.execute("SELECT path,error FROM files WHERE status='error'")]
    (out/'errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf8')
    report['remaining_files']=len(files)-sum(report['coverage'].values())
    (out/'progress.json').write_text(encoded({'phase':'complete','files':len(files),'coverage':report['coverage'],'remaining':report['remaining_files']}),encoding='utf8')
    db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.close()
    return {'files':len(files),'coverage':report['coverage'],'deduplication':report['deduplication']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='노래방 전체 주선율·명시 화음 통계, 기본 생성 변경 없음')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--reaggregate',action='store_true',help='기존 v1 추출을 v2 모호한 음 제외 기준으로 재집계')
    args=parser.parse_args()
    print(encoded(run(args.root,args.out,args.workers,args.limit,args.reaggregate)))
