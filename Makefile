.PHONY: install dev run test lint format typecheck docker-up docker-down

install:
\tpython -m pip install -U pip
\tpython -m pip install -e ".[dev]"

dev:
\tuvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
\tuvicorn app.main:app --host 0.0.0.0 --port 8000

test:
\tpytest -q

lint:
\truff check .
\tblack --check .

format:
\truff check --fix .
\tblack .

typecheck:
\tmypy .

docker-up:
\tdocker compose up --build

docker-down:
\tdocker compose down

