# Runbook

This is a local-first demo intended to be easy to run and inspect.

## Local setup (Python)

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Run the API

```bash
uvicorn app.main:app --reload
```

## Generate a report from a dataset

```bash
./scripts/generate_report.sh datasets/case_01_stable_patient.json
./scripts/generate_report.sh datasets/case_03_hallucinated_claim_risk.json
```

Artifacts are written under `ARTIFACTS_DIR/<report_id>/` (default `./artifacts/`).

## Run tests

```bash
pytest -q
```

## Docker

```bash
docker compose up --build
```

## Environment variables

See `.env.example` for the supported configuration surface.

