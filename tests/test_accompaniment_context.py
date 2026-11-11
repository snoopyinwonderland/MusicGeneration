import copy
from fractions import Fraction as F
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from musigen.accompaniment_context import requirements,chord_degrees,source_has_degrees,missing_requirements,entry_in_range,observe
from musigen.accomp import parse_chord
from musigen.corpus_accomp import PlannedFigures,semantic
from musigen.design import validate,DesignError
from musigen.piece import build,Note,ScoreError
from musicomp.realize.retrieval import target_bars
from musicomp.realize.musicxml import OutNote
from test_corpus_accomp import work


def policy():return dict(bars=[1,4],role='제시와 응답',decision='작성한 화음 성격을 보존한다',required_degrees=[3,7],entry_bass_range=[38,55])


class AccompanimentContextTests(unittest.TestCase):
    def test_plan_is_opt_in_and_does_not_modify_design(self):
        d,s=work();before=copy.deepcopy(d)
        self.assertEqual(requirements(d,4),{})
        d['accompaniment_plan']=[policy()];saved=copy.deepcopy(d)
        self.assertEqual(set(requirements(d,4)),{1,2,3,4})
        self.assertEqual(d,saved);validate(d)

    def test_invalid_ranges_degrees_and_overlap_are_rejected(self):
        for rows in (None,[dict(policy(),bars=[1,5])],[dict(policy(),required_degrees=[True])],[dict(policy(),required_degrees=[3,3])],[dict(policy(),entry_bass_range=[55,38])],[policy(),policy()]):
            d,s=work();d['accompaniment_plan']=rows
            with self.subTest(rows=rows),self.assertRaises(ScoreError):requirements(d,4)
            with self.assertRaises(DesignError):validate(d)

    def test_core_degrees_follow_spelling_not_only_pitch_class(self):
        self.assertEqual(chord_degrees(parse_chord('Cdim7'),[3,7]),{-3,-9})
        self.assertEqual(chord_degrees(parse_chord('Csus4'),[3,7]),set())
        self.assertEqual(chord_degrees(parse_chord('C6'),[7]),set())

    def test_source_roles_must_occur_in_each_harmony_span(self):
        target=SimpleNamespace(chords=[{'on':F(0),'end':F(2),'quality':'M'},{'on':F(2),'end':F(4),'quality':'Mm7'}])
        source={'lh':[{'on':'0','notes':[{'role':'3'}]},{'on':'2','notes':[{'role':'3'},{'role':'7'}]}]}
        self.assertTrue(source_has_degrees(target,source,[3,7]))
        source['lh'][1]['on']='1'
        self.assertFalse(source_has_degrees(target,source,[3,7]))

    def test_actual_missing_core_pitch_and_register_are_reported(self):
        d,s=work();p=build(d,s)
        ns=[Note(F(0),F(4),((48,0),),'lh',1,'test')]
        self.assertEqual(missing_requirements(ns,p,1,policy())[0]['missing_tpcs'],[4])
        self.assertTrue(entry_in_range(ns,policy()))
        self.assertFalse(entry_in_range([Note(F(0),F(4),((36,0),),'lh',1,'test')],policy()))

    def test_preview_rejects_dropped_tones_and_caches_realisation(self):
        d,s=work();d['accompaniment_plan']=[policy()];p=build(d,s);sm,plan=semantic(p,d)
        index=SimpleNamespace(figure=lambda _: 'arpeggio')
        source={'song':'fixture','bar':0,'lh':[{'on':'0','notes':[{'role':'R'},{'role':'3'}]}]}
        for pitches,want in ([[(48,0)],False],[[(48,0),(52,4)],True]):
            f=PlannedFigures(p,sm,index,d);f.prepare(sm,target_bars(sm,plan))
            with patch('musicomp.realize.retrieval.realise',return_value=([OutNote(F(0),F(4),pitches,staff=2)],[],[])) as engine,patch('musicomp.realize.voicing.inversion_bass'),patch('musicomp.realize.voicing.chord_bass'),patch('musicomp.realize.voicing.clean_left_hand',side_effect=lambda ns:(ns,{})):
                self.assertEqual(f.allows(0,source),want);self.assertEqual(f.allows(0,source),want)
                self.assertEqual(engine.call_count,1)
                self.assertFalse(f.allows(3,source)) # direct cadence stays fixed and breaks source chain

    def test_rest_activity_and_boundaries_are_observations(self):
        d,s=work();p=build(d,s);report=observe(p,d)
        self.assertEqual(len(report['bars']),4);self.assertEqual(len(report['boundaries']),3)
        self.assertTrue(report['boundaries'][1]['phrase_boundary'])
        self.assertEqual(report['status'],'observations_not_quality_ranking')
        self.assertNotIn('quality',report)

    def test_unmet_written_fallback_is_visible(self):
        d,s=work();d['accompaniment_plan']=[dict(policy(),entry_bass_range=[28,30])]
        report=observe(build(d,s),d)
        self.assertEqual(report['summary']['unmet_plan_bars'],[1,2,3,4])

    def test_carried_note_is_not_a_new_bar_entry(self):
        d,s=work();d['accompaniment_plan']=[policy()];p=build(d,s)
        p.notes=[n for n in p.notes if n.hand!='lh']+[Note(F(0),F(8),((48,0),(52,4)),'lh',1,'written sustain')]
        second=observe(p,d)['bars'][1]
        self.assertIsNone(second['first_attack'])
        self.assertFalse(second['entry_in_planned_range'])
