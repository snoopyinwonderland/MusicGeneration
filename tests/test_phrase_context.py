import copy
from fractions import Fraction as F
import unittest
from musigen.humdrum_timing import parse, duration, validate_alignment
from musigen.phrase_context import windows, clip_annotations, comparison, export_reference, melody_observation


SCORE='''**kern\t**kern
*M2/4\t*M2/4
=1-\t=1-
2C\t4e
.\t4f
=2\t=2
2G\t4g
.\t4a
*-\t*-
'''
JOINED='''**function\t**harm\t**kern\t**kern
*M2/4\t*M2/4\t*M2/4\t*M2/4
*C:\t*C:\t*C:\t*C:
=1\t=1\t=1\t=1
2T\t4I\t2C\t4e
.\t4IV\t.\t4f
=2\t=2\t=2\t=2
2D\t2V\t2G\t4g
.\t.\t.\t4a
*-\t*-\t*-\t*-
'''


class TimingTests(unittest.TestCase):
    def test_exact_reciprocal_dotted_and_grace(self):
        self.assertEqual(duration('12g'),F(1,3))
        self.assertEqual(duration('4..c'),F(7,4))
        self.assertEqual(duration('0C'),8)
        self.assertEqual(duration('(q32ff#'),0)
        for token in ('3%2c','00C','c'):
            with self.subTest(token=token),self.assertRaises(ValueError):duration(token)

    def test_harmonic_changes_on_note_time_and_literal_bar_labels(self):
        score,joined=parse(SCORE),parse(JOINED)
        self.assertTrue(validate_alignment(score,joined))
        self.assertEqual(score['bars'][0]['raw'],'=1-')
        self.assertEqual(joined['bars'][0]['raw'],'=1')
        harm=joined['spines'][1]['events']
        self.assertEqual([(e['onset'],e['duration'],e['label']) for e in harm],
                         [('0','1','I'),('1','1','IV'),('2','2','V')])

    def test_source_note_and_meter_mismatch_rejected(self):
        source=parse(SCORE)
        for joined in (JOINED.replace('4e','4e-'),JOINED.replace('*M2/4','*M2/2')):
            with self.assertRaises(ValueError):validate_alignment(source,parse(joined))

    def test_grace_does_not_consume_beat(self):
        source=SCORE.replace('2C\t4e','.\tq16d\n2C\t4e')
        parsed=parse(source)
        self.assertEqual(parsed['span'],'4')
        self.assertEqual(parsed['grace_events'],1)
        self.assertEqual(parsed['spines'][1]['events'][1]['onset'],'0')

    def test_unsupported_paths_overlap_and_missing_initial_time_rejected(self):
        for text in (SCORE.replace('=2\t=2','*^\t*'),
                     SCORE.replace('.\t4f','4D\t4f'),
                     SCORE.replace('*M2/4\t*M2/4\n','').replace('=2\t=2','*M2/4\t*M2/4\n=2\t=2'),
                     JOINED.replace('2T\t4I','4T\t4I')):
            with self.subTest(text=text),self.assertRaises(ValueError):parse(text)


class WindowTests(unittest.TestCase):
    def test_windows_do_not_bridge_partial_bar_or_phrase_boundary(self):
        p={'span':'9','bars':[{'ordinal':i,'onset':str(on),'duration':str(d),'raw':str(i),'full':d==2}
           for i,(on,d) in enumerate([(0,1),(1,2),(3,2),(5,2),(7,2)])]}
        units=windows(p)
        self.assertEqual(len([u for u in units if u['length_bars']==2]),3)
        self.assertEqual(len([u for u in units if u['length_bars']==4]),1)
        self.assertFalse(any(u['whole_source_phrase'] for u in units))
        self.assertTrue(units[-1]['ends_source_phrase'])
        with self.assertRaises(ValueError):windows(p,[3])

    def test_annotation_clip_keeps_original_duration_and_line(self):
        original={'onset':'1','duration':'3','label':'V','raw':'2.V','line':10}
        result=clip_annotations([original],F(2),F(3))[0]
        self.assertEqual((result['onset'],result['duration']),('0','1'))
        self.assertEqual(result['source_duration'],'3')
        self.assertTrue(result['clipped_at_window'])
        self.assertEqual(original['onset'],'1')

    def test_annotator_disagreement_retained_without_majority_vote(self):
        a={'harm':[dict(onset='0',duration='2',label='I')],'function':[dict(onset='0',duration='2',label='T')]}
        b=copy.deepcopy(a);b['harm'][0]['label']='V'
        result=comparison({'a':a,'b':b},'2')
        self.assertEqual(len(result['differences']),1)
        self.assertEqual(result['differences'][0]['a'],'I')
        self.assertNotIn('chosen',result)
        self.assertEqual(comparison({'a':a},'2')['status'],'two_aligned_annotators_unavailable')

    def test_sustained_entry_is_not_counted_as_new_attack(self):
        seq={'events':[dict(onset='0',duration='3',midi=60),dict(onset='3',duration='1',midi=None)],'role':'candidate'}
        result=melody_observation(seq,F(2),F(4))
        self.assertEqual(result['attacks'],0)
        self.assertEqual(result['rest_quarters'],'1')

    def test_export_requires_known_unit_and_keeps_choice_null(self):
        lib=dict(source_url='example',attribution='test',license='test',license_sha256='a'*64,
                 windows=[{'id':'x','phrase_id':'p'}],phrases=[{'id':'p','score':{'sha256':'b'*64},'annotations':[]}])
        result=export_reference(lib,'x')
        self.assertIsNone(result['user_selection'])
        self.assertIsNone(result['author_decision'])
        self.assertFalse(result['generation_eligible'])
        with self.assertRaises(ValueError):export_reference(lib,'missing')
