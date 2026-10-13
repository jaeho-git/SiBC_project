#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

uv sync --extra test
uv run python -m sibc_clinical_validation.cli preflight --data-env release --mode artifact
uv run python -m sibc_clinical_validation.cli run --data-env release --mode artifact
