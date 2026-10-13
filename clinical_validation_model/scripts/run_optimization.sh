#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# This cycle may correct implementation defects only; it never edits clinical rules.
uv run pytest
uv run python -m sibc_clinical_validation.cli run --data-env release --mode artifact
