"""Verify saved trial provenance and prefix retention without regenerating."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musigen.model_trial import protocol, summarize


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    args=p.parse_args(); root=args.directory
    read=lambda path:json.loads(path.read_text(encoding='utf-8'))
    spec=read(root/'protocol.json'); inputs=read(root/'input.json')
    assert spec==protocol()==inputs['protocol']
    triples=lambda values:Counter(zip(values[::3],values[1::3],values[2::3]))
    prefix=triples(inputs['prefix_tokens'])
    rows=[]; artifacts={}
    for seed in spec['seeds']:
        folder=root/f'candidate-{seed+1:02d}'
        tokens=read(folder/'raw_tokens.json')
        observed=triples([value for t in zip(tokens[::3],tokens[1::3],tokens[2::3])
                          if t[0]<spec['start_tick'] for value in t])
        assert observed==prefix, f'prefix changed: {seed}'
        report=read(folder/'report.json'); assert report['seed']==seed
        rows.append(report)
        assert (folder/'raw_with_fixed_harmony.mid').read_bytes().startswith(b'MThd')
        for path in sorted(folder.iterdir()):
            if path.is_file():artifacts[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    summary=read(root/'summary.json')
    assert all(summary[k]==v for k,v in summarize(rows,spec).items())
    report={'candidates':16,'prefix_exact_all':True,
            'controls_unchanged_in_saved_input':True,
            'control_application':'원본 사건에 고정 화음 사건을 더했다. 생성된 추가 음의 충돌은 제거하지 않았다.',
            'midi_files':16,'completed':sum(r['completed'] for r in rows),
            'summary_recomputed':True,'artifacts':artifacts,
            'runner_sha256':{name:hashlib.sha256((Path(__file__).resolve().parents[1]/name).read_bytes()).hexdigest()
                             for name in ('tools/amt_generate_trial.py','tools/amt_prepare_input.py','musigen/model_trial.py')},
            'user_choice':None}
    (root/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('artifacts','runner_sha256')},ensure_ascii=False))


if __name__=='__main__':main()
