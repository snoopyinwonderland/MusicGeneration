"""Compact note text for motifs and bars - what the composer (a person or a language model) writes.

  tokens are separated by spaces;  PITCH/DUR  e.g.  A4/q  D5/q.  E5/e  F#5/h~  [D3,F3,A3]/h.  r/q  |
  pitch     letter, accidentals (# or b, doubled allowed), octave (C4 = middle C); r = rest;
            [p1,p2,...] = a chord in one hand (no spaces inside the brackets)
  duration  w h q e s t = whole half quarter eighth 16th 32nd (quarter-note units 4 2 1 1/2 1/4 1/8)
            a trailing 3 = triplet value (e3 = 1/3), dots after it (q. = 3/2, q.. = 7/4);
            left out = the previous token's duration (the first defaults to q)
  ~         tie into the next note (same pitches): the two are written as one longer note
  |         bar check: the notes so far must fill whole bars (an error says where it does not)

The written spelling of a literal pitch is kept in the score; notes changed by a motif operation are spelled from
the key (musicomp.theory.spell).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction as F

from musicomp.theory import name_to_tpc

BASE = {"w": F(4), "h": F(2), "q": F(1), "e": F(1, 2), "s": F(1, 4), "t": F(1, 8)}
STEP_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PITCH_RE = re.compile(r"^([A-Ga-g])(#{1,2}|b{1,2})?(-?\d)$")
TOKEN_RE = re.compile(r"^(r|\[[^\]\s]+\]|[A-Ga-g](?:#{1,2}|b{1,2})?-?\d)(?:/([whqest])(3?)(\.{0,2}))?(~)?$")


class NotationError(ValueError):
    pass


@dataclass(frozen=True)
class Ev:
    """One attack (or rest) in one voice; onsets are implicit (events follow each other)."""
    dur: F
    pitches: tuple[int, ...] = ()            # MIDI; () = rest
    tpcs: tuple[int | None, ...] = ()        # written spelling (line of fifths, 0 = C); None = spell from the key
    tie: bool = False                         # tied into the next event
    src: str = ""                             # provenance: "lit", "a", "a|step:+1", "copy:1-4", "lh:broken(Dm)" ...

    art: str | None = None
    slur: str | None = None

    @property
    def rest(self) -> bool:
        return not self.pitches


def parse_pitch(text: str) -> tuple[int, int]:
    """'F#5' -> (MIDI 78, tpc 6)."""
    m = PITCH_RE.match(text.strip())
    if not m:
        raise NotationError(f"bad pitch {text!r} (examples: C4, F#5, Bb3)")
    letter, acc, octave = m.group(1).upper(), m.group(2) or "", int(m.group(3))
    alter = acc.count("#") - acc.count("b")
    return 12 * (octave + 1) + STEP_PC[letter] + alter, name_to_tpc(letter + acc)


def duration(code: str, triplet: str = "", dots: str = "") -> F:
    d = BASE[code]
    if triplet:
        d = d * F(2, 3)
    return d * {0: F(1), 1: F(3, 2), 2: F(7, 4)}[len(dots)]


def parse(text: str, bar_len: F | None = None, src: str = "lit", start: F = F(0)) -> list[Ev]:
    """Note text -> events.  With ``bar_len`` the '|' bar checks are verified (``start`` = offset of the text's first
    note from a barline)."""
    out: list[Ev] = []
    prev = F(1)
    pos = start
    slur_open = False
    for tok in text.split():
        if tok == "|":
            if bar_len and pos % bar_len:
                raise NotationError(f"bar check '|' after {_fmt(pos - start)} quarters: not on a barline "
                                    f"(bar = {_fmt(bar_len)}), text: {text!r}")
            continue
        starts, stops = tok.startswith("("), tok.endswith(")")
        core = tok[1:] if starts else tok
        core = core[:-1] if stops else core
        art = {">": "accent", "'": "staccato", "_": "tenuto"}.get(core[-1:] or "")
        if art:
            core = core[:-1]
        if starts and slur_open:
            raise NotationError("이음줄을 겹쳐 열 수 없습니다")
        if starts:
            slur_open = True
        if stops and not slur_open:
            raise NotationError("열리지 않은 이음줄을 닫았습니다")
        if stops:
            slur_open = False
        slur = "both" if starts and stops else "start" if starts else "stop" if stops else None
        m = TOKEN_RE.match(core)
        if not m:
            raise NotationError(f"bad token {tok!r} (form PITCH/DUR, e.g. A4/q. or [D3,F3]/h or r/e)")
        head, code, trip, dots, tie = m.groups()
        if art and (tie or (out and out[-1].tie)):
            raise NotationError("붙임줄 음에는 아티큘레이션을 덧붙일 수 없습니다")
        if head == "r" and (art or slur or tie):
            raise NotationError("쉼표에는 아티큘레이션·이음줄·붙임줄을 붙일 수 없습니다")
        d = duration(code, trip, dots) if code else prev
        prev = d
        if head == "r":
            out.append(Ev(d, src=src))
        else:
            names = head[1:-1].split(",") if head.startswith("[") else [head]
            ps = [parse_pitch(n) for n in names]
            ps.sort()
            out.append(Ev(d, tuple(p for p, _ in ps), tuple(t for _, t in ps), bool(tie), src, art, slur))
        pos += d
    if slur_open:
        raise NotationError("한 재료 안에서 이음줄을 닫아야 합니다")
    return out


def length(evs: list[Ev]) -> F:
    return sum((e.dur for e in evs), F(0))


def _fmt(x: F) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"
