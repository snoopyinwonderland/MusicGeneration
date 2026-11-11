import copy
from dataclasses import replace
from fractions import Fraction as F
import unittest
from unittest.mock import patch

from musigen.accompaniment_context import requirements, missing_requirements
from musigen.accompaniment_voicing import repair
from musigen.corpus_accomp import FIELD
from musigen.musical_checks import parallel_events, evaluate
from musigen.piece import build, Note, ScoreError
import test_corpus_accomp as corpus_fixture
from test_corpus_accomp import work


def fixture(symbols=('C','D')):
    d,s=work();d['form']=[{'label':'A','bars':[1,len(symbols)],'function':'statement'}]
    s={'blocks':[{'bars':str(i+1),'rh':'G5/w','lh':{'pattern':'alberti','chords':ch}} for i,ch in enumerate(symbols)]}
    return d,build(d,s)


def policy(bars,degrees=(3,7),enabled=True):
    return {b:{'required_degrees':list(degrees),'repair_voicing':enabled} for b in bars}


def note(on,dur,m,t,src='alberti(C)',hand='lh'):
    return Note(F(on),F(dur),((m,t),),hand,1,src)


def boundary_fixture():
    d,p=fixture()
    p.notes=[note(0,4,67,1,hand='rh'),note(4,4,69,3,hand='rh'),
             note(0,2,48,0),note(2,2,60,0),note(4,4,62,2,src='alberti(D)')]
    return d,p


