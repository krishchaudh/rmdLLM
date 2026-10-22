"""CLI ingestion (runs synchronously, no worker needed).

python scripts/ingest.py lecture --url URL --transcript file.txt [--title T]
python scripts/ingest.py book --file book.pdf --title T [--author A] [--no-tesseract]
"""

from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, ".")

from rmd.db import session_factory  # noqa: E402
from rmd.ingestion.service import (  # noqa: E402
    create_book_source,
    create_lecture_source,
    process_book,
    process_lecture,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("lecture")
    lp.add_argument("--url", required=True)
    lp.add_argument("--transcript", required=True)
    lp.add_argument("--title")
    bp = sub.add_parser("book")
    bp.add_argument("--file", required=True)
    bp.add_argument("--title", required=True)
    bp.add_argument("--author")
    bp.add_argument("--no-tesseract", action="store_true")
    bp.add_argument("--no-vision", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    with session_factory()() as db:
        if args.cmd == "lecture":
            raw = open(args.transcript, encoding="utf-8").read()
            source, job = create_lecture_source(db, url=args.url, transcript=raw, title=args.title)
            print("source", source.id, "job", job.status)
            if job.status == "queued":
                process_lecture(db, source.id, job.id)
        else:
            data = open(args.file, "rb").read()
            source, job = create_book_source(
                db, file_bytes=data, filename=args.file, title=args.title, author=args.author
            )
            print("source", source.id, "job", job.status, flush=True)
            if job.status in ("queued", "skipped"):
                process_book(
                    db,
                    source.id,
                    job.id if job.status == "queued" else None,
                    use_vision=not args.no_vision,
                    use_tesseract=not args.no_tesseract,
                )
        db.refresh(source)
        print(
            "status",
            source.status,
            source.status_detail,
            "chunks",
            source.chunk_count,
            f"{time.time() - t0:.0f}s",
        )


if __name__ == "__main__":
    main()
