# Model card

## Identity and placement

- Name: `clinical_validation_model`
- Version: `0.1.0`
- Placement: independent validation module inside the SiBC Clinical Layer
- Type: deterministic rule-engine technical prototype

## Intended use

Validate whether an upstream diagnosis candidate is traceable to an eligible,
temporally aligned, quality-controlled evidence set and an approved versioned
rule. The module also discloses contradictions, candidate-set conflicts,
limitations, and downstream permission.

## Out of scope

- generating a nursing or medical diagnosis;
- estimating disease, diagnosis, prognosis, or individual risk probability;
- replacing professional review;
- combining Reliability Model or Cross-Validation scores;
- using medical-checkup `pred_*` or `risk_*` outputs as measured evidence;
- claiming clinical performance from synthetic cases.

## Data

The baseline uses deterministic synthetic Clinical Layer output. Artifact mode
fingerprints existing pseudonymized medical-checkup artifacts before and after
execution without writing to them. No raw identifier or source row is copied to
the run output.

Only the `release` environment is executable. Dev/stg fallback is disabled, and
the source artifacts are re-fingerprinted immediately before atomic publication.

## Metrics

`clinical_validation_score`, `model_decision_confidence`, and `cdei_score` have
different meanings and are never combined. Confidence is explicitly
`NOT_CALIBRATED` and published as `0.0` per prototype policy. None is a clinical
probability or accuracy metric.

## Safety gates

Required criteria, applicability, exclusions, contradictions, rule integrity,
upstream eligibility, and temporal leakage cannot be compensated by an average
score. Test-only rules cannot write a Profile or hand off to Behavior.

## Validation status

- Technical fixture oracle: implemented
- Release comparison/visualization package: implemented
- Real-world clinical performance: `BLOCKED_BY_REFERENCE_STANDARD`
- NANDA operational rules: `BLOCKED_BY_LICENSE`
- Omaha operational mappings/thresholds: `BLOCKED_BY_CLINICAL_REVIEW`
- Production contract: `BLOCKED_BY_CLINICAL_LAYER_CONTRACT`
