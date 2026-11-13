"""Fit short transposed motifs to an existing rhythm and accompaniment."""
from collections import defaultdict
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction as F
import hashlib
from pathlib import Path

from musigen.accomp import parse_chords
from musigen.pop_rhythm import rhythm_window, source_windows
from musigen.rhythm_retrieval import events

MAJOR = frozenset((0, 2, 4, 5, 7, 9, 11))
LENGTHS = (4, 5, 6)


@dataclass(frozen=True)
class Motif:
    work: str
    title: str
    source_position: str
    source_onset: F
    intervals: tuple[int, ...]
    rhythm: tuple[tuple[F, F], ...]


@dataclass(frozen=True)
class Borrowing:
    start: int
    pitches: tuple[int, ...]
    motif: Motif


def rhythm_shape(rhythm):
    """Normalize by the first-to-last attack span for comparison across tempos."""
    first = rhythm[0][0]
    span = rhythm[-1][0]-first
    return tuple(((on-first)/span, length/span) for on, length in rhythm)


def motifs_from_chart(manifest):
    motifs = defaultdict(list)
    coverage = {}
    for cohort, group in manifest["cohorts"].items():
        for item in group["works"]:
            path = Path(item["path"])
            work = f'{cohort}/{item["rank"]}'
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(f"Source differs from chart manifest: {work}")
            seen = set()
            for start, notes, position, midi in source_windows(path):
                window = rhythm_window(start, notes, midi)
                if window is None:
                    continue
                for length in LENGTHS:
                    for index in range(len(window)-length+1):
                        selected = window[index:index+length]
                        if any(b[0]-a[1] > 1 for a,b in zip(selected, selected[1:])):
                            continue
                        root = selected[0][2]
                        intervals = tuple(p-root for _,_,p in selected)
                        if len(set(intervals)) < 3 or max(intervals)-min(intervals) > 12:
                            continue
                        shape = rhythm_shape([(a, b-a) for a,b,_ in selected])
                        key = (intervals, shape)
                        if key not in seen:
                            seen.add(key)
                            motifs[length].append(Motif(work, item["title"], position,
                                                        start+selected[0][0], intervals, shape))
            coverage[work] = len(seen)
    return motifs, coverage


def fit_options(placements, progression, motifs):
    """Shortlist transpositions per donor. A None chord leaves the bar open for later harmony."""
    options, baseline, bars = defaultdict(list), [], []
    chord_times, chord_tones = [], []
    for bar, symbols in enumerate(progression):
        if symbols is None:
            chord_times.append(F(4*bar))
            chord_tones.append(None)
            continue
        for onset, _, chord in parse_chords(symbols, F(4), F(1)):
            chord_times.append(4*bar+onset)
            chord_tones.append({pc for pc, _ in chord.tones})
    for placement in placements:
        pattern = placement["pattern"]
        rhythm, original = events(pattern), placement["pitches"]
        first_bar = placement["bars"][0]-1
        offset = len(baseline)
        baseline.extend(original)
        bars.extend(first_bar+int(on//4)+1 for on, _ in rhythm)
        for index in range(len(rhythm)):
            for length in LENGTHS:
                target = rhythm[index:index+length]
                if len(target) != length:
                    continue
                if any(b[0] - sum(a) > 1 for a,b in zip(target,target[1:])):
                    continue
                shape = rhythm_shape(target)
                local_chords = [chord_tones[bisect_right(chord_times, 4*first_bar+on)-1]
                                for on,_ in target]
                accent = [2.0 if on % 1 == 0 or d >= 1 else .35 for on,d in target]
                reference = tuple(original[index:index+length])
                by_donor = {}
                for motif in motifs[length]:
                    if motif.work == pattern["work"] or motif.rhythm == shape:
                        continue
                    for root in range(64, 82):
                        pitches = tuple(root+step for step in motif.intervals)
                        if sum(a != b for a,b in zip(pitches, reference)) < (length+1)//2:
                            continue
                        if any(p < 64 or p > 81 or p % 12 not in MAJOR for p in pitches):
                            continue
                        if first_bar == len(progression)-2 and index+length == len(rhythm) and pitches[-1] % 12:
                            continue
                        cost = sum(w for p,c,w in zip(pitches,local_chords,accent)
                                   if c is not None and p % 12 not in c)
                        cost += .12*sum(abs(a-b) for a,b in zip(pitches,reference))
                        cost += .12*sum(max(0,abs(a-b)-4) for a,b in zip(pitches,pitches[1:]))
                        old = by_donor.get(motif.work)
                        if old is None or cost < old[0]:
                            by_donor[motif.work] = (cost, Borrowing(offset+index,pitches,motif))
                options[offset+index].extend(by_donor.values())
    return options, baseline, bars


def arrange_borrowings(options, baseline, target, width=8):
    """Search for an exact note budget, at most two fragments per donor."""
    frontier = [defaultdict(list) for _ in range(len(baseline)+1)]
    frontier[0][0].append((0.0, baseline[0], (), ()))
    for start, bucket in enumerate(frontier[:-1]):
        for covered, states in bucket.items():
            for cost, previous, edits, donors in sorted(states, key=lambda item: item[0])[:width]:
                if covered+len(baseline)-start-1 >= target:
                    pitch = baseline[start]
                    step = abs(previous-pitch)
                    frontier[start+1][covered].append((cost+.12*max(0,step-4),pitch,edits,donors))
                for local_cost, edit in options[start]:
                    donor = edit.motif.work
                    size = len(edit.pitches)
                    if covered+size > target or donors.count(donor) >= 2 or (donors and donors[-1] == donor):
                        continue
                    step = abs(previous-edit.pitches[0])
                    total = cost + local_cost + .3*max(0,step-4) + .3*donors.count(donor)
                    frontier[start+size][covered+size].append(
                        (total,edit.pitches[-1],(*edits,edit),(*donors,donor)))
        bucket.clear()
    end = frontier[-1].get(target)
    if not end:
        return None
    cost, _, edits, _ = min(end, key=lambda item: item[0])
    return cost, edits


def compare_versions(placements, progression, motifs, ratios):
    options, baseline, bars = fit_options(placements, progression, motifs)
    for ratio in ratios:
        target = len(baseline)*ratio/100
        budgets = sorted(range(len(baseline)+1), key=lambda count: (abs(count-target),count))
        for budget in budgets:
            result = arrange_borrowings(options, baseline, budget)
            if result is not None:
                break
        cost, edits = result
        pitches = baseline.copy()
        for edit in edits:
            pitches[edit.start:edit.start+len(edit.pitches)] = edit.pitches
        yield {"target":ratio, "count":budget, "total":len(baseline), "cost":cost,
               "changed_notes":sum(a!=b for a,b in zip(baseline,pitches)), "pitches":pitches,
               "edits":[{"start":e.start, "count":len(e.pitches), "bars":[bars[e.start],bars[e.start+len(e.pitches)-1]],
                         "work":e.motif.work,"title":e.motif.title,"position":e.motif.source_position,
                         "source_onset":str(e.motif.source_onset),"intervals":list(e.motif.intervals)}
                        for e in edits]}
