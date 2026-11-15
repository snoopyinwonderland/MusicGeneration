"""Opt-in borrowing from uninterrupted, annotated 4/4 phrases."""

from collections import defaultdict
import argparse
from itertools import pairwise
import json
from pathlib import Path

from musigen.notation import length, parse
from musigen.pop_rhythm import notate
from musigen.rhythm_retrieval import events, extract


def rank_pairs(phrases, bars):
    """Match whole phrases from different works and, when known, tune families."""
    if bars not in (2, 3):
        raise ValueError("Borrowing requires two or three bars")
    by_attack_count = defaultdict(list)
    for phrase in phrases:
        if phrase["meter"] != "4/4" or phrase["span"] != str(4 * bars):
            continue
        rhythm = events(phrase)
        counts = tuple(sum(t // 4 == bar for t, _ in rhythm) for bar in range(bars))
        if (not all(counts) or len(rhythm) < 4 * bars - 2
                or any((value * 4).denominator != 1 for event in rhythm for value in event)):
            continue
        intervals = tuple(b - a for a, b in pairwise(phrase["pitches"]))
        by_attack_count[len(rhythm)].append((phrase, rhythm, intervals, counts))

    ranked = []
    for group in by_attack_count.values():
        for rhythm_source, rhythm, rhythm_intervals, counts in group:
            for melody_source, timing, intervals, melody_counts in group:
                family = rhythm_source["family"]
                if (rhythm_source["work"] == melody_source["work"]
                        or (family and family == melody_source["family"]) or rhythm == timing
                        or rhythm_intervals == intervals):
                    continue
                # Keep pitch gestures near their original bar, with leeway for a pickup or release.
                if sum(abs(a - b) for a, b in zip(counts, melody_counts, strict=True)) > 2:
                    continue
                pairs = zip(rhythm, timing, strict=True)
                # Match attack positions and length, keeping the input rhythm and pitch order intact.
                timing_cost = sum(abs(on - ref) + abs(dur - ref_dur) / 2
                                  for (on, dur), (ref, ref_dur) in pairs) / len(rhythm)
                leaps = sum(abs(interval) >= 5 for interval in intervals)
                ranked.append((timing_cost, leaps, rhythm_source, melody_source))
    ranked.sort(key=lambda row: (row[0], -row[1], row[2]["id"], row[3]["id"]))
    return ranked


def combine(rhythm_source, melody_source, shift=0):
    """Combine in order. Ties preserve source durations across score barlines."""
    span = rhythm_source["span"]
    if (span not in ("8", "12") or span != melody_source["span"]
            or rhythm_source["meter"] != "4/4" or melody_source["meter"] != "4/4"):
        raise ValueError("Source blocks must have the same two- or three-bar 4/4 span")
    rhythm = events(rhythm_source)
    pitches = [pitch + shift for pitch in melody_source["pitches"]]
    notes = [(t, t + duration, pitch) for (t, duration), pitch in zip(rhythm, pitches, strict=True)]
    written = []
    for start in range(0, int(span), 4):
        end = start + 4
        overlaps = [(a, b, pitch) for a, b, pitch in notes if a < end and b > start]
        bar = {"span": "4", "rhythm": [[max(a, start) - start, min(b, end) - max(a, start)]
                                          for a, b, _ in overlaps]}
        tokens = notate(bar, [pitch for _, _, pitch in overlaps])
        if overlaps and overlaps[-1][1] > end:
            tokens += "~"
        written.append(tokens)
    return written


def build_study(recipe, source_dir):
    """Resolve the recipe to score notation and retain both source locations."""
    libraries = {}
    study = []
    for entry in recipe["candidates"]:
        bars = entry["borrowed_bars"]
        if bars not in (2, 3):
            raise ValueError("Borrowing requires two or three bars")
        sources = {}
        for role in ("rhythm", "melody"):
            collection, ident = entry[role]
            library_key = collection, bars
            if library_key not in libraries:
                phrases, _ = extract(Path(source_dir) / recipe["collections"][collection],
                                      bars=bars, include_melody=True)
                libraries[library_key] = {p["id"]: p for p in phrases}
            sources[role] = libraries[library_key][ident]
        if not rank_pairs(list(sources.values()), bars):
            raise ValueError(f"Incompatible source pair for {entry['id']}")
        ending = entry["response"]
        if len(ending) != 4 - bars or any(length(parse(bar)) != 4 for bar in ending):
            raise ValueError(f"Response must complete four bars for {entry['id']}")
        written = combine(sources["rhythm"], sources["melody"], entry.get("shift", 0))
        study.append({**entry, "time": "4/4", "bars": written + ending,
                      "source_notes": {role: source["source_notes"] for role, source in sources.items()}})
    return study


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="2–3마디 리듬과 선율을 다른 출처에서 가져와 결합")
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    recipe = json.loads(args.recipe.read_text(encoding="utf-8-sig"))
    study = build_study(recipe, args.source_dir)
    with args.out.open("x", encoding="utf-8") as output:
        json.dump(study, output, ensure_ascii=False, indent=2)
