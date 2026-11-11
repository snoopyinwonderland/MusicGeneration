import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from musigen.corpus_features import xml_features, voice_observations, midi_features
from musigen.corpus_catalog import DATA, resolve_composer, source_files, query, variation_id


class CorpusObservationsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def xml(self, body):
        p=self.root/'synthetic.xml'
        p.write_text('<score-partwise><part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list><part id="P1"><measure number="0" implicit="yes"><attributes><divisions>2</divisions><time><beats>3</beats><beat-type>4</beat-type></time></attributes>'+body+'</measure></part></score-partwise>',encoding='utf-8')
        return xml_features(p)

    def midi(self, tracks, fmt=1, ppq=480):
        p=self.root/'synthetic.mid'
        p.write_bytes(b'MThd'+struct.pack('>IHHH',6,fmt,len(tracks),ppq)+b''.join(b'MTrk'+struct.pack('>I',len(t))+t for t in tracks))
        return p

    def test_multivoice_backups_chords_ties_and_grace(self):
        meta,rows=self.xml('''<note><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice><tie type="stop"/></note>
        <note><grace/><pitch><step>D</step><octave>4</octave></pitch><voice>1</voice></note>
        <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice></note>
        <note><chord/><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice></note>
        <backup><duration>3</duration></backup><note><rest/><duration>1</duration><voice>2</voice></note>
        <note><pitch><step>C</step><alter>1</alter><octave>3</octave></pitch><duration>2</duration><voice>2</voice></note>''')
        row=rows[0]; voices=voice_observations(row)
        self.assertEqual(row['extent_quarters'],'3/2') # pickup not padded to 3/4
        self.assertEqual(row['notes'][3]['on'],'1')
        self.assertEqual(row['notes'][-1]['on'],'1/2')
        self.assertEqual(row['notes'][-1]['spelling'],['C','1',3])
        self.assertEqual(voices[0]['attacks'],2) # tie stop/grace not reattacks
        self.assertFalse(voices[0]['monophonic'])
        self.assertEqual(voices[0]['intervals'],[])
        self.assertEqual(voices[1]['explicit_rest_quarters'],'1/2')
        self.assertEqual(meta['melody_role'],'unknown')
        self.assertEqual(meta['pitch_basis'],'written_not_concert')

    def test_invalid_backup_refused(self):
        with self.assertRaisesRegex(ValueError,'backup'):
            self.xml('<backup><duration>2</duration></backup>')

    def test_entities_refused(self):
        p=self.root/'entity.xml';p.write_text('<!DOCTYPE x [<!ENTITY x "a">]><score-partwise/>')
        with self.assertRaisesRegex(ValueError,'entity'):
            xml_features(p)

    def test_midi_running_status_channels_and_metadata(self):
        t=b'\x00\xff\x03\x06MELODY\x00\xff\x58\x04\x03\x02\x18\x08'
        t+=b'\x00\xc0\x00\x00\x90\x3c\x40\x83\x60\x3c\x00' # running note-on velocity 0 at 480
        t+=b'\x00\x99\x24\x50\x78\x89\x24\x00\x00\xb0\x40\x7f\x00\xff\x2f\x00'
        x=midi_features(self.midi([t]));track=x['tracks'][0]
        self.assertEqual(track['pitched_notes'],1);self.assertEqual(track['drum_notes'],1)
        self.assertEqual(track['duration_quarters'],'5/4')
        self.assertEqual(track['pedal_events'],1)
        self.assertEqual(x['meters'],[(0,3,4)])
        self.assertEqual(x['warnings'],{})
        self.assertFalse(x['training_eligible'])
        self.assertNotIn('note_events', track)
        explicit=midi_features(self.midi([t]),include_notes=True)['tracks'][0]
        self.assertEqual(explicit['note_events'],[(0,480,0,60,64),(480,600,9,36,80)])
        self.assertEqual(explicit['lyric_ticks'],[])

    def test_midi_bad_header_and_truncation(self):
        with self.assertRaises(ValueError): midi_features(self.midi([],fmt=2))
        with self.assertRaises(ValueError): midi_features(self.midi([],ppq=0xE728))
        with self.assertRaises(ValueError): midi_features(self.midi([b'\x00\x90\x40']))

    def test_midi_missing_meter_and_orphan_notes_remain_unknown(self):
        x=midi_features(self.midi([b'\x00\x80\x3c\x00\x00\x90\x3d\x40\x00\xff\x2f\x00']))
        self.assertEqual(x['meters'],[])
        self.assertEqual(x['warnings'],{'orphan_note_off':1,'unterminated_notes':1})

    def test_same_surname_different_composers_not_merged(self):
        c=json.loads(DATA.read_text(encoding='utf-8'))['composers']
        a=resolve_composer('Bach, Johann Sebastian_1_1.xml',[],c)
        b=resolve_composer('Bach, Carl Phillip Emanuel_1_1.xml',[],c)
        self.assertEqual(a['id'],'bach_js')
        self.assertNotEqual(a['id'],b['id'])
        conflict=resolve_composer('Bach, Johann Sebastian_1.xml',[{'type':'composer','text':'Joseph Haydn'}],c)
        self.assertIsNone(conflict['id']);self.assertEqual(conflict['basis'],'conflict')
        self.assertIsNone(resolve_composer('01-SINFN.xml',[],c)['id'])

    def test_inventory_preserves_newlines_in_filenames(self):
        filename=str(self.root/'a\nb.mid')
        with patch('musigen.corpus_catalog.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=filename+'\0',stderr='')):
            self.assertEqual(source_files({'path':str(self.root),'recursive':True}),[Path(filename)])

    def test_activity_filter_does_not_substitute_lifetime(self):
        contexts=json.loads(DATA.read_text(encoding='utf-8'))['composers']
        profiles={c['id']:{'context':c} for c in contexts}
        (self.root/'style-profiles.json').write_text(json.dumps({'profiles':profiles}),encoding='utf-8')
        result=query(self.root,era='classical',region='Vienna',active_at=1785)
        self.assertIn('mozart',result['profiles'])
        self.assertNotIn('haydn',result['profiles']) # missing documented dates stay missing

    def test_variation_filename_optional_content_label(self):
        self.assertEqual(variation_id('B063_00_01a_a'),('B063','00','01','a','a'))
        self.assertEqual(variation_id('B075_02_05_b'),('B075','02','05','','b'))
        self.assertIsNone(variation_id('README'))


if __name__=='__main__': unittest.main()
