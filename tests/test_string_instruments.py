import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from test_notation_expression import work
from musigen.piece import build
from musigen.duet import parts, write_duet, save_duet
from musigen.listen import _instrumentation, build_page, TEMPLATE
from musigen.versions import save


class StringInstrumentTest(unittest.TestCase):
    def test_clefs_programs_and_explicit_octave(self):
        piece = build(*work("lingering_light"))
        original, piano = parts(piece)
        for name, program, clef, shift in [("viola",42,"C",0),("cello",43,"F",-1)]:
            lead, accompaniment = parts(piece,name,shift)
            self.assertEqual([n.pitches[0][0] for n in lead.notes],
                             [n.pitches[0][0]+shift*12 for n in original.notes])
            self.assertEqual([(n.onset,n.dur) for n in lead.notes],[(n.onset,n.dur) for n in original.notes])
            self.assertEqual(accompaniment.notes,piano.notes)
            with tempfile.TemporaryDirectory() as tmp:
                xml=Path(tmp)/"score.xml"
                write_duet(piece,xml,instrument=name,lead_octaves=shift)
                tree=ET.parse(xml)
                self.assertEqual(tree.findtext("./part-list/score-part/midi-instrument/midi-program"),str(program))
                self.assertEqual(tree.findtext("./part/measure/attributes/clef/sign"),clef)
                self.assertFalse(tree.findall("./part[@id='P1']//pedal"))
                routing=_instrumentation(xml.read_text(encoding="utf-8"))
                self.assertEqual(routing["staffs"],{"1":{"instrument":name,"lh":False},"2":{"instrument":"piano","lh":False},"3":{"instrument":"piano","lh":True}})

    def test_invalid_instrument_range_and_shift_rejected(self):
        piece=build(*work("lingering_light"))
        for name,shift in [("flute",0),("cello",2),("viola",-2),("violin",True)]:
            with self.assertRaises(ValueError): parts(piece,name,shift)

    def test_assets_follow_score_instruments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            save(root/"solo",*work("lingering_light"))
            for name in ("viola","cello"):
                info=save_duet(root/"solo/v001",root/name,instrument=name,lead_octaves=-1)
                self.assertEqual(info["ensemble"],name+"_piano")
                self.assertEqual(info["lead_octaves"],-1)
            out=build_page([root/"viola",root/"cello"],root/"web/index.html",piano_samples=True,shared_assets=True,individual_pages=True)
            self.assertTrue((out.parent/"assets/viola.json").exists())
            self.assertTrue((out.parent/"assets/cello.json").exists())
            self.assertFalse((out.parent/"assets/violin.json").exists())
            viola=(out.parent/"viola/index.html").read_text(encoding="utf-8")
            self.assertIn("../assets/viola.json",viola)
            self.assertIn("const CELLO_BANK = null;",viola)
            inline=build_page([root/"cello"],root/"inline.html",piano_samples=True).read_text(encoding="utf-8")
            self.assertIn('"instrument": "cello", "notes":',inline)
            self.assertNotIn("/*CELLO_SAMPLES*/",inline)

    def test_new_sample_banks_integrity_and_audit(self):
        for name in ("viola","cello"):
            folder=TEMPLATE.parent/"assets"/name
            manifest=json.loads((folder/"manifest.json").read_text())['instruments'][name]
            payload=(folder/(name+".json")).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(),manifest["sha256"])
            bank=json.loads(payload)
            self.assertEqual(len(bank["notes"]),len(manifest["audioAudit"]))
            self.assertTrue(all(a["rms"]>0 for a in manifest["audioAudit"]))
            for key,value in bank["notes"].items():
                self.assertEqual(hashlib.sha256(base64.b64decode(value.split(',')[1])).hexdigest(),manifest['sampleSha256'][key])
            low,high=manifest['playbackRange']
            self.assertTrue(all(min(abs(n-int(k)) for k in bank['notes'])<=1 for n in range(low,high+1)))

    def test_multi_string_routing(self):
        xml='<score-partwise><part-list>'+''.join(f'<score-part id="P{i}"><midi-instrument><midi-program>{p}</midi-program></midi-instrument></score-part>' for i,p in enumerate([41,42,43,1]))+'</part-list>'+''.join(f'<part id="P{i}"><measure><attributes><staves>{2 if i==3 else 1}</staves></attributes></measure></part>' for i in range(4))+'</score-partwise>'
        route=_instrumentation(xml)
        self.assertEqual(route['instruments'],['violin','viola','cello','piano'])
        self.assertEqual(route['staffs']['5'],{'instrument':'piano','lh':True})
