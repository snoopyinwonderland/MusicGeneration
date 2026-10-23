"""Automatic checks of a built piece - what a program can judge; whether the music convinces is for the listener.

  playing   per hand: simultaneous notes and span against the grade profile (musicomp.realize.grades), range,
            hands crossing, the shortest left-hand value
  design    bar count, length in seconds, the climax bar (highest right-hand note), the declared motifs present in
            each section, the opening motif back in a 'return' section, the ending (tonic bass, tonic-triad top)
  theme     where each motif is used and how it was changed (the provenance of every note)

Messages are Korean (the user reads them); 'errors' mean the score is not playable as written at the design's grade,
'warnings' that it departs from the design.
"""
from __future__ import annotations

from collections import defaultdict

from musicomp.realize.grades import profile

from musigen.design import FUNCTIONS, seconds as design_seconds
from musigen.piece import Piece

RANGE = {"rh": (53, 100), "lh": (24, 69)}  # F3-E7, C1-A4: outside is possible but rare in a lyrical piece
NAMES = "C C# D Eb E F F# G Ab A Bb B".split()


def name(m: int) -> str:
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def motif_of(src: str) -> str | None:
    """'copy:1-4<a|at:C5' -> 'a'; 'lit', 'rest', 'broken(Dm)' -> None."""
    core = src.rsplit("<", 1)[-1]
    head = core.split("|", 1)[0]
    return head if head and head.isidentifier() and head not in ("lit", "rest") else None


def check(piece: Piece, design: dict) -> dict:
    prof = profile(int(design["basics"].get("grade", 6))) or {}
    errors: list[str] = []
    warnings: list[str] = []
    # -- playing -----------------------------------------------------------------------------------------------
    for hand in ("rh", "lh"):
        lo, hi = RANGE[hand]
        attacks = defaultdict(set)
        for n in piece.notes:
            if n.hand == hand:
                attacks[n.onset].update(m for m, _ in n.pitches)
        for on, ps in sorted(attacks.items()):
            bar = piece.bar_of(on)
            span, cnt = max(ps) - min(ps), len(ps)
            if prof and span > prof[f"span_{hand}"]:
                errors.append(f"{bar}마디 {_hand(hand)}: 동시음 폭 {span}반음({name(min(ps))}–{name(max(ps))}), "
                              f"{prof['grade']}급 한도 {prof[f'span_{hand}']}")
            if prof and cnt > prof[f"notes_{hand}"]:
                errors.append(f"{bar}마디 {_hand(hand)}: 동시음 {cnt}개, {prof['grade']}급 한도 {prof[f'notes_{hand}']}")
            out = [m for m in ps if not lo <= m <= hi]
            if out:
                warnings.append(f"{bar}마디 {_hand(hand)}: 음역 밖 {', '.join(name(m) for m in sorted(out))}")
    if prof:
        short = [n for n in piece.notes if n.hand == "lh" and n.dur < prof["min_dur_lh"]]
        if short:
            warnings.append(f"왼손 최소 음가보다 짧은 음 {len(short)}개(첫 위치 {piece.bar_of(short[0].onset)}마디)")
    crossings = sorted({piece.bar_of(n.onset) for n in piece.notes if n.hand == "rh" for l in piece.notes
                        if l.hand == "lh" and l.onset < n.onset + n.dur and n.onset < l.onset + l.dur
                        and min(m for m, _ in n.pitches) < max(m for m, _ in l.pitches)})
    if crossings:
        warnings.append(f"오른손이 왼손보다 낮아지는 마디: {_ranges(crossings)}")
    # -- design ------------------------------------------------------------------------------------------------
    want = design["basics"].get("length_sec")
    secs = design_seconds(design)
    if want and abs(secs - want) > 0.2 * want:
        warnings.append(f"길이 약 {secs:.0f}초(설계 {want}초)")
    rh = [n for n in piece.notes if n.hand == "rh"]
    climax = None
    if rh:
        top = max(max(m for m, _ in n.pitches) for n in rh)
        climax_bars = sorted({piece.bar_of(n.onset) for n in rh if max(m for m, _ in n.pitches) == top})
        climax = {"pitch": name(top), "bars": climax_bars}
        want_c = (design.get("climax") or {}).get("bar")
        if want_c and not any(abs(b - want_c) <= 1 for b in climax_bars):
            warnings.append(f"가장 높은 음 {name(top)}이 {_ranges(climax_bars)}마디에 있습니다(설계 절정 {want_c}마디).")
        elif want_c and len(climax_bars) > 1 and any(abs(b - want_c) > 1 for b in climax_bars):
            warnings.append(f"가장 높은 음 {name(top)}이 절정 밖({_ranges(climax_bars)}마디)에도 나옵니다.")
    usage: dict[str, list[dict]] = defaultdict(list)
    for n in piece.notes:
        mid = motif_of(n.src)
        if mid:
            bar = piece.bar_of(n.onset)
            row = {"bar": bar, "hand": n.hand, "how": n.src}
            if not usage[mid] or usage[mid][-1]["bar"] != bar or usage[mid][-1]["how"] != n.src:
                usage[mid].append(row)
    sections = []
    for i, s in enumerate(design["form"]):
        a, z = s["bars"]
        here = {m for m, rows in usage.items() for r in rows if a <= r["bar"] <= z}
        missing = [m for m in s.get("motifs", []) if m not in here]
        if missing:
            warnings.append(f"{s.get('label', i)}({a}–{z}마디, {FUNCTIONS[s['function']]}): 설계한 동기 "
                            f"{', '.join(missing)}가 쓰이지 않았습니다.")
        sections.append({"label": s.get("label"), "bars": [a, z], "function": s["function"], "motifs_used": sorted(here),
                         "motif_bars": len({r["bar"] for m in here for r in usage[m] if a <= r["bar"] <= z}),
                         "bars_total": z - a + 1})
    first = (design["form"][0].get("motifs") or [None])[0]
    for s, row in zip(design["form"], sections):
        if s["function"] == "return" and first and first not in row["motifs_used"]:
            warnings.append(f"재현 구간 {s['bars'][0]}–{s['bars'][1]}마디에 첫 동기 {first}가 없습니다.")
    last_bar = piece.in_bars(piece.bars, piece.bars)
    tonic = piece.key.tonic_pc
    lh_last = [n for n in last_bar if n.hand == "lh"]
    rh_last = [n for n in last_bar if n.hand == "rh"]
    if lh_last and min(m for m, _ in lh_last[-1].pitches) % 12 != tonic:
        warnings.append("마지막 마디 왼손 베이스가 으뜸음이 아닙니다.")
    if rh_last and (max(m for m, _ in rh_last[-1].pitches) - tonic) % 12 not in (0, 3, 4, 7):
        warnings.append("마지막 오른손 윗음이 으뜸화음 음이 아닙니다.")
    from musigen.theme_metrics import measure
    recognition = measure(piece, design)
    notes = [f"{r['bar']}마디 {_hand(r['hand'])}: 동기 {r['motif']} 점수 {r['score']:.2f}, 알아듣기 어려울 수 있음(잠정)"
             for r in recognition["occurrences"] if r["score"] is not None and r["score"] < .5]
    from musigen.musical_checks import evaluate
    musical = evaluate(piece, design)
    warnings += musical["warnings"]
    notes += musical["notes"]
    phrase_report = None
    if design.get("analysis", {}).get("phrases"):
        from musigen.phrases import analyze
        try:
            phrase_report = analyze(piece, design.get("phrase_plan", []))
        except ValueError as exc:
            phrase_report = {"status":"미평가", "reason":str(exc), "phrases":[], "rests":[], "plan":[]}
    return {"phrasing": phrase_report, "errors": errors, "warnings": warnings, "notes": notes, "recognition": recognition, "musical": musical,
            "stats": {"bars": piece.bars, "seconds": round(secs, 2), "notes_rh": len(rh),
                      "notes_lh": sum(1 for n in piece.notes if n.hand == "lh"), "climax": climax},
            "sections": sections, "motifs": dict(usage)}


