import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from fractions import Fraction as F
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from musigen.corpus_accomp import FIELD, select, semantic, _reject, PlannedFigures
from musigen.piece import Note, ScoreError, build
from musicomp.realize.retrieval import Choice, target_bars
from musicomp.realize.musicxml import OutNote
from musicomp.realize.grades import profile


def work():
    d = {"title": "Original test", "basics": {"key": "C", "mode": "major", "meter": "4/4", "tempo": 72, "grade": 6},
         "form": [{"label": "A", "bars": [1, 2], "function": "statement"},
                  {"label": "A′", "bars": [3, 4], "function": "return"}],
         "phrase_plan": [{"bars": [1, 2]}, {"bars": [3, 4]}], "climax": {"bar": 3}}
    s = {"motifs": {"a": "C5/h D5/q r/q"}, "blocks": [
        {"bars": "1-2", "rh": [{"motif": "a"}, {"motif": "a"}], "lh": {"pattern": "broken", "chords": "C G7"}, "dyn": "p"},
        {"bars": "3", "rh": {"motif": "a"}, "lh": {"pattern": "broken", "chords": "C"}, "rh2": "E4/h r/h"},
        {"bars": "4", "rh": "C5/w", "lh": "[C3,G3]/w", "chords": "C"}],
        "expression": [{"bars": "1-4", "pedal": "bar"}]}
    return d, s


