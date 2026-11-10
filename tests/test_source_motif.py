import tempfile
import unittest
from pathlib import Path
from musigen.source_motif import extract


class SourceMotifTest(unittest.TestCase):
    def run_extract(self, notes, start='0', end='2'):
        xml='<score-partwise><part id="P1"><measure number="7"><attributes><divisions>2</divisions></attributes>'+notes+'</measure></part></score-partwise>'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.xml';p.write_text(xml,encoding='utf-8')
            return extract(p,'P1','1','1','7',start,'7',end)

    def note(self,pitch='C',extra=''):
        return '<note>'+extra+'<pitch><step>'+pitch+'</step><octave>5</octave></pitch><duration>2</duration></note>'

    def test_timing_spelling_provenance(self):
        clip,source=self.run_extract(self.note('D')+self.note('E'))
        self.assertEqual(clip['events'],[{'duration':'1','pitches':['D5']},{'duration':'1','pitches':['E5']}])
        self.assertEqual(source['quarters'],'2');self.assertEqual(len(source['source_sha256']),64)
        self.assertEqual(clip['source']['start']['measure'],'7')

    def test_leading_gap_and_boundary_cut_are_explicit(self):
        clip,_=self.run_extract('<forward><duration>2</duration></forward>'+self.note(),end='3/2')
        self.assertEqual(clip['events'],[{'duration':'1','pitches':[]},{'duration':'1/2','pitches':['C5']}])
        self.assertTrue(clip['warnings'])

    def test_overlapping_chord_and_tie_rejected(self):
        for notes in [self.note()+self.note('E','<chord/>'),self.note(extra='<tie type="start"/>')]:
            with self.subTest(notes=notes),self.assertRaises(ValueError):self.run_extract(notes,end='1')

    def test_invalid_bounds_rejected(self):
        for start,end in [('2','2'),('0','3'),('1','1')]:
            with self.subTest(start=start,end=end),self.assertRaises(ValueError):self.run_extract(self.note()+self.note(),start,end)
