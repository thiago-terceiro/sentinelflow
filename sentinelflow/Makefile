backend-sync:
	cd backend && uv sync

backend-seed:
	cd backend && uv run alembic upgrade head && uv run python -m app.db.seed

backend-lint:
	cd backend && uv run ruff check app

backend-test:
	cd backend && uv run pytest

backend-run:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend-install:
	cd frontend && pnpm install

frontend-dev:
	cd frontend && pnpm dev

frontend-build:
	cd frontend && pnpm build

smoke-test:
	python ops/smoke_test.py

up:
	docker compose up --build

up-detached:
	docker compose up -d --build

down:
	docker compose down -v
