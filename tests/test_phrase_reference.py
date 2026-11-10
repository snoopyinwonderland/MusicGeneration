import tempfile
import unittest
from pathlib import Path
from musigen.phrase_reference import annotations,ending,query


class PhraseReferenceTest(unittest.TestCase):
    def parse(self,text):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.krn';p.write_text(text,encoding='utf-8');return annotations(p)

    def test_literal_annotations_keep_disagreement_and_no_cadence_guess(self):
        a=self.parse('**function\t**harm\t**kern\n*C:\t*C:\t*C:\n2T\t2I\t2c\n4P\t4ii\t4d\n4D\t4V7b\t4g\n*-\t*-\t*-\n')
        b=self.parse('**function\t**harm\n1T\t1I\n*-\t*-\n')
        self.assertEqual(a['function_labels'],['T','P','D'])
        self.assertEqual(a['terminal_harmony_raw'],'4V7b')
        self.assertIsNone(a['cadence_class'])
        self.assertNotEqual(a['function_labels'],b['function_labels'])

    def test_spine_changes_and_malformed_labels_rejected(self):
        for row in ('*^\t*','T\t4I','4T\t4I\t4c'):
            with self.subTest(row=row),self.assertRaises(ValueError):self.parse('**function\t**harm\n'+row+'\n')

    def test_ending_duration_and_rest_are_distinct(self):
        seq={'span':'5','events':[{'onset':'0','duration':'1','midi':60},
                                 {'onset':'1','duration':'3','midi':62},{'onset':'4','duration':'1','midi':None}]}
        e=ending(seq);self.assertEqual(e['last_to_preceding_median'],'3');self.assertEqual(e['trailing_rest'],'1')

    def test_single_note_does_not_invent_denominator(self):
        e=ending({'span':'4','events':[{'onset':'0','duration':'4','midi':60}]})
        self.assertIsNone(e['last_to_preceding_median'])

    def test_query_ignores_skipped_phrases_and_unknown_kind(self):
        lib={'phrases':[{'status':'skipped'},{'status':'observed','ending':{'trailing_rest':'1','last_to_preceding_median':'1'}}]}
        self.assertEqual(len(query(lib,'rest')),1);self.assertEqual(query(lib,'held_end'),[])
        with self.assertRaises(ValueError):query(lib,'cadence')
