"""Baseline tune over a chord progression (rules, seeded) - the part to replace with a learned model later.

  rhythm   per bar a template for the meter (normal / busier / calmer / held); inside a section the odd bars share
           one template and the even bars another (a rhythmic motif), the section's last bar closes long
  contour  an arch over each section (peak about 60% in, or at a request's 'climax' bar); B-type sections (a label
           not seen before after the first) sit a little higher; requests move the register by +-4 semitones
  pitch    notes on a beat: the chord tone nearest the contour (leaps at most a sixth); between them scale steps
           toward the next target
  cadence  authentic / plagal: the tonic on the last downbeat; half: a tone of the dominant (2nd / 7th / 5th degree)
  repeat   a section label seen before repeats that section's tune, except its last two bars when the cadence
           differs
Returns notes as (onset, duration, midi | None for a rest), quarter-note units from the start of the piece.
"""
from __future__ import annotations

import math
import random
from fractions import Fraction as F

from musigen.harmony import Chord, tonic_pc
from musigen.spec import Spec

BAR_LEN = {"2/4": F(2), "3/4": F(3), "4/4": F(4), "3/8": F(3, 2), "6/8": F(3), "12/8": F(6)}
H = F(1, 2)
Q = F(1, 4)
TEMPLATES = {
    "4/4": {"normal": [[1, 1, 1, 1], [F(3, 2), H, 1, 1], [1, H, H, 2], [2, 1, 1], [1, 1, 2], [H, H, 1, 1, 1]],
            "busier": [[H] * 8, [H, H, H, H, 1, 1], [1, H, H, H, H, 1]],
            "calmer": [[2, 2], [3, 1], [2, 1, 1]], "held": [[4]], "close": [[2, 2], [4], [3, 1]]},
    "3/4": {"normal": [[1, 1, 1], [2, 1], [F(3, 2), H, 1]], "busier": [[H, H, 1, 1], [H] * 6],
            "calmer": [[2, 1], [3]], "held": [[3]], "close": [[3], [2, 1]]},
    "2/4": {"normal": [[1, 1], [H, H, 1]], "busier": [[H] * 4], "calmer": [[2]], "held": [[2]], "close": [[2]]},
    "6/8": {"normal": [[1, H, 1, H], [F(3, 2), 1, H], [H, H, H, F(3, 2)]], "busier": [[H] * 6],
            "calmer": [[F(3, 2), F(3, 2)], [3]], "held": [[3]], "close": [[3], [F(3, 2), F(3, 2)]]},
    "3/8": {"normal": [[1, H], [H, H, H]], "busier": [[H, Q, Q, H]], "calmer": [[F(3, 2)]], "held": [[F(3, 2)]],
            "close": [[F(3, 2)]]},
}
TEMPLATES["12/8"] = {k: [p + p for p in v] for k, v in TEMPLATES["6/8"].items()}


def scale(spec: Spec) -> list[int]:
    rel = (0, 2, 3, 5, 7, 8, 11) if spec.mode == "minor" else (0, 2, 4, 5, 7, 9, 11)
    return sorted((tonic_pc(spec) + r) % 12 for r in rel)


def _range(spec: Spec) -> tuple[int, int]:
    if spec.register:
        from music21 import pitch
        lo, hi = (pitch.Pitch(x.strip()).midi for x in spec.register.split("-"))
        return int(lo), int(hi)
    t = tonic_pc(spec)
    centre = min((m for m in range(60, 72) if m % 12 == t), key=lambda m: abs(m - 67))
    return centre - 5, centre + 12


def _beat(meter: str) -> F:
    return F(3, 2) if meter in ("6/8", "12/8") else F(4, int(meter.split("/")[1]))


def _feel(spec: Spec, bar: int) -> str:
    for r in spec.requests_at(bar):
        if r.rhythm:
            return r.rhythm
    return "normal"


def _section_of(spec: Spec, bar: int):
    start = 1
    for sec in spec.form:
        if start <= bar < start + sec.bars:
            return sec, start
        start += sec.bars
    raise IndexError(bar)


