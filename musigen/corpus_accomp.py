"""Opt-in corpus accompaniment for authored piano pieces; no harmony/key inference.

The arranger's LH figures and existing pacing model are reused unchanged. Authored
RH (both voices), written LH, silence, harmony and expression are composition decisions.
A materialized snapshot makes subsequent builds independent of the corpus/selector.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, replace
from fractions import Fraction as F
from pathlib import Path

from musigen.piece import Note, ScoreError

FIELD = "corpus_accompaniment"


def fingerprint(design, score):
    base = {k: v for k, v in score.items() if k != FIELD}
    raw = json.dumps([design, base], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _pack(n):
    return {**asdict(n), "onset": str(n.onset), "dur": str(n.dur)}


def apply_snapshot(piece, design, score):
    data = score[FIELD]
    if data.get("version") != 1 or data.get("input_sha256") != fingerprint(design, score):
        raise ScoreError("자료 반주의 입력이 바뀌었습니다. --corpus-accompaniment로 다시 선택하거나 corpus_accompaniment를 삭제하세요")
    notes = []
    for row in data["notes"]:
        n = Note(**{**row, "onset": F(row["onset"]), "dur": F(row["dur"]),
                    "pitches": tuple(tuple(p) for p in row["pitches"])})
        if (n.hand != "lh" or n.voice not in (1, 2) or n.onset < 0 or n.dur <= 0
                or n.onset + n.dur > piece.bar_end(piece.bars) or not n.pitches
                or any(type(m) is not int or type(t) is not int or not 0 <= m <= 127
                       or (7*t-m) % 12 for m, t in n.pitches)):
            raise ScoreError("자료 반주 스냅샷의 왼손 음표가 유효하지 않습니다")
        notes.append(n)
    piece.notes = sorted([n for n in piece.notes if n.hand == "rh"] + notes,
                         key=lambda n: (n.onset, n.voice))


def semantic(piece, design):
    """Adapt declared keys/chords/sections; analysis observes motifs and cadences only."""
    from musigen.phrases import melody
    from musicomp.analysis.key import KeyEstimate, KeyRegion
    from musicomp.analysis.harmony import ChordSpan, roman_for, harmonic_function
    from musicomp.analysis.motif import analyze_motifs
    from musicomp.analysis.phrase import Phrase, segment_layers
    from musicomp.analysis.form import analyze_form
    from musicomp.semantic import SemanticMap
    from musicomp.plan import make_plan

    mel = melody(piece)  # Deliberately requires a monophonic RH1, never extracts a new tune.
    if not mel.notes:
        raise ScoreError("자료 반주에는 오른손 첫 성부의 선율이 필요합니다")
    regions = [KeyRegion(m.start, m.end, piece.bar_keys.get(int(m.number), piece.key), 1.0,
                         {"source": "authored", "not_estimated": True}) for m in mel.measures]
    keys = KeyEstimate(regions)
    # analysis_chords keeps harmony even when its display is off, including unknown spans.
    changes = {}
    for on, ch in piece.analysis_chords:
        if on in changes and changes[on] != ch:
            raise ScoreError(f"{piece.bar_of(on)}마디: 같은 시점의 화음 계획이 서로 다릅니다")
        changes[on] = ch
    changes.setdefault(F(0), None)
    # Split at key changes as well as harmony changes; carry the written chord, not its RN.
    times = sorted(set(changes) | {r.start for r in regions} | {mel.total})
    chords, ch = [], None
    for start, end in zip(times, times[1:]):
        ch = changes.get(start, ch)
        if ch is None:
            continue
        key = keys.key_at(start)
        root = key.rel_fifths(ch.root_tpc)
        quality = {"7sus4": "7sus4", "m6": "m6", "add9": "Madd9", "madd9": "madd9"}.get(ch.quality, ch.kind)
        token = roman_for(root, quality, key)
        chords.append(ChordSpan(start, end, token, harmonic_function(token), root,
                                [key.rel_fifths(t) for _, t in ch.tones], "given", None, None,
                                [f"authored {ch.symbol}"], key.rel_fifths(ch.bass_tpc), key=key))
    motifs = analyze_motifs(mel, cross_check=False)
    observed, gaps = segment_layers(mel, keys, motifs)
    by_bar = {int(m.number): m.index for m in mel.measures}
    cuts = {0, len(mel.measures)}
    planned = design.get("phrase_plan", [])
    if planned:
        for row in planned:
            a, z = row["bars"]
            cuts.update((by_bar[a], by_bar[z] + 1))
    else:
        cuts.update(p.first_bar for p in observed)
        cuts.update(p.last_bar + 1 for p in observed)
    for sec in design["form"]:
        a, z = sec["bars"]
        cuts.update((by_bar[a], by_bar[z] + 1))
    # Pickup belongs to the opening phrase; it remains ineligible for replacement.
    if piece.pickup:
        cuts.discard(1)
    phrases = []
    for a, z in zip(sorted(cuts), sorted(cuts)[1:]):
        lo, hi = mel.measures[a].start, mel.measures[z-1].end
        ns = [i for i, n in enumerate(mel.notes) if n.onset < hi and n.end > lo]
        if not ns:
            raise ScoreError("전체가 쉼인 프레이즈는 현재 자료 반주 대상이 아닙니다")
        subs = [(x, y) for p in observed for x, y in p.subphrases if ns[0] <= x <= y <= ns[-1]]
        phrases.append(Phrase(f"P{len(phrases)+1}", ns[0], ns[-1], lo, hi, a, z-1, subs,
                              {"source": "phrase_plan+form" if planned else "melody_analysis+form"}))
    form = analyze_form(mel, keys, phrases, motifs, chords)
    # Keep observed cadence/tension; author owns section boundaries and climax.
    form.sections = []
    for j, sec in enumerate(design["form"]):
        label = sec["label"]
        ids = []
        for p, info in zip(phrases, form.phrases):
            bar = max(1, int(mel.measures[p.first_bar].number))
            if sec["bars"][0] <= bar <= sec["bars"][1]:
                ids.append(p.id)
                info.section, info.label = f"{label}:{j+1}", label
        letter = label.rstrip("'′")
        form.sections.append({"name": f"{label}:{j+1}", "letter": letter,
                              "occurrence": 1 + sum(s["letter"] == letter for s in form.sections), "phrases": ids})
    climax = design.get("climax", {}).get("bar")
    form.climax_bar = by_bar.get(climax)
    sm = SemanticMap(mel, keys, motifs, phrases, gaps, chords, [], "given", form,
                     {"source": "authored piano composition; no key/harmony inference"})
    return sm, make_plan(sm)


def _protected(piece, bar):
    """Only explicitly generated LH figures are replaceable; preserve authored material."""
    from musigen.accomp import PATTERNS
    lo, hi = piece.bar_start(bar), piece.bar_end(bar)
    ns = [n for n in piece.notes if n.hand == "lh" and n.onset < hi and n.onset+n.dur > lo]
    if bar == 0 or not ns:
        return "못갖춘마디 또는 의도한 왼손 쉼"
    if any(n.onset < lo or n.onset+n.dur > hi for n in ns):
        return "마디를 가로지르는 왼손 지속음 보존"
    if any(n.voice != 1 or not any(n.src.rsplit("<", 1)[-1].startswith(f"{p}(") for p in PATTERNS) for n in ns):
        return "직접 쓴 왼손 선율·화음·둘째 성부 보존"
    return None


def _reject(notes, piece, bar, prof):
    if not notes:
        return "실현된 반주가 없음"
    lo, hi = piece.bar_start(bar), piece.bar_end(bar)
    ns = sorted(notes, key=lambda n: n.onset)
    if any(n.onset < lo or n.onset+n.dur > hi or n.dur <= 0 for n in ns):
        return "반주가 마디 범위를 벗어남"
    if any(a.onset+a.dur > b.onset for a, b in zip(ns, ns[1:])):
        return "한 성부에서 음의 길이가 겹침"
    for n in ns:
        ps = [m for m, _ in n.pitches]
        if not ps or min(ps) < 28 or max(ps) > 69:
            return "왼손 음역 범위 초과"
        if prof and (max(ps)-min(ps) > prof["span_lh"] or len(ps) > prof["notes_lh"] or n.dur < prof["min_dur_lh"]):
            return "설계한 난이도의 손 벌림·동시음·최소 음가 초과"
        rh = [r for r in piece.notes if r.hand == "rh" and r.onset < n.onset+n.dur and r.onset+r.dur > n.onset]
        if any(max(ps) >= min(m for m, _ in r.pitches) for r in rh):
            return "보존한 오른손 성부와 교차 또는 겹침"
    return None


class PlannedFigures:
    """Reuse musicomp's figure classifier for both authored and candidate LH.

    User feedback: accompaniment patterns and sectional contrast should matter.
    This is a hard composition constraint, not a newly tuned retrieval coefficient.
    If no compatible source exists, keep the written accompaniment.
    """
    neutral = False

    def __init__(self, piece, sm, index):
        self.index = index
        self.figures = {}
        for m in sm.melody.measures:
            bar = int(m.number)
            if _protected(piece, bar):
                continue
            row = {"meter": piece.meter, "bar_len": str(m.length), "lh": [
                {"on": str(n.onset-m.start), "dur": str(n.dur),
                 "notes": [{"midi": pitch} for pitch, _ in n.pitches]}
                for n in piece.in_bars(bar, bar, "lh")]}
            self.figures[m.index] = index.figure(row)

    def prepare(self, sm, bars):
        pass

    def allows(self, index, source):
        return index not in self.figures or self.index.figure(source) == self.figures[index]

    def base_cost(self, target, source, index):
        from musicomp.realize.retrieval import bar_cost
        return bar_cost(target, source, index)

    def cost(self, target, source):
        return 0.0, []


def select(design, score):
    """Return a new score containing frozen LH notes and auditable per-bar decisions."""
    from musigen.piece import build
    from musicomp.realize import retrieval, pacing, role_retrieval, transition_retrieval
    from musicomp.realize.grades import profile
    from musicomp.realize.voicing import clean_left_hand, inversion_bass, chord_bass
    from musicomp.analysis.meter import beat_unit
    from musicomp.theory import spell

    # Experimental selectors are deliberately outside this first adoption package.
    if (role_retrieval.enabled() or transition_retrieval.enabled() or retrieval.SEGMENT_COST
            or retrieval.PEDAL_BROKEN or retrieval.THIN_COST or retrieval.REUSE_COST):
        raise ScoreError("실험용 musicomp 검색 옵션을 끈 기본 환경에서 자료 반주를 생성하세요")
    base = copy.deepcopy(score)
    base.pop(FIELD, None)
    piece = build(design, base)
    sm, plan = semantic(piece, design)
    index = retrieval.load_index()
    if not index.size:
        raise ScoreError("피아노 반주 라이브러리가 없습니다. musicomp의 기존 학습용 patterns/bars.jsonl을 준비하세요")
    excluded = {piece.title}
    for motif in base.get("motifs", {}).values():
        if isinstance(motif, dict) and motif.get("format") == "musicanote-motif":
            name = motif.get("source", {}).get("file")
            if name:
                # A MusicXML filename may have both .musicxml and .xml suffixes.
                while Path(name).suffix.lower() in (".xml", ".musicxml", ".mxl"):
                    name = str(Path(name).with_suffix(""))
                excluded.add(name)
    grade = int(design["basics"].get("grade", 6))
    figures = PlannedFigures(piece, sm, index)
    choices = retrieval.choose(sm, plan, pacing=True, grade=grade, exclude=excluded,
                               alternate_selection=figures)
    # Never realise partially known harmony: target_chord would extend the last known slot.
    valid, protected = [], {}
    for c in choices:
        t = c.bar
        cover = sum((x["end"]-x["on"] for x in t.chords), F(0))
        bar = int(sm.melody.measures[t.index].number)
        protected[t.index] = _protected(piece, bar)
        if protected[t.index] is None and cover != t.length:
            protected[t.index] = "화성 계획이 마디 전체에 주어지지 않음"
        valid.append(replace(c, source=None) if protected[t.index] else c)
    lh, _, _ = retrieval.realise(sm, valid)
    inversion_bass(lh, sm.chords, sm.key, spell)
    chord_bass(lh, sm.chords, sm.key, spell, beat_unit(sm.melody))
    lh, cleanup = clean_left_hand(lh)
    prof = profile(grade)
    rows, replacements = [], {}
    for c in choices:
        bar = int(sm.melody.measures[c.bar.index].number)
        candidate = [n for n in lh if c.bar.start <= n.onset < c.bar.start+c.bar.length]
        reason = protected[c.bar.index]
        if reason is None and c.source is None:
            reason = "같은 반주 유형·박자·화성 변화 위치의 자료가 없음"
        if reason is None:
            reason = _reject(candidate, piece, bar, prof)
        source = c.source
        applied = reason is None
        if applied:
            replacements[bar] = [Note(n.onset, n.dur, tuple(n.pitches), "lh", 1,
                                     f"corpus:{source['song']}:{source['bar']+1}") for n in candidate]
        rows.append({"bar": bar, "status": "corpus" if applied else "kept", "reason": reason,
                     "source_song": source["song"] if source else None,
                     "source_bar": source["bar"]+1 if source else None,
                     "planned_figure": figures.figures.get(c.bar.index),
                     "source_figure": index.figure(source) if source else None,
                     "density_target": round(c.bar.intensity, 4),
                     "cost": round(c.cost, 4) if source else None, "selection_reasons": c.reasons})
    notes = [n for n in piece.notes if n.hand == "lh" and piece.bar_of(n.onset) not in replacements]
    notes += [n for group in replacements.values() for n in group]
    notes.sort(key=lambda n: (n.onset, n.voice))
    model = pacing.load_model()
    report = {"status": "실험 옵션 · 청취 검수 전", "engine": "musicomp.realize.retrieval + pacing",
              "scope": "계획한 반주 유형 안에서 왼손 패턴 변경 · 오른손 전체와 직접 쓴 왼손 보존",
              "engine_sha256": {"retrieval": _file_hash(retrieval.__file__), "pacing": _file_hash(pacing.__file__)},
              "library": {"path": str(index.path), "sha256": _file_hash(index.path),
                          "indexed_rows": index.size, "songs": len(index.by_song)},
              "pacing_model": {"used": bool(model), "trained_on": model.get("trained_on") if model else None, "sha256": _file_hash(pacing.MODEL) if model else None},
              "excluded_titles": sorted(excluded), "grade": grade, "cleanup": cleanup,
              "applied_bars": sorted(replacements), "bars": rows,
              "phrases": [{"bars": [int(sm.melody.measures[p.first_bar].number), int(sm.melody.measures[p.last_bar].number)],
                           "section": i.section, "cadence_observation": i.cadence.type} for p, i in zip(sm.phrases, sm.form.phrases)]}
    base[FIELD] = {"version": 1, "input_sha256": fingerprint(design, base),
                   "notes": [_pack(n) for n in notes], "report": report}
    return base