class CorpusTest(unittest.TestCase):
    def choose_score(self, d, s, missing=(), collide=()):
        calls = {}
        def choose(sm, plan, **kw):
            calls.update(kw)
            return [Choice(t, None if t.index in missing else {"song": "synthetic fixture", "bar": t.index}, 1.0)
                    for t in target_bars(sm, plan)]
        def realise(sm, choices):
            ns=[]
            for c in choices:
                if c.source is None: continue
                t=c.bar
                pitch = 84 if t.index in collide else 48
                ns.append(OutNote(t.start,F(4),[(pitch,0)],voice=1,staff=2))
            return ns, [], []
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as ctx:
            path=Path(tmp)/'synthetic.jsonl';path.write_text('synthetic test fixture',encoding='utf-8')
            index=SimpleNamespace(size=4,by_song={'synthetic fixture':{}},path=path,figure=lambda r:'held')
            for name, value in [('load_index',lambda:index),('choose',choose),('realise',realise)]:
                ctx.enter_context(patch('musicomp.realize.retrieval.'+name,value))
            ctx.enter_context(patch('musicomp.realize.pacing.load_model',return_value=None))
            result=select(d,s)
        return result,calls

    def test_fixed_snapshot_preserves_composition_and_rebuilds_without_library(self):
        d,s=work();original=build(d,s)
        result,calls=self.choose_score(d,s)
        self.assertNotIn(FIELD,s)
        self.assertTrue(calls['pacing']);self.assertEqual(calls['grade'],6)
        self.assertIn(d['title'],calls['exclude'])
        with patch('musicomp.realize.retrieval.load_index',side_effect=AssertionError('must not search')):
            rebuilt=build(d,json.loads(json.dumps(result)))
        self.assertEqual([n for n in original.notes if n.hand=='rh'],[n for n in rebuilt.notes if n.hand=='rh'])
        self.assertEqual(original.expression,rebuilt.expression)
        self.assertEqual(original.analysis_chords,rebuilt.analysis_chords)
        self.assertEqual(original.directions,rebuilt.directions)
        self.assertEqual(original.in_bars(4,4,'lh'),rebuilt.in_bars(4,4,'lh'))
        self.assertEqual(result[FIELD]['report']['applied_bars'],[1,2,3])

    def test_missing_and_crossing_candidates_keep_exact_original_bars(self):
        d,s=work();out,_=self.choose_score(d,s,missing=(0,),collide=(1,))
        a,b=build(d,s),build(d,out)
        for bar in (1,2,4): self.assertEqual(a.in_bars(bar,bar,'lh'),b.in_bars(bar,bar,'lh'))
        self.assertEqual(out[FIELD]['report']['applied_bars'],[3])

    def test_editing_melody_or_design_rejects_stale_snapshot(self):
        d,s=work();out,_=self.choose_score(d,s)
        changed=copy.deepcopy(out);changed['motifs']['a']='E5/h D5/q r/q'
        with self.assertRaisesRegex(ScoreError,'입력이 바뀌'): build(d,changed)
        d['basics']['tempo']=80
        with self.assertRaises(ScoreError): build(d,out)

    def test_invalid_snapshot_cannot_write_right_hand_or_out_of_range(self):
        d,s=work();out,_=self.choose_score(d,s)
        for key,value in [('hand','rh'),('dur','-1'),('onset','100'),('pitches',[[200,0]])]:
            bad=copy.deepcopy(out);bad[FIELD]['notes'][0][key]=value
            with self.assertRaises(ScoreError): build(d,bad)

    def test_unknown_harmony_does_not_carry_forward(self):
        d,s=work();s['blocks'][1]={'bars':'3','rh':{'motif':'a'},'lh':'C3/w'}
        sm,_=semantic(build(d,s),d)
        self.assertFalse(any(c.start<=8<c.end for c in sm.chords))

    def test_hidden_symbols_still_supply_authored_harmony(self):
        d,s=work();s['show_chords']=False
        p=build(d,s);self.assertFalse(p.chords)
        sm,_=semantic(p,d)
        self.assertEqual([c.root_pc for c in sm.chords],[0,7,0,0])

    def test_inversions_local_keys_sections_and_climax_are_not_reinferred(self):
        d,s=work();s['blocks'][0]['lh']['chords']='C/E G7'
        s['blocks'][1]['key']='D major';s['blocks'][1]['lh']['chords']='D/F#'
        sm,_=semantic(build(d,s),d)
        self.assertEqual((sm.chords[0].key.tonic_pc+7*sm.chords[0].bass)%12,4)
        self.assertEqual(sm.key.key_at(F(8)).name,'D')
        self.assertEqual(sm.chords[2].root_pc,2)
        self.assertEqual([p.first_bar for p in sm.phrases],[0,2])
        self.assertEqual(sm.form.climax_bar,2)
        self.assertEqual([s['letter'] for s in sm.form.sections],['A','A'])
        self.assertEqual([s['occurrence'] for s in sm.form.sections],[1,2])

    def test_source_title_excluded(self):
        d,s=work();s['motifs']['a']={'format':'musicanote-motif','version':1,'name':'a',
            'events':[{'duration':'4','pitches':['C5']}],
            'source':{'file':'An Original Theme.musicxml.xml'}}
        _,calls=self.choose_score(d,s)
        self.assertIn('An Original Theme',calls['exclude'])

    def test_written_left_motif_silence_and_crossbar_tie_are_protected(self):
        d,s=work()
        s['blocks'][0]['lh']='C3/w~ | C3/w'
        s['blocks'][1]['lh']='r/w'
        out,_=self.choose_score(d,s)
        self.assertEqual(out[FIELD]['report']['applied_bars'],[])
        self.assertEqual([n for n in build(d,s).notes if n.hand=='lh'],[n for n in build(d,out).notes if n.hand=='lh'])

    def test_held_inner_voice_and_overlapping_lh_guard(self):
        d,s=work();p=build(d,s)
        candidate=[OutNote(F(8),F(4),[(65,-1)],voice=1,staff=2)]
        self.assertIn('오른손',_reject(candidate,p,3,profile(6)))
        candidate=[OutNote(F(0),F(3),[(36,0)]),OutNote(F(2),F(2),[(43,1)])]
        self.assertIn('겹침',_reject(candidate,p,1,profile(6)))

    def test_pickup_preserved_and_opening_phrase_contains_it(self):
        d,s=work();d['basics']['pickup']='1'
        s['blocks'].insert(0,{'bars':'0','rh':'G4/q','lh':'C3/q','chords':'C:1'})
        out,_=self.choose_score(d,s)
        self.assertEqual(build(d,s).in_bars(0,0),build(d,out).in_bars(0,0))
        self.assertEqual(out[FIELD]['report']['phrases'][0]['bars'],[0,2])

    def test_chordal_rh1_is_not_silently_reduced(self):
        d,s=work();s['blocks'][-1]['rh']='[C5,E5]/w'
        with self.assertRaisesRegex(ValueError,'단선율'): semantic(build(d,s),d)

    def test_planned_figure_filter_retains_existing_texture_contrast(self):
        from musicomp.realize.retrieval import classify_figure
        d,s=work();p=build(d,s);sm,_=semantic(p,d)
        constraint=PlannedFigures(p,sm,SimpleNamespace(figure=classify_figure))
        self.assertEqual(constraint.figures[0],'arpeggio')
        held={'meter':'4/4','bar_len':'4','lh':[{'on':'0','dur':'4','notes':[{'midi':48}]}]}
        self.assertFalse(constraint.allows(0,held))
        self.assertTrue(constraint.allows(3,held))  # authored final chord is not replaced

    def test_experimental_selector_rejected(self):
        d,s=work()
        with patch('musicomp.realize.transition_retrieval.enabled',return_value=True):
            with self.assertRaisesRegex(ScoreError,'실험용'): select(d,s)

if __name__=='__main__': unittest.main()