def _hand(h: str) -> str:
    return "오른손" if h == "rh" else "왼손"


def _ranges(bars: list[int]) -> str:
    out, start = [], None
    for i, b in enumerate(bars):
        if start is None:
            start = b
        if i + 1 == len(bars) or bars[i + 1] != b + 1:
            out.append(str(start) if start == b else f"{start}–{b}")
            start = None
    return ", ".join(out)


def summary_ko(result: dict) -> str:
    s = result["stats"]
    lines = [f"- 길이 {s['bars']}마디, 약 {s['seconds']:.0f}초. 오른손 {s['notes_rh']}음, 왼손 {s['notes_lh']}음."]
    if s.get("climax"):
        lines.append(f"- 가장 높은 음: {s['climax']['pitch']} ({_ranges(s['climax']['bars'])}마디)")
    for sec in result["sections"]:
        lines.append(f"- {sec['label']} {sec['bars'][0]}–{sec['bars'][1]}마디({FUNCTIONS[sec['function']]}): 동기 "
                     f"{', '.join(sec['motifs_used']) or '없음'}, 동기가 나오는 마디 {sec['motif_bars']}/{sec['bars_total']}")
    for e in result["errors"]:
        lines.append(f"- 오류: {e}")
    for w in result["warnings"]:
        lines.append(f"- 주의: {w}")
    for n in result.get("notes", []):
        lines.append(f"- 참고: {n}")
    if not result["errors"] and not result["warnings"]:
        lines.append("- 자동 검사에서 걸린 것이 없습니다.")
    return "\n".join(lines) + "\n"
