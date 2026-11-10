"""Recheck source hashes and compare key spelling against music21, read-only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from musigen.tonal_reference import read_table,label_states
from music21 import roman,key


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();root=a.root.resolve();lib=json.loads(a.library.read_text(encoding='utf-8'));files=0;checked=set();rows=0
    for work in lib['works']:
        for ref in work['sources'].values():
            path=(root/ref['path']).resolve()
            if not path.is_relative_to(root):raise ValueError('source_outside_root')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:raise ValueError('source_changed')
            files+=1
        if work['status']!='validated':continue
        parsed=label_states(read_table(root/work['sources']['harmonies']['path']));rows+=len(parsed)
        for r in parsed:
            pairs=[(r['localkey'],r['global'],r['local'])]
            if r['applied_target']:pairs.append((r['relativeroot'],r['local'],r['applied_target']))
            for token,parent,target in pairs:
                signature=(token,parent['name'],target['name'])
                if signature in checked:continue
                tonic,mode=parent['name'].split()
                rn=roman.RomanNumeral(token,key.Key(tonic.replace('b','-'),mode),sixthMinor=roman.Minor67Default.FLAT,seventhMinor=roman.Minor67Default.FLAT)
                expected_tonic,expected_mode=target['name'].split()
                if rn.root().name.replace('-','b')!=expected_tonic:raise ValueError('independent_key_spelling_mismatch:'+str(signature))
                if token.split('/')[0].islower()!=(expected_mode=='minor'):raise ValueError('target_mode_mismatch')
                checked.add(signature)
    report={'source_file_checks':files,'validated_annotation_rows':rows,'independent_key_cases':len(checked),
            'cases':sorted(checked),'method':'music21 RomanNumeral with natural minor VI/VII convention (FLAT)',
            'library_sha256':hashlib.sha256(a.library.read_bytes()).hexdigest(),
            'scope':'key spelling and source hashes; not independent XML note timing or listening judgement'}
    with a.out.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False))


if __name__=='__main__':main()
