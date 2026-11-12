import gzip
import json
from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest

from musigen.rhythm_retrieval import extract, join_cost, notation, fit_pitches, arrange
from musigen.notation import parse

class RhythmRetrievalTests(unittest.TestCase):
    def pattern(self, name, rhythm):
        return {"id": name, "work": name, "span": "8", "rhythm": rhythm,
                "directions": [0, 1, -1, 0]}

    def test_annotation_preserves_pickup_rest_and_duration(self):
        row = {"id": "example", "features": {
            "phrase_end": [False, False, False, True],
            "timesignature": ["4/4"]*4, "beat_str": ["3/2", "2", "4", "1"],
            "duration_frac": ["1/2", "1", "1", "2"],
            "IOI_frac": ["1/2", "2", "1", "2"], "midipitch": [60, 62, 60, 60]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"source.jsonl.gz"
            with gzip.open(path, "wt", encoding="utf8") as stream:
                stream.write(json.dumps(row)+"\n")
            patterns, _ = extract(path)
        self.assertEqual(patterns[0]["rhythm"], [["1/2","1/2"],["1","1"],["3","1"],["4","2"]])
        self.assertEqual(patterns[0]["padded_tail"], "2")
        self.assertEqual(patterns[0]["directions"], [0,1,-1,0])

    def test_boundary_silence_increases_cost(self):
        a = self.pattern("a", [["0","1"],["1","1"],["2","1"],["7","1"]])
        b = self.pattern("b", [["0","1"],["1","1"],["2","1"],["3","1"]])
        delayed = self.pattern("c", [["2","1"],["3","1"],["4","1"],["5","1"]])
        self.assertGreater(join_cost(a, delayed)["total"], join_cost(a, b)["total"])

    def test_pitch_fitting_keeps_rhythm_and_can_be_notated(self):
        p = self.pattern("a", [["0","1"],["1","1"],["3","2"],["6","1"]])
        _, pitches = fit_pitches(p, [[0,4,7], [0,4,7]], final=True)
        self.assertEqual(pitches[-1] % 12, 0)
        onset, actual = F(0), []
        for event in parse(notation(p, pitches)):
            if not event.rest:
                actual.append([str(onset),str(event.dur)])
            onset += event.dur
        self.assertEqual(actual, p["rhythm"])
        self.assertEqual(onset, 8)

    def test_search_cost_is_accounted_and_uses_multiple_works(self):
        a = self.pattern("a", [["0","1"],["1","1"],["2","1"],["7","1"]])
        b = self.pattern("b", [["0","1"],["2","1"],["4","1"],["6","1"]])
        cost, path, traces = arrange([a,b], [.5,.5,.5])
        self.assertGreaterEqual(len({p["work"] for p in path}), 2)
        self.assertAlmostEqual(cost, sum(t["placement"]+t["connection"]["total"] for t in traces))

if __name__ == "__main__":
    unittest.main()
