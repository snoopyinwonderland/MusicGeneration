import copy
import json
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path
from musigen.expression import playback
from musigen.piece import build, ScoreError
from musigen.piano_io import write_musicxml
from musigen.development_comparison import signature

ROOT = Path(__file__).resolve().parents[1]


class PlaybackBalanceTest(unittest.TestCase):
    def fixture(self, name='after_rain'):
        return [json.loads((ROOT/'examples/pieces'/name/f).read_text(encoding='utf-8'))
                for f in ('design.json', 'score.json')]

    def test_opt_in_changes_playback_only_and_not_legacy_xml(self):
        design, score = self.fixture()
        original = build(design, score)
        self.assertNotIn('balance', playback(original))
        score['playback_balance'] = [{'bars': '1-8', 'lh': .8, 'reduce_lh_chords': True}]
        balanced = build(design, score)
        self.assertEqual(signature(original, 'rh'), signature(balanced, 'rh'))
        self.assertEqual(signature(original, 'lh'), signature(balanced, 'lh'))
        self.assertEqual(original.expression, balanced.expression)
        self.assertEqual(original.directions, balanced.directions)
        payload = playback(balanced)
        self.assertEqual(payload.pop('balance'), [{'start': 0., 'end': 24., 'rh': 1., 'lh': .8, 'reduce_lh_chords': True}])
        self.assertEqual(payload, playback(original))
        with tempfile.TemporaryDirectory() as tmp:
            a = write_musicxml(original, Path(tmp)/'a.xml')
            b = write_musicxml(balanced, Path(tmp)/'b.xml')
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_pickup_adjacent_ranges_sort_and_neutral_defaults(self):
        d, s = self.fixture('winter_morning')
        s['playback_balance'] = [{'bars': '1-2', 'rh': 1.1}, {'bars': '0', 'lh': .7}]
        rows = build(d, s).playback_balance
        self.assertEqual(rows[0]['end'], F(1, 2))
        self.assertEqual(rows[1]['start'], F(1, 2))
        self.assertEqual(rows[1]['lh'], 1.)
        self.assertFalse(rows[1]['reduce_lh_chords'])

    def test_invalid_or_overlapping_plans_fail_before_render(self):
        d, original = self.fixture()
        cases = [None, {}, [{'bars': '25'}], [{'bars': '0'}], [{'bars': '1', 'unexpected': 1}],
                 [{'bars': '1-4'}, {'bars': '4-8'}], [{'bars': '1', 'reduce_lh_chords': 1}]]
        cases += [[{'bars': '1', 'lh': value}] for value in [-.1, 2.1, float('nan'), float('inf'), True, '0.8']]
        for plan in cases:
            with self.subTest(plan=plan), self.assertRaises((ScoreError, ValueError)):
                s = copy.deepcopy(original); s['playback_balance'] = plan; build(d, s)
