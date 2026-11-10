import copy
import unittest
from musigen.model_trial import assess, protocol, summarize


class ModelTrialTests(unittest.TestCase):
    def setUp(self):
        self.p = protocol()
        self.events = [dict(tick=b*240, duration=120, pitch=72, program=0) for b in range(2, 8)]

    def test_valid_and_raw_preserved(self):
        self.events[0]['tick'] += 2
        before = copy.deepcopy(self.events)
        self.assertTrue(assess(self.events, self.p)['score_eligible'])
        self.assertEqual(before, self.events)

    def test_grid_key_polyphony_rejected_without_repair(self):
        self.events[0].update(tick=484, pitch=73)
        self.events.append(dict(tick=480, duration=120, pitch=72, program=0))
        result = assess(self.events, self.p)
        self.assertFalse(result['meter_key_eligible'])
        for reason in ('outside_notation_grid', 'outside_declared_key', 'polyphonic_continuation'):
            self.assertIn(reason, result['reasons'])
        self.assertIsNone(result['quantized_events'])

    def test_truncated_and_empty_rejected(self):
        self.assertFalse(assess(self.events, self.p, False)['score_eligible'])
        self.assertFalse(assess([], self.p)['score_eligible'])

    def test_duplicate_seeds_and_stop_threshold(self):
        good = assess(self.events, self.p)
        bad = assess([], self.p)
        rows = [dict(seed=s, assessment=good if s < 3 else bad) for s in range(16)]
        self.assertTrue(summarize(rows, self.p)['stop_gate_reached'])
        rows[3]['assessment'] = good
        self.assertFalse(summarize(rows, self.p)['stop_gate_reached'])
        rows[-1]['seed'] = 0
        with self.assertRaises(ValueError):
            summarize(rows, self.p)
