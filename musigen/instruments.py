"""Explicit audition presets; ranges are conservative validation limits, not technique grading.

User request 2026-10-23: add viola and cello sounds alongside violin and piano.
Programs are MusicXML's one-based General MIDI values. No automatic transposition.
"""
STRINGS = {
    "violin": {"name":"Violin", "ko":"바이올린", "abbr":"Vln.", "program":41, "clef":("G",2), "range":(55,93)},
    "viola": {"name":"Viola", "ko":"비올라", "abbr":"Vla.", "program":42, "clef":("C",3), "range":(48,88)},
    "cello": {"name":"Violoncello", "ko":"첼로", "abbr":"Vc.", "program":43, "clef":("F",4), "range":(36,79)},
}


def preset(instrument):
    if instrument not in STRINGS:
        raise ValueError("지원 현악기: violin, viola, cello")
    return STRINGS[instrument]
