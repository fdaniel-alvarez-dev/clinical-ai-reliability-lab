# clinical-ai-reliability-lab

A reliability-first, clinical-like AI workflow demo that generates a structured **Comprehensive Health Report (CHR)** from **synthetic** medical-style inputs (labs, medications, imaging summaries, longitudinal history).

This repository is intentionally **not** a chatbot demo and **not** a medical device. It exists to demonstrate launch-readiness thinking:

> **LLMs may draft. Deterministic systems decide.**

If the model output is unsupported, the system rejects it loudly with machine-readable reasons.

## What this is (and is not)

- This is an engineering portfolio repo: bounded orchestration, explicit validation rules, evaluation artifacts, and observability.
- This is **synthetic-data-only** and **not medical advice**.
- This is **not** an EHR integration, not a clinical decision support system, and not a regulated product.

## Architecture (high-level)

```mermaid
flowchart LR
  A[POST /v1/reports/generate] --> B[Ingest + Pydantic schema]
  B --> C[Normalize + fingerprint]
  C --> D[Provider draft (mock/anthropic)]
  D --> E[Deterministic validator]
  E -->|accepted| F[Evaluator + Export: JSON/MD/PDF]
  E -->|rejected| G[Evaluator + Rejection artifact]
  F --> H[(SQLite report store)]
  G --> H
```

Key design boundary: the provider output is treated as **advisory input** to a deterministic validation layer. The validator is the authority.

## Quickstart

Prereqs: Python 3.11+ (local), `make` optional.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"

uvicorn app.main:app --reload
```

Generate a report from a dataset:

```bash
curl -sS -X POST "http://localhost:8000/v1/reports/generate" \
  -H "Content-Type: application/json" \
  --data-binary "@datasets/case_01_stable_patient.json" | python -m json.tool
```

## API

- `POST /v1/reports/generate` — run the workflow and persist artifacts
- `GET /v1/reports/{report_id}` — fetch stored final report JSON (accepted report or rejection payload)
- `GET /v1/reports/{report_id}/evaluation` — fetch evaluation artifact
- `GET /v1/reports/{report_id}/artifacts` — fetch artifact index (relative paths)
- `GET /health` — liveness
- `GET /ready` — readiness

## Accepted vs rejected behavior

- Accepted runs export `report.md` and `report.pdf` plus JSON artifacts.
- Rejected runs export `rejection.md` plus JSON artifacts (including the model draft when available).
- Failures are explicit and machine-readable. No polished prose hides rejections.

## Providers

Default provider is deterministic `mock` so the repo works without paid APIs.

Optional: `LLM_PROVIDER=anthropic` requires `ANTHROPIC_API_KEY` and expects the model to return strict JSON.

## Observability

- Structured logs (JSON) via `structlog`
- OpenTelemetry spans across workflow stages and FastAPI
- Optional OTLP export via `OTEL_EXPORTER_OTLP_ENDPOINT` (see `docs/observability.md`)

## Tests

```bash
pytest -q
```

Test categories:
- `tests/unit/` — validator/evaluator/normalization/exporter/storage
- `tests/integration/` — API workflow using ASGI transport
- `tests/e2e/` — smoke run using dataset files

## Docs

- `docs/architecture.md`
- `docs/validation-rules.md`
- `docs/evaluation-methodology.md`
- `docs/observability.md`
- `docs/runbook.md`
- `docs/decision-log.md`

