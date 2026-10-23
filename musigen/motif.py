"""Motif operations: how a theme comes back changed but recognisable (the piece's main musical idea, docs/COMPOSING.md).

A motif is a list of events (musigen.notation.Ev).  Operations apply in order; each is written as a short string:

  step:+N     diatonic transposition by N scale steps in the key in force (sequence: the same motif step by step)
  semi:+N     chromatic transposition;  oct:+N  octaves
  at:PITCH    diatonic transposition so the first note becomes PITCH (chromatic if PITCH is outside the scale)
  invert      diatonic inversion around the first note (rising becomes falling)
  retro       backwards
  aug[:K]     durations x K (default 2);  dim[:K]  durations / K
  frag:I:J    notes I..J-1 (Python slice; frag:0:2 = the first two notes, frag:-2: = the last two)
  last:PITCH  the last note's pitch replaced (a different cadence note);  first:PITCH  the same for the first note

Two field-level variations (in the score's material item, musigen/piece.py):
  "pitches": "D5 C5 Bb4"   the motif's rhythm with new pitches (rhythmic identity kept)
  "durs": "q. e h"         the motif's pitches with new durations (melodic identity kept)

Every result carries its provenance, e.g. 'a|at:C5|frag:0:2', so the checks can find where each motif is used.
Minor keys use the harmonic scale (musicomp.theory.scale_pcs), so a step through the 6th and 7th degrees may give an
augmented second - check what you hear.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction as F

from musicomp.theory import Key, scale_pcs

from musigen.notation import Ev, NotationError, parse, parse_pitch


def _ladder(key: Key) -> list[int]:
    pcs = set(scale_pcs(key))
    return [m for m in range(0, 128) if m % 12 in pcs]


def _index(ladder: list[int], m: int) -> int:
    return min(range(len(ladder)), key=lambda i: (abs(ladder[i] - m), ladder[i]))


def _map(evs: list[Ev], fn) -> list[Ev]:
    return [e if e.rest else replace(e, pitches=tuple(sorted(fn(p) for p in e.pitches)), tpcs=(None,) * len(e.pitches))
            for e in evs]


def _first(evs: list[Ev]) -> int | None:
    return next((e.pitches[-1] for e in evs if not e.rest), None)


def apply(evs: list[Ev], op: str, key: Key) -> list[Ev]:
    name, _, arg = op.partition(":")
    lad = _ladder(key)
    if name == "step":
        n = int(arg)
        return _map(evs, lambda p: lad[max(0, min(len(lad) - 1, _index(lad, p) + n))])
    if name == "semi":
        return _map(evs, lambda p: p + int(arg))
    if name == "oct":
        return _map(evs, lambda p: p + 12 * int(arg))
    if name == "at":
        target, _ = parse_pitch(arg)
        f = _first(evs)
        if f is None:
            return evs
        if target % 12 in {x % 12 for x in lad} and f % 12 in {x % 12 for x in lad}:
            return apply(evs, f"step:{_index(lad, target) - _index(lad, f)}", key)
        return apply(evs, f"semi:{target - f}", key)
    if name == "invert":
        f = _first(evs)
        if f is None:
            return evs
        axis = _index(lad, f)
        return _map(evs, lambda p: lad[max(0, min(len(lad) - 1, 2 * axis - _index(lad, p)))])
    if name == "retro":
        return [replace(e, tie=False) for e in reversed(evs)]
    if name in ("aug", "dim"):
        k = F(arg) if arg else F(2)
        return [replace(e, dur=e.dur * k if name == "aug" else e.dur / k) for e in evs]
    if name == "frag":
        a, _, b = arg.partition(":")
        return evs[int(a) if a else None:int(b) if b else None]
    if name in ("last", "first"):
        target, tpc = parse_pitch(arg)
        idx = [i for i, e in enumerate(evs) if not e.rest]
        if not idx:
            return evs
        i = idx[-1] if name == "last" else idx[0]
        out = list(evs)
        out[i] = replace(out[i], pitches=(target,), tpcs=(tpc,))
        return out
    raise NotationError(f"unknown motif operation {op!r} (step, semi, oct, at, invert, retro, aug, dim, frag, last, first)")


def realise(motif: list[Ev], ops: list[str], key: Key, pitches: str | None = None, durs: str | None = None,
            label: str = "") -> list[Ev]:
    evs = list(motif)
    if pitches:
        new = [parse_pitch(p) for p in pitches.split()]
        slots = [i for i, e in enumerate(evs) if not e.rest]
        if len(new) != len(slots):
            raise NotationError(f"motif {label}: {len(slots)} notes, 'pitches' gives {len(new)}")
        for i, (m, t) in zip(slots, new):
            evs[i] = replace(evs[i], pitches=(m,), tpcs=(t,))
    if durs:
        new_d = [e.dur for e in parse(" ".join(f"C4/{d}" for d in durs.split()))]
        if len(new_d) != len(evs):
            raise NotationError(f"motif {label}: {len(evs)} events, 'durs' gives {len(new_d)}")
        evs = [replace(e, dur=d) for e, d in zip(evs, new_d)]
    for op in ops:
        evs = apply(evs, op, key)
    tag = "|".join([label] + (["pitches"] if pitches else []) + (["durs"] if durs else []) + list(ops))
    return [replace(e, src=tag) for e in evs]
