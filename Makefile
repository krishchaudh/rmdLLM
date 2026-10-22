.PHONY: up down api web worker migrate test lint

up:
	docker compose up -d postgres redis

down:
	docker compose down

migrate:
	cd apps/api && .venv/bin/alembic upgrade head

api:
	cd apps/api && .venv/bin/uvicorn rmd.main:app --reload --port 8000

worker:
	cd apps/api && .venv/bin/python -m rmd.worker

web:
	cd apps/web && pnpm dev

test:
	cd apps/api && .venv/bin/pytest -q

lint:
	cd apps/api && .venv/bin/ruff check rmd tests alembic && .venv/bin/ruff format --check rmd tests alembic
	cd apps/web && pnpm lint && pnpm typecheck
