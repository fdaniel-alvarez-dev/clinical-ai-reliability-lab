# AGENTS.md

## Mission

Build and maintain `clinical-ai-reliability-lab` as a reliability-first, clinical-like AI system demo that showcases how LLM workflows can be made bounded, observable, testable, and deterministic enough for serious launch-readiness conversations.

This repository is not a chatbot demo.
This repository is not a medical device.
This repository is not a clinical decision system.

It is an engineering portfolio project designed to demonstrate senior-level capability in:
- Python + FastAPI backend design
- workflow orchestration
- deterministic validation
- evaluation pipelines
- observability
- failure-aware architecture
- delivery discipline

## Product thesis

The central design principle is:

> LLMs may draft. Deterministic systems decide.

No agent, contributor, or code path should violate this principle.

---

## Non-negotiable constraints

1. **Synthetic data only**
   - Never use real patient data.
   - Never imply that data came from real clinical sources.
   - All examples must be clearly synthetic.

2. **No medical advice**
   - The system must not present itself as diagnosing, prescribing, or replacing clinicians.
   - This project is educational and architectural.

3. **Fail loudly**
   - The system must reject unsupported outputs explicitly.
   - Polished prose must never hide uncertainty or failure.

4. **Deterministic validation is primary**
   - Model output is advisory input to the validation layer.
   - The validator governs what may pass.

5. **Observability is mandatory**
   - Every important stage should be traceable.
   - A workflow that cannot be inspected is incomplete.

---

## Project goals

This repository should clearly demonstrate:

- bounded LLM orchestration
- structured output handling
- explicit validation rules
- evaluation of accepted vs rejected runs
- reproducibility thinking
- launch-readiness thinking
- API-first backend design
- maintainable engineering decisions

---

## Architecture boundaries

### The system should include

- ingestion and normalization
- workflow orchestration
- provider abstraction
- deterministic validation
- evaluation engine
- artifact export
- observability
- test harness
- documentation
- CI pipeline

### The system should not include

- complex auth
- real EHR integrations
- claims of HIPAA or medical compliance
- unsupported product complexity
- speculative ML research features
- unnecessary frontend polish

Keep the backend architecture coherent and portfolio-grade.

---

## Agent roles

Contributors and autonomous coding agents should behave according to these roles.

### 1. Planner Agent
Responsible for:
- understanding product intent
- decomposing work into coherent phases
- preserving architectural consistency
- preventing random feature drift

Must:
- define clear boundaries
- identify risks early
- keep scope aligned to reliability-first goals

### 2. Backend Agent
Responsible for:
- FastAPI endpoints
- schemas
- services
- orchestration
- storage interactions
- provider interfaces

Must:
- write typed Python
- preserve separation of concerns
- keep handlers thin and services cohesive

### 3. Validator Agent
Responsible for:
- deterministic validation rules
- failure taxonomy
- claim-to-evidence checking
- contradiction detection
- omission detection

Must:
- reject unsupported claims
- keep rules explicit and auditable
- never “soften” failures into vague wording

### 4. Evaluator Agent
Responsible for:
- scoring report quality
- comparing accepted vs rejected outputs
- generating reproducible evaluation artifacts

Must evaluate:
- factual consistency
- completeness
- contradiction risk
- traceability
- repeatability signals

### 5. Observability Agent
Responsible for:
- structured logs
- OpenTelemetry instrumentation
- workflow IDs and correlation IDs
- trace boundaries across major stages

Must:
- instrument important operations
- include meaningful span names
- preserve debuggability

### 6. Docs Agent
Responsible for:
- README
- architecture documentation
- runbook
- decision logs
- validation and evaluation docs

Must:
- explain the why, not just the how
- write clearly for senior reviewers
- highlight accepted vs rejected flows

### 7. DevOps Agent
Responsible for:
- Docker
- local developer experience
- CI pipeline
- repo health

Must:
- keep setup simple
- keep CI trustworthy
- avoid unnecessary platform complexity

---

## Design principles

### 1. Reliability over novelty
A simpler, explainable workflow is better than a clever but opaque one.

### 2. Explicitness over magic
Prefer explicit contracts, schemas, and named failure modes.

### 3. Small composable modules
Avoid monolith files full of mixed concerns.

### 4. Rejection over guessing
If the evidence is insufficient, reject the report.

### 5. Testability as architecture
Code should be structured so validators, evaluators, and orchestration can be tested independently.

### 6. Traceability as a first-class feature
Every important output should be explainable by:
- source data
- workflow step
- validator decision
- evaluation artifact

---

## Coding standards

### Python standards
- Python 3.11+
- use type hints broadly
- use Pydantic v2 for schemas
- keep functions focused
- avoid hidden global state
- prefer explicit dependency injection where useful
- use meaningful exceptions

### Style tools
- Ruff
- Black
- mypy

### API design
- thin route handlers
- business logic in services
- validators isolated from model adapters
- stable JSON response contracts

