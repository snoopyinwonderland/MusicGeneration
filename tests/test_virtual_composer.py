import base64
import collections
import hashlib
import json
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path
from xml.etree import ElementTree as ET

from test_notation_expression import work
from musigen.piece import build, ScoreError
from musigen.piano_io import piano_part
from musigen.duet import parts, write_duet, save_duet
from musigen.expression import compile_expression
from musigen.listen import build_page, TEMPLATE
from musigen.versions import save


class VirtualComposerTest(unittest.TestCase):
    def test_duet_preserves_every_note_and_expression(self):
        piece = build(*work('lingering_light'))
        original = piano_part(piece)
        violin, piano = parts(piece)
        signature = lambda n: (n.onset, n.dur, tuple(n.pitches), n.articulation, n.slur)
        self.assertEqual(collections.Counter(map(signature,original.notes)),
                         collections.Counter(map(signature,violin.notes+piano.notes)))
        lead = [n for n in original.notes if n.staff == 1 and n.voice == 1]
        self.assertEqual(list(map(signature,lead)),list(map(signature,violin.notes)))
        self.assertFalse(any(d.pedal for d in violin.directions))
        self.assertFalse(any(d.text for d in violin.directions))
        self.assertEqual(sum(bool(d.pedal) for d in piano.directions),48)
        with tempfile.TemporaryDirectory() as tmp:
            xml = ET.parse(write_duet(piece,Path(tmp)/'duet.xml'))
        self.assertEqual(xml.findall('.//midi-program')[0].text,'41')
        self.assertEqual(xml.findall('.//midi-program')[1].text,'1')
        self.assertEqual(len(xml.findall('./part')),2)
        self.assertEqual(len(xml.findall('./part[@id="P2"]//pedal')),48)
        self.assertEqual(len(xml.findall('./part[@id="P1"]//pedal')),0)

    def test_duet_rejects_lossy_lead(self):
        for pitches in ([(60,'C4'),(64,'E4')],[(48,'C3')]):
            piece = build(*work('lingering_light'))
            note = next(n for n in piece.notes if n.hand=='rh' and n.voice==1)
            note.pitches = pitches
            with self.assertRaises(ValueError):
                parts(piece)

    def test_pedal_release_does_not_shorten_hairpin(self):
        piece = build(*work('lingering_light'))
        pedal, hairpin = compile_expression(piece,[{'bars':'1','pedal':'held','release':'1/4','hairpin':'cresc'}])
        self.assertEqual(pedal['end'],F(11,4))
        self.assertEqual(hairpin['end'],F(3))
        for release in (-1,3,4):
            with self.assertRaises(ScoreError):
                compile_expression(piece,[{'bars':'1','pedal':'held','release':release}])

    def test_shared_assets_and_standalone_download(self):
        d,s=work('lingering_light')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            save(root/'solo',d,s)
            info=save_duet(root/'solo/v001',root/'duet')
            self.assertEqual(info['source'],{'piece':'solo','version':'v001'})
            pdf=b'%PDF-1.4\nfixture for transport only'
            (root/'duet/v001/piece.pdf').write_bytes(pdf)
            out=build_page([root/'solo',root/'duet'],root/'public/index.html',
                           piano_samples=True,individual_pages=True,shared_assets=True)
            text=(out.parent/'duet/index.html').read_text(encoding='utf-8')
            self.assertNotIn('data:audio/mpeg;base64,',text)
            self.assertNotIn(str(root),text)
            self.assertIn('../assets/violin.json',text)
            self.assertIn('../assets/duet-v001.pdf',text)
            self.assertEqual((out.parent/'assets/duet-v001.pdf').read_bytes(),pdf)
            self.assertEqual(len(list(out.parent.glob('**/violin.json'))),1)
            solo=(out.parent/'solo/index.html').read_text(encoding='utf-8')
            self.assertIn('const VIOLIN_BANK = null;',solo)
            standalone=build_page([root/'duet'],root/'standalone.html').read_text(encoding='utf-8')
            self.assertIn(base64.b64encode(pdf).decode(),standalone)

    def test_violin_sample_integrity(self):
        root=TEMPLATE.parent/'assets/violin'
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256((root/'violin.json').read_bytes()).hexdigest(),
                         manifest['instruments']['violin']['sha256'])
        bank=json.loads((root/'violin.json').read_text(encoding='utf-8'))
        self.assertEqual(len(bank['notes']),27)
        self.assertTrue(all(min(abs(m-int(k)) for k in bank['notes'])<=1 for m in range(55,94)))
