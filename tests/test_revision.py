import copy,json,tempfile,unittest
from pathlib import Path
from test_notation_expression import work
from musigen.versions import save,joins,join_notes,bar_signature
from musigen.piece import build
class RevisionTest(unittest.TestCase):
    def test_ranges(self):
        self.assertEqual(joins({'rh':[0,1,4,5],'lh':[2]},6,0),[
          {'changed':[0,2],'before':None,'after':3,'before_changed':False,'after_changed':False},
          {'changed':[4,5],'before':3,'after':6,'before_changed':False,'after_changed':False}])
    def test_feedback_preserve_and_boundary(self):
        d,s=work()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); save(root,d,s,reason='초안')
            s2=copy.deepcopy(s); next(b for b in s2['blocks'] if b['bars']=='14')['rh']='C4/h.'
            v=save(root,d,s2,preserve=['bars:1-8','motif:a'],feedback='중간 요청',interpretation='14마디를 낮춤')
            self.assertEqual(v['feedback'],'중간 요청'); self.assertEqual(v['interpretation'],'14마디를 낮춤')
            self.assertEqual(v['preserve_broken'],[]); self.assertEqual(v['joins'][0]['changed'],[14,14])
            c=json.loads((root/'v002/checks.json').read_text(encoding='utf-8'))
            self.assertTrue(any('연결부' in n for n in c['notes']))
            self.assertIn('작곡 해석: 14마디를 낮춤',(root/'history.md').read_text(encoding='utf-8'))
            self.assertEqual(json.loads((root/'v001/version.json').read_text(encoding='utf-8'))['feedback'],'초안')
    def test_expression_change_counts(self):
        d,s=work(); old=bar_signature(build(d,s))
        s['expression']=[{'bars':'24','pedal':'held'}]
        new=bar_signature(build(d,s))
        self.assertEqual(old['rh']['1'],new['rh']['1']); self.assertNotEqual(old['rh']['24'],new['rh']['24'])
