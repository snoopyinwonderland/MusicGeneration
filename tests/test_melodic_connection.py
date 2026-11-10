from fractions import Fraction as F
from types import SimpleNamespace
import unittest
from musigen.melodic_connection import connections, compare_connections


def note(on, dur, pitch, hand='rh'):
    return SimpleNamespace(onset=F(on), dur=F(dur), pitches=((pitch, 0),), hand=hand)


def piece(notes):
    return SimpleNamespace(notes=notes, bars=3, bar_len=F(4),
                           bar_start=lambda bar:F(4*(bar-1)), bar_end=lambda bar:F(4*bar))


class ConnectionTests(unittest.TestCase):
    def test_rest_and_empty_bar_are_not_fabricated_notes(self):
        result = connections(piece([note(0, 1, 72), note(9, 2, 74), note(4, 4, 48, 'lh')]))
        self.assertNotIn('join_semitones', result[0])
        self.assertEqual(result[1]['gap_quarters'], '8')
        self.assertEqual(result[1]['join_semitones'], 2)

    def test_observations_change_without_selecting_a_version(self):
        a = piece([note(0, 4, 60), note(4, 1, 72), note(5, 1, 76)])
        b = piece([note(0, 4, 60), note(4, F(1, 2), 62), note(F(9, 2), F(1, 2), 64)])
        report = compare_connections(a, b)
        self.assertEqual(report['a'][0]['join_semitones'], 12)
        self.assertEqual(report['b'][0]['join_semitones'], 2)
        self.assertEqual(report['b'][0]['median_duration_ratio'], '1/8')
        self.assertNotIn('selected', report)

    def test_polyphonic_input_is_not_silently_reduced(self):
        with self.assertRaises(ValueError):
            connections(piece([note(0, 4, 72), note(1, 1, 76)]))
