import copy
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

from musigen.blueprint import prepare,write_xml
from musigen.development_comparison import controls,common_left,verify_written
from musigen.variation_reference import upper_staff,compare,features
from test_blueprint import inputs


class ReferenceTest(unittest.TestCase):
    def parse(self,text):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.krn';p.write_text(text,encoding='utf-8')
            return upper_staff(p)

    def test_rests_and_ties_keep_timing(self):
        seq=self.parse('**kern\n*M4/4\n=1\n4r\n4cc[\n4cc]\n4dd\n*-\n')
        self.assertEqual(seq['span'],'4')
        self.assertEqual([e['duration'] for e in seq['events']],['1','2','1'])
        self.assertEqual(features(seq)['attacks'],2)
        self.assertEqual(features(seq)['rest_quarters'],'1')

    def test_no_chord_skyline(self):
        with self.assertRaisesRegex(ValueError,'chord'):
            self.parse('**kern\n*M4/4\n=1\n1c 1e 1g\n*-\n')

    def test_missing_meter_is_not_a_match(self):
        with self.assertRaisesRegex(ValueError,'missing_or_changing_meter'):
            self.parse('**kern\n1cc\n*-\n')

    def test_neighbor_denominator_excludes_rests(self):
        seq=self.parse('**kern\n*M4/4\n8cc\n8dd\n8cc\n8r\n8cc\n8b\n4cc\n*-\n')
        f=features(seq)
        self.assertEqual((f['neighbor_return_windows'],f['pitched_triplet_windows']),(2,2))

    def test_span_and_meter_must_match(self):
        a={'span':'4','meters':['4/4'],'events':[{'onset':'0','duration':'4','midi':72}]}
        b=copy.deepcopy(a);b['span']='3'
        with self.assertRaisesRegex(ValueError,'unequal'):compare(a,b)
        b=copy.deepcopy(a);b['meters']=['2/2']
        with self.assertRaisesRegex(ValueError,'unequal'):compare(a,b)

    def test_onset_metric_does_not_call_ornament_identity(self):
        a={'span':'1','meters':['4/4'],'events':[{'onset':'0','duration':'1','midi':72}]}
        b={'span':'1','meters':['4/4'],'events':[{'onset':'0','duration':'1/2','midi':74},{'onset':'1/2','duration':'1/2','midi':72}]}
        r=compare(a,b)
        self.assertEqual(r['shared_attack_onsets'],1)
        self.assertEqual(r['same_pitch_class_at_shared_onsets'],0)


class ComparisonTest(unittest.TestCase):
    def pieces(self):
        motif,plan=inputs();a=prepare(motif,plan)[0]
        return a,copy.deepcopy(a)

    def test_controls_reject_tempo_or_harmony_or_left_hand(self):
        for field in ('qpm','analysis_chords','notes'):
            a,b=self.pieces()
            if field=='qpm':b.qpm+=1
            elif field=='analysis_chords':b.analysis_chords=b.analysis_chords[:-1]
            else:next(n for n in b.notes if n.hand=='lh').dur=F(1)
            with self.subTest(field=field),self.assertRaises(ValueError):controls(a,b,1)

    def test_protection_includes_duration_and_silent_start(self):
        a,b=self.pieces();next(n for n in b.notes if n.hand=='rh').onset=F(0)
        with self.assertRaisesRegex(ValueError,'보존'):controls(a,b,1)
        a,b=self.pieces();next(n for n in b.notes if n.hand=='rh').dur=F(2)
        with self.assertRaisesRegex(ValueError,'보존'):controls(a,b,1)

    def test_only_changed_bar_reported(self):
        a,b=self.pieces()
        n=next(n for n in b.notes if n.hand=='rh' and n.onset==4);n.pitches=((76,4),)
        self.assertEqual(controls(a,b,1)['changed_melody_bars'],[2])

    def test_frozen_left_and_export_roundtrip(self):
        a,_=self.pieces()
        with tempfile.TemporaryDirectory() as tmp:
            p=write_xml(a,Path(tmp)/'a.musicxml')
            self.assertTrue(verify_written(a,p)['exact_notes_spelling_duration_voices'])
            lhs=common_left(p,F(5))
            self.assertTrue(all(n.hand=='lh' and n.onset+n.dur<=5 for n in lhs))
            self.assertTrue(any(n.onset+n.dur==5 for n in lhs))
            # A mutated XML note must fail independent verification.
            p.write_text(p.read_text(encoding='utf-8').replace('<octave>5</octave>','<octave>6</octave>',1),encoding='utf-8')
            with self.assertRaises(ValueError):verify_written(a,p)
