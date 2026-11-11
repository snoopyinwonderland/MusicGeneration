import unittest
from fractions import Fraction as F
from musigen.mscx_timing import parse,audit,raw_label


def xml(body,length='1',meter='<TimeSig><sigN>4</sigN><sigD>4</sigD></TimeSig>'):
    return f'<museScore version="3.02"><Score><Staff id="1"><Measure len="{length}"><voice>{meter}{body}</voice></Measure></Staff></Score></museScore>'


def chord(duration='quarter',extra='',pitch=60,tpc=14):
    return f'<Chord><durationType>{duration}</durationType>{extra}<Note><pitch>{pitch}</pitch><tpc>{tpc}</tpc></Note></Chord>'


class MuseScoreTimingTests(unittest.TestCase):
    def test_tuplets_dots_and_grace_have_exact_written_time(self):
        triplet='<Tuplet><normalNotes>2</normalNotes><actualNotes>3</actualNotes></Tuplet>'+chord('eighth')*3+'<endTuplet/>'
        p=parse(xml(chord(extra='<acciaccatura/>')+triplet+chord(extra='<dots>1</dots>')))
        self.assertEqual([n[3] for n in p['notes']],[0,0,F(1,3),F(2,3),1])
        self.assertEqual([n[4] for n in p['notes']],[0,F(1,3),F(1,3),F(1,3),F(3,2)])

    def test_locations_restore_annotation_time_without_moving_notes(self):
        body=chord()+'<location><fractions>-1/4</fractions></location><Harmony><harmonyType>1</harmonyType><name>C.I-vi6</name></Harmony>'
        p=parse(xml(body,length='1/4'))
        self.assertEqual(p['harmonies'],[(1,1,1,F(0),'C.I-vi6')])
        self.assertEqual(p['bars'][0][3],1)

    def test_alternative_label_is_not_dropped_or_merged(self):
        x=xml('<Harmony><harmonyType>1</harmonyType><name>C.I-vi6</name></Harmony>'+chord(),length='1/4')
        bars=[dict(mc='1',quarterbeats='0',act_dur='1/4',timesig='4/4')]
        notes=[dict(mc='1',staff='1',voice='1',mc_onset='0',duration='1/4',midi='60',tpc='0',gracenote='')]
        harmonies=[dict(mc='1',staff='1',voice='1',mc_onset='0',label='C.I',alt_label='vi6')]
        self.assertEqual(audit(x,bars,notes,harmonies)['status'],'validated')
        harmonies[0]['alt_label']='vi'
        self.assertEqual(audit(x,bars,notes,harmonies)['status'],'mismatch')

    def test_same_bar_wrong_onset_is_rejected(self):
        x=xml(chord()+'<Harmony><harmonyType>1</harmonyType><name>C.I</name></Harmony>')
        bars=[dict(mc='1',quarterbeats='0',act_dur='1',timesig='4/4')]
        notes=[dict(mc='1',staff='1',voice='1',mc_onset='0',duration='1/4',midi='60',tpc='0',gracenote='')]
        h=[dict(mc='1',staff='1',voice='1',mc_onset='0',label='C.I')]
        result=audit(x,bars,notes,h)
        self.assertEqual(result['status'],'mismatch')
        self.assertTrue(result['differences']['harmonies']['xml_only'])

    def test_missing_duplicate_and_respelled_notes_are_visible(self):
        bars=[dict(mc='1',quarterbeats='0',act_dur='1',timesig='4/4')]
        n=dict(mc='1',staff='1',voice='1',mc_onset='0',duration='1/4',midi='60',tpc='0',gracenote='')
        for notes in ([],[n,n],[dict(n,tpc='12')],[dict(n,duration='1/8')]):
            with self.subTest(notes=notes):self.assertEqual(audit(xml(chord()),bars,notes,[])['status'],'mismatch')

    def test_unknown_timing_and_unbalanced_tuplets_fail(self):
        for body in ('<tick>480</tick>'+chord(),'<endTuplet/>'+chord(),'<Tuplet><normalNotes>2</normalNotes><actualNotes>3</actualNotes></Tuplet>'+chord(),chord(extra='<duration>1/8</duration>'),chord('breve')):
            with self.subTest(body=body),self.assertRaises(ValueError):parse(xml(body))

    def test_staff_clocks_and_voices_are_independent(self):
        x=xml(chord()).replace('</voice>','</voice><voice><Rest><durationType>half</durationType></Rest>'+chord()+'</voice>')
        p=parse(x)
        self.assertEqual([(n[2],n[3]) for n in p['notes']],[(1,F(0)),(2,F(2))])

    def test_library_option_requires_exact_annotation_onset(self):
        from musigen.tonal_reference import validate_tables
        from test_tonal_reference import row
        bars=[dict(mc='1',mn='1',quarterbeats='0',act_dur='1',duration_qb='4',timesig='4/4')]
        notes=[dict(mc='1',mn='1',staff='1',voice='1',mc_onset='0',quarterbeats='0',duration='1/4',duration_qb='1',midi='60',tpc='0',gracenote='',timesig='4/4')]
        h=[dict(row(),staff='1')]
        label='<Harmony><harmonyType>1</harmonyType><name>C.I</name></Harmony>'
        old=validate_tables(h,bars,notes,xml(chord()+label))
        self.assertNotIn('xml_timing',old)
        with self.assertRaisesRegex(ValueError,'independent_xml'):validate_tables(h,bars,notes,xml(chord()+label),True)
        self.assertEqual(validate_tables(h,bars,notes,xml(label+chord()),True)['xml_timing']['status'],'validated')
