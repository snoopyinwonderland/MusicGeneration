import copy
import tempfile
import unittest
from pathlib import Path
from fractions import Fraction
from test_blueprint import inputs
from musigen.blueprint import prepare, write_xml, verify_roundtrip


class FunctionalHarmonyTest(unittest.TestCase):
    def exchange(self,motif,plan):
        piece,_,details=prepare(motif,plan)
        with tempfile.TemporaryDirectory() as tmp:
            result=verify_roundtrip(piece,write_xml(piece,Path(tmp)/'score.musicxml'))
        self.assertTrue(result['exact'])
        return details,result

    def test_augmented_sixths_keep_sharp_four_not_flat_five(self):
        for figure,tones in [('It6',{'Ab','C','F#'}),('Fr43',{'Ab','C','D','F#'}),('Ger65',{'Ab','C','Eb','F#'})]:
            motif,plan=inputs()
            plan['harmony'][1]={'bar':1,'offset':'2','duration':'2','figure':figure}
            with self.subTest(figure=figure):
                details,_=self.exchange(motif,plan)
                e=details['events'][1]
                self.assertEqual(set(e['tones']),tones)
                self.assertIsNone(e['root'])
                self.assertIsNone(e['inversion'])
                self.assertTrue(e['resolution_check']['target_root_or_bass_present'])

    def test_secondary_and_leading_tone_chords(self):
        for figure,symbol in [('V7/V','D7'),('V65/ii','A7/C#'),('viio7/ii','C#dim7')]:
            motif,plan=inputs();plan['harmony'][1]={'bar':1,'offset':'2','duration':'2','figure':figure}
            with self.subTest(figure=figure):
                details,_=self.exchange(motif,plan)
                self.assertEqual(details['events'][1]['symbol'],symbol)
                self.assertEqual(details['events'][1]['roman']['figure'],figure)

    def test_augmented_tendency_voices_require_octave_sensitive_resolution(self):
        motif,plan=inputs()
        plan['harmony'][1]={'bar':1,'offset':'2','duration':'2','figure':'Ger65','voicing':['Ab2','C3','Eb3','F#3']}
        plan['harmony'][2]={'bar':2,'duration':'2','symbol':'C/G','voicing':['G2','C3','E3','G3']}
        details,_=self.exchange(motif,plan)
        movements=details['events'][1]['resolution_check']['augmented_sixth_tendency_movements']
        self.assertTrue(all(x['matched_in_written_lh'] for x in movements))
        plan['harmony'][2]['voicing']=['G2','C3','E3']
        details,_=self.exchange(motif,plan)
        self.assertEqual([x['matched_in_written_lh'] for x in details['events'][1]['resolution_check']['augmented_sixth_tendency_movements']],[True,False])

    def test_symbol_must_agree_with_function(self):
        motif,plan=inputs();plan['harmony'][0].update(symbol='D7',figure='V7/ii')
        with self.assertRaisesRegex(ValueError,'구성음 또는 베이스'):prepare(motif,plan)

    def test_keys_change_and_return(self):
        motif,plan=inputs()
        plan['design']['form'][0]['bars']=[1,3]
        plan['score']['blocks'] += [{'bars':'3','rh':'C5/w','key':'C major'}]
        plan['score']['blocks'][1]['key']='G major'
        plan['harmony'][2:] = [{'bar':2,'duration':'4','figure':'V7/V'}, {'bar':3,'duration':'4','symbol':'C'}]
        details,result=self.exchange(motif,plan)
        self.assertEqual(result['key_regions'],3)
        self.assertEqual(details['events'][2]['symbol'],'A7')
        self.assertEqual([k['tonic'] for k in details['key_plan']],['C','G','C'])

    def test_relative_key_mode_is_preserved(self):
        motif,plan=inputs();plan['score']['blocks'][1]['key']='A minor'
        details,result=self.exchange(motif,plan)
        self.assertEqual(result['key_regions'],2)
        self.assertEqual(details['events'][2]['key'],'A minor')

    def test_unresolved_target_is_reported_not_silently_replaced(self):
        motif,plan=inputs();plan['harmony'][0]={'bar':1,'duration':'2','figure':'V7/V'}
        details,_=self.exchange(motif,plan)
        self.assertFalse(details['events'][0]['resolution_check']['target_root_or_bass_present'])
        self.assertEqual(details['events'][1]['symbol'],'Am7')
