"""MUSICANOTE Virtual Composer score pages, standalone or with shared public assets."""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote

TEMPLATE = Path(__file__).with_name("listen_template.html")
VEROVIO_CDN = "https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/verovio-toolkit-wasm.js"


def _entry(vdir: Path) -> dict:
    from musigen.piece import build
    from musigen.expression import playback
    read = lambda name: json.loads((vdir / name).read_text(encoding="utf-8"))
    design, score, info = read("design.json"), read("score.json"), read("version.json")
    piece = build(design, score)
    performance = playback(piece)
    from musigen.harmony_labels import analyze
    harmony = analyze(piece)
    pdf = vdir / "piece.pdf"
    return {"harmony":harmony, "performance":performance, "piece":vdir.parent.name,
            "xml":(vdir / "piece.musicxml").read_text(encoding="utf-8"),
            "design":design, "checks":read("checks.json"), "info":info,
            "_pdf":str(pdf) if pdf.exists() else None}


def build_page(roots: list[Path], out: Path, latest: bool = False,
               embed_verovio: Path | None = None, piano_samples: bool = False,
               individual_pages: bool = False, shared_assets: bool = False) -> Path:
    entries = []
    names = [Path(root).name for root in roots]
    if len(set(names)) != len(names):
        raise ValueError("곡 폴더 이름이 중복됩니다. 고유한 이름을 사용하세요")
    for root in roots:
        versions = sorted((p for p in Path(root).glob("v[0-9][0-9][0-9]")
                           if (p / "piece.musicxml").exists()), reverse=True)
        entries.extend(_entry(v) for v in (versions[:1] if latest else versions))
    if not entries:
        raise FileNotFoundError("생성한 악보 버전이 없습니다")
    out = Path(out)
    assets = out.parent / "assets" if shared_assets else None
    if assets:
        assets.mkdir(parents=True, exist_ok=True)
    return _write_page(entries, out, embed_verovio, piano_samples, individual_pages, assets)


def _relative(path, out):
    return quote(Path(os.path.relpath(path, out.parent)).as_posix(), safe="/.")


def _write_page(entries, out, embed_verovio, piano_samples, individual_pages=False, assets=None):
    page = TEMPLATE.read_text(encoding="utf-8")
    # tab icon inline, so a single shared HTML file keeps it (and browsers stop asking the server for /favicon.ico)
    icon = TEMPLATE.with_name("assets").joinpath("favicon.svg").read_text(encoding="utf-8").strip()
    page = page.replace("/*FAVICON*/", "data:image/svg+xml," + quote(icon))
    instruments = {"piano"} if piano_samples else set()
    if piano_samples and any(e["info"].get("ensemble") == "violin_piano" for e in entries):
        instruments.add("violin")
    for instrument, token in (("piano","/*PIANO_SAMPLES*/"),("violin","/*VIOLIN_SAMPLES*/")):
        value = None
        if instrument in instruments:
            source = TEMPLATE.parent / "assets" / instrument
            if assets:
                shutil.copyfile(source / f"{instrument}.json", assets / f"{instrument}.json")
                shutil.copyfile(source / "ATTRIBUTION.md", assets / f"{instrument}-ATTRIBUTION.md")
                value = {"url":_relative(assets / f"{instrument}.json", out)}
            else:
                value = json.loads((source / f"{instrument}.json").read_text(encoding="utf-8"))
        page = page.replace(token, json.dumps(value))
    public = []
    for entry in entries:
        item = {k:v for k,v in entry.items() if not k.startswith("_")}
        if entry["_pdf"]:
            if assets:
                target = assets / (entry["piece"] + "-" + entry["info"]["version"] + ".pdf")
                shutil.copyfile(entry["_pdf"], target)
                item["pdf"] = {"url":_relative(target,out)}
            else:
                item["pdf"] = {"base64":base64.b64encode(Path(entry["_pdf"]).read_bytes()).decode("ascii")}
        public.append(item)
    page = page.replace("/*MOTIF_PANEL*/", TEMPLATE.with_name("motif_panel.html").read_text(encoding="utf-8"))
    page = page.replace("/*MOTIF_TOOLS*/", TEMPLATE.with_name("motif_tools.js").read_text(encoding="utf-8"))
    page = page.replace("/*PIECES*/",json.dumps(public,ensure_ascii=False).replace("</","<\\/"))
    if embed_verovio:
        page = page.replace('<script src="/*VEROVIO_SRC*/"></script>',
                            '<script>' + Path(embed_verovio).read_text(encoding="utf-8") + '</script>')
    else:
        page = page.replace("/*VEROVIO_SRC*/",VEROVIO_CDN)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(page,encoding="utf-8")
    if individual_pages:
        groups = {}
        for entry in entries:
            groups.setdefault(entry["piece"],[]).append(entry)
        catalog = []
        for name, group in groups.items():
            if name in (".","..") or any(c in name for c in "/\\"):
                raise ValueError("곡 폴더 이름을 URL 경로로 사용할 수 없습니다")
            _write_page(group,out.parent / name / "index.html",embed_verovio,piano_samples,assets=assets)
            versions = []
            for entry in group:
                version = entry["info"]["version"]
                if not re.fullmatch(r"v[0-9]{3}",version):
                    raise ValueError("버전 이름 형식 오류")
                _write_page([entry],out.parent / name / (version+".html"),embed_verovio,piano_samples,assets=assets)
                versions.append({"version":version,"url":quote(name)+"/"+version+".html"})
            catalog.append({"piece":name,"title":group[0]["design"]["title"],
                            "url":quote(name)+"/","versions":versions})
        (out.parent / "catalog.json").write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding="utf-8")
    return out
