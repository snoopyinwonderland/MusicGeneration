import copy
import unittest
from test_blueprint import inputs
from musigen.development_recipe import compile_recipe


class RecipeTest(unittest.TestCase):
    def data(self):
        motif,plan=inputs();blocks=copy.deepcopy(plan['score']['blocks'])
        for b in blocks:b['lh']='C3/w'
        stage={'length':2,'role':'statement','label':'제시','reference_ids':['ref'],'observation':'끝 음가 관찰','decision':'종지 작성','blocks':blocks}
        recipe={'format':'musicanote-development-recipe','version':1,'design':plan['design'],'harmony':plan['harmony'],'stages':[stage],'request':'시험'}
        lib={'phrases':[{'id':'ref','status':'observed'}],'source_url':'local-test','license':'test-fixture'}
        return motif,recipe,lib

    def test_trace_keeps_observation_decision_and_real_sources(self):
        motif,r,lib=self.data();p,solo,trace=compile_recipe(motif,r,lib)
        self.assertEqual(p['design']['form'][0]['bars'],[1,2])
        self.assertNotIn('lh',p['score']['blocks'][0]);self.assertIn('lh',solo['score']['blocks'][0])
        self.assertTrue(trace['stages'][0]['actual']['material_sources'])
        self.assertNotEqual(trace['stages'][0]['observation'],trace['stages'][0]['decision'])

    def test_unknown_source_and_role_are_rejected(self):
        for field,value in [('reference_ids',['missing']),('role','invented')]:
            m,r,l=self.data();r['stages'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compile_recipe(m,r,l)

    def test_gap_is_rejected(self):
        m,r,l=self.data();r['stages'][0]['blocks']=r['stages'][0]['blocks'][1:]
        with self.assertRaises(ValueError):compile_recipe(m,r,l)

    def test_input_motif_cannot_be_replaced(self):
        m,r,l=self.data();r['stages'][0]['blocks'][0]['rh']='C5/w'
        with self.assertRaisesRegex(ValueError,'첫 제시'):compile_recipe(m,r,l)
