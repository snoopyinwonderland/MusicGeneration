import json,tempfile,unittest,hashlib
from pathlib import Path
from test_notation_expression import work
from musigen.versions import save
from musigen.listen import build_page,TEMPLATE
class PublishTest(unittest.TestCase):
    def test_piano_bank_integrity(self):
        root=TEMPLATE.parent/'assets/piano'
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256((root/'piano.json').read_bytes()).hexdigest(),manifest['instruments']['piano']['sha256'])
        bank=json.loads((root/'piano.json').read_text(encoding='utf-8'))
        self.assertEqual(len(bank['notes']),30)
        self.assertTrue(all(min(abs(m-int(k)) for k in bank['notes'])<=1 for m in range(21,109)))
    def test_individual_pages_and_opt_in(self):
        d,s=work()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); save(root/'rain',d,s)
            page=build_page([root/'rain'],root/'public/index.html',piano_samples=True,individual_pages=True)
            self.assertTrue((page.parent/'rain/v001.html').exists())
            self.assertIn('data:audio/mpeg;base64,',(page.parent/'rain/index.html').read_text(encoding='utf-8'))
            self.assertEqual(json.loads((page.parent/'catalog.json').read_text(encoding='utf-8'))[0]['url'],'rain/')
            self.assertIn('const PIANO_BANK = null;', (root/'rain/listen.html').read_text(encoding='utf-8'))
