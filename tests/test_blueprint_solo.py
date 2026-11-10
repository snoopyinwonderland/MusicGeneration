import copy
import tempfile
import unittest
from pathlib import Path
from fractions import Fraction as F
from test_blueprint import inputs
from musigen.blueprint import prepare,write_xml
from musigen.blueprint_solo import realize,preserve_prefix,performed_harmony


class BlueprintSoloTest(unittest.TestCase):
    def setup_score(self):
        motif,plan=inputs();lead,score,details=prepare(motif,plan)
        score['blocks'][0]['lh']={'pattern':'shell','chords':'C/E:2 Am7:2'}
        score['blocks'][1]['lh']={'pattern':'shell','chords':'G7/B:2 C:2'}
        return plan,lead,score,details

    def test_realization_keeps_melody_and_complete_design(self):
        plan,lead,score,details=self.setup_score()
        solo,frozen=realize(lead,plan,score)
        self.assertEqual(solo.analysis_chords,lead.analysis_chords)
        self.assertNotEqual([n.pitches for n in solo.notes if n.hand=='lh'],[n.pitches for n in lead.notes if n.hand=='lh'])
        rows=performed_harmony(solo,details)
        self.assertTrue(any(r['missing_tone_names_in_played_lh'] for r in rows))
        self.assertTrue(all(r['scope'].startswith('notes_overlapping') for r in rows))
        self.assertEqual(len(details['events'][0]['tones']),3)

    def test_wrong_melody_and_wrong_key_are_rejected(self):
        for mode in ('rh','key'):
            plan,lead,score,_=self.setup_score()
            if mode=='rh':score['blocks'][1]['rh']='E5/h C5/h'
            else:score['blocks'][1]['key']='G major'
            with self.subTest(mode=mode),self.assertRaises(ValueError):realize(lead,plan,score)

    def test_reharmonizing_pattern_is_rejected(self):
        plan,lead,score,_=self.setup_score();score['blocks'][0]['lh']['chords']='F:2 Am7:2'
        with self.assertRaisesRegex(ValueError,'화성'):realize(lead,plan,score)

    def test_prefix_checks_both_hands_and_duration(self):
        plan,lead,score,_=self.setup_score();solo,_=realize(lead,plan,score)
        with tempfile.TemporaryDirectory() as tmp:
            p=write_xml(solo,Path(tmp)/'previous.musicxml')
            self.assertTrue(preserve_prefix(solo,p,1)['notes_spelling_timing_exact'])
            for hand in ('rh','lh'):
                changed=copy.deepcopy(solo)
                next(n for n in changed.notes if n.hand==hand).dur+=F(1,2)
                with self.subTest(hand=hand),self.assertRaisesRegex(ValueError,'보존'):preserve_prefix(changed,p,1)

    def test_expression_is_explicit_and_opt_in(self):
        plan,lead,score,_=self.setup_score()
        score['expression']=[{'bars':'1','hairpin':'cresc'}]
        solo,_=realize(lead,plan,score)
        self.assertEqual([e['kind'] for e in solo.expression],['hairpin'])
        self.assertEqual(lead.expression,[])
