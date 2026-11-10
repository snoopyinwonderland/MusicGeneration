import unittest
from musigen.piece import build
from musigen.checks import check


class EndingKeyTest(unittest.TestCase):
    def result(self, ending, local):
        d={'title':'국소 조성 종결 검사','basics':{'key':'A','mode':'minor','meter':'4/4','tempo':80,'grade':6},
           'form':[{'label':'A','bars':[1,2],'function':'statement'}]}
        block={'bars':'2','rh':ending+'5/w','lh':ending+'3/w'}
        if local:block['key']=local
        p=build(d,{'blocks':[{'bars':'1','rh':'A4/w','lh':'A2/w'},block]})
        return [w for w in check(p,d)['warnings'] if '마지막 마디 왼손 베이스' in w]

    def test_final_explicit_key_used_and_non_tonic_still_warns(self):
        self.assertFalse(self.result('C','C major'))
        self.assertTrue(self.result('D','C major'))
        self.assertFalse(self.result('A',None))
        self.assertTrue(self.result('C',None))
