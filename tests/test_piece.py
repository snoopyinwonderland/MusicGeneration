"""The piano-piece frame: notation, motif operations, figures, building, checks, versions (examples/pieces)."""
import copy
import json
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

import musigen  # noqa: F401
from musicomp.theory import Key, name_to_tpc

from musigen import checks
from musigen.accomp import figure, parse_chord, parse_chords
from musigen.design import DesignError, summary_ko, validate
from musigen.motif import realise
from musigen.notation import NotationError, parse
from musigen.piece import ScoreError, build
from musigen.versions import save

WORK = Path(__file__).resolve().parents[1] / "examples" / "pieces" / "after_rain"
DMIN = Key(name_to_tpc("D"), True)
FMAJ = Key(name_to_tpc("F"), False)


def work():
    return (json.loads((WORK / "design.json").read_text(encoding="utf-8")),
            json.loads((WORK / "score.json").read_text(encoding="utf-8")))


def pitches(evs):
    return [e.pitches[0] for e in evs if not e.rest]


class NotationTest(unittest.TestCase):
    def test_durations_and_defaults(self):
        evs = parse("A4/q. B4/e C5 r/h [D3,F3]/e3 E5/q.. ")
        self.assertEqual([e.dur for e in evs], [F(3, 2), F(1, 2), F(1, 2), F(2), F(1, 3), F(7, 4)])
        self.assertEqual(evs[4].pitches, (50, 53))
        self.assertTrue(evs[3].rest)

    def test_bar_check(self):
        parse("A4/h. | B4/h.", F(3))
        with self.assertRaises(NotationError):
            parse("A4/h | B4/h.", F(3))

    def test_spelling_kept(self):
        e = parse("Bb4/q A#4/q")
        self.assertEqual(e[0].pitches, e[1].pitches)
        self.assertNotEqual(e[0].tpcs, e[1].tpcs)


class MotifTest(unittest.TestCase):
    a = parse("A4/q D5/q. E5/e")

    def test_at_is_diatonic(self):
        self.assertEqual(pitches(realise(self.a, ["at:C5"], FMAJ)), [72, 77, 79])   # C5 F5 G5

    def test_invert_retro_frag_aug(self):
        b = parse("F5/h E5/e D5/e")
        self.assertEqual(pitches(realise(b, ["invert"], FMAJ)), [77, 79, 81])       # F5 G5 A5
        self.assertEqual(pitches(realise(b, ["retro"], FMAJ)), [74, 76, 77])
        self.assertEqual(len(realise(b, ["frag:0:2"], FMAJ)), 2)
        self.assertEqual(sum(e.dur for e in realise(b, ["aug"], FMAJ)), 6)

    def test_pitches_keep_rhythm(self):
        r = realise(self.a, [], DMIN, pitches="D5 C5 Bb4", label="a")
        self.assertEqual([e.dur for e in r], [e.dur for e in self.a])
        self.assertEqual(r[0].src, "a|pitches")
        self.assertEqual(checks.motif_of("copy:1-4<" + realise(self.a, ["step:+1"], DMIN, label="a")[0].src), "a")


class AccompTest(unittest.TestCase):
    def test_symbols(self):
        c = parse_chord("Bb/D")
        self.assertEqual((c.root_tpc, c.bass_tpc), (name_to_tpc("Bb"), name_to_tpc("D")))
        self.assertEqual(parse_chord("A7sus4").quality, "7sus4")
        with self.assertRaises(NotationError):
            parse_chord("H7")

    def test_broken_fills_the_bar_and_spells_from_the_chord(self):
        cs = parse_chords("Gm6:2 A7:1 A7", F(3), F(1))
        evs = figure("broken", cs, F(1))
        self.assertEqual(sum(e.dur for e in evs), 6)
        self.assertIn(name_to_tpc("C#"), [t for e in evs for t in e.tpcs])   # A7's third is C#, not Db


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.design, self.score = work()
        self.piece = build(self.design, self.score)

    def test_example_builds_clean(self):
        self.assertEqual(validate(self.design), [])
        res = checks.check(self.piece, self.design)
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["warnings"], [])
        self.assertEqual(res["stats"]["climax"]["bars"], [14])

    def test_return_copies_the_opening(self):
        one = [(n.onset, n.pitches) for n in self.piece.in_bars(1, 4, "rh") if n.voice == 1]
        back = [(n.onset - 48, n.pitches) for n in self.piece.in_bars(17, 20, "rh") if n.voice == 1]
        self.assertEqual(one, back)
        res = checks.check(self.piece, self.design)
        self.assertIn("a", next(s for s in res["sections"] if s["function"] == "return")["motifs_used"])

    def test_short_block_is_an_error(self):
        sc = copy.deepcopy(self.score)
        sc["blocks"][0]["rh"] = "A4/q D5/q"
        with self.assertRaisesRegex(ScoreError, "short by 1"):
            build(self.design, sc)

    def test_span_error_at_grade(self):
        sc = copy.deepcopy(self.score)
        sc["blocks"][-1]["lh"] = "[D2,A2,F#3]/h."
        res = checks.check(build(self.design, sc), self.design)
        self.assertTrue(any("24마디 왼손" in e for e in res["errors"]))

    def test_musicxml_reads_back(self):
        from musicomp.realize.musicxml import read_parts
        from musigen.piano_io import write_musicxml
        with tempfile.TemporaryDirectory() as d:
            parts = read_parts(write_musicxml(self.piece, Path(d) / "p.musicxml"))
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].staves, 2)
        self.assertEqual(sum(len(n.pitches) for n in parts[0].notes), sum(len(n.pitches) for n in self.piece.notes))


class DesignTest(unittest.TestCase):
    def test_given_marked(self):
        design, _ = work()
        text = summary_ko(design)
        self.assertIn("| 장면 | 비가 그친 밤, 혼자 걸으며 지난 일을 떠올림 | 요청 |", text)
        self.assertIn("| 박자 | 3/4 | 제안 |", text)

    def test_gap_in_form(self):
        design, _ = work()
        design["form"][1]["bars"] = [10, 16]
        with self.assertRaises(DesignError):
            validate(design)


class VersionTest(unittest.TestCase):
    def test_changed_bars_and_preserve(self):
        design, score = work()
        with tempfile.TemporaryDirectory() as d:
            save(Path(d), design, score, "first")
            sc = copy.deepcopy(score)
            next(b for b in sc["blocks"] if b["bars"] == "14")["rh"] = "D6/q E6/q. F6/e"        # bar 14 only
            info = save(Path(d), design, sc, "climax later in the bar", ["bars:1-8", "rh:14"])
            hist = (Path(d) / "history.md").read_text(encoding="utf-8")
        self.assertEqual(info["changed_bars"], {"rh": [14], "lh": []})
        self.assertEqual(len(info["preserve_broken"]), 1)
        self.assertIn("rh:14", info["preserve_broken"][0])
        self.assertIn("들어 볼 곳: 14마디", hist)


if __name__ == "__main__":
    unittest.main()
