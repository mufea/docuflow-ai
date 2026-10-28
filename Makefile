.PHONY: test lint typecheck api web worker fmt

test:
	uv run pytest
	pnpm --filter web test

lint:
	uv run ruff check src tests
	pnpm --filter web lint

typecheck:
	uv run mypy src/docuflow
	pnpm --filter web typecheck

fmt:
	uv run ruff format src tests

api:
	uv run uvicorn docuflow.main:app --host 127.0.0.1 --port 43124

web:
	pnpm --filter web dev -- --port 43123 --hostname 127.0.0.1

worker:
	JOB_BROKER=rq uv run python -m docuflow.worker
