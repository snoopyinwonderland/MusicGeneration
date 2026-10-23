"""Chord symbols and accompaniment figures for a hand ("pattern" material in the score, musigen/piece.py).

  chords   "Dm Bb Gm6:2 A7:1"  one symbol per bar, or SYMBOL:BEATS to split a bar (beats of the meter: 6/8 has two)
  symbol   root (C, F#, Bb), quality, optional /bass:
           (none) m 7 maj7 m7 m7b5 dim dim7 aug sus2 sus4 7sus4 6 m6 add9 madd9
  pattern  block    the chord held (bass + close chord above)
           bass     the bass alone, held
           broken   rolling eighths over an open chord: bass, 5th, octave, 10th ... up and back
           alberti  low-high-middle-high eighths on the close chord
           waltz    bass on the first beat, the close chord on the others (4/4: bass, chord, 5th, chord)
  "bass_range": [lo, hi] MIDI for the bass (default 38-50, D2-D3); each bass is the chord's bass nearest the last one.

The figures are deliberately plain - a starting point the composer overrides with written notes where the
accompaniment should carry the theme (a left-hand motif is written as notes, not as a pattern).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction as F

from musicomp.theory import name_to_tpc

from musigen.notation import Ev, NotationError

# quality -> (tones as (semitones, fifths) above the root, MusicXML kind key in musicomp.realize.musicxml.KIND)
QUALITY = {
    "": ([(0, 0), (4, 4), (7, 1)], "M"), "m": ([(0, 0), (3, -3), (7, 1)], "m"),
    "7": ([(0, 0), (4, 4), (7, 1), (10, -2)], "Mm7"), "maj7": ([(0, 0), (4, 4), (7, 1), (11, 5)], "MM7"),
    "m7": ([(0, 0), (3, -3), (7, 1), (10, -2)], "mm7"), "m7b5": ([(0, 0), (3, -3), (6, -6), (10, -2)], "%7"),
    "dim": ([(0, 0), (3, -3), (6, -6)], "o"), "dim7": ([(0, 0), (3, -3), (6, -6), (9, -9)], "o7"),
    "aug": ([(0, 0), (4, 4), (8, 8)], "+"), "sus2": ([(0, 0), (2, 2), (7, 1)], "sus2"),
    "sus4": ([(0, 0), (5, -1), (7, 1)], "sus4"), "7sus4": ([(0, 0), (5, -1), (7, 1), (10, -2)], "sus4"),
    "6": ([(0, 0), (4, 4), (7, 1), (9, 3)], "M6"), "m6": ([(0, 0), (3, -3), (7, 1), (9, 3)], "m"),
    "add9": ([(0, 0), (2, 2), (4, 4), (7, 1)], "M"), "madd9": ([(0, 0), (2, 2), (3, -3), (7, 1)], "m"),
}
SYMBOL_RE = re.compile(r"^([A-G](?:#|b)?)(" + "|".join(sorted((re.escape(q) for q in QUALITY if q), key=len, reverse=True))
                       + r")?(?:/([A-G](?:#|b)?))?$")
PATTERNS = ("block", "bass", "broken", "alberti", "waltz")


@dataclass(frozen=True)
class Chord:
    symbol: str
    root_tpc: int
    quality: str                       # key of QUALITY
    bass_tpc: int
    tones: tuple[tuple[int, int], ...]  # (pitch class, tpc), root first

    @property
    def kind(self) -> str:
        return QUALITY[self.quality][1]

    @property
    def bass_pc(self) -> int:
        return (self.bass_tpc * 7) % 12


def parse_chord(symbol: str) -> Chord:
    m = SYMBOL_RE.match(symbol)
    if not m:
        raise NotationError(f"bad chord symbol {symbol!r} (examples: Dm, Bb/D, A7, Gm6, Fmaj7, Bm7b5, Esus4)")
    root, q, bass = m.group(1), m.group(2) or "", m.group(3)
    rt = name_to_tpc(root)
    tones = tuple((((rt + f) * 7) % 12, rt + f) for _, f in QUALITY[q][0])
    return Chord(symbol, rt, q, name_to_tpc(bass) if bass else rt, tones)


def parse_chords(text: str, bar_len: F, beat: F, start: F = F(0)) -> list[tuple[F, F, Chord]]:
    """'Dm Bb Gm6:2 A7:1' -> (offset from the figure's start, length, chord).  A bare symbol lasts to the end of its
    bar; SYMBOL:BEATS lasts that many beats.  ``start`` = where the figure begins inside its bar."""
    out: list[tuple[F, F, Chord]] = []
    pos = F(0)
    for tok in text.split():
        sym, _, beats = tok.partition(":")
        ln = F(beats) * beat if beats else bar_len - (start + pos) % bar_len
        out.append((pos, ln, parse_chord(sym)))
        pos += ln
    return out

def _bass(ch: Chord, prev: int | None, lo: int, hi: int) -> int:
    cands = [m for m in range(lo, hi + 1) if m % 12 == ch.bass_pc] or [lo + (ch.bass_pc - lo) % 12]
    ref = prev if prev is not None else (lo + hi) // 2
    return min(cands, key=lambda m: (abs(m - ref), m))


def _close(ch: Chord, above: int) -> list[int]:
    """The chord's tones in close position from the first tone at or above ``above`` (three or four notes)."""
    out = []
    m = above
    while len(out) < min(4, len(ch.tones)):
        if m % 12 in {pc for pc, _ in ch.tones}:
            out.append(m)
        m += 1
    return out


def _open(ch: Chord, bass: int, n: int = 4) -> list[int]:
    out, m = [bass], bass + 6
    while len(out) < n + 1:
        if m % 12 in {pc for pc, _ in ch.tones}:
            out.append(m)
        m += 1
    return out


def _ev(ln: F, notes, ch: Chord, tag: str) -> Ev:
    """Spelled from the chord (A7's C#, D's F# in D minor), the bass from the slash."""
    sp = {pc: t for pc, t in ch.tones}
    sp.setdefault(ch.bass_pc, ch.bass_tpc)
    notes = tuple(sorted(notes))
    return Ev(ln, notes, tuple(ch.bass_tpc if i == 0 and m % 12 == ch.bass_pc else sp.get(m % 12)
                               for i, m in enumerate(notes)), src=tag)


def figure(pattern: str, chords: list[tuple[F, F, Chord]], beat: F, bass_range=(38, 50)) -> list[Ev]:
    if pattern not in PATTERNS:
        raise NotationError(f"unknown pattern {pattern!r} ({', '.join(PATTERNS)})")
    lo, hi = bass_range
    evs: list[Ev] = []
    prev = None
    for _, ln, ch in chords:
        b = _bass(ch, prev, lo, hi)
        prev = b
        tag = f"{pattern}({ch.symbol})"
        close = _close(ch, max(b + 7, 48))
        if pattern == "block":
            evs.append(_ev(ln, [b] + close, ch, tag))
        elif pattern == "bass":
            evs.append(_ev(ln, [b], ch, tag))
        elif pattern in ("broken", "alberti"):
            lad = _open(ch, b) if pattern == "broken" else close[:3]
            order = (list(range(len(lad))) + list(range(len(lad) - 2, 0, -1)) if pattern == "broken"
                     else [0, 2, 1, 2])
            k, pos = 0, F(0)
            while pos < ln:
                d = min(F(1, 2), ln - pos)
                evs.append(_ev(d, [lad[order[k % len(order)]]], ch, tag))
                k += 1
                pos += d
        else:  # waltz
            pos, i = F(0), 0
            while pos < ln:
                d = min(beat, ln - pos)
                if i == 0:
                    notes = (b,)
                elif i == 2 and beat == 1 and ln >= 4:
                    notes = (_open(ch, b, 1)[1],)
                else:
                    notes = tuple(close)
                evs.append(_ev(d, notes, ch, tag))
                i += 1
                pos += d
    return evs
