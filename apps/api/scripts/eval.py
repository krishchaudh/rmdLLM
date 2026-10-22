"""Run the evaluation harness.

python scripts/eval.py --dataset ../../eval/datasets/lecture_v1.jsonl --modes dense,lexical,hybrid
python scripts/eval.py --dataset ../../eval/datasets/lecture_v1.jsonl --answers --out ../../eval/reports/run.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rmd.db import session_factory  # noqa: E402
from rmd.eval.runner import format_markdown, run  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--modes", default="hybrid")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument(
        "--answers", action="store_true", help="also generate + verify answers (costs tokens)"
    )
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--out", default=None, help="write markdown report here; JSON next to it")
    a = ap.parse_args()

    modes = tuple(m.strip() for m in a.modes.split(",") if m.strip())
    name = a.name or f"{Path(a.dataset).stem}-{'answers' if a.answers else 'retrieval'}"
    with session_factory()() as db:
        report = run(
            db, a.dataset, name=name, modes=modes, k=a.k, with_answers=a.answers, save=not a.no_save
        )
    md = format_markdown(report)
    print(md)
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        out.with_suffix(".json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"wrote {out} and {out.with_suffix('.json')}", file=sys.stderr)


if __name__ == "__main__":
    main()
