import unittest
from xml.etree import ElementTree as ET
from musigen.print_score import display_copy


class PrintScoreTest(unittest.TestCase):
    def test_render_copy_keeps_notes_and_functional_label_position(self):
        xml='<score-partwise><part id="P1"><measure number="1"><harmony placement="below"><root><root-step text="">E</root-step></root><kind>Italian</kind><offset>2</offset><staff>2</staff></harmony><note><rest/><duration>4</duration></note></measure></part></score-partwise>'
        original=ET.fromstring(xml);rendered=ET.fromstring(display_copy(xml))
        self.assertEqual(ET.tostring(original.find('.//note')),ET.tostring(rendered.find('.//note')))
        self.assertIsNotNone(original.find('.//harmony'))
        self.assertIsNone(rendered.find('.//harmony'))
        self.assertEqual(rendered.findtext('.//direction/direction-type/words'),'It+6')
        self.assertEqual(rendered.findtext('.//direction/offset'),'2')
        self.assertEqual(rendered.findtext('.//direction/staff'),'2')

    def test_degree_markup_is_retained_once(self):
        xml='<score-partwise><part><measure><harmony><kind text="add9">major</kind><degree><degree-value>9</degree-value><degree-type>add</degree-type></degree></harmony></measure></part></score-partwise>'
        root=ET.fromstring(display_copy(xml))
        self.assertIsNone(root.find('.//kind').get('text'))
        self.assertEqual(root.findtext('.//degree/degree-value'),'9')
