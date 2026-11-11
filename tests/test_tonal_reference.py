import copy
from fractions import Fraction as F
import unittest
from musigen.tonal_reference import absolute_key,relative_key,label_states,references,validate_tables,observe


def row(label='C.I',local='I',relative='',chord='I',on='0',duration='4'):
    return dict(label=label,globalkey='C',localkey=local,relativeroot=relative,chord=chord,
                globalkey_is_minor='0',localkey_is_minor=str(int(local.islower())),cadence='',
                mc='1',mn='1',mc_onset=str(F(on)/4),quarterbeats=on,duration_qb=duration,
                timesig='4/4',staff='2',voice='1',source_line=2,duration_exact_qb=duration)


class TonalReferenceTests(unittest.TestCase):
    def test_spelled_major_minor_and_nested_targets(self):
        self.assertEqual(relative_key('III',absolute_key('f'))['name'],'Ab major')
        self.assertEqual(relative_key('vi',absolute_key('F'))['name'],'D minor')
        self.assertEqual(relative_key('V/ii',absolute_key('C'))['name'],'A major')
        self.assertEqual(relative_key('#iv',absolute_key('C'))['name'],'F# minor')
        for token in ('H','Cbb#','V//ii','vI'):
            with self.subTest(token=token),self.assertRaises(ValueError):relative_key(token,absolute_key('C'))

    def test_applied_target_does_not_change_local_key(self):
        rows=[row(),row('V7/V',relative='V',chord='V7/V',on='4',duration='2'),row('V.I',local='V',on='6',duration='2')]
        rows[1]['source_line']=3;rows[2]['source_line']=4
        result=references('test',label_states(rows))
        self.assertEqual([r['kind'] for r in result],['tonicization','local_key_change'])
        self.assertEqual(result[0]['local_context']['name'],'C major')
        self.assertEqual(result[1]['local_context']['name'],'G major')

    def test_expanded_state_cannot_invent_modulation(self):
        for change in ({'localkey':'V'},{'globalkey_is_minor':'1'},{'relativeroot':'V'},{'cadence':'PAC'}):
            r=row();r.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):label_states([r])

    def test_augmented_sixth_expansion_is_not_counted_as_applied_chord(self):
        r=row('.Ger6',relative='V',chord='Ger6');r['special']='Ger'
        rows=label_states([row(),r])
        self.assertIsNone(rows[1]['applied_target'])
        self.assertEqual(rows[1]['special_expansion_target'],'V')
        self.assertFalse(references('test',rows))

    def fixture(self):
        harmonies=[row(duration='4'),row('{',chord='',on='2',duration='0')]
        harmonies[1]['source_line']=3
        bars=[dict(mc='1',mn='1',quarterbeats='0',duration_qb='4.0',act_dur='1',timesig='4/4')]
        notes=[dict(mc='1',mn='1',mc_onset='0',quarterbeats='0',duration_qb='0.3333333333333333',duration='1/12',gracenote='',timesig='4/4')]
        xml='<museScore><Score><Staff id="2"><Measure><voice><Harmony><harmonyType>1</harmonyType><name>C.I</name></Harmony><Harmony><harmonyType>1</harmonyType><name>{</name></Harmony></voice></Measure></Staff></Score></museScore>'
        return harmonies,bars,notes,xml

    def test_relative_augmented_sixth_keeps_context_without_counting_secondary(self):
        r=row('.Fr6/III',relative='V/III',chord='Fr6/III');r['special']='Fr'
        rows=label_states([row(),r])
        self.assertIsNone(rows[1]['applied_target'])
        self.assertEqual(rows[1]['special_relative_context']['name'],'E major')
        self.assertFalse(references('test',rows))
        r['relativeroot']='III'
        with self.assertRaises(ValueError):label_states([row(),r])

    def test_fractional_notes_and_zero_length_phrase_marker(self):
        h,m,n,x=self.fixture();r=validate_tables(h,m,n,x)
        self.assertEqual(r['point_annotations'],1)
        self.assertEqual(h[0]['duration_exact_qb'],'4')
        self.assertEqual(h[1]['duration_exact_qb'],'0')

    def test_wrong_address_clock_and_source_anchor_rejected(self):
        for kind in ('clock','anchor','duration','point'):
            h,m,n,x=self.fixture()
            if kind=='clock':h[0]['mc_onset']='1/4'
            if kind=='anchor':x=x.replace('C.I','C.V')
            if kind=='duration':h[0]['duration_qb']='3.999'
            if kind=='point':h[1]['duration_qb']='1'
            with self.subTest(kind=kind),self.assertRaises(ValueError):validate_tables(h,m,n,x)

    def test_source_use_requires_explicit_option(self):
        with self.assertRaisesRegex(ValueError,'allow-dcml'):observe('.',[],False)
