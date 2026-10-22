# RMD LLM V2 — Architecture

## Goal
Devotees ask questions in English, Hindi or Romanized Hindi about spiritual teachings. Answers are
generated **only** from retrieved passages in ingested sources (scanned English books, Hindi YouTube
lecture transcripts) and every substantive claim carries a citation that opens the exact PDF page or
YouTube timestamp. When evidence is missing the system abstains.

## Monorepo layout
```
apps/api          FastAPI + SQLAlchemy + Alembic (Python 3.10+)
  rmd/api         HTTP routers (health, ask, sources, admin, feedback)
  rmd/ingestion   PDF/OCR pipeline, transcript parser, chunking
  rmd/retrieval   dense (pgvector), lexical (tsvector/BM25), hybrid RRF, rerank
  rmd/generation  grounded answer generation + verification
  rmd/providers   LLM / embedding provider interfaces (OpenAI default, mock for tests)
  alembic/        migrations
  tests/          pytest
apps/web          Next.js 14 (App Router) + TypeScript + Tailwind
infrastructure/   deployment manifests (Render / Vercel / Neon notes)
docs/             architecture, runbooks, evaluation reports
tests/            cross-service / e2e tests
```

## Runtime components
| Component | Tech | Notes |
|---|---|---|
| API | FastAPI / uvicorn | `/health` liveness, `/ready` checks DB + Redis |
| Worker | RQ on Redis | OCR, chunking, embedding jobs — retryable, idempotent per content hash |
| DB | PostgreSQL 16 + pgvector | metadata, pages, segments, chunks + embeddings, chats, feedback, evals |
| Web | Next.js | chat UI, source viewer, admin dashboard |
| Providers | OpenAI (`text-embedding-3-large` @1024 dims, `gpt-4.1-mini`) | behind interfaces; swappable and benchmarkable |

## Data model (see `apps/api/rmd/models.py`)
- `sources` — a book or lecture; `status` tracks ingestion; `content_hash` gives idempotency.
- `books` / `pages` — page_index (0-based file index) vs `printed_page_number` are kept distinct;
  each page stores `extraction_method` (text|ocr|empty), `ocr_confidence`, size, chapter/section,
  `needs_review` flag and optional word boxes.
- `lectures` / `transcript_segments` — youtube_id, url, optional metadata (never blocks ingestion),
  raw transcript preserved; each segment has `start_seconds`, `end_seconds`, text, raw line.
- `chunks` — unified retrieval unit for both source kinds. `locator` JSON maps back to citation
  coordinates (`page_index`/`printed_page_number` or `start_seconds`/`end_seconds`/`youtube_id`).
  `embedding vector(1024)` with HNSW cosine index; `text_tsv` generated tsvector for lexical search.
- `conversations` / `messages` — stores citations, retrieval trace, verification result, latency,
  tokens and estimated cost per answer. `feedback` links to messages.
- `ingestion_jobs`, `eval_runs` — operational + evaluation records.

## Answer pipeline
1. Detect language/script of the question (Devanagari / Latin; Romanized Hindi heuristic).
2. Retrieve: detect question language → bridge it (LLM-translate hi/hi-Latn→en, en→hi) so both forms are searched → dense (pgvector cosine) + lexical (tsvector) per source kind (book / lecture pooled separately so the big English book can't crowd out the small Hindi lecture) → Reciprocal Rank Fusion over all lists → LLM listwise rerank of the top `RERANK_CANDIDATES` (default 16) → top-k.
3. Generate with a system prompt that treats passages as **untrusted data** (prompt-injection defence),
   requires `[n]` citations, distinguishes quote vs paraphrase vs translation.
4. Verify: every citation id must exist; each claim must be supported by its cited passage; unsupported
   content is removed or the answer abstains.
5. Persist message + trace; return citations with deep links (`/sources/{id}/pdf#page=N`,
   `youtube.com/watch?v=ID&t=Ns`).

## Security
Env-based config, no secrets in repo, admin JWT auth, upload validation (type/size/hash),
request validation (Pydantic), rate limiting (slowapi), safe error responses with request ids,
structured JSON logs in staging/prod, CI with lint/type/tests/migration check/dependency audit.

## Local development
```
cp .env.example .env            # fill OPENAI_API_KEY (or use LLM_PROVIDER=mock)
make up                         # postgres + redis
cd apps/api && uv venv .venv && uv pip install -e ".[dev]" && cd ../..
make migrate && make api        # http://localhost:8000/docs
cd apps/web && pnpm install && pnpm dev   # http://localhost:3000
```
