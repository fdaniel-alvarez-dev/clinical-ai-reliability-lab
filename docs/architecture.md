# Architecture

This repository demonstrates a reliability-first stance for LLM workflows:

> **LLMs may draft. Deterministic systems decide.**

The workflow produces a **Comprehensive Health Report (CHR)** from **synthetic** clinical-like inputs. The system is intentionally bounded, observable, and testable.

## Core flow

1. **Ingest**
   - Accept `SyntheticPatientPayload` JSON.
   - Pydantic enforces required fields, timestamps, and basic types.

2. **Normalize**
   - Convert labs into a canonical `NormalizedPatient` form.
   - Derive simple lab interpretations (`low|normal|high`).
   - Compute a deterministic fingerprint over normalized input for traceability.

3. **Biomarker Graph (deterministic)**
   - Build a simple, explicit graph over labs + longitudinal biomarker series.
   - Emit deterministic "concerns" derived from abnormal values or rising trends.
   - This stage is fully deterministic and produces inspectable artifacts.

4. **Draft (provider)**
   - Default: deterministic mock provider (`LLM_PROVIDER=mock`) so the repo is runnable without external credentials.
   - Optional: Anthropic adapter (`LLM_PROVIDER=anthropic`) for stakeholders who want to see an actual provider interface.
   - Provider output is treated as an *untrusted draft*.

5. **Validate (deterministic)**
   - Reject unsupported claims (evidence refs must exist).
   - Reject contradictory statements (e.g., "LDL normal" when LDL is high).
   - Reject critical omissions (abnormal labs must be covered).
   - Reject prescriptive language and "medical advice" patterns (this is an educational demo).

6. **Evaluate**
   - Produce simple, inspectable scores (consistency/completeness/traceability/contradiction risk).
   - Evaluation never overrides validation. It exists to help reviewers inspect outcomes.

7. **Export + Persist**
   - Accepted: `report.md` + `report.pdf` + JSON artifacts.
   - Rejected: `rejection.md` + JSON artifacts (including model draft when available).
   - Persist summary to SQLite for retrieval via API endpoints.

Artifact storage:
- Default: local filesystem under `ARTIFACTS_DIR/`.
- Optional: remote artifact stores via `ARTIFACT_STORE=s3|r2|gcs` (see `docs/runbook.md`).

## Artifacts

Each run creates an artifacts folder under `ARTIFACTS_DIR/<report_id>/`:

- `normalized_input.json`
- `biomarker_graph.json`
- `concerns.json`
- `model_draft.json` (when available)
- `validation_decision.json`
- `evaluation.json`
- `final.json`
- `report.md` + `report.pdf` (accepted) **or** `rejection.md` (rejected)

This is intentional: a reviewer can trace exactly what happened and why.

## Trade-offs (deliberate)

- **Validator simplicity over clever NLP**: the deterministic rules are intentionally explicit and auditable.
- **Mock-first provider**: a working repo without paid APIs is more useful than a "requires key" demo.
- **Small module boundaries**: orchestration, validation, evaluation, export, and storage are separated so they can be tested independently.
