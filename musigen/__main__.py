import argparse
import json
import sys
from pathlib import Path

import musigen  # noqa: F401  (puts musicomp on the path)


def _load_work(folder: Path) -> tuple[dict, dict | None]:
    folder = Path(folder)
    if folder.is_file():  # a design.json given directly
        return json.loads(folder.read_text(encoding="utf-8")), None
    design = json.loads((folder / "design.json").read_text(encoding="utf-8"))
    score_path = folder / "score.json"
    return design, json.loads(score_path.read_text(encoding="utf-8")) if score_path.exists() else None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="MUSICANOTE Virtual Composer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("compose", "text"):
        p = sub.add_parser(name, help="lead sheet from a spec (baseline tune) -> musicomp arrangement")
        p.add_argument("source", help="spec JSON file (compose) or the request text (text)")
        p.add_argument("--out", required=True)
        p.add_argument("--arrange", action="store_true", help="also arrange with musicomp (piano solo ... quartet)")
        p.add_argument("--grade", type=int, default=7)
        p.add_argument("--style", default="lyrical")
        p.add_argument("--seed", type=int, help="override the spec's seed (another tune / progression)")
    p = sub.add_parser("design", help="show a composition design (작곡 설계) as the user reads it")
    p.add_argument("work", help="work folder with design.json, or the design.json file")
    p = sub.add_parser("piece", help="build a piano piece from a work folder (design.json + score.json) as a new version")
    p.add_argument("work", help="work folder with design.json and score.json")
    p.add_argument("--out", required=True, help="the piece's output folder; versions v001, v002 ... go inside")
    p.add_argument("--reason", default="", help="what this version answers (the listener's words)")
    p.add_argument("--feedback", default="", help="사용자 피드백 원문")
    p.add_argument("--interpretation", default="", help="작곡자의 변경 해석")
    p.add_argument("--preserve", nargs="*", default=[], help="kept from the last version: bars:1-8 rh:1-8 lh:1-8 motif:a")
    p = sub.add_parser("listen", help="one HTML page to see and hear built pieces (every version, newest first)")
    p.add_argument("roots", nargs="+", help="piece output folders (with v001, v002 ...)")
    p.add_argument("--out", required=True)
    p.add_argument("--latest", action="store_true", help="only the newest version of each piece")
    p.add_argument("--shared-assets", action="store_true", help="공개 페이지의 샘플·PDF를 공통 assets 폴더에서 읽기")
    p.add_argument("--piano-samples", action="store_true", help="출처를 표시한 FluidR3 피아노 샘플 포함")
    p.add_argument("--individual-pages", action="store_true", help="곡별·버전별 URL 경로와 catalog.json 생성")
    p.add_argument("--embed-verovio", help="path to verovio-toolkit-wasm.js to embed (offline page, about 7 MB)")
    p = sub.add_parser("duet", help="피아노 솔로 버전을 바이올린–피아노 듀엣으로 확장")
    p.add_argument("source", help="솔로 v001 등 버전 폴더")
    p.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "duet":
        from musigen.duet import save_duet
        print(json.dumps(save_duet(Path(a.source),Path(a.out)),ensure_ascii=False,indent=2))
        return
    if a.cmd == "listen":
        from musigen.listen import build_page
        print(build_page([Path(r) for r in a.roots], Path(a.out), a.latest, a.embed_verovio, a.piano_samples, a.individual_pages, a.shared_assets))
        return
    if a.cmd == "design":
        from musigen.design import summary_ko, validate
        design, _ = _load_work(Path(a.work))
        warn = validate(design)
        print(summary_ko(design) + "".join(f"\n주의: {w}" for w in warn))
        return
    if a.cmd == "piece":
        from musigen.design import validate
        from musigen.versions import save
        design, score = _load_work(Path(a.work))
        if score is None:
            sys.exit(f"{a.work}: score.json not found")
        validate(design)
        info = save(Path(a.out), design, score, a.reason, a.preserve, a.feedback, a.interpretation)
        print(json.dumps(info, ensure_ascii=False, indent=1))
        print((Path(a.out) / info["version"] / "checks.json").resolve())
        return
    from musigen.compose import compose
    from musigen.spec import from_dict
    if a.cmd == "compose":
        spec = from_dict(json.loads(Path(a.source).read_text(encoding="utf-8")))
    else:
        from musigen.prompt import spec_from_text
        spec = spec_from_text(a.source)
    if a.seed is not None:
        spec.seed = a.seed
    print(json.dumps(compose(spec, Path(a.out), a.arrange, a.grade, a.style), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
