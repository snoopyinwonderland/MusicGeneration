import json
from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest
from musigen.melody_evidence import connect, line, packed
from musigen.melody_annotated import put
from musigen.melody_line_audit import internal, near, scan, Matcher


class MelodyAuditTest(unittest.TestCase):
    def test_internal_long_transposition_and_short_cell(self):
        a=[(F(i),F(1),p) for i,p in enumerate([60,62,65,64,67,65,64,62])]
        self.assertEqual(internal(a+[(t+8,d,p+5) for t,d,p in a],F(4),4)['long_repeats'][0]['kind'],'transposed')
        # A short cell recurring with different continuation is allowed.
        b=a+[(t+8,d,p) for t,d,p in a[:3]]+[(F(11),F(5),69)]
        self.assertEqual(internal(b,F(4),4)['long_repeats'],[])

    def test_near_copy_transposition_tempo_and_rejection(self):
        a=[(F(i),F(1,2),p) for i,p in enumerate([60,62,65,64,67,65,64,62]*2)]
        b=[(t*2+3,d*2,p+4) for t,d,p in a]
        self.assertEqual(near(a,b)['changed_pitch_notes'],0)
        b[8]=(b[8][0],b[8][1],b[8][2]+1)
        self.assertEqual(near(a,b)['changed_pitch_notes'],1)
        b[6]=(b[6][0],b[6][1],b[6][2]+2)
        self.assertIsNone(near(a,b))
        b=[(t*2+3,d*2,p+4) for t,d,p in a];b[0]=(b[0][0],F(1,20),b[0][2])
        self.assertIsNone(near(a,b))

    def test_overlapping_matcher(self):
        m=Matcher([([1,2], 'a'),([2], 'b')])
        self.assertEqual(list(m.find([1,2,1,2])),[(0,'a'),(1,'b'),(2,'a'),(3,'b')])

    def test_database_retrieves_known_near_copy(self):
        a=[(F(i),F(1,2),p) for i,p in enumerate([60,62,65,64,67,65,64,62,61,63,68,66,69,67,65,63])]
        b=[(t*2,d*2,p+3+(i==5)) for i,(t,d,p) in enumerate(a)]
        repeated=a+[(t+16,d,p+(i==5)) for i,(t,d,p) in enumerate(a)]
        self.assertTrue(internal(repeated,F(4),8)['near_repeats'])
        with tempfile.TemporaryDirectory() as tmp:
            dbpath=Path(tmp)/'a.db';db=connect(dbpath)
            put(db,'source','test',{},line('1','documented_melody','test',b));db.commit();db.close()
            result=scan({'query':{'events':packed(a),'bar_length':'4','bars':4}},[dbpath],Path(tmp)/'audit.json')
            self.assertGreater(result['matches']['query'],0)
            self.assertEqual(result['coverage']['lines_scanned'],1)
            parallel=scan({'query':{'events':packed(a),'bar_length':'4','bars':4}},[dbpath],Path(tmp)/'parallel.json',workers=2)
            self.assertEqual(result,parallel)
            self.assertEqual(json.loads((Path(tmp)/'audit.json').read_text())['pieces'],
                             json.loads((Path(tmp)/'parallel.json').read_text())['pieces'])
