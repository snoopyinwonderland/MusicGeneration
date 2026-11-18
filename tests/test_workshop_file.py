from io import BytesIO
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from musigen.workshop_file import compressed_score, midi_score


class WorkshopFileTests(unittest.TestCase):
    def test_midi_keeps_named_tracks_initial_rest_and_pitch(self):
        def track(title,pitch):
            events=bytes([0,255,3,len(title)])+title
            events+=bytes([96,144,pitch,80,96,128,pitch,0,0,255,47,0])
            return b'MTrk'+len(events).to_bytes(4,'big')+events
        data=b'MThd'+bytes.fromhex('00000006000100020060')+track(b'Bass',48)+track(b'Tune',67)
        root=ET.fromstring(midi_score(data)['xml'])
        self.assertEqual([p.get('id') for p in root.findall('part')],['T1','T2'])
        self.assertIn('Tune',root.findtext('./part-list/score-part[@id="T2"]/part-name'))
        notes=root.findall('./part[@id="T2"]/measure/note')
        self.assertIsNotNone(notes[0].find('rest'))
        self.assertEqual(notes[1].findtext('pitch/step'),'G')

    def test_compressed_score_uses_declared_root(self):
        buf=BytesIO()
        with ZipFile(buf,'w') as archive:
            archive.writestr('unused.xml','<other/>')
            archive.writestr('META-INF/container.xml','<container><rootfile full-path="music/song.xml"/></container>')
            archive.writestr('music/song.xml','<score-partwise/>')
        self.assertEqual(ET.fromstring(compressed_score(buf.getvalue())['xml']).tag,'score-partwise')

    def test_invalid_midi_reports_input_error(self):
        with self.assertRaises(ValueError):midi_score(b'not midi')
