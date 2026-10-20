"""Lead sheet MusicXML in the form musicomp reads as its input: part 1 the tune, part 2 the chords as block chords
(one per chord, held for its length) - the 'melody score with an accompaniment chord part' of the arranger's
material (musicomp/core/score.py `_chord_part`).  Spelling follows the key (musicomp.theory.spell)."""
from __future__ import annotations

from fractions import Fraction as F
from pathlib import Path

from music21 import chord as m21chord, key as m21key, metadata, meter, note, pitch, stream, tempo

from musicomp.theory import Key, name_to_tpc, spell, tpc_name

from musigen.harmony import Chord
from musigen.melody import BAR_LEN
from musigen.spec import Spec


def _key(spec: Spec) -> Key:
    t = name_to_tpc(spec.key)
    return Key(t, spec.mode == "minor")


def _pitch(midi: int, k: Key) -> pitch.Pitch:
    p = pitch.Pitch(tpc_name(spell(midi, k)).replace("b", "-"))
    p.octave = 4
    p.octave += (midi - int(p.midi)) // 12
    return p


def write_leadsheet(spec: Spec, chords: list[Chord], notes: list[tuple[F, F, int | None]], path: Path) -> Path:
    k = _key(spec)
    sc = stream.Score()
    sc.metadata = metadata.Metadata(title=spec.title)
    mel, acc = stream.Part(), stream.Part()
    mel.partName, acc.partName = "Melody", "Chords"
    for p in (mel, acc):
        p.append(meter.TimeSignature(spec.meter))
        p.append(m21key.Key(spec.key.replace("b", "-"), spec.mode))
    mel.insert(0, tempo.MetronomeMark(number=spec.tempo))
    for on, du, m in notes:
        n = note.Rest(quarterLength=float(du)) if m is None else note.Note(_pitch(m, k), quarterLength=float(du))
        mel.insert(float(on), n)
    blen = BAR_LEN[spec.meter]
    for c in chords:
        # close position, root in the octave below middle C
        root = 48 + (c.root_pc - 48) % 12
        midis = [root + ((pc - c.root_pc) % 12) for pc in c.pcs]
        acc.insert(float((c.bar - 1) * blen), m21chord.Chord([_pitch(x, k) for x in midis], quarterLength=float(blen)))
    sc.insert(0, mel)
    sc.insert(0, acc)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sc.write("musicxml", fp=str(path))
    return path
