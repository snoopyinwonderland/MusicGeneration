"""Piano solo output: MusicXML (one part, two staves) with musicomp's writer, and a MIDI file to listen to.

musicomp.realize.musicxml.write_score is the same writer the arrangements use: spelling kept, notes split at
barlines and beats with ties, several voices per staff, chord symbols, dynamics.
"""
from __future__ import annotations

import re
from pathlib import Path
from fractions import Fraction as F

from musicomp.core.score import Measure
from musicomp.realize.musicxml import Direction, HarmonySymbol, OutNote, OutPart, write_score

from musigen.piece import Piece


def piano_part(piece: Piece) -> OutPart:
    part = OutPart("P1", "Piano", "Pno.", 1, [("G", 2), ("F", 4)])
    for n in piece.notes:
        part.notes.append(OutNote(n.onset, n.dur, list(n.pitches), voice=n.voice, staff=1 if n.hand == "rh" else 2,
                                  meta={"src": n.src}, articulation=n.art,
                                  **({"slur": n.slur} if n.slur else {})))
    for on, text, dyn in piece.directions:
        part.directions.append(Direction(on, text, 1, "below" if dyn else "above", dyn))
    for e in piece.expression:
        if e["kind"] == "pedal":
            for on, value in [(e["start"], "start")] + [(t, "change") for t in e["changes"]] + [(e["end"], "stop")]:
                part.directions.append(Direction(on, "", 2, "below", pedal=value))
        else:
            part.directions.append(Direction(e["start"], "", 1, "below",
                                             wedge="crescendo" if e["mode"] == "cresc" else "diminuendo"))
            part.directions.append(Direction(e["end"], "", 1, "below", wedge="stop"))
    # Adjacent explicit pedal spans share a change, not simultaneous stop/start.
    pedal_at = {}
    for direction in part.directions:
        if getattr(direction, "pedal", None):
            pedal_at.setdefault(direction.onset, []).append(direction)
    for group in pedal_at.values():
        if {d.pedal for d in group} == {"start", "stop"}:
            for d in group:
                part.directions.remove(d)
            part.directions.append(Direction(group[0].onset, "", 2, "below", pedal="change"))
    part.directions.sort(key=lambda d: d.onset)
    prev, prev_on = None, None
    for on, ch in piece.chords:
        # the same chord running on (A7 at the end of one bar and through the next) is written once; after a gap
        # (written notes without symbols) it is written again (햇살 골목 v001 lost the G of bar 17 after bar 8's G)
        same = ch.symbol == prev and on - prev_on <= piece.bar_len
        prev, prev_on = ch.symbol, on
        if same:
            continue
        # <kind text> is the suffix only - the reader prints the root and the /bass itself ('DDm', 'F/A/A' otherwise)
        suffix = re.sub(r"^[A-G][#b]?", "", ch.symbol).split("/")[0]
        part.harmonies.append(HarmonySymbol(on, ch.root_tpc, ch.kind, ch.bass_tpc, suffix))
    return part


def write_musicxml(piece: Piece, path: Path, subtitle: str = "") -> Path:
    part = piano_part(piece)
    blen = piece.bar_len
    measures = ([Measure(0, "0", F(0), piece.pickup, blen)] if piece.pickup else [])
    measures += [Measure(i + len(measures), str(i + 1), piece.pickup + i * blen, blen, blen) for i in range(piece.bars)]
    beats, beat_type = (int(x) for x in piece.meter.split("/"))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_score(path, piece.title, [part], measures, beats, beat_type, piece.key.sharps, piece.key.minor,
                       tempo=piece.qpm, subtitle=subtitle)


def write_midi(musicxml: Path, path: Path) -> Path | None:
    """MIDI through music21 (for listening without a notation program); None when music21 cannot convert."""
    try:
        from music21 import converter
        converter.parse(str(musicxml), forceSource=True).write("midi", fp=str(path))
        return Path(path)
    except Exception:  # noqa: BLE001 - listening copy only; the MusicXML is the result
        return None


def seconds(piece: Piece) -> float:
    return float(piece.pickup + piece.bars * piece.bar_len) * 60 / piece.qpm
