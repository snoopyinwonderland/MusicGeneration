"""The composition spec: everything the composer needs, as data.

A spec is what a text request is turned into (musigen/prompt.py) and what the composer reads (musigen/compose.py).
It can also be written by hand (examples/*.json).  Bars are 1-based everywhere in a spec.

  {
    "title": "Evening",
    "key": "F", "mode": "major",            # tonic name, major | minor
    "meter": "4/4", "tempo": 84,
    "form": [{"label": "A", "bars": 8, "cadence": "half"},
             {"label": "A", "bars": 8, "cadence": "authentic"},
             {"label": "B", "bars": 8, "cadence": "half"},
             {"label": "A", "bars": 8, "cadence": "authentic"}],
    "genre": "pop",                          # chord statistics: pop | jazz | classical (musicomp)
    "progression": null,                     # optional: one roman token per bar, e.g. ["I", "vi", "IV", "V", ...]
    "register": "C4-F5",                     # optional melody range
    "requests": [                            # optional, bar ranges inclusive
      {"bars": [9, 12], "register": "higher", "rhythm": "busier"},
      {"bars": [16, 16], "rhythm": "held"},
      {"bars": [13, 13], "chord": "IV"}
    ],
    "seed": 1
  }

Request fields (all optional): register higher | lower; rhythm busier | calmer | held; rest true (the tune rests);
chord <roman token> (forced chord for those bars); climax true (the phrase's highest note there).
"""
from __future__ import annotations

from dataclasses import dataclass, field

METERS = {"2/4", "3/4", "4/4", "6/8", "3/8", "12/8"}
CADENCES = {"authentic", "half", "plagal", "none"}
REGISTER = {"higher", "lower"}
RHYTHM = {"busier", "calmer", "held"}


@dataclass
class Section:
    label: str
    bars: int
    cadence: str = "authentic"


@dataclass
class Request:
    bars: tuple[int, int]
    register: str | None = None
    rhythm: str | None = None
    rest: bool = False
    chord: str | None = None
    climax: bool = False


@dataclass
class Spec:
    key: str = "C"
    mode: str = "major"
    meter: str = "4/4"
    tempo: int = 90
    form: list[Section] = field(default_factory=lambda: [Section("A", 8, "half"), Section("A", 8, "authentic")])
    genre: str = "pop"
    progression: list[str] | None = None
    register: str | None = None
    requests: list[Request] = field(default_factory=list)
    title: str = "Untitled"
    seed: int = 0

    @property
    def total_bars(self) -> int:
        return sum(s.bars for s in self.form)

    def requests_at(self, bar: int) -> list[Request]:
        """Requests covering a 1-based bar."""
        return [r for r in self.requests if r.bars[0] <= bar <= r.bars[1]]


class SpecError(ValueError):
    pass


def from_dict(d: dict) -> Spec:
    """Validate a spec dict (from JSON or a language model) and build the Spec; unknown fields are rejected so a
    model's invention is noticed instead of silently ignored."""
    allowed = {"title", "key", "mode", "meter", "tempo", "form", "genre", "progression", "register", "requests", "seed"}
    extra = set(d) - allowed
    if extra:
        raise SpecError(f"unknown fields: {sorted(extra)}")
    s = Spec()
    s.title = str(d.get("title", s.title))
    s.key = str(d.get("key", s.key))
    if not s.key or s.key[0].upper() not in "ABCDEFG" or any(c not in "#b" for c in s.key[1:]):
        raise SpecError(f"bad key {s.key!r}")
    s.key = s.key[0].upper() + s.key[1:]
    s.mode = str(d.get("mode", s.mode)).lower()
    if s.mode not in ("major", "minor"):
        raise SpecError(f"bad mode {s.mode!r}")
    s.meter = str(d.get("meter", s.meter))
    if s.meter not in METERS:
        raise SpecError(f"meter must be one of {sorted(METERS)}")
    s.tempo = int(d.get("tempo", s.tempo))
    if not 30 <= s.tempo <= 240:
        raise SpecError("tempo 30-240")
    if "form" in d:
        s.form = []
        for x in d["form"]:
            sec = Section(str(x.get("label", "A")), int(x["bars"]), str(x.get("cadence", "authentic")))
            if sec.bars < 1 or sec.cadence not in CADENCES:
                raise SpecError(f"bad section {x}")
            s.form.append(sec)
    s.genre = str(d.get("genre", s.genre))
    if s.genre not in ("pop", "jazz", "classical"):
        raise SpecError("genre pop | jazz | classical")
    if d.get("progression") is not None:
        s.progression = [str(t) for t in d["progression"]]
        if len(s.progression) != s.total_bars:
            raise SpecError(f"progression has {len(s.progression)} tokens for {s.total_bars} bars")
    s.register = d.get("register")
    s.seed = int(d.get("seed", 0))
    for x in d.get("requests", []) or []:
        a, b = (int(v) for v in x["bars"])
        if not 1 <= a <= b <= s.total_bars:
            raise SpecError(f"request bars {x['bars']} outside 1-{s.total_bars}")
        r = Request((a, b), x.get("register"), x.get("rhythm"), bool(x.get("rest", False)), x.get("chord"),
                    bool(x.get("climax", False)))
        if r.register not in (None, *REGISTER) or r.rhythm not in (None, *RHYTHM):
            raise SpecError(f"bad request {x}")
        s.requests.append(r)
    return s


def to_dict(s: Spec) -> dict:
    return {"title": s.title, "key": s.key, "mode": s.mode, "meter": s.meter, "tempo": s.tempo,
            "form": [{"label": x.label, "bars": x.bars, "cadence": x.cadence} for x in s.form],
            "genre": s.genre, "progression": s.progression, "register": s.register, "seed": s.seed,
            "requests": [{k: v for k, v in {"bars": list(r.bars), "register": r.register, "rhythm": r.rhythm,
                                            "rest": r.rest or None, "chord": r.chord, "climax": r.climax or None}.items()
                          if v is not None} for r in s.requests]}
