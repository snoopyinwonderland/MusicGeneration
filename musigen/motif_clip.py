"""Portable motif clips: explicit pitches, rational durations and source metadata."""
from fractions import Fraction as F
from pathlib import Path
import json
import re

from musicomp.theory import Key, name_to_tpc, tpc_name
from musigen.notation import Ev, NotationError, STEP_PC, parse_pitch

FORMAT = "musicanote-motif"


def read_events(clip, label=""):
    if not isinstance(clip, dict) or clip.get("format") != FORMAT or clip.get("version") != 1:
        raise NotationError("MUSICANOTE 모티프 형식(version 1)이 필요합니다")
    rows = clip.get("events")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
        raise NotationError("모티프에는 1–4096개의 음 또는 쉼이 필요합니다")
    events = []
    for row in rows:
        if not isinstance(row, dict):
            raise NotationError("모티프 사건은 duration과 pitches를 가진 객체여야 합니다")
        if not re.fullmatch(r"\d+(?:/\d+)?", str(row.get("duration"))):
            raise NotationError("모티프 음가는 양의 정수 또는 분수여야 합니다")
        try:
            dur = F(str(row.get("duration")))
        except (ValueError, ZeroDivisionError):
            raise NotationError("모티프 음가는 양의 분수여야 합니다") from None
        # The shared writer supports binary values and triplets, down to 1/12 quarter.
        if dur < F(1, 12) or dur > 256 or 24 % dur.denominator:
            raise NotationError("현재 기보는 1/12박 이상인 일반 음가·셋잇단음표를 지원합니다")
        pitches = row.get("pitches")
        if not isinstance(pitches, list) or len(pitches) > 10 or not all(isinstance(p, str) for p in pitches):
            raise NotationError("pitches는 음이름 목록이며 쉼표는 빈 목록입니다")
        ps = sorted(parse_pitch(p) for p in pitches)
        if any(not 0 <= midi <= 127 for midi, _ in ps):
            raise NotationError("MIDI 0–127 밖의 음은 지원하지 않습니다")
        if len(set(ps)) != len(ps):
            raise NotationError("한 화음에 같은 음이 중복되었습니다")
        events.append(Ev(dur, tuple(m for m, _ in ps), tuple(t for _, t in ps), src=label))
    if not any(e.pitches for e in events):
        raise NotationError("모티프에 소리 나는 음이 하나 이상 필요합니다")
    return events


def pitch_name(midi, tpc):
    name = tpc_name(tpc)
    alter = name.count("#") - name.count("b")
    octave = (midi - alter - STEP_PC[name[0]]) // 12 - 1
    return f"{name}{octave}"


def to_clip(events, name="a", source=None):
    from musicomp.theory import spell
    key = Key(0, False)
    return {"format": FORMAT, "version": 1, "name": name,
            "events": [{"duration": str(e.dur),
                        "pitches": [pitch_name(m, t if t is not None else spell(m, key))
                                    for m, t in zip(e.pitches, e.tpcs)]} for e in events],
            "source": source or {}}


def develop(source, out, ops=(), key="C", mode="major", meter="4/4"):
    """Make a preview and an embeddable score from an imported motif, using existing operations."""
    from dataclasses import replace
    from musigen.motif import realise
    from musigen.piece import build
    from musigen.design import bar_len
    from musigen.piano_io import write_musicxml, write_midi
    from musicomp.theory import spell

    clip = json.loads(Path(source).read_text(encoding="utf-8-sig"))
    original = read_events(clip, "a")
    local_key = Key(name_to_tpc(key), mode == "minor")
    events = realise(original, list(ops), local_key, label="a")
    events = [replace(e, tpcs=tuple(t if t is not None else spell(m, local_key)
                                  for m, t in zip(e.pitches, e.tpcs))) for e in events]
    result = to_clip(events, clip.get("name", "a"), {"clip": clip.get("source", {}), "operations": list(ops)})
    read_events(result)  # Reject unsupported durations introduced by a transformation.
    length = sum((e.dur for e in events), F(0))
    blen = bar_len(meter)
    bars = max(1, -(-length // blen))
    padded = list(events)
    if length < bars * blen:
        padded.append(Ev(bars * blen - length))
    preview = to_clip(padded, "a", result["source"])
    read_events(preview)
    design = {"title": "모티프 발전 미리보기", "basics": {"key": key, "mode": mode, "meter": meter, "tempo": 72},
              "theme": {"motifs": {"a": {"describe": "불러온 모티프", "hand": "rh"}}},
              "form": [{"label": "A", "bars": [1, int(bars)], "function": "statement", "motifs": ["a"]}]}
    score = {"motifs": {"a": preview}, "blocks": [{"bars": f"1-{bars}", "rh": [{"motif": "a"}]}]}
    piece = build(design, score)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    for name, obj in (("motif.json", result), ("design.json", design), ("score.json", score)):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    xml = write_musicxml(piece, out / "piece.musicxml")
    write_midi(xml, out / "piece.mid")
    return {"out": str(out), "quarters": str(length), "bars": int(bars), "operations": list(ops)}