### File organization
Organize by responsibility, not by random convenience.

Expected core packages:
- `api`
- `models`
- `services`
- `adapters`
- `validators`
- `evaluators`
- `exporters`
- `observability`
- `storage`

---

## Data and schema rules

### Input rules
- input payloads must be synthetic
- timestamps, units, and identifiers should be validated
- canonical normalization should happen before generation

### Output rules
- model output must be structured
- output must conform to schema
- accepted outputs must preserve evidence links or traceable references
- rejected outputs must produce machine-readable reasons

### Artifact rules
Each workflow should generate inspectable artifacts such as:
- normalized input
- model draft
- validation decision
- evaluation summary
- final accepted report or rejection artifact

---

## Deterministic validation philosophy

Validation is the heart of this repository.

The validator must be able to answer questions like:
- Is this statement supported by the source data?
- Did the report omit a critical abnormal finding?
- Is there a contradiction between the narrative and the data?
- Did the output invent a diagnosis or unsupported recommendation?
- Does the structure match the expected schema?

### Validator requirements
- explicit rule definitions
- auditable outcomes
- stable error taxonomy
- no silent acceptance of unsupported claims

### Example failure types
- `VALIDATION_FAILED_UNSUPPORTED_CLAIM`
- `VALIDATION_FAILED_CONTRADICTION`
- `VALIDATION_FAILED_CRITICAL_OMISSION`
- `VALIDATION_FAILED_SCHEMA`
- `INSUFFICIENT_EVIDENCE`

---

## Evaluation philosophy

Evaluation is not optional polish. It is part of system credibility.

Every significant run should be assessable across:
- factual consistency
- completeness
- contradiction risk
- traceability
- reproducibility signals

### Evaluation rules
- separate evaluation logic from validation logic
- make scoring inspectable
- prefer simple explainable scoring over fancy opaque scoring
- compare accepted and rejected cases

### Reproducibility stance
True determinism is limited with LLMs, but the system should still:
- constrain outputs
- validate structure
- measure repeatability
- expose variability instead of hiding it

---

## Observability standards

Observability is mandatory.

### Minimum expectations
- structured logs
- correlation IDs
- workflow IDs
- OpenTelemetry spans around major steps

### Instrument these stages
- ingestion
- normalization
- generation
- validation
- evaluation
- export

### Observability objective
A reviewer should be able to understand:
- what happened
- where it failed
- why it failed
- what artifact proves it

---

## Testing standards

Testing is required for architecture credibility.

### Minimum required test categories
1. unit tests
   - validators
   - evaluators
   - schema normalization
   - failure mapping

2. integration tests
   - API workflow
   - accepted case
   - rejected case

3. evaluation tests
   - completeness penalties
   - contradiction scoring
   - traceability scoring

4. smoke end-to-end test
   - one clean run from input to artifacts

### Testing principles
- tests should prove the architecture, not just syntax
- include both happy path and failure path
- rejected cases are as important as accepted cases

---

## Security and privacy posture

This repo is educational and synthetic-only, but still follow disciplined engineering practices.

### Must do
- use environment variables for secrets
- do not hardcode credentials
- do not commit real sensitive data
- sanitize logs when appropriate
- avoid implying production medical compliance

### Must not do
- fake HIPAA claims
- fake compliance claims
- represent the demo as safe for clinical deployment

---

## Documentation standards

Every substantial architectural choice should be documented.

### Required docs
- `README.md`
- `docs/architecture.md`
- `docs/validation-rules.md`
- `docs/evaluation-methodology.md`
- `docs/observability.md`
- `docs/runbook.md`
- `docs/decision-log.md`

### Documentation style
- explain purpose before mechanism
- use diagrams where useful
- show accepted vs rejected examples
- write for senior reviewers, recruiters, and engineers

---

## CI/CD standards

The CI pipeline must be simple and trustworthy.

### Minimum CI steps
- install dependencies
- lint
- type-check
- run tests

Optional:
- build Docker image

### CI philosophy
A green pipeline should mean the repo is credibly runnable and reviewable.

---

## Definition of Done

A task is done only when:
1. code is coherent and typed
2. relevant tests exist and pass
3. logs/traces are not broken
4. docs are updated if behavior changed
5. architectural boundaries remain intact
6. failure behavior is explicit
7. the result increases repo credibility as a reliability-first AI system

---

## Pull request checklist

Before merging, confirm:
- Does this preserve the “LLMs draft, deterministic systems decide” principle?
- Does this improve reliability or clarity?
- Are failure modes explicit?
- Are tests present?
- Are docs updated?
- Is observability preserved?
- Does this avoid fake medical-product claims?

---

## Final reviewer lens

When in doubt, optimize for this reviewer reaction:

> “This engineer clearly understands that the hard part of applied AI is not generation. It is control, validation, observability, and disciplined delivery.”

That is the bar.
