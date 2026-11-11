import unittest
from fractions import Fraction as F
from types import SimpleNamespace
from musigen.accomp import parse_chord
from musigen.notation import parse_pitch
from musigen.voice_independence import contour,embellishments


def score(rh,lh=(),symbol='C'):
    def note(hand,row):
        t,d,p=row
        return SimpleNamespace(onset=F(t),dur=F(d),pitches=(parse_pitch(p),),hand=hand,voice=1)
    return SimpleNamespace(notes=[note('rh',x) for x in rh]+[note('lh',x) for x in lh],
                           analysis_chords=[(F(0),parse_chord(symbol))],chords=[],bar_of=lambda t:int(t//4)+1)


class VoiceIndependenceTest(unittest.TestCase):
    def test_similar_motion_is_not_always_parallel_fifths(self):
        result=contour(score([(0,1,'C4'),(1,1,'E4')],[(0,1,'C3'),(1,1,'D3')]))
        self.assertEqual(result['counts'],{'similar':1})
        self.assertEqual(result['parallel_perfect_count'],0)

    def test_release_only_rest_breaks_motion_comparison(self):
        result=contour(score([(0,1,'C4'),(2,1,'D4')],[(0,1,'C3'),(2,1,'D3')]))
        self.assertEqual(result['compared_transitions'],0)
        self.assertEqual(result['both_sounding_quarters'],'2')

    def test_held_bass_and_chord_extension(self):
        result=contour(score([(0,1,'A4'),(1,1,'C5')],[(0,2,'F3')],'F6'))
        self.assertEqual(result['counts'],{'oblique':1})
        self.assertEqual(embellishments(score([(0,1,'D5')],symbol='F6'))['events'],[])

    def test_released_chord_member_is_not_downward_melody(self):
        p=score([(0,1,'E5'),(1,1,'D5')],[(0,2,'C3'),(0,1,'G3')])
        self.assertEqual(contour(p,'top')['counts'],{})
        self.assertEqual(contour(p,'bass')['counts'],{'oblique':1})

    def test_contiguous_passing_neighbor_and_gap(self):
        self.assertEqual(embellishments(score([(0,1,'C5'),(1,1,'D5'),(2,1,'E5')]))['counts'],{'passing':1})
        self.assertEqual(embellishments(score([(0,1,'E5'),(1,1,'F5'),(2,1,'E5')]))['counts'],{'neighbor':1})
        result=embellishments(score([(0,1,'E5'),(2,1,'F5'),(3,1,'E5')]))
        self.assertNotEqual(result['events'][0]['kind'],'neighbor')

    def test_chromatic_approach_targets_next_written_harmony(self):
        p=score([(0,1,'C#5'),(1,1,'D5')])
        p.analysis_chords.append((F(1),parse_chord('Dm')))
        self.assertEqual(embellishments(p)['counts'],{'chromatic_approach':1})
