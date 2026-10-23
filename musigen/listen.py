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
    from musigen.piece import build
    from musigen.expression import playback
    performance = playback(build(read("design.json"), read("score.json")))
    return {"performance": performance, "piece": vdir.parent.name, "xml": (vdir / "piece.musicxml").read_text(encoding="utf-8"),
            "design": read("design.json"), "checks": read("checks.json"), "info": read("version.json")}


def build_page(roots: list[Path], out: Path, latest: bool = False, embed_verovio: Path | None = None, piano_samples: bool = False, individual_pages: bool = False) -> Path:
    entries = []
    for root in roots:
        versions = sorted((p for p in Path(root).glob("v[0-9][0-9][0-9]") if (p / "piece.musicxml").exists()),
                          reverse=True)
        entries += [_entry(v) for v in (versions[:1] if latest else versions)]
    if not entries:
        raise FileNotFoundError(f"no built versions under {', '.join(map(str, roots))}")
    if individual_pages:
        # Detect ambiguous slugs instead of silently overwriting a different work.
        names=[Path(root).name for root in roots]
        if len(set(names))!=len(names): raise ValueError("곡 폴더 이름이 중복됩니다. 고유한 이름을 사용하세요")
    return _write_page(entries, Path(out), embed_verovio, piano_samples, individual_pages)


def _write_page(entries, out, embed_verovio, piano_samples, individual_pages=False):
    page = TEMPLATE.read_text(encoding="utf-8")
    bank = json.loads((TEMPLATE.parent/'assets/piano/piano.json').read_text(encoding='utf-8')) if piano_samples else None
    page = page.replace('/*PIANO_SAMPLES*/',json.dumps(bank))
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
    if individual_pages:
        from urllib.parse import quote
        groups={}
        for entry in entries: groups.setdefault(entry['piece'],[]).append(entry)
        catalog=[]
        for name, group in groups.items():
            # Filesystem names come from input directory basenames, never prompt text.
            if name in ('.','..') or any(c in name for c in '/\\'):
                raise ValueError('곡 폴더 이름을 URL 경로로 사용할 수 없습니다')
            _write_page(group,out.parent/name/'index.html',embed_verovio,piano_samples)
            versions=[]
            for entry in group:
                ver=entry['info']['version']
                import re
                if not re.fullmatch(r'v[0-9]{3}',ver): raise ValueError('버전 이름 형식 오류')
                _write_page([entry],out.parent/name/(ver+'.html'),embed_verovio,piano_samples)
                versions.append({'version':ver,'url':quote(name)+'/'+ver+'.html'})
            catalog.append({'piece':name,'title':group[0]['design']['title'],'url':quote(name)+'/','versions':versions})
        (out.parent/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    return out
