"""Resolve an explicit two-bar karaoke-source recipe; no default generator changes.

Run with the repository on PYTHONPATH. Source notes and resulting scores remain local.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

from musigen.phrase_borrowing import combine
from musigen.pop_rhythm import rhythm_window, source_windows


def resolve(ref):
    path = Path(ref['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError(f"Source hash differs: {ref['title']}")
    for start, notes, position, quantize in source_windows(path):
        if start == F(ref['start']) and position == ref['position']:
            selected = rhythm_window(start, notes, quantize)
            if selected is None:
                raise ValueError('Source window is not notatable without truncation')
            return {'meter': '4/4', 'span': '8',
                    'rhythm': [[str(a), str(b-a)] for a, b, _ in selected],
                    'pitches': [p for _, _, p in selected]}
    raise ValueError(f"Source position not found: {ref}")


def build(recipe):
    bars, evidence = [], []
    for index, block in enumerate(recipe['blocks']):
        rhythm = resolve(block['rhythm'])
        if 'melody' in block:
            if block['rhythm']['path'] == block['melody']['path']:
                raise ValueError('Use different songs for rhythm and pitch')
            melody = resolve(block['melody'])
            if rhythm['rhythm'] == melody['rhythm']:
                raise ValueError('Pair must change the original melodic rhythm')
        else:
            melody = {'meter': '4/4', 'span': '8', 'pitches': block['authored_pitches']}
        written = combine(rhythm, melody, block.get('shift', 0))
        bars.extend(written)
        evidence.append({**block, 'output_bars': [2*index+1, 2*index+2],
                         'rhythm_resolved': rhythm, 'melody_resolved': melody,
                         'attacks': len(melody['pitches'])})
    return {**{k: recipe[k] for k in ('id', 'title', 'key', 'keyLabel', 'quarterBpm')},
            'time': '4/4', 'bars': bars, 'evidence': evidence}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('recipe', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.recipe.read_text(encoding='utf8')))
    with args.out.open('x', encoding='utf8') as output:
        json.dump([result], output, ensure_ascii=False, indent=2)
