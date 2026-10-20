import argparse
import json
import sys
from pathlib import Path

import musigen  # noqa: F401  (puts musicomp on the path)
from musigen.compose import compose
from musigen.spec import from_dict


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="musigen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("compose", "text"):
        p = sub.add_parser(name)
        p.add_argument("source", help="spec JSON file (compose) or the request text (text)")
        p.add_argument("--out", required=True)
        p.add_argument("--arrange", action="store_true", help="also arrange with musicomp (piano solo ... quartet)")
        p.add_argument("--grade", type=int, default=7)
        p.add_argument("--style", default="lyrical")
        p.add_argument("--seed", type=int, help="override the spec's seed (another tune / progression)")
    a = ap.parse_args()
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
