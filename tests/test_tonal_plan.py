import copy
import unittest
from musigen.blueprint import digest
from musigen.development_recipe import compile_recipe
from musigen.tonal_reference import absolute_key
from test_blueprint import inputs


def data():
    motif,old=inputs();design=old['design']
    source={'id':'test/work','status':'validated','license':'test','sources':{},'source_url':'local-fixture'}
    refs=[dict(id=kind,kind=kind,work_id='test/work',status='source_annotation_validated_not_independently_heard',
               from_key=absolute_key('C'),to_key=absolute_key('G')) for kind in ('tonicization','local_key_change')]
    tonal={'format':'musicanote-tonal-library','version':1,'works':[source],'references':refs}
    base=dict(reference_ids=['ref'],observation='끝 쉼 관찰',decision='작성자가 발전',length=2)
    first={**base,'role':'statement','label':'제시','blocks':[dict(bars='1',rh={'motif':'input'},lh='C3/w'),dict(bars='2',rh='F#5/h D5/h',lh='D3/w')]}
    second={**base,'role':'development','label':'이동','blocks':[dict(bars='1',key='G major',rh='G5/h B5/h',lh='G3/w'),dict(bars='2',key='G major',rh='G5/w',lh='G3/w')]}
    first['tonal_moves']=[dict(at_bar=2,kind='tonicization',reference_id='tonicization',from_key='C major',to_key='G major',observation='명시적 /V',decision='현재 조성 안의 딸림 준비')]
    second['tonal_moves']=[dict(at_bar=1,kind='local_key_change',reference_id='local_key_change',from_key='C major',to_key='G major',observation='명시적 국소 조성',decision='새 조성 구간',pivot=dict(bar=1,from_figure='I',to_figure='IV'),confirmation=dict(bar=4,cadence='PAC'))]
    recipe=dict(format='musicanote-development-recipe',version=1,design=design,stages=[first,second],request='검증용',
                harmony=[dict(bar=1,duration='4',symbol='C'),dict(bar=2,duration='4',figure='V7/V'),dict(bar=3,duration='4',symbol='G'),dict(bar=4,duration='4',symbol='G',cadence='PAC')],tonal_library_sha256=digest(tonal))
    phrases={'phrases':[{'id':'ref','status':'observed'}],'source_url':'local-test','license':'test'}
    return motif,recipe,phrases,tonal


class TonalPlanTests(unittest.TestCase):
    def test_checked_moves_and_pivot_are_kept_with_provenance(self):
        p,solo,t=compile_recipe(*data())
        self.assertEqual([r['bar'] for r in t['tonal_moves']],[2,3])
        self.assertTrue(t['tonal_moves'][1]['evidence']['pivot']['exact_spelling_match'])
        self.assertEqual(len(p['references']),2)

    def test_missing_library_and_stale_digest_rejected(self):
        m,r,l,t=data()
        with self.assertRaises(ValueError):compile_recipe(m,r,l)
        t['works'][0]['license']='changed'
        with self.assertRaises(ValueError):compile_recipe(m,r,l,t)

    def test_kind_and_transposition_relation_must_match(self):
        for change in ({'kind':'tonicization'},{'to_key':'G minor'},{'reference_id':'missing'}):
            m,r,l,t=data();r['stages'][1]['tonal_moves'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):compile_recipe(m,r,l,t)

    def test_written_key_change_is_required(self):
        m,r,l,t=data()
        for block in r['stages'][1]['blocks']:block['key']='C major'
        with self.assertRaisesRegex(ValueError,'실제 마디 조성'):compile_recipe(m,r,l,t)

    def test_secondary_intent_cannot_be_claimed_without_secondary_chord(self):
        m,r,l,t=data();r['harmony'][1]={'bar':2,'duration':'4','symbol':'D7'}
        with self.assertRaisesRegex(ValueError,'실제 세컨더리'):compile_recipe(m,r,l,t)

    def test_pivot_spelling_and_confirmation_are_not_faked(self):
        for target in ('pivot','confirmation'):
            m,r,l,t=data();move=r['stages'][1]['tonal_moves'][0]
            if target=='pivot':move['pivot']['to_figure']='iv'
            else:move['confirmation']['cadence']='HC'
            with self.subTest(target=target),self.assertRaises(ValueError):compile_recipe(m,r,l,t)

    def test_no_option_preserves_legacy_compilation(self):
        m,r,l,t=data()
        for s in r['stages']:s.pop('tonal_moves')
        r.pop('tonal_library_sha256')
        before=compile_recipe(m,r,l);after=compile_recipe(m,r,l,t)
        self.assertEqual(before,after)
        self.assertNotIn('tonal_moves',before[2])
