# Validation rules (CHR v1)

Validation is the authority in this repository.

The provider draft is not "the answer" — it is input to a deterministic decision system.

Implemented in `app/validators/chr_v1_validator.py`.

## Rule categories

## 1) Evidence must exist

- Every `EvidenceRef(kind="lab", id=...)` must refer to a lab present in the normalized input.
- Missing references produce `VALIDATION_FAILED_UNSUPPORTED_CLAIM`.

## 2) Traceability is mandatory

- `input_fingerprint` and `draft_fingerprint` must be present and non-empty.
- Missing traceability produces `INSUFFICIENT_EVIDENCE`.

## 3) Contradictions are rejected

- For lab findings, if the draft claims a status (`high|low|normal`) that contradicts the normalized interpretation, reject with `VALIDATION_FAILED_CONTRADICTION`.

This is a deliberately conservative rule: if the draft can’t be proven consistent with evidence, it does not pass.

## 4) Critical omissions are rejected

- All abnormal labs (`low` or `high`) must be referenced by at least one lab finding evidence ref.
- Missing abnormal lab coverage produces `VALIDATION_FAILED_CRITICAL_OMISSION`.

## 5) Medical advice is out of scope

This repo is an educational demo, not a clinical system.

- Recommendations must not contain prescriptive "do X now" language (e.g., "start", "stop", "increase dose") unless clearly framed as "discuss with a clinician".
- Violations produce `VALIDATION_FAILED_UNSUPPORTED_CLAIM`.

## Failure taxonomy

See `app/models/failures.py` for the full set of failure codes used across the workflow.

