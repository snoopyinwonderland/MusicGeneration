"""Choose diverse two-bar pop rhythms from the verified local chart cohorts."""
from bisect import bisect_left
from collections import Counter
from fractions import Fraction as F
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import zlib

from musigen.corpus_features import midi_features, xml_features
from musigen.melody_evidence import unpacked, xml_lines
from musigen.notation import duration
from musigen.rhythm_retrieval import events, join_cost


def source_windows(path):
    """Yield each two-bar start and the corresponding melody in quarter-note units."""
    if path.suffix.lower() == ".mid":
        data = midi_features(path, include_notes=True)
        ppq = data["ppq"]
        tracks = [track for track in data["tracks"] if track["name"].upper() == "S1"]
        if len(tracks) != 1:
            raise ValueError("S1 track ambiguous")
        notes = [(F(a, ppq), F(b, ppq), p) for a, b, ch, p, _ in tracks[0]["note_events"]
                 if ch == 3 and a < b]
        meters = data["meters"]
        for index, (tick, beats, unit) in enumerate(meters):
            if (beats, unit) != (4, 4):
                continue
            start = F(tick, ppq)
            end = F(meters[index + 1][0], ppq) if index + 1 < len(meters) else max(b for _, b, _ in notes)
            for bar in range(int((end-start)//4)-1):
                yield start + 4*bar, notes, f"tick {tick+4*bar*ppq}", True
        return

    _, measures = xml_features(path)
    _, lines = xml_lines(path, "local-musicxml/root")
    line, = (line for line in lines if line["track"] == "P1/1/1")
    notes = [(a, a+d, p) for a, d, p in unpacked(json.loads(zlib.decompress(line["events"])))]
    rows = [row for row in measures if row["part"] == "P1"]
    at = F(0)
    for index, row in enumerate(rows):
        pair = rows[index:index+2]
        if len(pair) == 2 and all(r["meter"] == "4/4" and F(r["extent_quarters"]) == 4 for r in pair):
            yield at, notes, f'{row["printed_bar"]}–{pair[1]["printed_bar"]}', False
        extent = F(row["extent_quarters"])
        if not extent and row["meter"]:
            extent = sum(4*F(meter) for meter in row["meter"].split("+"))
        at += extent


def rhythm_window(start, notes, quantize):
    """Keep only complete notes in the window, on a notatable sixteenth grid."""
    index = bisect_left(notes, start, key=lambda n: n[0])
    if any(off > start for _, off, _ in notes[:index]):
        return None
    end_index = bisect_left(notes, start+8, lo=index, key=lambda n: n[0])
    if not 6 <= end_index-index <= 20:
        return None
    result = []
    for on, off, pitch in notes[index:end_index]:
        if off > start+8:
            return None
        a, b = on-start, off-start
        ga, gb = F(round(a*4), 4), F(round(b*4), 4)
        if not quantize and (a, b) != (ga, gb):
            return None
        if abs(a-ga) > F(1, 12) or abs(b-gb) > F(1, 8) or gb <= ga:
            return None
        if result and result[-1][1] > ga:
            return None
        result.append((ga, gb, pitch))
    return result


def collect(manifest):
    patterns, coverage = [], []
    for cohort, group in manifest["cohorts"].items():
        for item in group["works"]:
            path = Path(item["path"])
            work = f'{cohort}/{item["rank"]}'
            source = {"work": work, "title": item["title"], "cohort": cohort}
            row = {**source, "windows": 0}
            coverage.append(row)
            try:
                if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                    raise ValueError("source differs from verified chart manifest")
                seen = set()
                for start, notes, position, quantize in source_windows(path):
                    window = rhythm_window(start, notes, quantize)
                    if window is None:
                        continue
                    rhythm = tuple((a, b-a) for a, b, _ in window)
                    if rhythm in seen:
                        continue
                    seen.add(rhythm)
                    pitches = [p for _, _, p in window]
                    patterns.append({
                        **source, "id": f"{work}/{position}", "span": "8", "source_position": position,
                        "source_start_quarters": str(start), "sha256": item["sha256"],
                        "timing": "quantized_sixteenth" if quantize else "written",
                        "rhythm": [[str(a), str(d)] for a, d in rhythm],
                        "directions": [0]+[(b>a)-(b<a) for a,b in zip(pitches,pitches[1:])],
                    })
                row["windows"] = len(seen)
            except (OSError, ValueError) as error:
                patterns = [p for p in patterns if p["work"] != work]
                row["error"] = str(error)
    return patterns, coverage


def choose(patterns, densities, breaths, width=48):
    """Use each source work once, with at least two works from each cohort."""
    source_counts = Counter(p["cohort"] for p in {p["work"]:p for p in patterns}.values())
    if len(source_counts) != 2 or min(source_counts.values()) < 2 or sum(source_counts.values()) < len(densities):
        raise ValueError(f"Insufficient distinct sources for {len(densities)} slots: {source_counts}")
    states = [(0.0, (), frozenset(), frozenset(), ())]
    rhythm_keys = [tuple(map(tuple, p["rhythm"])) for p in patterns]
    rhythms = [events(p) for p in patterns]
    works = [p["work"] for p in patterns]
    cohorts = [p["cohort"] for p in patterns]

    @lru_cache(maxsize=None)
    def connection(left, right):
        return join_cost(patterns[left], patterns[right])

    for slot, target in enumerate(densities):
        placement_costs = []
        for rhythm in rhythms:
            placement = abs(len(rhythm)/8-target)
            if slot == 0:
                placement += .65*abs(float(rhythm[0][0])-.5)
            if slot == len(densities)-1:
                onset, length = rhythm[-1]
                placement += .5*abs(float(8-onset-length)-.75) + .65*max(0, 1.75-float(length))
            placement_costs.append(placement)
        shortlist = []
        by_work = Counter()
        for index in sorted(range(len(patterns)), key=placement_costs.__getitem__):
            if by_work[works[index]] < 12:
                by_work[works[index]] += 1
                shortlist.append(index)
        candidates = []
        for cost, path, used_works, used_rhythms, traces in states:
            for index in shortlist:
                if works[index] in used_works or rhythm_keys[index] in used_rhythms:
                    continue
                cohort_counts = Counter(cohorts[i] for i in (*path, index))
                if cohort_counts[cohorts[index]] > len(densities)-2:
                    continue
                gap_cost, edge = 0.0, {}
                if path:
                    edge = connection(path[-1], index)
                    gap_cost = abs(float(F(edge["silence_quarters"])) - breaths[slot-1])
                placement = placement_costs[index]
                total = placement + gap_cost
                if edge:
                    total += .65*edge["components"]["pulse"] + .4*edge["components"]["density"]
                trace = {"placement": placement, "join": edge, "breath_cost": gap_cost, "total": total}
                candidates.append((cost+total, (*path,index), used_works|{works[index]},
                                   used_rhythms|{rhythm_keys[index]}, (*traces,trace)))
        states = sorted(candidates, key=lambda state: (state[0], state[1]))[:width]
        if not states:
            raise ValueError(f"No feasible diverse path at slot {slot+1}")
    cost, path, _, _, trace = states[0]
    return cost, [patterns[i] for i in path], trace


def notate(pattern, pitches):
    """Split offbeat durations into tied values without shifting any attacks."""
    codes = sorted(((duration(base, dots=dots), base+dots)
                    for base in "whqes" for dots in ("", ".", "..")
                    if duration(base, dots=dots) % F(1,4) == 0), reverse=True)
    names = "C C# D Eb E F F# G Ab A Bb B".split()
    tokens = []

    def append(name, length):
        for value, code in codes:
            while value <= length:
                length -= value
                tie = "~" if name != "r" and length else ""
                tokens.append(f"{name}/{code}{tie}")
        if length:
            raise ValueError("Duration outside the sixteenth-note grid")

    cursor = F(0)
    for (on, dur), pitch in zip(events(pattern), pitches, strict=True):
        append("r", on-cursor)
        append(f"{names[pitch%12]}{pitch//12-1}", dur)
        cursor = on+dur
    append("r", F(pattern["span"])-cursor)
    return " ".join(tokens)
