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

## Playwright (optional UI smoke)

Install extras and browsers:

```bash
python -m pip install -e ".[playwright]"
python -m playwright install chromium
```

Run:

```bash
RUN_PLAYWRIGHT=1 pytest -q tests/playwright
```

## Docker

```bash
docker compose up --build
```

## Environment variables

See `.env.example` for the supported configuration surface.

## Observability (SigNoz)

```bash
docker compose --profile observability up -d
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_INSECURE=true
```

Open `http://localhost:3301`.

Artifact storage (optional):
- `ARTIFACT_STORE=local|s3|r2|gcs` (default `local`)
- `ARTIFACT_STORE_BUCKET=...` (required for non-local)
- `ARTIFACT_STORE_PREFIX=...` (object key prefix; default `clinical-ai-reliability-lab`)
- `ARTIFACT_STORE_S3_ENDPOINT_URL=...` (for R2/S3-compatible)
- `ARTIFACT_STORE_S3_REGION=...` (optional)

Dependency extras (optional):
- S3 / R2: `python -m pip install -e ".[storage-s3]"`
- GCS: `python -m pip install -e ".[storage-gcs]"`
