# Decision log

This document captures a few deliberate architectural choices.

## 2026-04-01 — Mock-first provider

**Decision:** Default to a deterministic mock provider.

**Why:** Reviewers can run the repo locally without API keys. It also enables a repeatability story where the same input yields the same draft and fingerprints.

**Trade-off:** Mock output is not "model-like". That’s acceptable here because the point is the deterministic control plane, not creative generation.

## 2026-04-01 — Deterministic validator is the authority

**Decision:** The workflow rejects drafts that can’t be validated against evidence.

**Why:** The thesis of this repo is reliability-first orchestration with explicit failure modes.

**Trade-off:** Rules are conservative and may reject drafts that are “probably right”. That is intentional: rejection is better than guessing.

## 2026-04-01 — ReportLab for PDF export

**Decision:** Use ReportLab instead of HTML-to-PDF tooling.

**Why:** ReportLab is a pure-Python dependency and avoids system-level rendering dependencies that complicate local and CI environments.

