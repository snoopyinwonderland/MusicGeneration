import copy
import json
import tempfile
import unittest
from pathlib import Path
from musigen.studio import validate_request,save_request,write_studio


def request():
    return {'format':'musicanote-composition-request','version':1,
            'motif':{'format':'musicanote-motif','version':1,'events':[{'duration':'1','pitches':['Eb4']},{'duration':'1','pitches':[]}]},
            'preferences':{'prompt':'주제의 쉼을 살려 발전','key':'Eb major','meter':'3/4','tempo':80,'bars':16,
                           'secondary':True,'augmented_sixth':True,'modulation':True,'outputs':['melody_harmony','piano_solo']}}


class StudioTest(unittest.TestCase):
    def test_save_keeps_motif_and_separates_requests(self):
        data=request()
        with tempfile.TemporaryDirectory() as tmp:
            a=save_request(tmp,data);b=save_request(tmp,data)
            self.assertNotEqual(a['id'],b['id'])
            saved=json.loads((Path(tmp)/a['url']).read_text(encoding='utf-8'))
            self.assertEqual(saved,data)
            self.assertEqual(a['status'],'awaiting_composer')

    def test_reject_polyphony_bad_preferences_and_oversized_motif(self):
        for change in [lambda d:d['motif']['events'][0]['pitches'].append('G4'),
                       lambda d:d['preferences'].update(secondary='yes'),
                       lambda d:d['preferences'].update(tempo=0),
                       lambda d:d['preferences'].update(outputs=['piano_solo']),
                       lambda d:d['motif']['events'][0].update(duration='256'),
                       lambda d:d.update(path='../elsewhere')]:
            data=request();change(data)
            with self.assertRaises(ValueError):validate_request(data)

    def test_studio_preserves_saved_requests_when_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved=save_request(tmp,request());root=write_studio(tmp)
            self.assertTrue((root/saved['url']).is_file())
            self.assertNotIn('/*VEROVIO_SRC*/',(root/'index.html').read_text(encoding='utf-8'))
            core=(root/'assets/motif-core.js').read_text(encoding='utf-8')
            self.assertIn('parseMusicXML',core)
            self.assertNotIn("el('openMotifStudio')",core)
