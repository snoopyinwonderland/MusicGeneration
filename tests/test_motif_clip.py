import copy
import json
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

from test_notation_expression import work
from musigen.motif_clip import read_events, to_clip, develop
from musigen.notation import NotationError
from musigen.piece import build
from musigen.motif import realise
from musicomp.theory import Key


def example():
    return {"format":"musicanote-motif", "version":1, "name":"a", "events":[
        {"duration":"1", "pitches":["F#4"]},
        {"duration":"1/2", "pitches":["A4"]},
        {"duration":"1/2", "pitches":["B4"]},
        {"duration":"1", "pitches":["A4"]}],
        "source":{"file":"own.musicxml", "part":"P1", "staff":"1", "voice":"1"}}


class MotifClipTest(unittest.TestCase):
    def test_pitch_spelling_chords_and_rational_rests_roundtrip(self):
        clip = example()
        clip['events'] = [{'duration':'1/3','pitches':['Bb4','D5']},
                          {'duration':'2/3','pitches':[]}, {'duration':'3','pitches':['F#4']}]
        events = read_events(clip)
        self.assertEqual(to_clip(events)['events'], clip['events'])
        self.assertEqual(sum(e.dur for e in events), F(4))

    def test_pasted_clip_matches_literal_and_existing_development(self):
        design, score = work('lingering_light')
        old = build(design, score)
        score['motifs']['a'] = example()
        new = build(design, score)
        # Clip v1 intentionally imports pitch, duration and rests; source slurs are redesigned.
        signature = lambda p: [(n.onset,n.dur,n.pitches,n.hand,n.voice) for n in p.notes]
        self.assertEqual(signature(old), signature(new))
        self.assertEqual(realise(read_events(example()), ['aug:2'], Key(2,False))[0].dur, F(2))
        self.assertEqual(realise(read_events(example()), ['step:1'], Key(2,False))[0].pitches, (67,))

    def test_invalid_clips_fail_without_guessing(self):
        cases = []
        for dur in ['0','-1','1/0','1/5','1/48','nan','1.25']:
            clip = example()
            clip['events'][0]['duration'] = dur
            cases.append(clip)
        clip = example()
        clip['events'][0]['pitches'] = ['C4','C4']
        cases.append(clip)
        cases += [{},dict(example(),version=2),dict(example(),events=[]),
                  dict(example(),events=[{'duration':'1','pitches':[]}])]
        for clip in cases:
            with self.subTest(clip=clip), self.assertRaises(NotationError):
                read_events(clip)

    def test_develop_outputs_portable_motif_and_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'a.json'
            source.write_text(json.dumps(example()),encoding='utf-8')
            target = Path(tmp)/'developed'
            info = develop(source,target,['step:1','aug:2'],'D','major','3/4')
            self.assertEqual(info['quarters'],'6')
            result = json.loads((target/'motif.json').read_text(encoding='utf-8'))
            self.assertEqual(result['events'][0],{'duration':'2','pitches':['G4']})
            self.assertEqual(result['source']['operations'],['step:1','aug:2'])
            score = json.loads((target/'score.json').read_text(encoding='utf-8'))
            design = json.loads((target/'design.json').read_text(encoding='utf-8'))
            self.assertEqual(build(design,score).bars,2)
            self.assertTrue((target/'piece.musicxml').exists())
            self.assertTrue((target/'piece.mid').exists())
            with self.assertRaises(FileExistsError):
                develop(source,target)
