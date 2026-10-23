"""MUSICANOTE Virtual Composer score pages, standalone or with shared public assets."""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET
from musigen.instruments import STRINGS

TEMPLATE = Path(__file__).with_name("listen_template.html")
VEROVIO_CDN = "https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/verovio-toolkit-wasm.js"


def _instrumentation(xml):
    score = ET.fromstring(xml)
    programs = {1: "piano", **{v["program"]: k for k, v in STRINGS.items()}}
    ids = {}
    for part in score.findall("./part-list/score-part"):
        program = int(part.findtext("midi-instrument/midi-program", "1"))
        if program not in programs:
            raise ValueError(f"지원하지 않는 재생 악기 프로그램: {program}")
        ids[part.get("id")] = programs[program]
    staffs, n = {}, 1
    for part in score.findall("part"):
        instrument = ids[part.get("id")]
        counts = {int(x.text) for x in part.findall("./measure/attributes/staves")}
        if len(counts) > 1:
            raise ValueError("재생 중 보표 수가 바뀌는 악보는 지원하지 않습니다")
        count = next(iter(counts), 1)
        for local in range(1, count + 1):
            staffs[str(n)] = {"instrument": instrument, "lh": instrument == "piano" and local == 2}
            n += 1
    names = list(dict.fromkeys(x["instrument"] for x in staffs.values()))
    label = " · ".join("피아노" if x == "piano" else STRINGS[x]["ko"] for x in names)
    return {"staffs":staffs, "instruments":names, "label":label if names != ["piano"] else "피아노 솔로"}


def _entry(vdir: Path) -> dict:
    from musigen.piece import build
    from musigen.expression import playback
    read = lambda name: json.loads((vdir / name).read_text(encoding="utf-8"))
    design, score, info = read("design.json"), read("score.json"), read("version.json")
    piece = build(design, score)
    # Reflect an explicit string octave shift in articulation pitch matching and bass analysis.
    for note in piece.notes:
        if note.hand == "rh" and note.voice == 1 and info.get("lead_octaves"):
            note.pitches = [(m + 12 * info["lead_octaves"], tpc) for m, tpc in note.pitches]
    performance = playback(piece)
    from musigen.harmony_labels import analyze
    harmony = analyze(piece)
    xml = (vdir / "piece.musicxml").read_text(encoding="utf-8")
    pdf = vdir / "piece.pdf"
    return {"harmony":harmony, "performance":performance, "piece":vdir.parent.name,
            "xml":xml, "instrumentation":_instrumentation(xml),
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
    if piano_samples:
        instruments.update(i for e in entries for i in e["instrumentation"]["instruments"])
    for instrument in ("piano", *STRINGS):
        token = f"/*{instrument.upper()}_SAMPLES*/"
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
