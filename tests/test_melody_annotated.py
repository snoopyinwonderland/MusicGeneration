import unittest
from fractions import Fraction as F
from musigen.melody_annotated import mtc_record, weimar_record


class AnnotatedMelodyTest(unittest.TestCase):
    def test_mtc_ioi_units_and_length_validation(self):
        row = {'id': 'test', 'features': {'midipitch': [60, 62] * 4,
               'duration_frac': ['1/2'] * 8, 'IOI_frac': ['3/4'] * 7 + [None]}}
        metadata, item = mtc_record(row)
        self.assertEqual(metadata['time_unit'], 'quarter_note')
        self.assertEqual(item['features']['rest_quarters'], '7/4')
        row['features']['IOI_frac'].pop()
        with self.assertRaises(ValueError):
            mtc_record(row)

    def test_weimar_seconds_remain_seconds(self):
        row = dict.fromkeys(['compid','performer','title','instrument','style','rhythmfeel','key','signature'], '')
        row['melid'] = 1
        meta, item = weimar_record(row, [(i * .5, .3, 60 + i) for i in range(8)])
        self.assertEqual(meta['time_unit'], 'performance_seconds')
        self.assertNotIn('span_quarters', item['features'])
        self.assertEqual(F(item['features']['rest_seconds']), F(7,5))
