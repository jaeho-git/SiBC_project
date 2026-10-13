# Medical Checkup reuse analysis

Reused conventions: exact-one-environment selection, redacted environment summary,
read-only DB defense in depth, allowlisted SQL concept, SHA-256 artifacts, run IDs,
environment result namespaces, manifest/checksum/ledger layout, `actual_*` versus
`measured_*` versus `pred_*` naming, and performance-unavailable reporting.

Direct in-place reuse is limited because the sibling config and scripts contain an
absolute project root and the existing SQL regex is not sufficient as a standalone
security boundary. The adapter directly reuses the sibling SHA-256 function when
available and otherwise remains portable. Clinical managed SQL adds exact file
allowlisting, schema-qualified relations, function blocking, post-validation hash
checking, repeatable-read, explicit timezone, query limits, and TLS verification.

Prediction/training logic and medical prediction/risk outputs are deliberately not
reused.

