import copy
import json
import tempfile
import unittest
from pathlib import Path
from fractions import Fraction as F
from musigen.motif_candidates import generate as motifs, dump, digest
from musigen.motif_clip import read_events
from musigen.phrase_candidates import generate, run, selected_motif
from musigen.phrase_grammar import expand, observations
from musigen.piece import build
from musigen.selections import choose

ROOT=Path(__file__).resolve().parents[1]

def fixture(meter='3/4'):
    name='lyrical_34' if meter=='3/4' else 'bright_44'
    d=json.loads((ROOT/'examples/stages'/name/'design.json').read_text(encoding='utf-8'))
    data,_=motifs(d);row=data['candidates'][5 if meter=='3/4' else 4]
    selected={'motif':{k:v for k,v in row.items() if k not in ('preview','features')},'selection':{'chosen':row['id'],'selection_id':'test'}}
    return d,selected

class PhraseGrammarTest(unittest.TestCase):
    def test_three_forms_both_meters(self):
        for meter in ('3/4','4/4'):
            d,s=fixture(meter);data,pieces=generate(d,s)
            self.assertEqual(len(data['candidates']),4)
            self.assertEqual({r['score']['blocks'][0]['phrase']['type'] for r in data['candidates']},{'sentence','period','hybrid'})
            for row in data['candidates']:
                piece,checks=pieces[row['id']]
                self.assertEqual(piece.bars,8)
                self.assertFalse(checks['errors'])
                self.assertTrue(all(f['ok'] for f in checks['phrase_functions']['findings']))
                self.assertEqual(piece.chords[-1][1].symbol,d['basics']['key'])
                self.assertEqual(piece.phrase_plans[0]['end'],8)
                self.assertEqual(piece.phrase_plans[0]['functions'],{'presentation':[1,4],'continuation':[5,6],'cadential':[7,8]} if row['id'] in ('p1','p4') else {'antecedent':[1,4],'consequent':[5,8]} if row['id']=='p2' else {'antecedent':[1,4],'continuation':[5,6],'cadential':[7,8]})

    def test_selected_motif_notes_and_rests_preserved(self):
        d,s=fixture();data,pieces=generate(d,s);ev=read_events(s['motif']);pos=F(0);expected=[]
        for e in ev:
            if e.pitches:expected.append((pos,e.dur,e.pitches))
            pos+=e.dur
        for p,c in pieces.values():
            got=[(n.onset,n.dur,tuple(m for m,t in n.pitches)) for n in p.in_bars(1,1,'rh')]
            self.assertEqual(got,expected)

    def test_candidates_different_and_deterministic(self):
        d,s=fixture('4/4');a,_=generate(d,s);b,_=generate(d,s)
        self.assertEqual(a,b)
        self.assertEqual(len({digest(r['score']) for r in a['candidates']}),4)
        with self.assertRaises(ValueError):generate(d,s,2)

    def test_override_changes_actual_cadence_check(self):
        d,s=fixture();data,_=generate(d,s);r=data['candidates'][0]
        r['score']['blocks'][0]['phrase']['overrides']=[{'bars':'8','rh':'G4/h.'}]
        p=build(r['design'],r['score']);report=observations(p)
        self.assertFalse(next(f for f in report['findings'] if f['check']=='authentic_cadence')['ok'])

    def test_override_breaks_period_repeat(self):
        d,s=fixture();data,_=generate(d,s);r=data['candidates'][1]
        r['score']['blocks'][0]['phrase']['overrides']=[{'bars':'5','rh':'F4/h.'}]
        p=build(r['design'],r['score'])
        self.assertFalse(next(f for f in observations(p)['findings'] if f['check']=='consequent_return')['ok'])

    def test_override_continuation_requires_reassessment(self):
        d,s=fixture();data,_=generate(d,s);r=data['candidates'][0]
        r['score']['blocks'][0]['phrase']['overrides']=[{'bars':'5','rh':'F4/h.'},{'bars':'6','rh':'F4/h.'}]
        report=observations(build(r['design'],r['score']))
        self.assertFalse(next(f for f in report['findings'] if f['check']=='shorter_units')['ok'])

    def test_explicit_harmony_and_invalid_boundaries(self):
        d,s=fixture();data,_=generate(d,s);r=data['candidates'][0];ph=r['score']['blocks'][0]['phrase']
        ph['harmony']='I I V V IV V V I'
        self.assertEqual(build(r['design'],r['score']).chords[-1][1].symbol,'F')
        ph['harmony']='I I V V | IV V I'
        with self.assertRaises(ValueError):build(r['design'],r['score'])
        ph.pop('harmony');ph['functions']={'continuation':{'bars':[4,6]}}
        with self.assertRaises(ValueError):build(r['design'],r['score'])

    def test_offset_and_existing_blocks(self):
        d,s=fixture();data,_=generate(d,s);r=data['candidates'][0];pd=copy.deepcopy(r['design']);score=copy.deepcopy(r['score'])
        pd['form'][0]['bars']=[1,16]
        later=copy.deepcopy(score['blocks'][0]);later['bars']='9-16';score['blocks'].append(later)
        p=build(pd,score)
        self.assertEqual([x['start'] for x in p.phrase_plans],[1,9])
        self.assertIn(16,[f['bars'][0] for f in observations(p)['findings']])

    def test_minor_cadences(self):
        d,s=fixture();d['basics'].update(key='A',mode='minor')
        s['motif']['events']=[{'duration':'1','pitches':['A4']},{'duration':'1','pitches':['B4']},{'duration':'1','pitches':['C5']}]
        data,pieces=generate(d,s)
        for p,c in pieces.values():
            self.assertEqual(p.chords[-1][1].symbol,'Am')
            self.assertTrue(all(f['ok'] for f in observations(p)['findings']))

