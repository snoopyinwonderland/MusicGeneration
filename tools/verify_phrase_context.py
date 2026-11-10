"""Independently verify timed source events with music21; no corpus writes."""
import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from musigen.humdrum_timing import parse


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--library',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); root=args.root.resolve()
    lib=json.loads(args.library.read_text(encoding='utf-8'))
    from music21 import converter
    verified=[]; files=0
    for row in lib['phrases']:
        for ref in [row['score']]+row['annotations']:
            path=(root/ref['path']).resolve()
            if not path.is_relative_to(root):raise ValueError('source_outside_root')
            assert hashlib.sha256(path.read_bytes()).hexdigest()==ref['sha256']
            files+=1
        if row['status']!='context_available':continue
        text=(root/row['score']['path']).read_text(encoding='utf-8')
        timed=parse(text)
        independent=converter.parseData(text,format='humdrum')
        expected=Counter(tuple((F(e['onset']),F(e['duration'])) for e in s['events'] if not e['grace'])
                         for s in timed['spines'] if s['kind']=='**kern')
        actual=Counter(tuple((F(n.offset),F(n.duration.quarterLength))
                       for n in part.flatten().notesAndRests if n.duration.quarterLength>0)
                       for part in independent.parts)
        assert actual==expected, row['id']+': independent note timing differs'
        expected_bars=[(F(b['onset']),F(b['duration'])) for b in timed['bars']]
        for part in independent.parts:
            actual_bars=[(F(m.offset),F(m.duration.quarterLength)) for m in part.getElementsByClass('Measure') if m.duration.quarterLength>0]
            assert actual_bars==expected_bars, row['id']+': independent bar timing differs'
        verified.append({'phrase':row['id'],'all_kern_note_and_rest_times_equal':True,'all_bar_spans_equal':True})
    for unit in lib['windows']:
        row=next(r for r in lib['phrases'] if r['id']==unit['phrase_id'])
        bars=[row['bars'][i] for i in unit['bar_ordinals']]
        assert len(bars)==unit['length_bars'] and all(b['full'] for b in bars)
        assert all(F(a['onset'])+F(a['duration'])==F(b['onset']) for a,b in zip(bars,bars[1:]))
        assert not unit['generation_eligible'] and unit['cadence_class'] is None
        span=F(unit['end'])-F(unit['start'])
        for ann in unit['annotators'].values():
            for kind in ('harm','function'):
                end=F(0)
                for event in ann[kind]:
                    assert F(event['onset'])==end
                    end+=F(event['duration'])
                assert end==span
    report={'library_sha256':hashlib.sha256(args.library.read_bytes()).hexdigest(),
            'source_files_hash_verified':files,'independent_parser':'music21.converter.parseData(format=humdrum)',
            'phrases_verified':verified,'windows_with_exact_annotation_coverage':len(lib['windows']),
            'source_written':False,'cadence_classes_inferred':False,'user_selection':None}
    with args.out.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='phrases_verified'}|{'verified_phrase_count':len(verified)},ensure_ascii=False))


if __name__=='__main__':main()