def compose_melody(spec: Spec, chords: list[Chord]) -> list[tuple[F, F, int | None]]:
    rng = random.Random(spec.seed * 7919 + 1)
    blen = BAR_LEN[spec.meter]
    beat = _beat(spec.meter)
    lo, hi = _range(spec)
    sc = scale(spec)
    ladder = [m for m in range(lo - 2, hi + 3) if m % 12 in sc]
    templates = TEMPLATES[spec.meter]
    notes: list[tuple[F, F, int | None]] = []
    first_bar_of: dict[str, int] = {}
    seen_labels: list[str] = []
    motif: dict[tuple[int, str], list] = {}
    prev = None
    start = 1
    for si, sec in enumerate(spec.form):
        repeat_from = first_bar_of.get(sec.label)
        if repeat_from is None:
            first_bar_of[sec.label] = start
        lift = 3 if (sec.label not in seen_labels and si > 0 and sec.label != spec.form[0].label) else 0
        seen_labels.append(sec.label)
        climax = next((b for r in spec.requests if r.climax for b in range(r.bars[0], r.bars[1] + 1)
                       if start <= b < start + sec.bars), None)
        peak_pos = ((climax - start) / max(1, sec.bars - 1)) if climax else 0.6
        cad_bars = 2 if sec.cadence != "none" else 0
        for k in range(sec.bars):
            bar = start + k
            t0 = (bar - 1) * blen
            if repeat_from is not None and k < sec.bars - cad_bars:
                src0 = (repeat_from + k - 1) * blen
                notes += [(on - src0 + t0, du, m) for on, du, m in notes if src0 <= on < src0 + blen]
                last = [m for on, du, m in notes if m is not None]
                prev = last[-1] if last else prev
                continue
            if any(r.rest for r in spec.requests_at(bar)):
                notes.append((t0, blen, None))
                continue
            closing = k == sec.bars - 1 and sec.cadence != "none"
            feel = "close" if closing else _feel(spec, bar)
            key_ = (k % 2, feel)
            if key_ not in motif:
                motif[key_] = rng.choice(templates.get(feel) or templates["normal"])
            durs = [F(d) for d in motif[key_]]
            pos = k / max(1, sec.bars - 1)
            shape = math.sin(math.pi * min(1.0, pos / (2 * peak_pos)) if pos <= peak_pos else
                             math.pi / 2 + math.pi / 2 * (pos - peak_pos) / max(1e-6, 1 - peak_pos))
            shift = sum(4 if r.register == "higher" else -4 if r.register == "lower" else 0 for r in spec.requests_at(bar))
            target = lo + 2 + (hi - lo - 4) * (0.35 + 0.55 * shape) + lift + shift
            ch = chords[bar - 1]
            on = t0
            for i, du in enumerate(durs):
                strong = (on - t0) % beat == 0
                last_note = closing and i == len(durs) - 1
                if last_note:
                    pcs = _cadence_pcs(spec, sec.cadence, ch)
                else:
                    pcs = ch.pcs if strong else None
                if pcs:
                    cands = [m for m in range(lo, hi + 1) if m % 12 in pcs]
                    if prev is not None:
                        near = [m for m in cands if abs(m - prev) <= 9] or cands
                    else:
                        near = cands
                    m = min(near, key=lambda x: abs(x - target) + (1.5 if x == prev else 0) + rng.random() * 0.8)
                else:
                    # a scale step from the previous note toward the target (a neighbour when already there)
                    base = prev if prev is not None else int(target)
                    i0 = min(range(len(ladder)), key=lambda j: abs(ladder[j] - base))
                    step = 1 if target > base + 1 else -1 if target < base - 1 else rng.choice((1, -1))
                    m = ladder[max(0, min(len(ladder) - 1, i0 + step))]
                notes.append((on, du, m))
                prev = m
                on += du
        start += sec.bars
    return notes


def _cadence_pcs(spec: Spec, cadence: str, ch: Chord) -> list[int]:
    t = tonic_pc(spec)
    if cadence == "half":
        # a tone of the dominant: its root, third (leading tone) or fifth (2nd degree)
        return [p for p in ch.pcs[:3]]
    return [t]
