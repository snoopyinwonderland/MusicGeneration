"""Chord progression for a spec: one chord per bar (baseline), sampled from musicomp's genre statistics.

The progression comes before the tune here (composition), the reverse of musicomp's harmonisation of a given tune.
Statistics: musicomp.analysis.harmonize_gen (1- to 4-gram counts over key-relative chord tokens per genre/mode).

  first bar          tonic
  section end        authentic: V - I | half: ... V | plagal: IV - I | none: free
  forced             spec.progression (every bar) or a request's "chord" (its bars)
  elsewhere          sampled: n-gram probability ** (1 / temperature), no chord three bars running
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from musicomp.analysis.harmonize_gen import QPCS, lm_logp, parse_token, vocabulary

from musigen.spec import Spec
from musicomp.theory import name_to_tpc


@dataclass
class Chord:
    bar: int          # 1-based
    token: str        # key-relative roman token (musicomp convention)
    root_pc: int      # absolute pitch class
    quality: str      # M m 7 M7 m7 o o7 %7 + sus
    pcs: list[int]    # absolute pitch classes, root first


def tonic_pc(spec: Spec) -> int:
    return (name_to_tpc(spec.key) * 7) % 12


def make_chord(spec: Spec, bar: int, token: str) -> Chord:
    mode = spec.mode
    parsed = parse_token(token, mode)
    if parsed is None:
        raise ValueError(f"bar {bar}: unknown chord token {token!r} (examples: I, vi, IV, V7, ii7, bVII, V7/V)")
    rel, q = parsed
    root = (tonic_pc(spec) + rel) % 12
    return Chord(bar, token, root, q, [(root + i) % 12 for i in QPCS[q]])


def progression(spec: Spec, temperature: float = 0.8) -> list[Chord]:
    mode = spec.mode
    tonic = "i" if mode == "minor" else "I"
    dom = "V7" if spec.genre != "classical" else "V"
    sub = "iv" if mode == "minor" else "IV"
    n = spec.total_bars
    fixed: dict[int, str] = {}
    if spec.progression:
        fixed = {i + 1: t for i, t in enumerate(spec.progression)}
    else:
        fixed[1] = tonic
        end = 0
        for sec in spec.form:
            end += sec.bars
            if sec.cadence == "authentic":
                fixed[end], fixed[end - 1] = tonic, dom
            elif sec.cadence == "half":
                fixed[end] = "V"
            elif sec.cadence == "plagal":
                fixed[end], fixed[end - 1] = tonic, sub
        for r in spec.requests:
            if r.chord:
                for b in range(r.bars[0], r.bars[1] + 1):
                    fixed[b] = r.chord
    # a repeated section (same label) repeats the first one's chords, apart from its own cadence bars
    first_of: dict[str, int] = {}
    repeat_of: dict[int, int] = {}
    start = 1
    for sec in spec.form:
        if sec.label in first_of:
            for k in range(sec.bars):
                repeat_of[start + k] = first_of[sec.label] + k
        else:
            first_of[sec.label] = start
        start += sec.bars
    rng = random.Random(spec.seed)
    vocab = [t for t in vocabulary(spec.genre, mode) if "/" not in t or spec.genre == "jazz"]
    hist: list[str] = []
    out: list[Chord] = []
    for bar in range(1, n + 1):
        if bar in fixed:
            tok = fixed[bar]
        elif bar in repeat_of and repeat_of[bar] <= len(hist):
            tok = hist[repeat_of[bar] - 1]
        else:
            nxt = fixed.get(bar + 1)
            cands = []
            for t in vocab:
                if len(hist) >= 2 and hist[-1] == hist[-2] == t:
                    continue
                s = lm_logp(spec.genre, mode, tuple(hist[-3:]), t)
                if nxt:  # lead into the fixed chord that follows
                    s += 0.5 * lm_logp(spec.genre, mode, tuple((hist + [t])[-3:]), nxt)
                cands.append((t, s))
            w = [math.exp(s / max(temperature, 1e-3)) for _, s in cands]
            tok = rng.choices([t for t, _ in cands], weights=w)[0]
        hist.append(tok)
        out.append(make_chord(spec, bar, tok))
    return out
