# Draft data contract

No production Clinical Layer schema was found. The prototype contract below is a
mock adapter contract, not an operating API.

## DiagnosisCandidate

Required fields include candidate/case/scenario ID, taxonomy, opaque diagnosis
reference, exactly one applied rule ID/version, source evidence IDs,
`index_datetime`, observation window, structured reasoning trace, priority,
coexistence/mutual-exclusion references, upstream validation status, and origin.

Candidates are intermediate objects. They cannot be written to Profile or sent to
Behavior before validation.

## CriterionAssessment

Each item has criterion ID, feature ID, role, state (`MET`, `NOT_MET`, or
`NOT_ASSESSABLE`), linked evidence IDs, and rationale code. Candidate summary
fields such as `criteria_met` are claims and are not trusted as an oracle.

## EvidenceItem / EvidenceLink

The fixture keeps evidence metadata separate from links. Required metadata includes
timestamp, source, unit, quality, upstream status, eligibility, provenance, and
origin. Raw actual values are not required for gate testing and are not copied into
run registries.

## ValidatedClinicalOutput

Contains the seven-state validation decision; score, confidence, and CDEI as
separate objects; recomputed criteria sets; quality issues; blockers; limitations;
human review; candidate-set summary; Profile permission; Behavior permission; and
decision/input/rule provenance.

`expected_*` fixture fields are excluded by the allowlisted domain constructors.

Every published contract uses `environment=release`. Public execution modes are
`release_artifact`, `release_db`, and `synthetic_fixture`; internal policy dispatch
may continue to use the shorter `artifact`, `db`, and `fixture` keys.
