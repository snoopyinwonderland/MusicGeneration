"""Explicit opt-in extension of the existing read-only corpus inventory."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
from musigen.corpus_catalog import inventory, source_files, XML, MIDI, NOTATION, ANNOTATIONS, AUDIO


def extend(out, midi_root=None, leadsheets_root=None):
    out=Path(out)
    path=out/'inventory.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    for ident,root,purpose in [('kysing-midi',midi_root,'documented_vocal_melody'),
                               ('kysing-leadsheets',leadsheets_root,'derived_leadsheet')]:
        if root is None or any(s['id']==ident for s in data['sources']):continue
        source={'id':ident,'path':str(root),'family':'karaoke','purpose':purpose,'recursive':True,
                'generation_default':False,'rights_state':'explicit_opt_in_local_analysis_no_redistribution'}
        files=source_files(source);ext=Counter(p.suffix.lower() for p in files)
        source.update(exists=Path(root).exists(),files=len(files),extensions=dict(ext),
                      musicxml=sum(ext[e] for e in XML),midi=sum(ext[e] for e in MIDI),
                      other_notation=sum(ext[e] for e in NOTATION),annotations=sum(ext[e] for e in ANNOTATIONS),
                      audio=sum(ext[e] for e in AUDIO),documentation=[])
        with gzip.open(out/'files.jsonl.gz','at',encoding='utf-8') as stream:
            for file in files:
                stream.write(json.dumps({'source':ident,'path':str(file),'extension':file.suffix.lower()},ensure_ascii=False)+'\n')
        data['sources'].append(source)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'roots':len(data['sources']),'files':sum(s['files'] for s in data['sources'])}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='보유 자료 목록과 명시적으로 허용한 KYSing 원본 경로')
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--kysing-midi-root',type=Path)
    parser.add_argument('--kysing-leadsheets-root',type=Path)
    args=parser.parse_args()
    inventory(args.out)
    print(json.dumps(extend(args.out,args.kysing_midi_root,args.kysing_leadsheets_root)))
