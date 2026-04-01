# Evaluation methodology

Evaluation is not optional polish in this repo; it is part of credibility. It answers:

- Did validation accept or reject?
- If rejected, what quality signals explain the outcome?
- Is the output traceable and complete with respect to abnormal findings?

Implemented in `app/evaluators/chr_v1_evaluator.py`.

## Core scores

- `factual_consistency`: `1.0` if validation accepted, else `0.0`
- `completeness`: fraction of abnormal labs referenced by evidence
- `traceability`: fraction of findings/recommendations that include evidence refs
- `contradiction_risk`: `1.0` if contradiction issues exist, else `0.0`
- `overall`: weighted combination (bounded to `[0,1]`)

## Why this is simple (on purpose)

This is not ML research. It’s a reliability architecture demo.

Scores are intentionally:
- explainable,
- stable,
- and directly tied to the artifacts a reviewer can inspect.

