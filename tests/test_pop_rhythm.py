import unittest
from fractions import Fraction as F

from musigen.notation import parse
from musigen.pop_rhythm import choose, notate, rhythm_window


class PopRhythmTests(unittest.TestCase):
    def test_only_midi_snaps_near_grid_and_crossing_notes_are_skipped(self):
        notes = [(F(i)+F(1, 30), F(i)+F(29, 30), 60+i) for i in range(6)]
        self.assertIsNone(rhythm_window(F(0), notes, False))
        self.assertEqual(rhythm_window(F(0), notes, True), [(F(i), F(i+1), 60+i) for i in range(6)])
        self.assertIsNone(rhythm_window(F(1, 2), notes, True))

    def test_join_search_uses_distinct_works_and_rhythms(self):
        patterns = [
            {"work": str(i), "cohort": "A" if i < 3 else "B", "span": "8",
             "rhythm": [[str(F(i,4)+j), "1/2"] for j in range(6)]}
            for i in range(6)
        ]
        cost, path, traces = choose(patterns, [.75]*4, [1]*3)
        self.assertEqual(len({p["work"] for p in path}), 4)
        self.assertEqual(sum(p["cohort"] == "A" for p in path), 2)
        self.assertAlmostEqual(cost, sum(t["total"] for t in traces))

    def test_notation_keeps_long_offbeat_attack_tied(self):
        pattern = {"span": "8", "rhythm": [["3/4","17/4"], ["11/2","3/2"]]}
        tokens = parse(notate(pattern, [67, 69]))
        cursor = F(0)
        attacks = []
        tied = False
        for token in tokens:
            if token.pitches and not tied:
                attacks.append(cursor)
            cursor += token.dur
            tied = token.tie
        self.assertEqual(attacks, [F(3,4), F(11,2)])
        self.assertEqual(cursor, 8)
