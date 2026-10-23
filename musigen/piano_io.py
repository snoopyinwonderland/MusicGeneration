"""Piano solo output: MusicXML (one part, two staves) with musicomp's writer, and a MIDI file to listen to.

musicomp.realize.musicxml.write_score is the same writer the arrangements use: spelling kept, notes split at
barlines and beats with ties, several voices per staff, chord symbols, dynamics.
"""
from __future__ import annotations

import re
from pathlib import Path

from musicomp.core.score import Measure
from musicomp.realize.musicxml import Direction, HarmonySymbol, OutNote, OutPart, write_score

from musigen.piece import Piece


def write_musicxml(piece: Piece, path: Path, subtitle: str = "") -> Path:
    part = OutPart("P1", "Piano", "Pno.", 1, [("G", 2), ("F", 4)])
    for n in piece.notes:
        part.notes.append(OutNote(n.onset, n.dur, list(n.pitches), voice=n.voice, staff=1 if n.hand == "rh" else 2,
                                  meta={"src": n.src}))
    for on, text, dyn in piece.directions:
        part.directions.append(Direction(on, text, 1, "below" if dyn else "above", dyn))
    prev = None
    for on, ch in piece.chords:
        if ch.symbol == prev:  # the same chord again (A7 at the end of one bar and through the next): written once
            continue
        prev = ch.symbol
        # <kind text> is the suffix only - the reader prints the root and the /bass itself ('DDm', 'F/A/A' otherwise)
        suffix = re.sub(r"^[A-G][#b]?", "", ch.symbol).split("/")[0]
        part.harmonies.append(HarmonySymbol(on, ch.root_tpc, ch.kind, ch.bass_tpc, suffix))
    blen = piece.bar_len
    measures = [Measure(i, str(i + 1), i * blen, blen, blen) for i in range(piece.bars)]
    beats, beat_type = (int(x) for x in piece.meter.split("/"))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_score(path, piece.title, [part], measures, beats, beat_type, piece.key.sharps, piece.key.minor,
                       tempo=piece.qpm, subtitle=subtitle)


def write_midi(musicxml: Path, path: Path) -> Path | None:
    """MIDI through music21 (for listening without a notation program); None when music21 cannot convert."""
    try:
        from music21 import converter
        converter.parse(str(musicxml)).write("midi", fp=str(path))
        return Path(path)
    except Exception:  # noqa: BLE001 - listening copy only; the MusicXML is the result
        return None


def seconds(piece: Piece) -> float:
    return float(piece.bars * piece.bar_len) * 60 / piece.qpm
