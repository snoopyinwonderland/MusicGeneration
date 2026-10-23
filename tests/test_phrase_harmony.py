import json
import unittest
from test_notation_expression import work
from musicomp.theory import Key, name_to_tpc
from musigen.accomp import parse_chord
from musigen.harmony_labels import analyze as harmony, label
from musigen.phrases import analyze as phrasing
from musigen.piece import build
from musigen.checks import check
from musigen.design import validate, DesignError


class PhraseHarmonyTest(unittest.TestCase):
    def test_classical_inversions_and_extensions(self):
        key=Key(name_to_tpc('D'),False)
        examples={'D':'I','D/F#':'I⁶','D/A':'I⁶₄','A7':'V⁷','A7/C#':'V⁶₅',
                  'A7/E':'V⁴₃','A7/G':'V⁴₂','C#dim':'vii°','C#m7b5':'viiø⁷',
                  'D6':'I(add6)','Dadd9':'I(add9)'}
        for symbol,expected in examples.items():
            with self.subTest(symbol=symbol):
                self.assertEqual(label(parse_chord(symbol),key)['display'],expected)

    def test_context_secondary_and_minor(self):
        key=Key(name_to_tpc('D'),False)
        self.assertEqual(label(parse_chord('D'),key,secondary=True)['display'],'I')
        self.assertEqual(label(parse_chord('E7'),key,secondary=True)['display'],'V⁷/V')
        minor=Key(name_to_tpc('D'),True)
        self.assertEqual(label(parse_chord('Dm/F'),minor)['display'],'i⁶')
        self.assertEqual(label(parse_chord('Em7b5'),minor)['display'],'iiø⁷')
        self.assertEqual(label(parse_chord('A7'),minor)['display'],'V⁷')
        self.assertEqual(label(parse_chord('Bb'),minor)['display'],'VI')
        self.assertEqual(label(parse_chord('C#dim7'),minor)['display'],'vii°⁷')
        f_major=Key(name_to_tpc('F'),False)
        self.assertEqual(label(parse_chord('Eb7'),f_major)['display'],'♭VII⁷')
        self.assertEqual(label(parse_chord('Cm7'),f_major)['display'],'v⁷')

    def test_sounding_bass_and_local_key(self):
        d,s=work('lingering_light')
        p=build(d,s)
        rows=harmony(p)
        self.assertEqual(rows[1]['display'],'I⁶')
        self.assertEqual(rows[1]['bass'],'F#')
        p.bar_keys[1]=Key(name_to_tpc('G'),False)
        self.assertEqual(harmony(p)[0]['display'],'V')
        # Explicit non-chord pedal bass remains disclosed, not a fictional inversion.
        value=label(parse_chord('D'),p.key,name_to_tpc('E'))
        self.assertIsNotNone(value['note'])
        self.assertIn('/ E',value['display'])

    def test_phrase_observations_have_real_breaths_and_all_notes(self):
        d,s=work('lingering_light')
        p=build(d,s)
        report=phrasing(p,d['phrase_plan'])
        self.assertEqual(len(report['rests']),9)
        self.assertAlmostEqual(report['rest_quarters'],7.5)
        self.assertEqual([r['bars'] for r in report['phrases']],[[1,4],[5,8],[9,12],[13,16],[17,20],[21,24]])
        self.assertTrue(all(r['detected_end'] for r in report['plan']))
        json.dumps(report)  # No Fraction objects escape into the public JSON payload.
        self.assertFalse(check(p,d)['errors'])
        self.assertFalse(check(p,d)['warnings'])

    def test_optional_phrase_analysis_and_title_independence(self):
        d,s=work('after_rain')
        self.assertIsNone(check(build(d,s),d)['phrasing'])
        d,s=work('lingering_light')
        original=phrasing(build(d,s),d['phrase_plan'])
        d['title']='다른 제목'
        self.assertEqual(original,phrasing(build(d,s),d['phrase_plan']))

    def test_phrase_pickup_numbering_and_polyphonic_rejection(self):
        d,s=work('winter_morning')
        piece=build(d,s)
        # The old fixture ends in a chord; select a monophonic lead for this pickup test.
        for note in piece.notes:
            if note.hand=='rh' and note.voice==1:
                note.pitches=(max(note.pitches),)
        report=phrasing(piece)
        self.assertTrue(report['phrases'])
        self.assertLessEqual(report['phrases'][0]['bars'][0],1)
        d,s=work('lingering_light')
        p=build(d,s)
        next(n for n in p.notes if n.hand=='rh' and n.voice==1).pitches=((60,0),(64,4))
        with self.assertRaises(ValueError):phrasing(p)

    def test_phrase_plan_validation(self):
        for plan in ([{'bars':[1,25]}],[{'bars':[4,2]}],[{'bars':[1,4]},{'bars':[3,8]}],[{'bars':['1',4]}]):
            d,_=work('lingering_light')
            d['phrase_plan']=plan
            with self.assertRaises(DesignError):validate(d)
