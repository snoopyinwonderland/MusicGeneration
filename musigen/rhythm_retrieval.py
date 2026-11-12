"""Opt-in retrieval of annotated phrase rhythms, connection search and pitch fitting."""
import argparse
from collections import Counter
from fractions import Fraction as F
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from musigen.melody_evidence import packed

# Initial design choices from the user's request to join borrowed rhythms.
# Components are reported independently; weights are not learned quality scores.
WEIGHTS = {"gap": 1.0, "pulse": 1.0, "density": 1.0, "repeated_rhythm": 0.5}


def extract(path, meter="4/4", bars=2):
    """Preserve source onset/duration and beat phase on annotated phrase boundaries."""
    beat_length = F(4, int(meter.split("/")[1]))
    span = F(int(meter.split("/")[0])) * beat_length * bars
    patterns, excluded = [], Counter()
    with gzip.open(path, "rt", encoding="utf8") as stream:
        for text in stream:
            row = json.loads(text)
            f = row["features"]
            start = 0
            for end, boundary in enumerate(f["phrase_end"]):
                if not boundary:
                    continue
                indices = range(start, end + 1)
                ordinal = len([v for v in f["phrase_end"][:end] if v]) + 1
                if set(f["timesignature"][start:end+1]) != {meter} or row.get("freemeter"):
                    excluded["meter"] += 1
                    start = end + 1
                    continue
                # This first implementation uses simple metre with exact beat strings.
                onset = (F(f["beat_str"][start]) - 1) * beat_length
                notes = []
                for index in indices:
                    notes.append((onset, F(f["duration_frac"][index]), f["midipitch"][index]))
                    if index < end:
                        onset += F(f["IOI_frac"][index])
                length = notes[-1][0] + notes[-1][1]
                valid = (4 <= len(notes) <= 32 and 0 <= notes[0][0] < span
                         and span - 4 * beat_length < length <= span
                         and all(d > 0 and t >= 0 for t, d, _ in notes)
                         and all(a[0]+a[1] <= b[0] for a, b in zip(notes, notes[1:])))
                if not valid:
                    excluded["span_or_polyphony"] += 1
                else:
                    directions = [0] + [(b[2] > a[2]) - (b[2] < a[2]) for a, b in zip(notes, notes[1:])]
                    patterns.append({
                        "id": f'{row["id"]}/{ordinal}', "work": row["id"],
                        "family": row.get("tunefamily"), "source_phrase": ordinal,
                        "source_notes": [start, end], "meter": meter, "span": str(span),
                        "rhythm": [[str(t), str(d)] for t, d, _ in notes],
                        "directions": directions, "padded_tail": str(span-length),
                    })
                start = end + 1
    return patterns, dict(excluded)


def events(pattern):
    return [(F(t), F(d)) for t, d in pattern["rhythm"]]


def join_cost(left, right):
    a, b = events(left), events(right)
    gap = F(left["span"]) + b[0][0] - a[-1][0] - a[-1][1]
    pulse_a = median([y[0]-x[0] for x, y in zip(a, a[1:])][-3:])
    pulse_b = median([y[0]-x[0] for x, y in zip(b, b[1:])][:3])
    # Rest over one quarter is increasingly costly, but still eligible.
    components = {
        "gap": max(0.0, float(gap)-1),
        "pulse": abs(math.log2(float(pulse_b / pulse_a))),
        "density": abs(len(a)/float(left["span"]) - len(b)/float(right["span"])),
        "repeated_rhythm": float(left["rhythm"] == right["rhythm"]),
    }
    return {"components": components, "silence_quarters": str(gap),
            "total": sum(WEIGHTS[k]*v for k, v in components.items())}


def arrange(patterns, density_targets, width=48):
    """Beam search over complete paths. Return all actual costs and source identities."""
    if len({p["work"] for p in patterns}) < 2:
        raise ValueError("At least two source works are required")
    states = [(0.0, [], [])]
    for target in density_targets:
        next_states = []
        for cost, path, traces in states:
            for pattern in patterns:
                # A previous rhythmic cell may return, but excess reuse costs progressively.
                reuse = sum(p["rhythm"] == pattern["rhythm"] for p in path)
                unary = abs(len(pattern["rhythm"])/float(F(pattern["span"]))-target)
                unary += float(F(pattern["rhythm"][0][0])) / 4 + max(0, reuse-1)
                edge = join_cost(path[-1], pattern) if path else {"components": {}, "total": 0}
                next_states.append((cost+unary+edge["total"], path+[pattern],
                                    traces+[{"placement": unary, "connection": edge}]))
        states = sorted(next_states, key=lambda item: (item[0], [p["id"] for p in item[1]]))[:width]
    eligible = [s for s in states if len({p["work"] for p in s[1]}) >= 2]
    if not eligible:
        raise ValueError("Search retained no multi-work path; increase beam width")
    return eligible[0]


