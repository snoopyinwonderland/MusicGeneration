"""Fit a small swing-melody model and audit the local accompaniment sources.

Reads source files only. Stores counts, evaluation and source inventory, not
corpus excerpts. Generated score material stays outside the repository.
"""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import re
import sqlite3
from xml.etree import ElementTree as ET

NAMES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
STEPS = range(-12, 13)


def chord_class(symbol):
    match = re.match(r'^([A-G])([b#]?)(.*)$', symbol.strip())
    if not match:
        return None
    name, alter, suffix = match.groups()
    root = (NAMES[name] + alter.count('#') - alter.count('b')) % 12
    s = suffix.split('/')[0]
    if any(token in s for token in ('ø', 'h7', 'm7b5', '-7b5', '%', '-7(b5)')):
        quality = 'half_dim'
    elif s.startswith(('o', 'dim', '°')):
        quality = 'dim'
    elif s.startswith(('m', '-', 'min')) and not s.startswith('maj'):
        quality = 'minor'
    elif s.startswith(('7', '9', '13', '11', '+7')):
        quality = 'dominant'
    elif not s or s.startswith(('maj', '^', 'M', '6', 'add')):
        quality = 'major'
    else:
        return None
    return root, quality


def holdout(composition):
    return int(composition) % 5 == 0


def probability(table, value, support, alpha=0.5):
    return (table.get(str(value), 0) + alpha) / (sum(table.values()) + support * alpha)


def wjd(root):
    path = root / 'weimar-jazz-database/wjazzd.db'
    bins = defaultdict(Counter)
    landing = defaultdict(Counter)
    global_steps = Counter()
    eval_rows = []
    train_solos, test_solos, train_tunes, test_tunes = set(), set(), set(), set()
    event_counts = Counter()
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        solos = db.execute("SELECT melid, compid FROM solo_info WHERE signature='4/4' AND rhythmfeel='SWING' AND compid>0").fetchall()
        for melid, compid in solos:
            is_test = holdout(compid)
            (test_solos if is_test else train_solos).add(melid)
            (test_tunes if is_test else train_tunes).add(compid)
            times, beat_chords = [], []
            current = None
            for time, chord in db.execute('SELECT onset,chord FROM beats WHERE melid=? ORDER BY onset', (melid,)):
                if chord and chord.strip():
                    current = chord_class(chord)
                times.append(time)
                beat_chords.append(current)
            previous = None
            previous_step = None
            for time, value in db.execute('SELECT onset,pitch FROM melody WHERE melid=? ORDER BY onset,eventid', (melid,)):
                pitch = round(value)
                index = bisect_right(times, time) - 1
                if 0 <= index < len(times) - 1 and times[index + 1] > times[index]:
                    fraction = (time - times[index]) / (times[index + 1] - times[index])
                    # Swing offbeats fall late. Near the next beat, use the
                    # next beat's harmony rather than mislabelling an anticipation.
                    if fraction >= .87:
                        index += 1
                        fraction = 0
                    metric = 'beat' if fraction < .22 else 'off'
                    ch = beat_chords[index]
                    if ch and not is_test:
                        pc, quality = ch
                        landing[f'{quality}:{metric}'][str((pitch - pc) % 12)] += 1
                    step = pitch - previous[1] if previous and time - previous[0] < 2 else None
                    if step in STEPS and previous_step in STEPS:
                        key = f'{max(-6, min(6, previous_step))}:{metric}'
                        event_counts['test' if is_test else 'train'] += 1
                        if is_test:
                            eval_rows.append((key, step))
                        else:
                            bins[key][str(step)] += 1
                            global_steps[str(step)] += 1
                    previous_step = step
                else:
                    previous_step = None
                previous = time, pitch
    assert train_tunes.isdisjoint(test_tunes) and eval_rows
    unigram_loss, conditional_loss = 0.0, 0.0
    for key, step in eval_rows:
        unconditional = probability(global_steps, step, len(STEPS))
        conditioned = .85 * probability(bins[key], step, len(STEPS)) + .15 * unconditional
        unigram_loss -= math.log(unconditional)
        conditional_loss -= math.log(conditioned)
    return {'model': {'transition': dict(bins), 'relative_pitch': dict(landing), 'unigram': global_steps},
            'evaluation': {'train_solos': len(train_solos), 'test_solos': len(test_solos),
                           'train_compositions': len(train_tunes), 'test_compositions': len(test_tunes),
                           'train_transitions': event_counts['train'], 'test_transitions': event_counts['test'],
                           'unigram_mean_nll': unigram_loss / len(eval_rows),
                           'conditional_mean_nll': conditional_loss / len(eval_rows)}}


def xml_pitch(note):
    step = note.findtext('pitch/step')
    if step in NAMES and note.find('chord') is None and note.find('grace') is None:
        return 12 * (int(note.findtext('pitch/octave')) + 1) + NAMES[step] + int(note.findtext('pitch/alter', '0'))
    return None


