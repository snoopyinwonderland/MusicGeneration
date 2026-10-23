"""The composition design (작곡 설계): what the piece is to be, decided before any note is written.

It is shown to the user first (summary_ko) so the musical choices can be corrected before composing, and it is what
the checks hold the score to (musigen/checks.py).  Bars are 1-based and inclusive.

  {
    "title": "비 갠 밤",
    "request": "<the user's words, verbatim>",
    "given": ["basics.meter", "ending"],         # what the user asked for; everything else was chosen by the composer
    "impression": {"mood": "...", "scene": "...", "arc": "how the feeling changes"},
    "basics": {"length_sec": 60, "meter": "3/4", "tempo": 66, "key": "D", "mode": "minor", "grade": 6},
    "theme": {"idea": "the musical idea in words",
              "motifs": {"a": {"describe": "rising fourth, then a step", "hand": "rh"}}},
    "form": [{"label": "A", "bars": [1, 8], "function": "statement",
              "plan": "what happens and why", "motifs": ["a", "b"],
              "harmony": "...", "texture": "...", "register": "...", "dynamics": "p"}],
    "climax": {"bar": 14, "how": "..."},
    "ending": {"how": "..."}
  }

tempo counts the meter's beat (6/8: dotted quarters).  'given' entries are dotted paths; a path covers everything under
it ("form" marks all sections as the user's, "form.1" only the second).  The notes of each motif are in the score
(score.json), the design only describes them.
"""
from __future__ import annotations

from fractions import Fraction as F

FUNCTIONS = {"intro": "도입", "statement": "제시", "development": "발전", "contrast": "대조", "transition": "연결",
             "return": "재현", "coda": "종결"}
METERS = {"2/4", "3/4", "4/4", "6/8", "9/8", "12/8"}
TOP = {"title", "request", "given", "impression", "basics", "theme", "form", "climax", "ending", "notes"}


class DesignError(ValueError):
    pass


def bar_len(meter: str) -> F:
    n, d = (int(x) for x in meter.split("/"))
    return F(4 * n, d)


def beat(meter: str) -> F:
    n, d = (int(x) for x in meter.split("/"))
    return F(3, 2) if d == 8 and n % 3 == 0 and n > 3 else F(4, d)


def qpm(basics: dict) -> float:
    """Quarter notes per minute (tempo counts the meter's beat)."""
    return float(basics["tempo"] * beat(basics["meter"]))


def total_bars(d: dict) -> int:
    return d["form"][-1]["bars"][1]


def pickup(basics: dict) -> F:
    try:
        value = F(str(basics.get("pickup", 0)))
    except (ValueError, ZeroDivisionError):
        raise DesignError("여린내기 길이는 4분음표 단위 숫자나 분수여야 합니다") from None
    if not 0 <= value < bar_len(basics["meter"]):
        raise DesignError("여린내기 길이는 0 이상, 한 마디보다 짧아야 합니다")
    return value


def seconds(d: dict) -> float:
    b = d["basics"]
    return float(pickup(b) + total_bars(d) * bar_len(b["meter"])) * 60 / qpm(b)


def validate(d: dict) -> list[str]:
    """Raises DesignError on what the score cannot be built from; returns warnings (the design still works)."""
    extra = set(d) - TOP
    if extra:
        raise DesignError(f"unknown fields: {sorted(extra)}")
    b = d.get("basics") or {}
    for k in ("meter", "tempo", "key", "mode"):
        if k not in b:
            raise DesignError(f"basics.{k} missing")
    if b["meter"] not in METERS:
        raise DesignError(f"basics.meter one of {sorted(METERS)}")
    pickup(b)
    if b["mode"] not in ("major", "minor"):
        raise DesignError("basics.mode major | minor")
    if not b["key"] or b["key"][0] not in "ABCDEFG" or any(c not in "#b" for c in b["key"][1:]):
        raise DesignError(f"bad basics.key {b['key']!r}")
    if not 30 <= int(b["tempo"]) <= 240:
        raise DesignError("basics.tempo 30-240")
    if not 1 <= int(b.get("grade", 6)) <= 10:
        raise DesignError("basics.grade 1-10")
    form = d.get("form") or []
    if not form:
        raise DesignError("form is empty")
    nxt = 1
    for i, s in enumerate(form):
        a, z = s.get("bars", [0, 0])
        if a != nxt or z < a:
            raise DesignError(f"form[{i}] bars {s.get('bars')}: sections must follow each other from bar 1")
        if s.get("function") not in FUNCTIONS:
            raise DesignError(f"form[{i}].function one of {sorted(FUNCTIONS)}")
        if s.get("cadence", "none") not in ("authentic", "half", "plagal", "deceptive", "none"):
            raise DesignError(f"{a}–{z}마디: cadence는 authentic/half/plagal/deceptive/none 중 하나여야 합니다")
        nxt = z + 1
    motifs = (d.get("theme") or {}).get("motifs") or {}
    for i, s in enumerate(form):
        for m in s.get("motifs", []):
            if m not in motifs:
                raise DesignError(f"form[{i}] uses motif {m!r} not described in theme.motifs")
    warn = []
    c = (d.get("climax") or {}).get("bar")
    if c is not None and not 1 <= c <= total_bars(d):
        raise DesignError(f"climax.bar {c} outside 1-{total_bars(d)}")
    want = b.get("length_sec")
    if want and abs(seconds(d) - want) > 0.2 * want:
        warn.append(f"길이: {total_bars(d)}마디는 약 {seconds(d):.0f}초입니다(설계 {want}초).")
    for g in d.get("given", []):
        if _lookup(d, g) is _MISSING:
            raise DesignError(f"given path {g!r} not in the design")
    return warn


