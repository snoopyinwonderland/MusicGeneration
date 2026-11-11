from fractions import Fraction as F
import unittest
from musigen.melody_pacing import gaps,observe


class MelodyPacingTest(unittest.TestCase):
    def test_sustain_without_attack_is_not_rest(self):
        report=observe([(F(1),F(5),60),(F(7),F(1),62)],4,2)
        self.assertEqual(report['bars'][1]['attacks'],1)
        self.assertTrue(report['bars'][1]['held_from_previous_bar'])
        self.assertEqual(report['bars'][1]['rest_quarters'],'1')
        self.assertEqual(report['held_across_barline'],[{'bar':1,'offset':'1','duration_quarters':'5'}])

    def test_overlapping_parts_and_outer_rests(self):
        self.assertEqual(gaps([(1,3,60),(1,1,64),(3,2,67)],6),[(F(0),F(1)),(F(5),F(1))])
        self.assertEqual(gaps([],3),[(F(0),F(3))])

    def test_invalid_bounds(self):
        for events in [[(-1,1,60)],[(0,0,60)],[(3,2,60)]]:
            with self.assertRaises(ValueError):observe(events,4,1)