def notation_audit(root, family):
    folder = root / 'charlie-parker-50-solos' / family
    files = sorted(folder.rglob('*.musicxml'))
    # Editions of the same stem count once. Use the first sorted edition;
    # this is not a claim that it is the authoritative transcription.
    unique = {}
    for path in files:
        unique.setdefault(path.stem.casefold(), path)
    intervals, final_steps, harmony_sizes = Counter(), Counter(), Counter()
    for path in unique.values():
        score = ET.parse(path)
        notes = [p for n in score.findall('./part[1]/measure/note') if (p := xml_pitch(n)) is not None]
        if family != 'RealBook':
            intervals.update(str(b - a) for a, b in zip(notes, notes[1:]) if -12 <= b-a <= 12)
        if family == 'FiloBass':
            previous = None
            for m in score.findall('./part[1]/measure'):
                pitches = [p for n in m.findall('note') if (p := xml_pitch(n)) is not None]
                if pitches and previous is not None:
                    final_steps[str(pitches[0] - previous)] += 1
                previous = pitches[-1] if pitches else None
        if family == 'RealBook':
            measures = score.findall('./part[1]/measure')
            harmony_sizes.update(str(len(m.findall('harmony'))) for m in measures)
    return {'xml_files': len(files), 'distinct_stems': len(unique), 'intervals': intervals,
            'barline_steps': final_steps, 'harmony_events_per_bar': harmony_sizes}


def pijama(root, max_artists):
    from music21.midi import MidiFile

    folder = root / 'pijama-jazz-piano-midi'
    with (folder / 'pijama.csv').open(encoding='utf-8-sig', newline='') as handle:
        metadata = list(csv.DictReader(handle))
    artists, attack_sizes = set(), Counter()
    unmatched = 0
    for row in sorted(metadata, key=lambda r: (r['artist'], int(r['id']))):
        if row['split'] != 'train' or row['artist'] in artists:
            continue
        path = folder / 'midi_kong' / row['midi_filepath'].removeprefix('data/midi/')
        if not path.is_file():
            unmatched += 1
            continue
        midi = MidiFile()
        midi.readstr(path.read_bytes())
        onsets = Counter()
        for track in midi.tracks:
            tick = 0
            for event in track.events:
                if event.isDeltaTime():
                    tick += event.time
                elif event.isNoteOn():
                    onsets[tick] += 1
        if onsets:
            artists.add(row['artist'])
            attack_sizes.update(str(size) for size in onsets.values())
        if len(artists) == max_artists:
            break
    return {'metadata_rows': len(metadata), 'train_artists_sampled': len(artists),
            'train_files_sampled': len(artists), 'missing_paths_encountered': unmatched,
            'exact_midi_tick_group_sizes': attack_sizes}


def fit(root, piano_sample=24):
    with (root / 'jazznet-patterns/jazznet-main/metadata/full.csv').open(encoding='utf-8-sig', newline='') as handle:
        data = list(csv.DictReader(handle))
    shapes = Counter(row['mode'] for row in data if row['type'] == 'progression')
    with (root / 'jazz-harmony-treebank/treebank.json').open(encoding='utf-8') as handle:
        songs = json.load(handle)
    return {'weimar': wjd(root), 'parker': notation_audit(root, 'Omnibook'),
            'filobass': notation_audit(root, 'FiloBass'), 'realbook': notation_audit(root, 'RealBook'),
            'pijama': pijama(root, piano_sample), 'jazznet': {'metadata_types': Counter(r['type'] for r in data),
                                                           'progression_shapes': shapes},
            'harmony_treebank': {'records': len(songs), 'meters': Counter(str(s['meter']) for s in songs)}}


def rank_bar(positions, harmonies, anchor, previous, following, bounds, fitted, width=24):
    """Rank pitch lines for one bar's written attack positions.

    Harmonies contain (offset, root PC, quality, chord-tone PCs). The first
    attack is the authored anchor. Boundary distances are planning costs,
    separate from the fitted pitch and transition probabilities.
    """
    model = fitted['weimar']['model']
    parker = fitted['parker']['intervals']
    lo, hi = bounds
    beam = [(0.0, (anchor,))]
    for i, position in enumerate(positions[1:], 1):
        _, root, quality, tones = next(h for h in reversed(harmonies) if h[0] <= position)
        _, _, _, prior_tones = next(h for h in reversed(harmonies) if h[0] <= positions[i-1])
        metric = 'beat' if position.denominator == 1 else 'off'
        pitch_counts = model['relative_pitch'].get(f'{quality}:{metric}', {})
        new = []
        for cost, line in beam:
            last = line[-1]
            pred = line[-2] if len(line) > 1 else previous
            transition = model['transition'].get(f'{max(-6, min(6, last-pred))}:{metric}', {})
            for pitch in range(max(lo, last-7), min(hi, last+7)+1):
                step = pitch - last
                if metric == 'beat' and pitch % 12 not in tones:
                    continue
                if last % 12 not in prior_tones and abs(step) > 2:
                    continue
                if len(line) > 1 and pitch == last == line[-2]:
                    continue
                chance = (.78 * probability(transition, step, len(STEPS))
                          + .15 * probability(model['unigram'], step, len(STEPS))
                          + .07 * probability(parker, step, len(STEPS)))
                added = -math.log(chance) - .5 * math.log(probability(pitch_counts, (pitch-root)%12, 12))
                added += .24 if step == 0 else .025 * abs(step)
                added += .06 * abs(pitch - (anchor + following)/2)
                if i == len(positions)-1:
                    added += .17 * abs(pitch-following)
                    if pitch % 12 not in tones and abs(pitch-following) > 2:
                        added += 1.0
                new.append((cost+added, line+(pitch,)))
        if not new:
            raise ValueError(f'No pitch candidate for attack {i} at {position}')
        beam = sorted(new)[:width]
    return beam


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', required=True, type=Path)
    cli.add_argument('--out', required=True, type=Path)
    cli.add_argument('--piano-sample', type=int, default=24)
    args = cli.parse_args()
    if args.piano_sample < 1:
        cli.error('--piano-sample must be positive')
    result = fit(args.root, args.piano_sample)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['weimar']['evaluation'], ensure_ascii=False))


if __name__ == '__main__':
    main()
