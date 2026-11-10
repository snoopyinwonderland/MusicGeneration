import unittest
from musigen.phrase_review import evidence


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.library={'phrases':[{'id':'p','status':'observed'},{'id':'q','status':'skipped'}]}
        self.uses=[{'bars':[3,4],'reference_ids':['p'],'observation':'끝 쉼','decision':'새 쉼 작성'}]

    def test_evidence_requires_exact_changed_bars(self):
        self.assertEqual(evidence(self.library,self.uses,[3,4])['observed_ids'],['p'])
        with self.assertRaises(ValueError):evidence(self.library,self.uses,[3])

    def test_skipped_and_unknown_references_rejected(self):
        for source in ('q','unknown'):
            self.uses[0]['reference_ids']=[source]
            with self.subTest(source=source),self.assertRaises(ValueError):evidence(self.library,self.uses,[3,4])

    def test_observation_is_not_a_composition_decision(self):
        self.uses[0].pop('decision')
        with self.assertRaises(ValueError):evidence(self.library,self.uses,[3,4])
