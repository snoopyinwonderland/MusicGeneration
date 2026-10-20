"""Baseline checks: spec validation, the composer's rules, and that musicomp reads the lead sheet back."""
import json
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

import musigen  # noqa: F401
from musigen.harmony import progression, tonic_pc
from musigen.melody import BAR_LEN, compose_melody
from musigen.score_io import write_leadsheet
from musigen.spec import SpecError, from_dict

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "evening.json"


def example(**over):
    d = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    d.update(over)
    return from_dict(d)


class SpecTest(unittest.TestCase):
    def test_unknown_field_rejected(self):
        with self.assertRaises(SpecError):
            from_dict({"key": "C", "colour": "warm"})

    def test_request_outside_piece_rejected(self):
        with self.assertRaises(SpecError):
            example(requests=[{"bars": [40, 41], "rhythm": "busier"}])

    def test_progression_length_checked(self):
        with self.assertRaises(SpecError):
            example(progression=["I", "IV"])


class ComposeTest(unittest.TestCase):
    def setUp(self):
        self.spec = example()
        self.chords = progression(self.spec)
        self.notes = compose_melody(self.spec, self.chords)

    def test_cadences_and_repeats(self):
        toks = [c.token for c in self.chords]
        self.assertEqual(toks[0], "I")
        self.assertEqual(toks[7], "V")             # half cadence, end of the first A
        self.assertEqual(toks[15], "I")            # authentic cadence, end of the second A
        self.assertEqual(toks[1:6], toks[9:14])    # the repeated A repeats its chords

    def test_length_and_strong_beats_on_chord_tones(self):
        blen = BAR_LEN[self.spec.meter]
        self.assertEqual(sum(d for _, d, _ in self.notes), blen * self.spec.total_bars)
        strong = [(on, m) for on, _, m in self.notes if m is not None and on % 1 == 0]
        ok = sum(m % 12 in self.chords[int(on // blen)].pcs for on, m in strong)
        self.assertGreaterEqual(ok / len(strong), 0.9)

    def test_ends_on_tonic(self):
        last = [m for _, _, m in self.notes if m is not None][-1]
        self.assertEqual(last % 12, tonic_pc(self.spec))

    def test_rest_request(self):
        spec = example(requests=[{"bars": [3, 3], "rest": True}])
        notes = compose_melody(spec, progression(spec))
        blen = BAR_LEN[spec.meter]
        self.assertTrue(all(m is None for on, _, m in notes if 2 * blen <= on < 3 * blen))

    def test_musicomp_reads_the_leadsheet(self):
        from musicomp.core.score import load_melody
        with tempfile.TemporaryDirectory() as d:
            path = write_leadsheet(self.spec, self.chords, self.notes, Path(d) / "lead.musicxml")
            mel = load_melody(path)
        self.assertEqual(len(mel.notes), sum(1 for _, _, m in self.notes if m is not None))
        self.assertGreaterEqual(len(mel.given_chords), self.spec.total_bars - 1)
        self.assertEqual(mel.given_chords[0].bass_tpc * 7 % 12, tonic_pc(self.spec))


if __name__ == "__main__":
    unittest.main()
