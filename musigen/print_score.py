"""Opt-in MusicXML display copy for Verovio PDF engraving.

Verovio 6.3 renders a suppressed reference root on native augmented-sixth harmony
and duplicates custom add9 text. The original exchange score is never modified.
The display copy replaces only those labels; actual pitches and timing stay intact.
"""
from copy import deepcopy
from xml.etree import ElementTree as ET


def display_copy(xml):
    root=ET.fromstring(xml)
    labels={'Italian':'It+6','French':'Fr+6','German':'Ger+6'}
    for measure in root.findall('./part/measure'):
        for harmony in list(measure.findall('harmony')):
            kind=harmony.find('kind')
            if kind is None:continue
            if kind.text in labels:
                direction=ET.Element('direction',{'placement':harmony.get('placement','below')})
                words=ET.SubElement(ET.SubElement(direction,'direction-type'),'words',{'font-style':'italic'})
                words.text=labels[kind.text]
                offset=harmony.find('offset')
                if offset is not None:direction.append(deepcopy(offset))
                ET.SubElement(direction,'staff').text=harmony.findtext('staff','1')
                measure.insert(list(measure).index(harmony),direction);measure.remove(harmony)
            elif kind.get('text') in ('add9','madd9') and harmony.find('degree/degree-value') is not None:
                kind.attrib.pop('text')
    return ET.tostring(root,encoding='unicode')
