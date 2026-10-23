r"""A listening page for built pieces: the score drawn by Verovio, played in the browser, with the design and checks.

  python -m musigen listen output\after_rain [output\other ...] --out output\after_rain\listen.html
  python -m musigen listen output\after_rain --out docs\listen\index.html --latest      # only the newest version

One HTML file holds every version given (newest first in the menu); the score, design, version note and check
results are embedded, so the file can be opened directly or served as a static page (GitHub Pages).  Verovio comes
from the jsDelivr CDN (the version musicomp's viewer uses); --embed-verovio <verovio-toolkit-wasm.js> puts it inside
the file instead (about 7 MB) for listening offline.
"""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("listen_template.html")
VEROVIO_CDN = "https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/verovio-toolkit-wasm.js"


def _entry(vdir: Path) -> dict:
    read = lambda name: json.loads((vdir / name).read_text(encoding="utf-8"))
    return {"piece": vdir.parent.name, "xml": (vdir / "piece.musicxml").read_text(encoding="utf-8"),
            "design": read("design.json"), "checks": read("checks.json"), "info": read("version.json")}


def build_page(roots: list[Path], out: Path, latest: bool = False, embed_verovio: Path | None = None) -> Path:
    entries = []
    for root in roots:
        versions = sorted((p for p in Path(root).glob("v[0-9][0-9][0-9]") if (p / "piece.musicxml").exists()),
                          reverse=True)
        entries += [_entry(v) for v in (versions[:1] if latest else versions)]
    if not entries:
        raise FileNotFoundError(f"no built versions under {', '.join(map(str, roots))}")
    page = TEMPLATE.read_text(encoding="utf-8")
    # '</' inside the embedded JSON would end the script element early
    page = page.replace("/*PIECES*/", json.dumps(entries, ensure_ascii=False).replace("</", "<\\/"))
    if embed_verovio:
        page = page.replace('<script src="/*VEROVIO_SRC*/"></script>',
                            "<script>" + Path(embed_verovio).read_text(encoding="utf-8") + "</script>")
    else:
        page = page.replace("/*VEROVIO_SRC*/", VEROVIO_CDN)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out
