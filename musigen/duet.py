"""A string-piano duet: transfer the solo's monophonic lead, keep its inner voice and bass.

This explicit transformation is intentionally narrow. It does not claim orchestration
or string fingering/bow planning; polyphonic leads are rejected instead of dropped.
"""
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
import datetime as dt
import json

from musicomp.core.score import Measure
from musicomp.realize.musicxml import OutPart, write_score
from musigen.piano_io import piano_part, write_midi
from musigen.piece import build
from musigen.instruments import preset


def parts(piece, instrument="violin", lead_octaves=0):
    piano = piano_part(piece)
    config = preset(instrument)
    if type(lead_octaves) is not int or lead_octaves not in (-2, -1, 0, 1, 2):
        raise ValueError("선율 옥타브 이동은 -2부터 2까지 정수여야 합니다")
    violin = OutPart("P1", config["name"], config["abbr"], config["program"], [config["clef"]])
    lead = [n for n in piano.notes if n.staff == 1 and n.voice == 1]
    if not lead or any(len(n.pitches) != 1 for n in lead):
        raise ValueError("듀엣 변환은 단선율 오른손 첫 성부가 필요합니다")
    low, high = config["range"]
    if any(not low <= n.pitches[0][0] + 12 * lead_octaves <= high for n in lead):
        raise ValueError(f"{config['ko']} 선율이 이번 변환의 MIDI {low}–{high} 범위를 벗어납니다. 명시적인 옥타브 이동을 선택하세요")
    if any(n.staff == 1 and n.voice > 2 for n in piano.notes):
        raise ValueError("이번 듀엣 변환은 오른손 두 성부까지만 지원합니다")
    violin.notes = [replace(n, staff=1, voice=1, pitches=[(m + 12 * lead_octaves, tpc) for m, tpc in n.pitches]) for n in lead]
    # Transfer dynamics and hairpins; free text belongs to the original piano part
    # (for example con pedale) and must not become a violin instruction.
    violin.directions = [replace(d, text="", staff=1) for d in piano.directions
                         if not d.pedal and (d.dynamics or d.wedge)]
    piano.id = "P2"
    piano.notes = [replace(n, voice=1) if n.staff == 1 else n for n in piano.notes if n not in lead]
    return violin, piano


def write_duet(piece, path, subtitle="", instrument="violin", lead_octaves=0):
    violin, piano = parts(piece, instrument, lead_octaves)
    measures = [Measure(0, "0", F(0), piece.pickup, piece.bar_len)] if piece.pickup else []
    measures += [Measure(i + len(measures), str(i + 1), piece.bar_start(i + 1), piece.bar_len, piece.bar_len)
                 for i in range(piece.bars)]
    beats, beat_type = map(int, piece.meter.split("/"))
    return write_score(Path(path), piece.title, [violin, piano], measures, beats, beat_type,
                       piece.key.sharps, piece.key.minor, tempo=piece.qpm, subtitle=subtitle)


INTERPRETATION = "오른손 첫 성부를 바이올린으로, 안쪽 응답과 베이스를 피아노에 배치. 원래 음과 리듬을 보존."


def save_duet(source: Path, root: Path, feedback: str = "", interpretation: str | None = None,
              instrument: str = "violin", lead_octaves: int = 0):
    """Save a derivative as its own version; keep provenance back to the solo."""
    from musigen.versions import _versions
    from musigen.listen import build_page
    source, root = Path(source), Path(root)
    read = lambda name: json.loads((source / name).read_text(encoding="utf-8"))
    design, score = read("design.json"), read("score.json")
    piece = build(design, score)
    config = preset(instrument)
    violin, piano = parts(piece, instrument, lead_octaves)  # validate before creating a version directory
    if interpretation is None:
        interpretation = INTERPRETATION if instrument == "violin" and lead_octaves == 0 else (
            f"오른손 첫 성부를 {config['ko']}으로, 안쪽 응답과 베이스를 피아노에 배치. "
            f"선율 {lead_octaves:+d}옥타브 이동, 리듬·화성 보존.")
    versions = _versions(root)
    number = int(versions[-1].name[1:]) + 1 if versions else 1
    vdir = root / f"v{number:03d}"
    vdir.mkdir(parents=True, exist_ok=False)
    info = read("version.json")
    info.update(created=dt.datetime.now(dt.timezone.utc).isoformat(), version=vdir.name, parent=None, ensemble=instrument + "_piano", lead_instrument=instrument, lead_octaves=lead_octaves, joins=[], changed_bars=None,
                source={"piece":source.parent.name,"version":source.name},
                feedback=feedback,  # the request this duet answers, from the command line (not fixed in code)
                interpretation=interpretation,
                preserve_broken=[], preserve=["선율·리듬·화성·전체 길이" if not lead_octaves else "선율 음정·리듬·화성·전체 길이 (음역 이동)"],
                files={"musicxml":"piece.musicxml","midi":"piece.mid"})
    # The original design remains the shared compositional source; the version states instrumentation.
    result = read("checks.json")
    result["notes"].append("화성·동기·손별 검사는 원본 피아노 솔로 기준입니다.")
    result["notes"].append(f"전곡 {config['ko']}·피아노: 선율 {lead_octaves:+d}옥타브 이동 및 악기별 음역 확인. 운지·활 배분은 연주자 검수 전입니다.")
    result["duet"] = {"lead_notes":len(violin.notes),"piano_notes":len(piano.notes),"source":info["source"]}
    for name, value in (("design.json",design),("score.json",score),("version.json",info),("checks.json",result)):
        (vdir / name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    write_duet(piece,vdir / "piece.musicxml",subtitle=config["ko"] + " · 피아노 / " + vdir.name, instrument=instrument, lead_octaves=lead_octaves)
    if not write_midi(vdir / "piece.musicxml",vdir / "piece.mid"):
        info["files"]["midi"] = None
        (vdir / "version.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
    build_page([root],root / "listen.html")
    return info
