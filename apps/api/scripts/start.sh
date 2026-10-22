#!/usr/bin/env sh
set -e

# Free-tier hosts have no persistent disk: fetch the book PDF on boot if it isn't present.
if [ -n "$BOOK_PDF_URL" ]; then
  mkdir -p "${UPLOAD_DIR:-/data/uploads}"
  target="${UPLOAD_DIR:-/data/uploads}/${BOOK_PDF_NAME:-prem-ras-siddhanta-english.pdf}"
  if [ ! -s "$target" ]; then
    echo "downloading book PDF -> $target"
    curl -fsSL --retry 3 -o "$target" "$BOOK_PDF_URL"
  fi
fi

alembic upgrade head
exec uvicorn rmd.main:app --host 0.0.0.0 --port "${PORT:-8000}"
