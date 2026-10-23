"""Versions of a piece: every build is kept, with what changed, why, and whether what was to be kept stayed.

  output/<piece>/v001/  design.json  score.json  piece.musicxml  piece.mid  checks.json  bars.json  version.json
  output/<piece>/v002/  ...
  output/<piece>/history.md   one entry per version (Korean, for the user)
  output/<piece>/listen.html  every version drawn and playable in the browser (musigen/listen.py)

version.json: {"version", "parent", "created", "reason", "preserve", "changed_bars": {"rh": [...], "lh": [...]},
               "design_changes": [...], "preserve_broken": [...]}
'reason' is the request the version answers ("17마디부터 더 고조", the listener's words); 'preserve' lists what it
promised to keep:  bars:1-8 (every note), rh:1-8 / lh:1-8 (one hand), motif:a (the motif's notes).
changed_bars compares each bar's notes with the parent version, so the user knows where to listen.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from musigen import checks as checks_mod
from musigen.design import summary_ko as design_summary, total_bars
from musigen.piano_io import write_midi, write_musicxml
from musigen.piece import Piece, build


def bar_signature(piece: Piece) -> dict[str, dict[str, list]]:
    """{hand: {bar: [[offset, dur, [midi...]], ...]}} - what is compared between versions."""
    out: dict[str, dict[str, list]] = {"rh": {}, "lh": {}}
    for n in piece.notes:
        bar = piece.bar_of(n.onset)
        off = n.onset - piece.bar_start(bar)
        out[n.hand].setdefault(str(bar), []).append([str(off), str(n.dur), [m for m, _ in n.pitches]])
    for h in out.values():
        for v in h.values():
            v.sort()
    return out


def _changed(old: dict, new: dict, bars: int) -> dict[str, list[int]]:
    return {h: [b for b in range(0 if any("0" in s.get(h, {}) for s in (old,new) for h in ("rh","lh")) else 1, bars + 1) if old.get(h, {}).get(str(b)) != new.get(h, {}).get(str(b))]
            for h in ("rh", "lh")}


def _design_changes(old: dict, new: dict) -> list[str]:
    out = [k for k in sorted(set(old) | set(new)) if k != "form" and old.get(k) != new.get(k)]
    fo, fn = old.get("form", []), new.get("form", [])
    for i in range(max(len(fo), len(fn))):
        if (fo[i] if i < len(fo) else None) != (fn[i] if i < len(fn) else None):
            out.append(f"form.{i}")
    return out


def _versions(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("v[0-9][0-9][0-9]") if p.is_dir())


def _preserve_broken(preserve: list[str], old_sig: dict, new_sig: dict, old_score: dict, new_score: dict) -> list[str]:
    broken = []
    for item in preserve:
        kind, _, arg = item.partition(":")
        if kind in ("bars", "rh", "lh"):
            m = re.fullmatch(r"(\d+)(?:-(\d+))?", arg)
            if not m:
                broken.append(f"{item}: 형식은 bars:1-8")
                continue
            a, z = int(m.group(1)), int(m.group(2) or m.group(1))
            hands = ("rh", "lh") if kind == "bars" else (kind,)
            bad = [b for h in hands for b in range(a, z + 1) if old_sig[h].get(str(b)) != new_sig[h].get(str(b))]
            if bad:
                broken.append(f"{item}: {', '.join(str(b) for b in sorted(set(bad)))}마디가 바뀌었습니다")
        elif kind == "motif":
            if (old_score.get("motifs") or {}).get(arg) != (new_score.get("motifs") or {}).get(arg):
                broken.append(f"{item}: 동기의 음이 바뀌었습니다")
        else:
            broken.append(f"{item}: 알 수 없는 보존 항목(bars: / rh: / lh: / motif:)")
    return broken


def save(root: Path, design: dict, score: dict, reason: str = "", preserve: list[str] | None = None) -> dict:
    """Build the piece, run the checks, write the next version folder and the history entry; returns version.json."""
    root = Path(root)
    piece = build(design, score)
    result = checks_mod.check(piece, design)
    prev = _versions(root)
    num = int(prev[-1].name[1:]) + 1 if prev else 1
    vdir = root / f"v{num:03d}"
    vdir.mkdir(parents=True, exist_ok=False)
    dump = lambda name, obj: (vdir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    dump("design.json", design)
    dump("score.json", score)
    xml = write_musicxml(piece, vdir / "piece.musicxml", subtitle=f"v{num:03d}")
    midi = write_midi(xml, vdir / "piece.mid")
    dump("checks.json", result)
    sig = bar_signature(piece)
    dump("bars.json", sig)
    (vdir / "design.md").write_text(design_summary(design), encoding="utf-8")
    info = {"version": f"v{num:03d}", "parent": prev[-1].name if prev else None,
            "created": dt.datetime.now().isoformat(timespec="seconds"), "reason": reason,
            "preserve": preserve or [], "changed_bars": None, "design_changes": [], "preserve_broken": [],
            "files": {"musicxml": xml.name, "midi": midi.name if midi else None}}
    if prev:
        p = prev[-1]
        old_sig = json.loads((p / "bars.json").read_text(encoding="utf-8"))
        old_design = json.loads((p / "design.json").read_text(encoding="utf-8"))
        old_score = json.loads((p / "score.json").read_text(encoding="utf-8"))
        info["changed_bars"] = _changed(old_sig, sig, max(piece.bars, total_bars(old_design)))
        info["design_changes"] = _design_changes(old_design, design)
        info["preserve_broken"] = _preserve_broken(preserve or [], old_sig, sig, old_score, score)
    dump("version.json", info)
    _history(root, info, result)
    from musigen.listen import build_page
    build_page([root], root / "listen.html")
    return info


def _history(root: Path, info: dict, result: dict) -> None:
    lines = [f"## {info['version']} ({info['created'][:16].replace('T', ' ')})", ""]
    if info["reason"]:
        lines.append(f"- 요청: {info['reason']}")
    if info["parent"]:
        ch = info["changed_bars"]
        both = sorted(set(ch["rh"]) | set(ch["lh"]))
        lines.append(f"- {info['parent']}에서 바뀐 마디: 오른손 {checks_mod._ranges(ch['rh']) or '없음'}, "
                     f"왼손 {checks_mod._ranges(ch['lh']) or '없음'}" + (f" (들어 볼 곳: {checks_mod._ranges(both)}마디)" if both else ""))
        if info["design_changes"]:
            lines.append(f"- 설계에서 바뀐 항목: {', '.join(info['design_changes'])}")
    if info["preserve"]:
        lines.append(f"- 보존 약속: {', '.join(info['preserve'])} → "
                     + ("지켜졌습니다" if not info["preserve_broken"] else "; ".join(info["preserve_broken"])))
    lines.append(checks_mod.summary_ko(result).rstrip())
    path = root / "history.md"
    head = "" if path.exists() else "# 버전 기록\n\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(head + "\n".join(lines) + "\n\n")