class VoicingTests(unittest.TestCase):
    def test_option_is_strict_boolean_and_off_is_exact(self):
        d,p=fixture(('Gm7',));ns=[n for n in p.notes if n.hand=='lh']
        after,r=repair(p,ns,policy([1],enabled=False),6)
        self.assertEqual(after,ns);self.assertEqual(r['steps'],[])
        for bad in (1,'true',None):
            d['accompaniment_plan']=[{'bars':[1,1],'role':'제시','decision':'유지','repair_voicing':bad}]
            with self.assertRaises(ScoreError):requirements(d,p)

    def test_missing_third_filled_with_rhythm_first_bass_and_other_hand_fixed(self):
        d,p=fixture(('Gm7','A7'));saved=copy.deepcopy(p)
        ns=[n for n in p.notes if n.hand=='lh'];ps=policy([1,2])
        self.assertTrue(missing_requirements(ns,p,1,ps[1]))
        after,r=repair(p,ns,ps,6)
        self.assertEqual(p,saved);self.assertFalse(r['unresolved_requirements'])
        self.assertEqual([(n.onset,n.dur,n.voice,n.art,n.slur,len(n.pitches)) for n in ns],[(n.onset,n.dur,n.voice,n.art,n.slur,len(n.pitches)) for n in after])
        for bar in [1,2]:
            a=next(n for n in ns if p.bar_of(n.onset)==bar);b=next(n for n in after if p.bar_of(n.onset)==bar)
            self.assertEqual(min(a.pitches),min(b.pitches))
        self.assertEqual(r['changed_fallback_bars'],[1,2])
        self.assertFalse(r['changed_corpus_bars'])

    def test_boundary_repair_checks_entire_piece_and_retains_corpus_provenance(self):
        d,p=boundary_fixture();ns=[replace(n,src='corpus:fixture:1') for n in p.notes if n.hand=='lh']
        self.assertEqual(parallel_events(p),[(F(2),F(4),7)])
        after,r=repair(p,ns,policy([1,2],()),6)
        actual=replace(p,notes=[n for n in p.notes if n.hand=='rh']+after)
        self.assertEqual(parallel_events(actual),[])
        self.assertEqual(r['changed_corpus_bars'],[1]);self.assertEqual(r['changed_fallback_bars'],[])
        self.assertTrue(any(n.src.endswith('|voicing') for n in after))
        events=evaluate(actual,d)['events']
        self.assertFalse([e for e in events if e['kind']=='parallel'])

    def test_unfixable_first_basses_are_preserved_and_reported(self):
        d,p=boundary_fixture();p.notes=[n for n in p.notes if n.hand=='rh']+[note(0,4,60,0),note(4,4,62,2,src='alberti(D)')]
        ns=[n for n in p.notes if n.hand=='lh'];after,r=repair(p,ns,policy([1,2]),6)
        self.assertEqual(after,ns);self.assertEqual(len(r['parallel_after']),1)
        self.assertEqual(len(r['unresolved_requirements']),2)

    def test_written_and_cross_bar_material_are_protected(self):
        d,p=fixture(('Gm7','A7'))
        for ns in ([note(0,4,55,1,src='written'),note(4,4,57,3,src='written')],[note(0,8,55,1)]):
            actual=replace(p,notes=[n for n in p.notes if n.hand=='rh']+ns)
            after,r=repair(actual,ns,policy([1,2]),6)
            self.assertEqual(after,ns);self.assertEqual(set(r['protected_bars']),{'1','2'})

    def test_spelled_seventh_and_grade_constraints(self):
        d,p=fixture(('Bdim7',));ns=[note(i,1,m,t,src='alberti(Bdim7)') for i,(m,t) in enumerate([(47,5),(50,2),(53,-1),(59,5)])]
        p.notes=[n for n in p.notes if n.hand=='rh']+ns
        after,r=repair(p,ns,policy([1],(7,)),6)
        self.assertFalse(r['unresolved_requirements'])
        self.assertTrue(any((56,-4) in n.pitches for n in after)) # Ab, not respelled G#
        self.assertTrue(all(28<=m<=69 for n in after for m,t in n.pitches))

    def test_held_right_hand_participates_but_rest_attack_breaks_parallel(self):
        d,p=boundary_fixture()
        self.assertEqual(evaluate(p,d)['warnings'],['2마디 양손: 병행 5도 (1→2마디)'])
        p.notes=[replace(n,dur=F(1)) if n.hand=='rh' and n.onset==0 else n for n in p.notes]
        self.assertFalse(parallel_events(p))

    def test_missing_tones_are_checked_in_each_harmonic_span(self):
        d,s=work();d['form']=[{'label':'A','bars':[1,1],'function':'statement'}]
        s={'blocks':[{'bars':'1','rh':'G5/w','lh':{'pattern':'alberti','chords':'C:2 D7:2'}}]}
        p=build(d,s);ns=[note(i,1,m,t) for i,(m,t) in enumerate([(48,0),(52,4),(50,2),(50,2)])]
        p.notes=[n for n in p.notes if n.hand=='rh']+ns
        after,r=repair(p,ns,policy([1]),6)
        remaining=missing_requirements(after,p,1,policy([1])[1])
        self.assertEqual(remaining[0]['onset'],'2');self.assertEqual(len(remaining[0]['missing_tpcs']),1)
        self.assertEqual(after[0].pitches,ns[0].pitches);self.assertEqual(after[2].pitches,ns[2].pitches)

    def test_selection_snapshot_rebuild_and_disabled_default(self):
        d,s=work();d['accompaniment_plan']=[{'bars':[1,4],'role':'제시','decision':'구성음 보존','required_degrees':[3,7],'repair_voicing':False}]
        before,_=corpus_fixture.CorpusTest().choose_score(d,s,missing=(0,1,2,3))
        self.assertNotIn('voicing_repair',before[FIELD]['report'])
        d['accompaniment_plan'][0]['repair_voicing']=True
        after,_=corpus_fixture.CorpusTest().choose_score(d,s,missing=(0,1,2,3))
        self.assertIn('voicing_repair',after[FIELD]['report'])
        with patch('musicomp.realize.retrieval.load_index',side_effect=AssertionError('frozen')):build(d,after)
        d['accompaniment_plan'][0]['repair_voicing']=False
        with self.assertRaises(ScoreError):build(d,after)