def fit_pitches(pattern, chords, previous=None, final=False):
    """Dynamic programming on scale pitches, preserving source direction as a soft cost."""
    rhythm = events(pattern)
    scale = [m for m in range(62, 80) if m % 12 in (0, 2, 4, 5, 7, 9, 11)]
    states = {previous: (0.0, [])}
    for index, (onset, duration) in enumerate(rhythm):
        chord = chords[min(int(onset//4), len(chords)-1)]
        next_states = {}
        for pitch in scale:
            local = 0.0
            if onset.denominator == 1 or duration >= 1:
                local += 1.5 * (pitch % 12 not in chord)
            if index == len(rhythm)-1:
                local += 2.0 * (pitch % 12 not in chord)
                if final:
                    local += 6 * (pitch % 12 != 0)
            options = []
            for last, (cost, path) in states.items():
                step = pitch-last if last is not None else 0
                direction = (step > 0)-(step < 0)
                mismatch = index > 0 and direction != pattern["directions"][index]
                motion = abs(step)*.08 + max(0, abs(step)-5)*.8 + 1.8*mismatch
                register = abs(pitch-70)*.025
                options.append((cost+local+motion+register, path+[pitch]))
            next_states[pitch] = min(options, key=lambda item: (item[0], item[1]))
        states = next_states
    return min(states.values(), key=lambda item: (item[0], item[1]))


def notation(pattern, pitches):
    from musigen.notation import duration
    codes = {duration(base, triplet, dots): base+triplet+dots
             for base in "whqest" for triplet in ("", "3") for dots in ("", ".", "..")}
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    result, cursor = [], F(0)
    for (onset, dur), pitch in zip(events(pattern), pitches, strict=True):
        if onset > cursor:
            result.append("r/"+codes[onset-cursor])
        result.append(f"{names[pitch%12]}{pitch//12-1}/{codes[dur]}")
        cursor = onset+dur
    if cursor < F(pattern["span"]):
        result.append("r/"+codes[F(pattern["span"])-cursor])
    return " ".join(result)


def run(source, out):
    out.mkdir(parents=True, exist_ok=False)
    patterns, excluded = extract(source)
    density_targets = [1.5, 1.25, 1.75, 1, 1.5, 1.75, 1.25, 1]
    cost, selected, traces = arrange(patterns, density_targets)
    progression = [[0,4,7], [9,0,4], [2,5,9], [7,11,2],
                   [0,4,7], [5,9,0], [2,5,9], [7,11,2],
                   [9,0,4], [4,7,11], [5,9,0], [0,4,7],
                   [2,5,9], [7,11,2], [7,11,2], [0,4,7]]
    blocks, query, placements = [], [], []
    previous = None
    for i, (pattern, trace) in enumerate(zip(selected, traces, strict=True)):
        pitch_cost, pitches = fit_pitches(pattern, progression[2*i:2*i+2], previous, i == 7)
        text = notation(pattern, pitches)
        blocks.append({"bars": f"{2*i+1}-{2*i+2}", "rh": text, "dyn": "mp" if i < 4 else "mf"})
        query.extend((t+8*i, d, p) for (t, d), p in zip(events(pattern), pitches))
        previous = pitches[-1]
        placements.append({"bars": [2*i+1, 2*i+2], "pattern": pattern, **trace,
                           "pitch_cost": pitch_cost, "pitches": pitches})
    report = {"source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "eligible_patterns": len(patterns), "excluded": excluded,
              "weights": WEIGHTS, "density_targets": density_targets,
              "pitch_plan": {"key": "C major", "range_midi": [62, 79], "chord_pitch_classes": progression},
              "search": "beam48", "path_cost": cost, "placements": placements,
              "assumptions": "4/4, two-bar annotated phrases; end padded to bar; C major pitch fitting"}
    design = {"title": "자료 리듬 기반 선율", "request": "자료의 리듬을 연결하고 음높이를 붙인다.",
              "given": [], "basics": {"key": "C", "mode": "major", "meter": "4/4", "tempo": 112},
              "form": [{"label": f"악구 {i+1}", "bars": row["bars"], "function": "development"}
                       for i, row in enumerate(placements)]}
    for name, data in [("report.json", report), ("design.json", design), ("score.json", {"blocks": blocks}),
                       ("queries.json", {"rhythm_first": {"events": packed(query), "bar_length": "4", "bars": 16}})]:
        (out/name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({"patterns": len(patterns), "sources": [p["id"] for p in selected], "cost": cost}))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source", type=Path, required=True)
    cli.add_argument("--out", type=Path, required=True)
    args = cli.parse_args()
    run(args.source, args.out)
