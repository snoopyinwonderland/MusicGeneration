import copy
import unittest
from musigen.accompaniment_trial import controlled_inputs,fixed_sources


def inputs():
    a={'motif':{'events':[{'duration':'1','pitches':['C5']}]},
       'development':{'design':{'basics':{'grade':6}},'harmony':['C']},
       'realization':{'score':{'lh':'C3/q','expression':[]},'feedback':{'user_text':'시험'}}}
    b=copy.deepcopy(a);b['development']['design']['accompaniment_plan']=[{'bars':[1,4],'required_degrees':[3,7]}]
    return a,b


class AccompanimentTrialTests(unittest.TestCase):
    def test_only_policy_changes_with_no_input_mutation(self):
        a,b=inputs();saved=copy.deepcopy((a,b));r=controlled_inputs(a,b)
        self.assertEqual((a,b),saved);self.assertEqual(r['changed_input'],'design.accompaniment_plan')

    def test_authored_lh_melody_and_grade_changes_cannot_masquerade_as_policy(self):
        for which in ('lh','motif','grade','expression'):
            a,b=inputs()
            if which=='lh':b['realization']['score']['lh']='G3/q'
            elif which=='motif':b['motif']['events'][0]['pitches']=['D5']
            elif which=='grade':b['development']['design']['basics']['grade']=7
            else:b['realization']['score']['expression']=['pedal']
            with self.subTest(which=which),self.assertRaisesRegex(ValueError,'작성 입력'):controlled_inputs(a,b)

    def test_requires_actual_off_on_and_unselected_authored_input(self):
        a,b=inputs()
        with self.assertRaises(ValueError):controlled_inputs(a,a)
        with self.assertRaises(ValueError):controlled_inputs(b,b)
        a['realization']['score']['corpus_accompaniment']={};b['realization']['score']['corpus_accompaniment']={}
        with self.assertRaisesRegex(ValueError,'스냅샷'):controlled_inputs(a,b)

    def test_changed_or_missing_corpus_identity_is_rejected(self):
        a={'engine_sha256':{'retrieval':'one'},'library':{'sha256':'two'},'pacing_model':{'sha256':'three'},'grade':6}
        self.assertEqual(fixed_sources(a,a),a)
        for field in a:
            b=copy.deepcopy(a);b.pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError):fixed_sources(a,b)
        b=copy.deepcopy(a);b['library']['sha256']='different'
        with self.assertRaises(ValueError):fixed_sources(a,b)
