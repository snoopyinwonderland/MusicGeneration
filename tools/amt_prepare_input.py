"""Freeze an explicitly author-designated diagnostic prefix and harmony."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from musigen.blueprint import prepare
from musigen.model_trial import protocol


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--piece', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    plan = json.loads((args.piece/'development.json').read_text(encoding='utf-8'))
    motif = json.loads((args.piece/'motif.json').read_text(encoding='utf-8'))
    lead, _, _ = prepare(motif, plan)
    if str(lead.bar_len) != '4' or lead.qpm != 100 or plan['design']['basics']['key'] != 'C' or plan['design']['basics']['mode'] != 'major':
        p.error('이번 사전 지정 진단은 C장조 4/4, 100 BPM만 받습니다')
    prefix, harmony = [], []
    for note in lead.notes:
        if note.onset >= 32:
            continue
        if note.onset < 8:
            target, offset = prefix, 0
        elif note.hand == 'lh':
            target, offset = harmony, 27513
        else:
            continue
        onset, duration = note.onset*60, note.dur*60
        if onset.denominator != 1 or duration.denominator != 1:
            raise ValueError('입력은 10ms 해상도로 정확히 표현되어야 합니다')
        for pitch, _ in note.pitches:
            target.extend([int(onset)+offset, 10000+int(duration)+offset, 11000+pitch+offset])
    value = {'protocol': protocol(), 'title': lead.title,
             'prefix_tokens': prefix, 'control_tokens': harmony,
             'source_files': {name: hashlib.sha256((args.piece/name).read_bytes()).hexdigest()
                              for name in ('motif.json', 'development.json')},
             'input_decision': '작곡자가 수정된 m5 기반 완성곡의 1–2마디를 진단 입력으로 지정. '
                               '사용자가 P2 프레이즈를 골랐다는 뜻이 아니다.',
             'harmony': [h for h in plan['harmony'] if h['bar'] <= 8]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
