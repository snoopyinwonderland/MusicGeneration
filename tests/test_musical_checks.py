import unittest
from fractions import Fraction as F
from musigen.piece import Piece,Note,parse_key,build
from musigen.accomp import parse_chord
from musigen.musical_checks import evaluate
from test_notation_expression import work

def fixture(rh,lh,chords,bars=2):
    p=Piece('검사',parse_key('C major'),'4/4',60,bars)
    for hand,vn,seq in [('rh',1,rh),('lh',5,lh)]:
        p.notes += [Note(F(t),F(d),((m,0),),hand,vn,src) for t,d,m,src in seq]
    p.notes.sort(key=lambda n:(n.onset,n.voice))
    p.chords=[(F(t),parse_chord(ch)) for t,ch in chords]
    d={'form':[{'label':'A','bars':[1,bars],'function':'statement'}]}
    return p,d
def n(t,m,d=1,src='lit'): return (t,d,m,src)
class MusicalTest(unittest.TestCase):
    def test_nonchord_classes(self):
        cases=[([n(0,60),n(1,65),n(2,64)],'전타음'),([n(0,64),n(1,65),n(2,67)],'경과음'),([n(0,60),n(1,66),n(2,60)],'미분류')]
        for line,label in cases:
            p,d=fixture(line,[],[(0,'C')]); x=evaluate(p,d)
            self.assertTrue(any(label in e['message'] for e in x['events']))
        p,d=fixture([n(0,65,5),n(5,64)],[],[(0,'F'),(4,'C')])
        self.assertTrue(any('계류음' in s for s in evaluate(p,d)['notes']))
    def test_ninth_and_inner_voice_ignored(self):
        p,d=fixture([n(0,62,4)],[],[(0,'C')])
        p.notes.append(Note(F(0),F(1),((66,0),),'rh',2,'lit'))
        self.assertFalse(evaluate(p,d)['warnings'])
    def test_parallel_and_same_chord_exemption(self):
        p,d=fixture([n(0,67,4),n(4,69,4)],[n(0,48,4),n(4,50,4)],[(0,'C'),(4,'Dm')])
        self.assertTrue(any(e['kind']=='parallel' for e in evaluate(p,d)['events']))
        p.chords[-1]=(F(4),parse_chord('C'))
        self.assertFalse(any(e['kind']=='parallel' for e in evaluate(p,d)['events']))
    def test_rhythm_copy_seq_exemption(self):
        p,d=fixture([n(i*4,60,4) for i in range(4)],[],[(0,'C')],4)
        self.assertTrue(any(e['kind']=='rhythm' for e in evaluate(p,d)['events']))
        for x in p.notes: x.src='a|seq:0'
        self.assertFalse(any(e['kind']=='rhythm' for e in evaluate(p,d)['events']))
    def test_cadences(self):
        for kind,cs,last in [('authentic',[(0,'G7'),(4,'C')],60),('half',[(0,'C'),(4,'G')],67),('plagal',[(0,'F'),(4,'C')],60),('deceptive',[(0,'G'),(4,'Am')],69)]:
            p,d=fixture([n(0,67,4),n(4,last,4)],[],cs); d['form'][0]['cadence']=kind
            self.assertFalse(any(e['kind']=='cadence' for e in evaluate(p,d)['events']))
            p.chords=[(F(0),parse_chord('Dm'))]
            self.assertTrue(any(e['kind']=='cadence' for e in evaluate(p,d)['events']))
    def test_contrast(self):
        p,d=fixture([n(0,60,4),n(4,60,4)],[],[(0,'C')])
        d['form']=[{'label':'A','bars':[1,1],'function':'statement'},{'label':'B','bars':[2,2],'function':'contrast'}]
        self.assertTrue(any(e['kind']=='contrast' for e in evaluate(p,d)['events']))
    def test_hidden_chord_symbols_still_checked(self):
        d,s=work(); a=evaluate(build(d,s),d); s['show_chords']=False
        self.assertEqual(a,evaluate(build(d,s),d))
