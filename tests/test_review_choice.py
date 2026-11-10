import copy
import json
from pathlib import Path
import tempfile
import unittest
from musigen.review_choice import manifest, record, validate, section


class ReviewChoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for side in ('a','b'):
            (self.root/side).mkdir()
            for kind in ('melody_harmony','piano_solo'):
                (self.root/side/(kind+'.musicxml')).write_text(side+kind)
        self.m = manifest(self.root, {'input_sha256':'f'*64})
        self.e = {k:self.m[k] for k in ('work','stage','shown','design_sha256','comparison_sha256')}
        self.e.update(format='musicanote-listening-choice',version=1,
            event_id='00000000-0000-4000-8000-000000000001',time='2026-11-11T12:00:00Z',
            verdict='b',chosen='b',reason='연결',evaluation=False)

    def test_explicit_choice_and_idempotent_import(self):
        self.assertTrue(record(self.root, self.e))
        self.assertFalse(record(self.root, self.e))
        row = json.loads((self.root/'selections.jsonl').read_text(encoding='utf-8'))
        self.assertEqual(row['origin']['b'],'composer')
        self.assertFalse(row['used_for_training'])

    def test_rejection_is_not_selection(self):
        self.e.update(verdict='reject_all',chosen=None)
        self.assertIsNone(validate(self.m,self.e)['chosen'])

    def test_stale_unshown_and_qa_records_rejected(self):
        for change in ({'shown':['b']},{'chosen':'c'},{'design_sha256':'0'*64},{'evaluation':True}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate(self.m,self.e|change)
        (self.root/'a'/'piano_solo.musicxml').write_text('changed')
        with self.assertRaises(ValueError):record(self.root,self.e)

    def test_page_has_no_preselection_and_escapes_script(self):
        self.m['work']='</script><img onerror=x>'
        page=section(self.m)
        self.assertIn('disabled',page)
        self.assertNotIn(' checked',page)
        self.assertNotIn('</script><img',page)
        self.assertIn('reject_all',page)
