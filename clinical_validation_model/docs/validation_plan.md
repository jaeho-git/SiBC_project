# Validation plan

## Technical baseline

Run the deterministic 19-scenario matrix and compare 23 candidate results against
an independently declared technical oracle. Validate schema, rule integrity, status
precedence, hard gates, temporal leakage, conflicts, CDEI faithfulness, output
permissions, determinism, secret scanning, and source artifact immutability.

## Regression acceptance

An implementation change is acceptable only when safety/hard-gate/leakage/secret
tests do not regress, all oracle comparisons pass, source artifacts remain unchanged,
and no clinical definition, threshold, exclusion, intended use, or licensing state
is changed automatically.

All comparisons use the same release snapshot, Scenario Matrix, rule set, feature
version, generator version, and source hash. A candidate is rejected on any source,
privacy, unsafe-pass, leakage, hard-gate, oracle, or reproducibility regression.
With no safe measurable improvement, two consecutive candidate cycles are rejected
and the baseline is retained as the final-selected presentation slot.

## Release publication

Only `release` may execute. The staging run must contain the governed comparison
CSV/Parquet/Markdown, 12 PNG/SVG figure pairs, figure manifests, interpretation
MD/DOCX, automation summary, and final selection. The pipeline then rechecks source
artifacts and code hash, performs a final text/Parquet/SVG/DOCX privacy scan,
registers and verifies SHA-256 checksums, atomically renames the staging directory,
and updates `01_Results/release/latest_run.json`.

## Clinical validation

Requires licensed and clinically approved rules, an intended-use statement,
representative cases, an independent reference standard, blinded adjudication,
predefined acceptance criteria, and prospective/external validation. Until then:

```text
CLINICAL_VALIDATION_STATUS = BLOCKED_BY_REFERENCE_STANDARD
```
