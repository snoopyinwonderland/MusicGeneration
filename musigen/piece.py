"""The score (score.json): the notes of a piano piece, built from motifs, written notes, copies and figures.

  {
    "motifs": {"a": "A4/q D5/q. E5/e", "b": {"notes": "F5/h E5/e D5/e", "note": "answer to a"}},
    "show_chords": true,
    "blocks": [
      {"bars": "1-2", "rh": [{"motif": "a"}, {"motif": "b"}],
                      "lh": {"pattern": "broken", "chords": "Dm Bb"}, "dyn": "p"},
      {"bars": "3",   "rh": {"motif": "a", "ops": ["at:D5"]}, "lh": {"pattern": "broken", "chords": "Gm"}},
      {"bars": "9-12", "key": "F major", ...},
      {"bars": "17-20", "copy": "1-4", "lh": {"pattern": "waltz", "chords": "Dm Bbmaj7 Gm7 A7"}},
      {"bars": "24", "rh": "[A4,D5,F#5]/h.", "lh": "[D2,A2,F#3]/h.", "dyn": "pp", "text": "rit."}
    ]
  }

Blocks follow each other from bar 1 to the design's last bar.  A block's voices are rh, rh2 (a second right-hand
voice, e.g. an inner line under the tune), lh, lh2; a voice left out rests.  Each voice is material:
  "A4/q D5/q."                       written notes (musigen/notation.py)
  {"motif": "a", "ops": [...], "pitches": "...", "durs": "..."}   a motif, changed (musigen/motif.py)
  {"pattern": "broken", "chords": "Dm Bb", "bass_range": [38, 50]} a figure (musigen/accomp.py)
  [item, item, ...]                  items one after another
Every voice must fill the block exactly; the error names the block, the voice and the shortfall.
  "copy": "1-4"     every voice of bars 1-4 (built earlier), unless the block gives that voice itself;
                    "copy_ops": {"rh": ["oct:+1"]} changes a copied voice
  "key": "F major"  the key in force for motif operations and spelling inside the block (a modulation; the key
                    signature stays the piece's)
  "dyn": "p"        a dynamic at the block's first beat; "text": "rit." a word above the staff
A tie at the end of a block ("D5/h.~") joins the next block's first note when the pitches are the same.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction as F

from musicomp.theory import Key, name_to_tpc, spell

from musigen import accomp
from musigen.design import bar_len, beat, qpm, total_bars, pickup
from musigen.motif import apply, realise
from musigen.notation import Ev, NotationError, length, parse

VOICES = {"rh": ("rh", 1), "rh2": ("rh", 2), "lh": ("lh", 5), "lh2": ("lh", 6)}
DYNAMICS = {"ppp", "pp", "p", "mp", "mf", "f", "ff", "fff", "sf", "sfz", "fp"}


class ScoreError(ValueError):
    pass


@dataclass
class Note:
    onset: F
    dur: F
    pitches: tuple[tuple[int, int], ...]   # (MIDI, tpc)
    hand: str                              # rh | lh
    voice: int                             # 1, 2 (right hand), 5, 6 (left hand)
    src: str                               # provenance (musigen/notation.py Ev.src)
    art: str | None = None
    slur: str | None = None


@dataclass
class Piece:
    title: str
    key: Key
    meter: str
    qpm: float
    bars: int
    notes: list[Note] = field(default_factory=list)
    directions: list[tuple[F, str, str | None]] = field(default_factory=list)  # (onset, text, dynamic)
    chords: list[tuple[F, accomp.Chord]] = field(default_factory=list)

    pickup: F = F(0)
    expression: list[dict] = field(default_factory=list)
    bar_keys: dict[int, Key] = field(default_factory=dict)
    motifs: dict[str, list[Ev]] = field(default_factory=dict)

    def bar_start(self, bar: int) -> F:
        return F(0) if bar == 0 else self.pickup + (bar - 1) * self.bar_len

    def bar_end(self, bar: int) -> F:
        return self.pickup if bar == 0 else self.pickup + bar * self.bar_len

    @property
    def bar_len(self) -> F:
        return bar_len(self.meter)

    def bar_of(self, onset: F) -> int:
        return 0 if onset < self.pickup else int((onset - self.pickup) // self.bar_len) + 1

    def in_bars(self, a: int, z: int, hand: str | None = None) -> list[Note]:
        lo, hi = self.bar_start(a), self.bar_end(z)
        return [n for n in self.notes if lo <= n.onset < hi and (hand is None or n.hand == hand)]


def parse_key(text: str) -> Key:
    """'F major', 'd minor', 'F', 'd' (lower case = minor)."""
    name, _, mode = text.strip().partition(" ")
    minor = mode.strip().lower() == "minor" if mode else name[:1].islower()
    return Key(name_to_tpc(name[0].upper() + name[1:]), minor)


def _bars(spec, n_bars: int) -> tuple[int, int]:
    a, _, z = str(spec).partition("-")
    a, z = int(a), int(z or a)
    if not 1 <= a <= z <= n_bars:
        raise ScoreError(f"bars {spec!r} outside 1-{n_bars}")
    return a, z


def _material(item, motifs: dict, key: Key, blen: F, bt: F, where: str, chords_out: list, start: F) -> list[Ev]:
    """``start`` = the item's offset from the block's first barline (bar checks, chord lengths)."""
    if isinstance(item, list):
        out: list[Ev] = []
        for x in item:
            out += _material(x, motifs, key, blen, bt, where, chords_out, start + length(out))
        return out
    if isinstance(item, str):
        return parse(item, blen, "lit", start % blen)
    if not isinstance(item, dict):
        raise ScoreError(f"{where}: material is text, a motif, a pattern or a list")
    if "motif" in item:
        mid = item["motif"]
        if mid not in motifs:
            raise ScoreError(f"{where}: unknown motif {mid!r}")
        return realise(motifs[mid], list(item.get("ops", [])), key, item.get("pitches"), item.get("durs"), mid)
    if "pattern" in item:
        cs = accomp.parse_chords(item.get("chords", ""), blen, bt, start % blen)
        chords_out += [(start + off, ch) for off, _, ch in cs]
        return accomp.figure(item["pattern"], cs, bt, tuple(item.get("bass_range", (38, 50))))
    raise ScoreError(f"{where}: material item needs 'motif' or 'pattern'")


def _copy(voice: list[tuple[F, Ev, Key]], s0: F, s1: F, tag: str) -> list[Ev]:
    """The events of bars [s0, s1) of a built voice, as material (a held note entering s0 is left out: a rest)."""
    evs, pos = [], s0
    for on, e, _ in voice:
        if s0 <= on < s1:
            if on > pos:
                evs.append(Ev(on - pos, src=tag))
            d = min(e.dur, s1 - on)
            evs.append(replace(e, dur=d, tie=e.tie and d == e.dur, src=f"{tag}<{e.src}"))
            pos = on + d
    if pos < s1:
        evs.append(Ev(s1 - pos, src=tag))
    return evs


def _place(timeline: list[tuple[F, Ev, Key]], hand: str, voice: int) -> list[Note]:
    """Events -> notes; tied events of the same pitches become one note, rests vanish."""
    out: list[Note] = []
    tie_open = False
    for on, e, key in timeline:
        if not e.rest:
            if tie_open and out and tuple(m for m, _ in out[-1].pitches) == e.pitches and out[-1].onset + out[-1].dur == on:
                out[-1].dur += e.dur
                if e.slur in ("stop", "both"):
                    out[-1].slur = "both" if out[-1].slur in ("start", "both") else "stop"
            else:
                tp = e.tpcs or (None,) * len(e.pitches)
                ps = tuple((m, t if t is not None else spell(m, key)) for m, t in zip(e.pitches, tp))
                out.append(Note(on, e.dur, ps, hand, voice, e.src, e.art, e.slur))
        tie_open = e.tie
    return out


def build(design: dict, score: dict) -> Piece:
    b = design["basics"]
    key = Key(name_to_tpc(b["key"]), b["mode"] == "minor")
    meter = b["meter"]
    blen, bt = bar_len(meter), beat(meter)
    n_bars = total_bars(design)
    motifs: dict[str, list[Ev]] = {}
    for mid, m in (score.get("motifs") or {}).items():
        try:
            motifs[mid] = [replace(e, src=mid) for e in parse(m if isinstance(m, str) else m["notes"])]
        except NotationError as e:
            raise ScoreError(f"motif {mid}: {e}") from e
    piece = Piece(design.get("title", "Untitled"), key, meter, qpm(b), n_bars)
    piece.pickup = pickup(b)
    piece.motifs = motifs
    timeline: dict[str, list[tuple[F, Ev, Key]]] = {v: [] for v in VOICES}
    blocks = list(score.get("blocks") or [])
    if piece.pickup and (not blocks or str(blocks[0].get("bars")) != "0"):
        blocks.insert(0, {"bars": "0"})
    nxt = 0 if piece.pickup else 1
    for bi, blk in enumerate(blocks):
        a, z = (0, 0) if piece.pickup and str(blk.get("bars")) == "0" else _bars(blk.get("bars"), n_bars)
        where = f"block {bi} (bars {blk.get('bars')})"
        if a != nxt:
            raise ScoreError(f"{where}: expected to start at bar {nxt}")
        nxt = z + 1
        lkey = parse_key(blk["key"]) if blk.get("key") else key
        t0, need = piece.bar_start(a), piece.bar_end(z) - piece.bar_start(a)
        piece.bar_keys.update({i: lkey for i in range(a, z+1)})
        src0 = None
        if blk.get("copy"):
            ca, cz = _bars(blk["copy"], n_bars)
            if cz >= a or cz - ca != z - a:
                raise ScoreError(f"{where}: copy {blk['copy']} must be earlier bars, as many as the block")
            src0 = piece.bar_start(ca)
        for v, (hand, _) in VOICES.items():
            if v in blk:
                chords: list = []
                try:
                    evs = _material(blk[v], motifs, lkey, blen, bt, f"{where} {v}", chords, F(0))
                except NotationError as e:
                    raise ScoreError(f"{where} {v}: {e}") from e
                piece.chords += [(t0 + off, ch) for off, ch in chords]
            elif src0 is not None:
                evs = _copy(timeline[v], src0, src0 + need, f"copy:{blk['copy']}")
                for op in (blk.get("copy_ops") or {}).get(v, []):
                    evs = [replace(x, src=f"{x.src}|{op}") for x in apply(evs, op, lkey)]
                if hand == "lh" and v == "lh":
                    piece.chords += [(on - src0 + t0, ch) for on, ch in piece.chords if src0 <= on < src0 + need]
            else:
                evs = [Ev(need, src="rest")]
            got = length(evs)
            if got != need:
                raise ScoreError(f"{where} {v}: {got} quarters written, the bars need {need} "
                                 f"({'short' if got < need else 'over'} by {abs(need - got)})")
            pos = t0
            for e in evs:
                timeline[v].append((pos, e, lkey))
                pos += e.dur
        if blk.get("dyn"):
            if blk["dyn"] not in DYNAMICS:
                raise ScoreError(f"{where}: dyn one of {sorted(DYNAMICS)}")
            piece.directions.append((t0, blk["dyn"], blk["dyn"]))
        if blk.get("text"):
            piece.directions.append((t0, str(blk["text"]), None))
    if nxt != n_bars + 1:
        raise ScoreError(f"blocks end at bar {nxt - 1}, the design has {n_bars} bars")
    for v, (hand, vn) in VOICES.items():
        piece.notes += _place(timeline[v], hand, vn)
    from musigen.expression import compile_expression
    piece.expression = compile_expression(piece, score.get("expression", []))
    piece.notes.sort(key=lambda n: (n.onset, n.voice))
    piece.chords = sorted(piece.chords, key=lambda c: c[0]) if score.get("show_chords", True) else []
    return piece
