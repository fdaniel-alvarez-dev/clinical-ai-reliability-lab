#!/usr/bin/env bash
set -euo pipefail

DATASET_PATH="${1:-datasets/case_01_stable_patient.json}"

curl -sS -X POST "http://localhost:8000/v1/reports/generate" \
  -H "Content-Type: application/json" \
  --data-binary "@${DATASET_PATH}" | python -m json.tool

