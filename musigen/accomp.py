"""Chord symbols and accompaniment figures for a hand ("pattern" material in the score, musigen/piece.py).

  chords   "Dm Bb Gm6:2 A7:1"  one symbol per bar, or SYMBOL:BEATS to split a bar (beats of the meter: 6/8 has two)
  symbol   root (C, F#, Bb), quality, optional /bass:
           (none) m 7 maj7 m7 m7b5 dim dim7 aug sus2 sus4 7sus4 6 m6 add9 madd9
  pattern  block    the chord held (bass + close chord above)
           bass     the bass alone, held
           broken   rolling eighths over an open chord: bass, 5th, octave, 10th ... up and back
           alberti  low-high-middle-high eighths on the close chord
           waltz    bass on the first beat, the close chord on the others (4/4: bass, chord, 5th, chord; stride)
           shell    jazz shell voicing held: the bass and the chord's 7th (6th; the 3rd for a triad), within an octave
           walk     walking bass in quarter notes (beats of the meter): the root on the chord's first beat, chord
                    tones after it, and a half step into the next chord's root on the last beat before it
  "push": true      (block, shell) every chord after the figure's first is struck an eighth early and held over -
                    the anticipation of jazz and pop comping; the chord symbol stays where it is written
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
PATTERNS = ("block", "bass", "broken", "alberti", "waltz", "shell", "walk")
WALK_RANGE = (31, 50)  # G1-D3, where a walking bass line sits on the piano


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


def _shell(ch: Chord, b: int) -> list[int]:
    """Bass + the 7th (or 6th) above it, or the 3rd when the chord has neither."""
    root = (ch.root_tpc * 7) % 12
    rel = {(pc - root) % 12 for pc, _ in ch.tones}
    top = next((i for i in (10, 11, 9) if i in rel), None)
    if top is None:
        top = next((i for i in (4, 3, 5, 2) if i in rel), 7)
    pc = (root + top) % 12
    return [b, b + ((pc - b) % 12 or 12)]


def _walk(ch: Chord, b: int, beats: int, nxt: int | None, lo: int, hi: int) -> list[int]:
    """Quarter-note line over one chord: root, chord tones, then a half step into the next root."""
    line = [b]
    pcs = {pc for pc, _ in ch.tones}
    up = [m for m in range(b + 1, b + 13) if m % 12 in pcs]
    down = sorted((m for m in range(b - 12, b) if m % 12 in pcs), reverse=True)
    # walk toward the next root (F2 -> D2 goes F E C C#, not up to C3 and a leap down - 모퉁이 카페 v001 bar 9),
    # and down when there is no room above
    steps = down if (nxt is not None and nxt < b and down[0] >= lo) or b + 7 > hi else up
    while len(line) < beats - (1 if nxt is not None and beats > 1 else 0):
        line.append(steps[(len(line) - 1) % len(steps)])
    if nxt is not None and beats > 1:
        # a half step into the next root, from the side not already sounding (Gm7 -> Gb7: F, not G again)
        side = [nxt - 1, nxt + 1] if nxt > line[-1] else [nxt + 1, nxt - 1]
        line.append(next((m for m in side if m != line[-1]), side[0]))
    return line


def figure(pattern: str, chords: list[tuple[F, F, Chord]], beat: F, bass_range=(38, 50), push: bool = False) -> list[Ev]:
    if pattern not in PATTERNS:
        raise NotationError(f"unknown pattern {pattern!r} ({', '.join(PATTERNS)})")
    if pattern == "walk" and tuple(bass_range) == (38, 50):
        bass_range = WALK_RANGE
    lo, hi = bass_range
    lens = [ln for _, ln, _ in chords]
    if push and pattern in ("block", "shell"):
        for i in range(1, len(lens)):
            if lens[i - 1] > F(1, 2):
                lens[i - 1] -= F(1, 2)
                lens[i] += F(1, 2)
    evs: list[Ev] = []
    prev = None
    basses = []
    for _, _, ch in chords:
        prev = _bass(ch, prev, lo, hi)
        basses.append(prev)
    for k, ((_, _, ch), ln, b) in enumerate(zip(chords, lens, basses)):
        tag = f"{pattern}({ch.symbol})"
        close = _close(ch, max(b + 7, 48))
        if pattern == "block":
            evs.append(_ev(ln, [b] + close, ch, tag))
        elif pattern == "bass":
            evs.append(_ev(ln, [b], ch, tag))
        elif pattern == "shell":
            evs.append(_ev(ln, _shell(ch, b), ch, tag))
        elif pattern == "walk":
            n = int(ln // beat)
            nxt = basses[k + 1] if k + 1 < len(basses) else None
            for m in _walk(ch, b, n, nxt, lo, hi):
                evs.append(_ev(beat, [m], ch, tag))
            if ln - n * beat:
                evs.append(_ev(ln - n * beat, [b], ch, tag))
        elif pattern in ("broken", "alberti"):
            lad = _open(ch, b) if pattern == "broken" else close[:3]
            order = (list(range(len(lad))) + list(range(len(lad) - 2, 0, -1)) if pattern == "broken"
                     else [0, 2, 1, 2])
            j, pos = 0, F(0)
            while pos < ln:
                d = min(F(1, 2), ln - pos)
                evs.append(_ev(d, [lad[order[j % len(order)]]], ch, tag))
                j += 1
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