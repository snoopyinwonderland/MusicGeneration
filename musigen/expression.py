"""ROUND1 P1: explicit performance instructions in quarter positions, never XML postprocessing."""
from fractions import Fraction as F
from math import isfinite
from musigen.piece import ScoreError, _bars

def compile_expression(piece, rows):
    result, occupied, hairpins = [], set(), []
    for row in rows:
        a, z = ((0, 0) if piece.pickup and str(row.get("bars")) == "0"
                else _bars(row.get("bars"), piece.bars))
        start, end = piece.bar_start(a), piece.bar_end(z)
        if row.get("pedal"):
            mode = row["pedal"]
            if mode not in ("bar", "half", "chord", "held"):
                raise ScoreError("페달은 bar/half/chord/held 중 하나여야 합니다")
            bars = set(range(a,z+1))
            if occupied & bars:
                raise ScoreError("같은 마디에 페달 지시가 겹칩니다")
            occupied |= bars
            changes = []
            if mode in ("bar", "half"):
                for b in range(a,z+1):
                    lo, hi = piece.bar_start(b), piece.bar_end(b)
                    changes.append(lo)
                    # ROUND1: odd simple meters (3/4) refresh once per bar.
                    if mode == "half" and b != 0 and piece.meter != "3/4":
                        changes.append((lo+hi)/2)
            elif mode == "chord":
                prev = None
                for on, ch in piece.chords:
                    if ch.symbol != prev and start < on < end:
                        changes.append(on)
                    prev = ch.symbol
            release = F(str(row.get("release", 0)))
            if release < 0 or release >= end - start:
                raise ScoreError("페달을 미리 떼는 길이는 0 이상, 구간보다 짧아야 합니다")
            pedal_end = end - release
            result.append({"kind": "pedal", "start": start, "end": pedal_end,
                           "changes": sorted(set(t for t in changes if start < t < pedal_end)), "mode": mode})
        if row.get("hairpin"):
            kind = row["hairpin"]
            if kind not in ("cresc", "dim"):
                raise ScoreError("셈여림 증감은 cresc/dim 중 하나여야 합니다")
            end = min([end] + [on for on, _, dyn in piece.directions if dyn and start < on <= end])
            if any(start < hi and lo < end for lo, hi in hairpins):
                raise ScoreError("셈여림 증감 구간이 겹칩니다")
            hairpins.append((start,end))
            result.append({"kind": "hairpin", "start": start, "end": end, "mode": kind})
    return result


def compile_balance(piece, rows):
    """Opt-in playback gains; score notes, dynamics and pedal remain unchanged.

    Motivation: listener-requested melody/accompaniment balance (2026-11-11).
    Values are authored preview gain multipliers, not measured piano dynamics.
    """
    if not isinstance(rows, list):
        raise ScoreError("재생 음량 계획은 마디 구간 목록이어야 합니다")
    result = []
    for row in rows:
        if (not isinstance(row, dict) or 'bars' not in row or
                set(row)-{'bars', 'rh', 'lh', 'reduce_lh_chords'}):
            raise ScoreError("재생 음량 계획의 필드를 확인하세요")
        a, z = ((0, 0) if piece.pickup and str(row['bars']) == '0'
                else _bars(row['bars'], piece.bars))
        start, end = piece.bar_start(a), piece.bar_end(z)
        if any(start < r['end'] and r['start'] < end for r in result):
            raise ScoreError("재생 음량 계획의 마디 구간이 겹칩니다")
        gains = {hand: row.get(hand, 1.0) for hand in ('rh', 'lh')}
        if any(type(v) not in (int, float) or not isfinite(v) or not 0 <= v <= 2 for v in gains.values()):
            raise ScoreError("재생 음량 배수는 0–2의 유한한 숫자여야 합니다")
        reduce = row.get('reduce_lh_chords', False)
        if type(reduce) is not bool:
            raise ScoreError("왼손 동시 발음 완화는 참/거짓이어야 합니다")
        result.append({'start': start, 'end': end, **gains, 'reduce_lh_chords': reduce})
    return sorted(result, key=lambda r: r['start'])

# Provisional playback multipliers required by ROUND1 P1; no claim of acoustic calibration.
LEVELS = {"ppp": .25, "pp": .35, "p": .5, "mp": .65, "mf": .8, "f": .95, "ff": 1.1, "fff": 1.25,
          "sf": .95, "sfz": .95, "fp": .5}
def playback(piece):
    dynamics = [{"q": float(on), "level": LEVELS.get(dyn,.8), "name": dyn}
                for on, _, dyn in piece.directions if dyn]
    result = {"dynamics": dynamics,
            "expression": [{k: ([float(t) for t in v] if k == "changes" else float(v) if isinstance(v,F) else v)
                            for k,v in r.items()} for r in piece.expression],
            "articulations": [{"q": float(n.onset), "pitches": [m for m,_ in n.pitches],
                              "hand": n.hand, "art": n.art} for n in piece.notes if n.art],
            "bars": [{"bar": b, "start": float(piece.bar_start(b)), "end": float(piece.bar_end(b))}
                     for b in range(0 if piece.pickup else 1, piece.bars+1)]}
    if piece.playback_balance:
        result['balance'] = [{**r, 'start': float(r['start']), 'end': float(r['end'])}
                             for r in piece.playback_balance]
    return result
