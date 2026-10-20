"""Spec -> lead sheet (tune + chord part) -> optional musicomp arrangement (piano solo, duet, trio, quartet).

  python -m musigen compose examples/evening.json --out output/evening [--arrange --grade 7 --style lyrical]
  python -m musigen text "F장조 4/4, 32마디 AABA, 브리지에서 높아지게" --out output/x [--arrange]
"""
from __future__ import annotations

import json
from pathlib import Path

from musigen.harmony import progression
from musigen.melody import compose_melody
from musigen.score_io import write_leadsheet
from musigen.spec import Spec, to_dict


def compose(spec: Spec, out_dir: Path, arrange: bool = False, grade: int | None = 7, style: str | None = "lyrical") -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chords = progression(spec)
    notes = compose_melody(spec, chords)
    lead = write_leadsheet(spec, chords, notes, out_dir / "leadsheet.musicxml")
    (out_dir / "spec.json").write_text(json.dumps(to_dict(spec), ensure_ascii=False, indent=1), encoding="utf-8")
    result = {"leadsheet": str(lead), "bars": spec.total_bars, "chords": [c.token for c in chords],
              "notes": sum(1 for _, _, m in notes if m is not None)}
    if arrange:
        from musicomp.pipeline import arrange as musicomp_arrange
        arr = musicomp_arrange(str(lead), str(out_dir / "arrangement"), "given", piano="retrieval", grade=grade,
                               style_plan=[{"from_bar": 1, "style": style}] if style else None)
        result["arrangement"] = str(arr)
    (out_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result