_MISSING = object()


def _lookup(d, path: str):
    cur = d
    for part in path.split("."):
        if isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def is_given(d: dict, path: str) -> bool:
    return any(path == g or path.startswith(g + ".") for g in d.get("given", []))


def _mark(d: dict, path: str) -> str:
    return "요청" if is_given(d, path) else "제안"


MODE_KO = {"major": "장조", "minor": "단조"}


def summary_ko(d: dict) -> str:
    """The design as the user reads it: every choice marked 요청 (the user's) or 제안 (the composer's)."""
    b = d["basics"]
    imp = d.get("impression") or {}
    th = d.get("theme") or {}
    lines = [f"# 작곡 설계: {d.get('title', '제목 없음')}", ""]
    if d.get("request"):
        lines += [f"> {d['request']}", ""]
    lines += ["표시: **요청** = 요청에서 정해진 것, **제안** = 작곡자가 고른 것.", "",
              "| 요소 | 내용 | 출처 |", "|---|---|---|"]
    row = lambda name, text, path: lines.append(f"| {name} | {text} | {_mark(d, path)} |")
    for k, name in (("mood", "정서"), ("scene", "장면"), ("arc", "변화")):
        if imp.get(k):
            row(name, imp[k], f"impression.{k}")
    row("박자", b["meter"], "basics.meter")
    if pickup(b):
        row("여린내기", f"0마디, {pickup(b)} (4분음표 단위)", "basics.pickup")
    row("빠르기", f"{b['tempo']} (박/분)", "basics.tempo")
    row("조성", f"{b['key']} {MODE_KO[b['mode']]}", "basics.key")
    row("길이", f"{total_bars(d)}마디, 약 {seconds(d):.0f}초", "basics.length_sec")
    row("난이도", f"{b.get('grade', 6)}급", "basics.grade")
    if th.get("idea"):
        row("주제", th["idea"], "theme.idea")
    for k, m in (th.get("motifs") or {}).items():
        row(f"동기 {k}", f"{m.get('describe', '')} ({m.get('hand', 'rh')})", f"theme.motifs.{k}")
    lines += ["", "## 형식", "", "| 구간 | 마디 | 역할 | 계획 | 동기 | 화성 | 반주 | 음역 | 셈여림 | 출처 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(d["form"]):
        a, z = s["bars"]
        lines.append(f"| {s.get('label', '')} | {a}–{z} | {FUNCTIONS[s['function']]} | {s.get('plan', '')} | "
                     f"{', '.join(s.get('motifs', []))} | {s.get('harmony', '')} | {s.get('texture', '')} | "
                     f"{s.get('register', '')} | {s.get('dynamics', '')} | {_mark(d, f'form.{i}')} |")
    lines.append("")
    if d.get("climax"):
        c = d["climax"]
        lines.append(f"- **절정** ({_mark(d, 'climax')}): {c.get('bar', '')}마디. {c.get('how', '')}")
    if d.get("ending"):
        lines.append(f"- **끝맺음** ({_mark(d, 'ending')}): {d['ending'].get('how', '')}")
    if d.get("notes"):
        lines.append(f"- **메모**: {d['notes']}")
    return "\n".join(lines) + "\n"
