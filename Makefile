.PHONY: install dev run test test-unit test-integration test-e2e test-all lint format typecheck docker-up docker-down

install:
	python -m pip install -U pip
	python -m pip install -e ".[dev]"

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	$(MAKE) test-all

test-unit:
	pytest -q tests/unit

test-integration:
	pytest -q tests/integration

test-e2e:
	pytest -q tests/e2e

test-all:
	pytest -q tests/unit
	pytest -q tests/integration
	pytest -q tests/e2e

lint:
	ruff check .
	black --check .

format:
	ruff check --fix .
	black .

typecheck:
	mypy .

docker-up:
	docker compose up --build

docker-down:
	docker compose down
