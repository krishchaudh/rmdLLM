# Staging deployment

Target: **Vercel** (web) + **Render** (api, redis) + **Neon** (Postgres w/ pgvector). All free tiers.
Nothing here is public-facing until the Vercel URL is shared; the admin panel is JWT-protected.

## 1. Neon
1. Create project → copy the pooled connection string.
2. `CREATE EXTENSION IF NOT EXISTS vector;` (the first Alembic migration also does this).
3. Use `postgresql+psycopg://USER:PASS@HOST/neondb?sslmode=require` as `DATABASE_URL`.

## 2. Render
1. New → Blueprint → point at this repo; `render.yaml` creates `rmd-api` (Docker, free) + `rmd-redis`.
2. Fill `DATABASE_URL` and `OPENAI_API_KEY` when prompted. `ADMIN_PASSWORD`/`JWT_SECRET` are generated — copy the admin password from the env tab.
3. First boot runs `alembic upgrade head` (see `apps/api/Dockerfile` CMD). Health: `https://<api>.onrender.com/ready`.
4. Free tier sleeps after 15 min idle → first request ~30 s cold start. Free tier has no persistent disk; uploaded PDFs must be re-ingested after a restart unless upgraded to a paid plan (the `disk` block in `render.yaml` is ignored on free).

## 3. Ingest sources (one-off, from a laptop with the Neon URL)
```
cd apps/api
DATABASE_URL=... OPENAI_API_KEY=... python scripts/ingest.py lecture --url https://www.youtube.com/watch?v=P4u061hYAXs --transcript transcript.txt
DATABASE_URL=... OPENAI_API_KEY=... python scripts/ingest.py book --file "Prem Ras Siddhanth.pdf" --title "Prema Rasa Siddhanta"
```
Or via the admin UI once deployed (PDF upload → background job; needs the worker, see below).

## 4. Vercel
1. Import repo, **Root Directory = `apps/web`**, framework Next.js.
2. Env: `NEXT_PUBLIC_API_URL=https://<api>.onrender.com`.
3. Deploy; then put the Vercel URL into Render's `CORS_ORIGINS` (JSON list) and redeploy the api.

## Worker
Ingestion jobs are dispatched by `INGEST_MODE` (default `auto`): if an RQ worker (`python -m rmd.worker`, a Render **Background Worker**, ~$7/mo) is listening on Redis the job goes there; otherwise it runs in a background thread of the API process. On the free tier that means admin "Add lecture" works out of the box (~1 min); a full book OCR (~1 hr) is better run with `scripts/ingest.py` or a worker because the free API instance can be put to sleep mid-job.

## Smoke test
```
curl https://<api>.onrender.com/ready
curl -X POST https://<api>.onrender.com/ask -H 'content-type: application/json' -d '{"question":"Why doesn'"'"'t material wealth provide lasting happiness?"}'
```