class PhraseSelectionTest(unittest.TestCase):
    def setup_work(self,path):
        from musigen.motif_candidates import run as run_motifs
        d,_=fixture();dump(path/'design.json',d);run_motifs(path);choose(path,'m6');run(path)

    def test_user_chain_and_sixteen_bar_piece(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);self.setup_work(work)
            self.assertFalse((work/'selected_phrase.json').exists())
            record=choose(work,'p2');pw=Path(record['piece_work'])
            p=build(json.loads((pw/'design.json').read_text(encoding='utf-8')),json.loads((pw/'score.json').read_text(encoding='utf-8')))
            self.assertEqual(p.bars,16)
            self.assertEqual([json.loads(line)['stage'] for line in (work/'selections.jsonl').read_text(encoding='utf-8').splitlines()],['motif','phrase'])
            old=(work/'selections.jsonl').read_bytes()
            choose(work,'m5')
            with self.assertRaises(ValueError):choose(work,'p1')
            self.assertEqual(len((work/'selections.jsonl').read_text(encoding='utf-8').splitlines()),3)

    def test_tampered_selection_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);self.setup_work(work)
            p=work/'selected_motif.json';s=json.loads(p.read_text(encoding='utf-8'));s['motif']['events'][0]['duration']='2';dump(p,s)
            with self.assertRaises(ValueError):selected_motif(work)

    def test_export_reason_and_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);self.setup_work(work);data=json.loads((work/'stage2_phrases/candidates.json').read_text(encoding='utf-8'))
            payload={'format':'musicanote-selection','version':1,'stage':'phrase','set_id':data['set_id'],'design_sha256':data['design_sha256'],'chosen':'p1','shown':['p1','p2','p3','p4'],'reason':'검증용: 실제 사용자 선택 아님'}
            dump(work/'test.json',payload);r=choose(work,work/'test.json');self.assertEqual(r['reason'],payload['reason'])
            payload['set_id']='stale';dump(work/'test.json',payload)
            with self.assertRaises(ValueError):choose(work,work/'test.json')

if __name__=='__main__':unittest.main()
