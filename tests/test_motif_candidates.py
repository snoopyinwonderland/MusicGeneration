import copy
import json
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

from musigen.motif_candidates import generate, run, read_json, dump, preview, contour, digest
from musigen.selections import choose, identity

def design(meter='3/4'):
    return {'title':'후보 시험','basics':{'key':'F' if meter=='3/4' else 'C','mode':'major','meter':meter,'tempo':72 if meter=='3/4' else 100,'grade':6},
            'impression':{'mood':'서정적' if meter=='3/4' else '밝음'},
            'theme':{'constraints':{'bars':1,'range':'C4-A5',**({'rhythm':'syncopated','start_on_beat':False} if meter=='4/4' else {})}}}

class CandidatesTest(unittest.TestCase):
    def test_two_designs_diversity_reproducibility_and_playability(self):
        for meter in ('3/4','4/4'):
            d=design(meter);data,previews=generate(d)
            self.assertEqual(data,generate(d)[0]);self.assertEqual(data['status'],'ready')
            rows=data['candidates'];self.assertEqual(len(rows),8)
            self.assertEqual(len({tuple(r['features']['rhythm_fingerprint']) for r in rows}),8)
            self.assertEqual(len({r['features']['contour_type'] for r in rows}),8)
            left=[]
            for r in rows:
                p,pd,s,c=previews[r['id']];self.assertFalse(c['errors']);self.assertEqual(p.bars,2)
                self.assertTrue(all(60<=m<=81 for n in p.notes if n.hand=='rh' for m,t in n.pitches))
                left.append([(n.onset,n.dur,n.pitches) for n in p.notes if n.hand=='lh'])
                self.assertFalse(p.expression)
                if meter=='4/4': self.assertTrue(r['features']['syncopated'])
            self.assertTrue(all(x==left[0] for x in left))

    def test_strong_attacks_are_tonic_tones(self):
        data,_=generate(design())
        for row in data['candidates']:
            pos=F(0)
            from musigen.motif_clip import read_events
            for e in read_events(row):
                if e.pitches and pos.denominator==1:self.assertIn(e.pitches[0]%12,(5,9,0))
                pos+=e.dur

    def test_contour_is_measured_from_pitches_not_generator_label(self):
        self.assertEqual(contour([60,62,64,65]),'ascending')
        self.assertEqual(contour([60,64,62,60]),'arch')
        self.assertEqual(contour([60,60,62,64]),'repeat_up')
        data,_=generate(design())
        from musigen.notation import parse_pitch
        for row in data['candidates']:
            self.assertEqual(row['features']['contour_type'],contour([parse_pitch(e['pitches'][0])[0] for e in row['events'] if e['pitches']]))

    def test_import_preserved_and_bad_import_not_silently_cut(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'source.json'
            clip={'format':'musicanote-motif','version':1,'name':'source','origin':'composer','events':[{'duration':'1/2','pitches':['C4']},{'duration':'1','pitches':['F4']},{'duration':'1/2','pitches':[]}],'source':{'file':'original.xml'}}
            dump(path,clip);r=generate(design(),includes=[path])[0]['candidates'][0]
            self.assertEqual(r['events'],clip['events']);self.assertEqual(r['source'],clip['source'])
            self.assertEqual(r['origin']['kind'],'composer')
            clip['events'][0]['duration']='8';dump(path,clip)
            with self.assertRaisesRegex(ValueError,'한 마디'):generate(design(),includes=[path])

    def test_stop_is_bounded_and_reports_missing_material(self):
        d=design();d['theme']['constraints']['range']='C4-C4'
        data,_=generate(d)
        self.assertEqual(data['status'],'stopped');self.assertLess(len(data['candidates']),6)
        self.assertLessEqual(data['diagnostics']['attempts'],320)
        self.assertTrue(data['diagnostics']['missing_contours'])

    def test_invalid_constraints(self):
        for change in ({'bars':2},{'bars':True},{'range':'A5-C4'},{'start_on_beat':'no'},{'rhythm':'unknown'},{'typo':1}):
            d=design();d['theme']['constraints'].update(change)
            with self.assertRaises(ValueError):generate(d)
        d=design();d['basics'].update(key='F#',grade=1)
        with self.assertRaisesRegex(ValueError,'조표'):generate(d)
        for bad in ([],{'basics':[]},{**design(),'theme':{'constraints':[]}}):
            with self.assertRaises(ValueError):generate(bad)
        d=design();d['basics']['swing']=True
        with self.assertRaisesRegex(ValueError,'swing'):generate(d)

    def test_minor_harmony_and_low_grade_do_not_silently_transpose(self):
        d=design();d['basics'].update(key='A',mode='minor',grade=1)
        data,previews=generate(d)
        self.assertEqual(data['status'],'ready')
        for row in data['candidates']:
            p,pd,s,c=previews[row['id']]
            self.assertEqual(pd['basics'],d['basics'])
            self.assertEqual([ch.symbol for on,ch in p.chords],['Am','E'])
            self.assertTrue(all(len(n.pitches)==1 for n in p.notes if n.hand=='lh'))
            self.assertFalse(c['errors'])

class ChoiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.work=Path(self.tmp.name);self.d=design();dump(self.work/'design.json',self.d)
        data,_=generate(self.d);self.data=data
        (self.work/'stage1_motifs').mkdir();dump(self.work/'stage1_motifs/candidates.json',data)
        self.payload={'format':'musicanote-selection','version':1,'stage':'motif','chosen':'m2','shown':['m1','m2'],'reason':'쉼이 좋다','set_id':data['set_id'],'design_sha256':data['design_sha256']}

    def test_explicit_selection_journal_next_input_and_append(self):
        p=self.work/'selection.json';dump(p,self.payload)
        a=choose(self.work,p);b=choose(self.work,'m3')
        self.assertEqual(a['reason'],'쉼이 좋다');self.assertEqual(a['shown'],['m1','m2'])
        records=[json.loads(x) for x in (self.work/'selections.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(records,[a,b]);selected=read_json(self.work/'selected_motif.json')
        self.assertEqual(selected['selection'],b);self.assertEqual(selected['motif']['events'],self.data['candidates'][2]['events'])
        self.assertEqual(b['origin']['m3'],self.data['candidates'][2]['origin'])

    def test_stale_export_and_changed_design_refused_before_write(self):
        self.payload['set_id']='wrong';p=self.work/'choice.json';dump(p,self.payload)
        with self.assertRaisesRegex(ValueError,'이전'):choose(self.work,p)
        self.d['basics']['tempo']=73;dump(self.work/'design.json',self.d)
        with self.assertRaisesRegex(ValueError,'설계'):choose(self.work,'m1')
        self.assertFalse((self.work/'selections.jsonl').exists())
        self.assertFalse((self.work/'selected_motif.json').exists())

    def test_invalid_choice_cannot_create_history(self):
        for changes in ({'chosen':'m99'},{'shown':['m1']},{'reason':42},{'shown':['m2','m2']},{'stage':'phrase'}):
            payload={**self.payload,**changes};p=self.work/'choice.json';dump(p,payload)
            with self.assertRaises(ValueError):choose(self.work,p)
        self.assertFalse((self.work/'selections.jsonl').exists())

    def test_candidate_tampering_refused(self):
        self.data['candidates'][0]['events'][0]['duration']='8'
        dump(self.work/'stage1_motifs/candidates.json',self.data)
        with self.assertRaisesRegex(ValueError,'후보 묶음'):choose(self.work,'m1')

    def test_stopped_cannot_advance(self):
        self.data['status']='stopped';self.data['set_id']=identity(self.data)
        dump(self.work/'stage1_motifs/candidates.json',self.data)
        with self.assertRaisesRegex(ValueError,'중단'):choose(self.work,'m1')

    def test_page_packaging_escaping_and_archive(self):
        self.d['title']='</script><img src=x onerror=alert(1)>'
        dump(self.work/'design.json',self.d);result=run(self.work)
        page=Path(result['path']).read_text(encoding='utf-8')
        self.assertNotIn(self.d['title'],page);self.assertIn('<\\/script>',page)
        data=read_json(self.work/'stage1_motifs/candidates.json')
        self.assertEqual(data['set_id'],identity(data))
        self.assertTrue((self.work/'stage1_motifs/runs'/result['set_id']/'m1/preview.musicxml').exists())
        self.assertTrue((self.work/'stage1_motifs/assets/piano-ATTRIBUTION.md').exists())
        self.assertFalse((self.work/'selections.jsonl').exists())
