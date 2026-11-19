import unittest

from scripts.karaoke_lyric_associations import MATCH, cue_labels, describe, lines


class LyricAssociationTest(unittest.TestCase):
    def test_syllable_padding_does_not_hide_korean_cues(self):
        self.assertEqual(cue_labels('사 랑 과 눈 물'), ['affection','loss'])
        self.assertEqual(cue_labels('gloved'), [])

    def test_line_end_belongs_to_its_final_syllable(self):
        events = [(10, 'meta', 5, '그리'.encode('cp949')),
                  (20, 'meta', 5, '워\r'.encode('cp949')),
                  (21, 'meta', 5, b'\n'), (30, 'meta', 5, b'hope')]
        first, second = lines(events)
        self.assertEqual(first, [(10, '그리'), (20, '워')])
        self.assertTrue(MATCH['longing'].search(''.join(s for _,s in first)))
        self.assertEqual(second, [(30, 'hope')])

    def test_four_notes_and_unknown_chord_gap(self):
        notes = [(0,48,60),(48,96,62),(96,192,62),(192,384,57)]
        minor = {'root':9,'ivs':[0,3,7,10]}
        major = {'root':2,'ivs':[0,4,7]}
        chords = [(0,minor),(96,None),(192,major)]
        values, grams = describe(notes,96,chords,[0,96,192])
        self.assertNotIn('minor_chord_onset_share',values)
        self.assertEqual(grams['root_motion'],{})
        self.assertEqual(grams['melody4'],{'2/0/-5+':1})
        self.assertEqual(grams['rhythm4'],{'s/s/m/l':1})
        values,grams=describe(notes,96,[(0,minor),(192,major)],[0,192])
        self.assertEqual(values['minor_chord_onset_share'],.75)
        self.assertEqual(grams['root_motion'],{'5':1})
