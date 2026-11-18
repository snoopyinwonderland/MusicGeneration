import json
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path
from unittest.mock import patch

from music21 import converter
from musigen.motif_workshop import compose, develop_neighbors, motif, rerhythm, settings, unpack


class MotifWorkshopTests(unittest.TestCase):
    def setUp(self):
        self.data=dict(key='Eb major',meter='4/4',bars=8,tempo=92,title='이어쓰기')
        self.clip={'format':'musicanote-motif','version':1,'name':'앞부분',
                   'events':[{'duration':'1/2','pitches':['Eb4']},{'duration':'1/2','pitches':[]},
                             {'duration':'1','pitches':['G4']}]}

    def test_completion_preserves_events_and_fills_two_bars(self):
        for meter,length in [('4/4',8),('3/4',6),('6/8',6)]:
            result=motif(dict(self.data,mode='complete',meter=meter,clip=self.clip))
            self.assertEqual(result['events'][:3],self.clip['events'])
            self.assertEqual(sum(d for d,_ in unpack(result)),length)
            with self.assertRaises(ValueError):
                motif(dict(self.data,mode='complete',meter=meter,clip=result))

    def test_random_seed_uses_repeatable_phrase_statistics(self):
        with patch('musigen.motif_workshop.secrets.randbits',return_value=126):
            first=motif(dict(self.data,mode='auto'))
            self.assertEqual(first,motif(dict(self.data,mode='auto')))
            self.assertGreater(len(set(n for _,n in unpack(first))),1)

    def test_neighbor_answers_keep_the_theme_and_change_two_bar_rhythms(self):
        for bars in [8,16]:
            for meter,beat in [('4/4',4),('3/4',3),('6/8',3)]:
                spec=settings(dict(self.data,bars=bars,meter=meter))
                spec.seed=42
                theme=[(F(1),60+i%3) for i in range(2*beat)]
                line=develop_neighbors(spec,theme)
                self.assertEqual(line[:len(theme)],theme)
                self.assertEqual(sum(d for d,_ in line),beat*bars)
                self.assertTrue(all(d>0 for d,_ in line))
                self.assertNotEqual(line[len(theme):len(theme)*2],theme)
                self.assertTrue(any(d!=1 for d,_ in line[len(theme):]))

    def test_repeated_rhythm_changes_keep_notes_rests_and_total(self):
        current=self.clip
        for _ in range(20):
            varied=rerhythm(current)
            self.assertNotEqual(varied['events'],current['events'])
            original,changed=unpack(current),unpack(varied)
            self.assertEqual([p for _,p in original],[p for _,p in changed])
            self.assertEqual(sum(d for d,_ in original),sum(d for d,_ in changed))
            self.assertTrue(varied['rhythm_variation']['same_length'])
            current=varied
        self.assertEqual(self.clip['events'][0]['duration'],'1/2')

    def test_single_note_reroll_changes_its_duration(self):
        clip={**self.clip,'events':self.clip['events'][:1]}
        varied=rerhythm(clip)
        self.assertNotEqual(varied['events'][0]['duration'],'1/2')
        self.assertFalse(varied['rhythm_variation']['same_length'])

    def test_manual_incipit_survives_published_score_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=compose(tmp,dict(self.data,clip=self.clip))
            self.assertEqual(result['development'],'neighbors')
            dest=Path(tmp)/'compositions'/result['id']
            self.assertEqual(json.loads((dest/'piece.json').read_text('utf8'))['clip'],self.clip)
            score=converter.parse(dest/'melody.musicxml')
            self.assertEqual(len(score.parts),2)
            line=score.parts[0].flatten().notesAndRests
            self.assertEqual([(None if e.isRest else e.pitch.midi,e.duration.quarterLength) for e in line[:3]],
                             [(63,F(1,2)),(None,F(1,2)),(67,1)])
            self.assertEqual(score.highestTime,32)
