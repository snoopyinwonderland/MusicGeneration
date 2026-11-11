"""Corpus observations, never inferred melody/harmony or a quality score.

Times are exact quarter-note units. XML repeats remain written; MIDI keeps
performance ticks and is not quantized into notated bars.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from fractions import Fraction as F
from pathlib import Path
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_xml(path):
    data = Path(path).read_bytes()
    if data[:4] == b'PK\x03\x04':
        with zipfile.ZipFile(path) as z:
            container = ET.fromstring(z.read('META-INF/container.xml'))
            rf = next(e for e in container.iter() if e.tag.split('}')[-1] == 'rootfile')
            info = z.getinfo(rf.attrib['full-path'])
            if info.file_size > 100_000_000:
                raise ValueError('MXL root too large')
            data = z.read(info)
    if b'<!ENTITY' in data:
        raise ValueError('entity declarations unsupported')
    root = ET.fromstring(data)
    for e in root.iter():
        e.tag = e.tag.split('}')[-1]
    if root.tag != 'score-partwise':
        raise ValueError('not score-partwise MusicXML')
    return root


def xml_features(path):
    root = read_xml(path)
    meta = {
        'title': root.findtext('work/work-title') or root.findtext('movement-title'),
        'creators': [{'type': e.get('type'), 'text': e.text} for e in root.findall('identification/creator')],
        'rights_raw': [e.text for e in root.findall('identification/rights')],
        'parts': {e.get('id'): e.findtext('part-name') for e in root.findall('part-list/score-part')},
        'repeats': 'not-expanded', 'melody_role': 'unknown',
        'pitch_basis': 'written_not_concert',
        'work_date': None, 'annotation_origin': 'explicit_xml_only',
    }
    rows, issues = [], Counter()
    for part in root.findall('part'):
        div, meter, key = None, None, None
        for mi, measure in enumerate(part.findall('measure')):
            cursor = extent = F(0)
            last_on = None
            notes, harmonies = [], []
            for e in measure:
                if e.tag == 'attributes':
                    if e.find('divisions') is not None:
                        div = F(e.findtext('divisions'))
                        if div <= 0:
                            raise ValueError('nonpositive divisions')
                    if e.find('time') is not None:
                        t = e.find('time')
                        pairs = list(zip(t.findall('beats'), t.findall('beat-type')))
                        meter = '+'.join(f'{a.text}/{b.text}' for a, b in pairs) or None
                    if e.find('key') is not None:
                        key = {'fifths': e.findtext('key/fifths'), 'mode': e.findtext('key/mode')}
                elif e.tag in ('backup', 'forward'):
                    if div is None:
                        raise ValueError('duration before divisions')
                    delta = F(e.findtext('duration', '0')) / div
                    if delta < 0:
                        raise ValueError('negative duration')
                    cursor += delta if e.tag == 'forward' else -delta
                    if cursor < 0:
                        raise ValueError('backup before measure start')
                    extent = max(extent, cursor)
                    last_on = None
                elif e.tag == 'note':
                    grace = e.find('grace') is not None
                    if not grace and div is None:
                        raise ValueError('note before divisions')
                    dur = F(0) if grace else F(e.findtext('duration', '0')) / div
                    if dur < 0:
                        raise ValueError('negative note duration')
                    chord = e.find('chord') is not None
                    if chord and last_on is None:
                        raise ValueError('chord without prior note')
                    on = last_on if chord else cursor
                    if not chord:
                        last_on = on
                        cursor += dur
                    extent = max(extent, on + dur)
                    pitch = e.find('pitch')
                    midi, spelling = None, None
                    if pitch is not None:
                        step = pitch.findtext('step')
                        alt = F(pitch.findtext('alter', '0'))
                        octave = int(pitch.findtext('octave'))
                        midi = str(12 * (octave + 1) + {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}[step] + alt)
                        spelling = [step, str(alt), octave]
                    ties = sorted({t.get('type') for t in e.findall('tie') if t.get('type')})
                    if grace:
                        issues['grace_notes_preserved_not_timed'] += 1
                    notes.append({'on': str(on), 'dur': str(dur), 'midi': midi, 'spelling': spelling,
                                  'rest': e.find('rest') is not None, 'unpitched': e.find('unpitched') is not None,
                                  'staff': e.findtext('staff', '1'), 'voice': e.findtext('voice', '1'),
                                  'grace': grace, 'ties': ties,
                                  'lyrics_count': len(e.findall('lyric'))})
                elif e.tag == 'harmony':
                    offset = F(e.findtext('offset', '0')) / (div or 1)
                    harmonies.append({'on': str(cursor + offset), 'xml': ET.tostring(e, encoding='unicode')})
            rows.append({'part': part.get('id'), 'bar': mi, 'printed_bar': measure.get('number'),
                         'implicit': measure.get('implicit'), 'meter': meter, 'key_signature': key,
                         'extent_quarters': str(extent), 'notes': notes, 'harmony': harmonies})
    # Same event fingerprint is an edition candidate, NOT certified work identity.
    fingerprint = digest(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode())
    meta.update(issues=dict(issues), event_fingerprint=fingerprint,
                score_positions=max((r['bar'] + 1 for r in rows), default=0))
    return meta, rows


def voice_observations(row):
    groups = defaultdict(list)
    for n in row['notes']:
        groups[(n['staff'], n['voice'])].append(n)
    result = []
    for (staff, voice), notes in groups.items():
        pitched = [n for n in notes if n['midi'] is not None and not n['grace']]
        attacks = sorted([n for n in pitched if 'stop' not in n['ties']], key=lambda n: F(n['on']))
        sounding = sorted(pitched, key=lambda n: F(n['on']))
        monophonic = all(F(a['on']) + F(a['dur']) <= F(b['on']) for a, b in zip(sounding, sounding[1:]))
        intervals = [str(F(b['midi']) - F(a['midi'])) for a,b in zip(attacks, attacks[1:])] if monophonic else []
        result.append({'staff': staff, 'voice': voice, 'attacks': len(attacks), 'monophonic': monophonic,
                       'intervals': intervals, 'durations': [n['dur'] for n in attacks],
                       'explicit_rest_quarters': str(sum((F(n['dur']) for n in notes if n['rest']), F(0))),
                       'extent_quarters': row['extent_quarters']})
    return result


def midi_features(path, include_notes=False):
    """SMF 0/1 audit. Per track/channel notes; no hand/melody assignment.

    Ambiguous same-pitch overlaps are counted and paired FIFO for diagnostics,
    never promoted to training examples. Sustain is counted, not baked into note
    duration. Missing meter stays unknown (no fabricated 4/4 bars).
    """
    data = Path(path).read_bytes()
    if len(data) < 14 or data[:4] != b'MThd':
        raise ValueError('not SMF')
    length = int.from_bytes(data[4:8], 'big')
    fmt, count, ppq = struct.unpack('>HHH', data[8:14])
    if length < 6 or fmt not in (0,1) or not ppq or ppq & 0x8000:
        raise ValueError('unsupported SMF header/format2/SMPTE')
    pos, tracks, warnings, meters, tempos = 8+length, [], Counter(), set(), set()
    for ti in range(count):
        if data[pos:pos+4] != b'MTrk':
            raise ValueError('missing MTrk')
        size = int.from_bytes(data[pos+4:pos+8], 'big')
        tr = data[pos+8:pos+8+size]
        if len(tr) != size:
            raise ValueError('truncated track')
        pos += 8+size
        at = tick = 0
        running, name = None, ''
        active, notes, programs = defaultdict(deque), [], set()
        lyrics = pedal = 0
        lyric_ticks=[]
        def take(n):
            nonlocal at
            b = tr[at:at+n]
            at += n
            if len(b) != n:
                raise ValueError('truncated MIDI event')
            return b
        def vlq():
            v = 0
            for _ in range(4):
                b = take(1)[0]
                v = (v<<7) | (b & 127)
                if b < 128:
                    return v
            raise ValueError('invalid VLQ')
        while at < size:
            tick += vlq()
            status = take(1)[0]
            if status < 128:
                at -= 1
                if running is None:
                    raise ValueError('invalid running status')
                status = running
            elif status < 240:
                running = status
            else:
                running = None
            if status == 255:
                kind = take(1)[0]
                payload = take(vlq())
                if kind == 3:
                    name = payload.decode('utf-8', errors='replace')
                if kind == 5:
                    lyrics += 1  # never copy lyric text into public reports
                    if include_notes:lyric_ticks.append(tick)
                if kind == 88 and len(payload) >= 2:
                    meters.add((tick, payload[0], 2**payload[1]))
                if kind == 81 and len(payload) == 3:
                    tempos.add((tick, int.from_bytes(payload, 'big')))
                continue
            if status in (240,247):
                take(vlq())
                continue
            kind, channel = status >> 4, status & 15
            if kind not in range(8,15):
                raise ValueError('unsupported MIDI status')
            vals = take(1 if kind in (12,13) else 2)
            if any(v >= 128 for v in vals):
                raise ValueError('invalid MIDI data byte')
            if kind == 12:
                programs.add((channel, vals[0]))
            if kind == 11 and vals[0] == 64:
                pedal += 1
            if kind in (8,9):
                ident = (channel, vals[0])
                if kind == 9 and vals[1] > 0:
                    if active[ident]:
                        warnings['overlapping_same_pitch'] += 1
                    active[ident].append((tick, vals[1]))
                elif active[ident]:
                    start, velocity = active[ident].popleft()
                    if tick <= start:
                        warnings['nonpositive_duration'] += 1
                    notes.append((start, tick, channel, vals[0], velocity))
                else:
                    warnings['orphan_note_off'] += 1
        warnings['unterminated_notes'] += sum(map(len,active.values()))
        pitched = [n for n in notes if n[2] != 9]
        tracks.append({'track': ti, 'name': name, 'notes': len(notes), 'pitched_notes': len(pitched),
                       'drum_notes': len(notes)-len(pitched), 'programs': sorted(programs),
                       'lyrics_events': lyrics, 'pedal_events': pedal,
                       'duration_quarters': str(F(tick,ppq)),
                       'mean_velocity': round(sum(n[4] for n in pitched)/len(pitched),3) if pitched else None,
                       'pitch_min': min((n[3] for n in pitched),default=None),
                       'pitch_max': max((n[3] for n in pitched),default=None)})
        if include_notes:
            tracks[-1]['note_events']=sorted(notes)
            tracks[-1]['lyric_ticks']=lyric_ticks
    return {'format': fmt, 'ppq': ppq, 'tracks': tracks, 'meters': sorted(meters),
            'tempos': sorted(tempos), 'warnings': {k:v for k,v in warnings.items() if v},
            'time_basis': 'performance_ticks_not_quantized', 'melody_role': 'unknown',
            'harmony': None, 'training_eligible': False}
