# Clinical Rule Candidates

## Candidate-set metadata

- `scope`: Research-only validation gates for upstream Clinical Diagnosis Engine candidates
- `accessed_at`: `2026-08-06`
- `rule_set_status`: `RESEARCH_ONLY`
- `operational_approval`: `NOT_GRANTED`
- `operation_gate`: `BLOCKED_BY_CLINICAL_REVIEW`
- `profile_write_allowed`: `false`
- `behavior_handoff_allowed`: `false`

These are validator design candidates, not diagnostic criteria. No NANDA-I diagnosis content, Omaha definitions, medical thresholds, or patient-specific diagnosis rules are included. Every candidate below is blocked from operation.

## Required rule envelope

```yaml
rule_id: CLV-RC-XXXX
taxonomy: NANDA_I | OMAHA | TAXONOMY_AGNOSTIC
taxonomy_source_ids: []
taxonomy_version: null
rule_version: 0.1.0
status: RESEARCH_ONLY

applicability:
  population: []
  clinical_context: []
  exclusions: []

source_threshold: null
normalized_threshold: null
clinical_interpretation: null
sibc_operational_threshold: null

required_evidence_schema: []
supporting_evidence_schema: []
contradictory_evidence_schema: []
temporal_requirements: null
measurement_requirements: null

provenance:
  source_ids: []
  source_version: null
  accessed_at: 2026-08-06
  license_status: UNKNOWN
  clinical_review_status: NOT_REVIEWED

operation_gate: BLOCKED_BY_RULE_DEFINITION
profile_write_allowed: false
behavior_handoff_allowed: false
```

Null thresholds are intentional. Literature values must not become SiBC thresholds without normalization documentation and clinical approval.

## Candidate register

Shared status for `CLV-RC-0001` through `CLV-RC-0018`:

```yaml
status: RESEARCH_ONLY
operational_status: OPERATION_BLOCKED
clinical_review_status: NOT_REVIEWED
profile_write_allowed: false
behavior_handoff_allowed: false
```

| rule_id | taxonomy | research-only validation intent | required inputs | candidate outcome | source basis | blocking condition / status |
|---|---|---|---|---|---|---|
| `CLV-RC-0001` | Taxonomy agnostic | Require taxonomy name, current source version, source ID, access date, rule version, and provenance before evaluation. | Candidate metadata and source registry | Missing metadata yields `BLOCKED_BY_RULE_DEFINITION`. | `NANDA-OFFICIAL-001`, `OMAHA-OFFICIAL-001` | Always `RESEARCH_ONLY`; operation blocked until schema and source review pass. |
| `CLV-RC-0002` | NANDA-I | Prevent use of any non-synthetic NANDA-I content unless the signed license explicitly covers stored fields and software purpose. | License artifact ID, permitted fields/use, effective dates, taxonomy version | Missing or mismatched rights yields `BLOCKED_BY_LICENSE`. | `NANDA-LICENSE-001`, `NANDA-TERMS-001`, `NANDA-PUBLISHER-002` | `BLOCKED_BY_LICENSE`; no automatic override. |
| `CLV-RC-0003` | Omaha | Verify that an Omaha reference follows the canonical component hierarchy and current official counts without renaming or merging elements. | Canonical code/reference, component, parent reference, pinned source version | Structural mismatch yields `BLOCKED_BY_RULE_DEFINITION`. | `OMAHA-PCS-001`, `OMAHA-INTERVENTION-001`, `OMAHA-PRSO-001` | `BLOCKED_BY_CLINICAL_REVIEW`; structural pass is not clinical approval. |
| `CLV-RC-0004` | Taxonomy agnostic | Check source applicability before any evidence sufficiency decision. | Source population, setting, age range, clinical context, candidate context | Unknown or mismatched applicability yields `REVIEW_REQUIRED` or `INSUFFICIENT_EVIDENCE`. | `NANDA-RESEARCH-001`, `NANDA-METHOD-001`, `OMAHA-REVIEW-001` | No operational population/context has been approved. |
| `CLV-RC-0005` | Taxonomy agnostic | Require each evidence item to be traceable to an observed or approved derived value. | Evidence ID, source, timestamp, unit, quality, provenance, upstream eligibility | Missing provenance or upstream rejection yields `BLOCKED_BY_UPSTREAM_VALIDATION`. | Official governance sources; SiBC architecture requirement | `RESEARCH_ONLY`; upstream scores must not be added to the clinical score. |
| `CLV-RC-0006` | Taxonomy agnostic | Enforce time direction and observation-window consistency. | Index time, measurement time, lookback/freshness window, intervention time | Future evidence, stale evidence, or post-intervention leakage yields `TEMPORAL_MISMATCH` and review. | `NANDA-METHOD-002`; SiBC temporal policy | Observation windows and freshness limits remain null pending approval. |
| `CLV-RC-0007` | Taxonomy agnostic | Separate required, supporting, contradictory, and exclusion evidence; hard-gate missing required evidence and exclusions. | Versioned evidence-role definitions and matched evidence | Required evidence missing: `INSUFFICIENT_EVIDENCE`; exclusion present: `CONTRADICTED` or `REVIEW_REQUIRED`. | `NANDA-METHOD-001`, `NANDA-DIFF-001` | No diagnosis-specific evidence roles are licensed or clinically approved. |
| `CLV-RC-0008` | Omaha | Check internal consistency between the selected problem modifier and the type of documented evidence without inventing medical thresholds. | Canonical problem reference, modifier axes, observed evidence type | Inconsistent modifier/evidence representation yields `REVIEW_REQUIRED`. | `OMAHA-PCS-001`, `OMAHA-CASE-001` | Formal mapping criteria are undefined; `BLOCKED_BY_RULE_DEFINITION`. |
| `CLV-RC-0009` | Omaha | Prevent PRSO Knowledge/Behavior/Status ratings from being used as diagnosis probability, validator confidence, or CDEI. | Field lineage and score semantic type | Misuse yields `INVALID_SCORE_SEMANTICS` and blocks handoff. | `OMAHA-PRSO-001`, `OMAHA-VAL-001` | Always enforced as a safety guard; clinical use of PRSO still requires review. |
| `CLV-RC-0010` | Taxonomy agnostic | Evaluate explicit contradictory evidence and competing candidates without selecting a new diagnosis. | Candidate set, contradiction links, exclusion links, mapping provenance | Unresolved conflict yields `REVIEW_REQUIRED`; validator must not generate a replacement diagnosis. | `NANDA-DIFF-001` | Conflict pairs are undefined and unapproved. |
| `CLV-RC-0011` | NANDA-I + Omaha | Prohibit automatic cross-taxonomy equivalence and require versioned mapping relation plus independent adjudication. | Source/target versions, relation type, two reviewer decisions, adjudication | Missing review or ambiguous mapping yields `NANDA_OMAHA_CROSS_TAXONOMY_OVERLAP` and blocks handoff. | `CROSSMAP-001`, `NANDA-ROADMAP-001` | No official current crosswalk identified; `BLOCKED_BY_CLINICAL_REVIEW`. |
| `CLV-RC-0012` | Taxonomy agnostic | Require the evaluation reference standard to be independent of both diagnosis engine output and validator output. | Reference-standard source, acquisition time, blinding/independence metadata | Circular or absent standard yields `BLOCKED_BY_REFERENCE_STANDARD`. | `NANDA-METHOD-001`, `NANDA-PRIMARY-001` | Reference standards are not yet defined for any rule. |
| `CLV-RC-0013` | Taxonomy agnostic | Keep implementation data quality separate from taxonomy validity. | Missingness, unit validity, duplicate state, timestamp quality, rater consistency | Material quality failure yields `REVIEW_REQUIRED` or `INSUFFICIENT_EVIDENCE`. | `OMAHA-DQ-001`; SiBC data-quality policy | Thresholds remain undefined; no operational quality cutoff approved. |
| `CLV-RC-0014` | Taxonomy agnostic | Enforce score semantics: validation score is criteria satisfaction, model confidence is decision stability, and CDEI is explainability completeness. | Score name, derivation, range, limitations | Probability-like labeling or unsupported aggregation yields `INVALID_SCORE_SEMANTICS`. | SiBC architecture; official PRSO distinction | Formulas and cutoffs remain unapproved. |
| `CLV-RC-0015` | Taxonomy agnostic | Require a complete, human-readable reasoning trace without exposing protected taxonomy content. | Rule/source IDs, evidence links, gates, contradictions, limitations, decision | Missing trace yields `REVIEW_REQUIRED`; protected text leakage yields `BLOCKED_BY_LICENSE`. | Licensing register and SiBC explainability requirement | Trace template only; no operational content. |
| `CLV-RC-0016` | Taxonomy agnostic | Block profile write and Behavior Layer handoff unless license, rule, clinical, reference-standard, and contract gates all pass. | All gate statuses and explicit human approval | Any non-approved state sets both handoff flags false. | Official licensing/governance sources; SiBC contract | Default and current state is blocked. |
| `CLV-RC-0017` | Taxonomy agnostic | Keep synthetic Clinical Layer outputs physically and logically separate from real user measurements. | `data_origin`, storage path, run mode, identifier policy | Mixed or unknown origin yields `BLOCKED_BY_DATA`. | SiBC synthetic-data requirement | Only synthetic opaque taxonomy references are allowed in the prototype. |
| `CLV-RC-0018` | Taxonomy agnostic | Detect source edition, website snapshot, license, or local-rule drift and invalidate stale approvals. | Source checksum/date, edition, license version, rule checksum | Drift yields `SOURCE_VERSION_CHANGED` and returns rule to review. | `NANDA-ROADMAP-001`, `OMAHA-OFFICIAL-001` | Reapproval workflow not yet implemented; operation blocked. |

## Prohibited candidate behavior

The validator must not:

- generate a new patient diagnosis;
- infer a diagnosis from a medical checkup reference range alone;
- use prediction or risk-model output as diagnostic evidence;
- convert article sensitivity, specificity, likelihood ratios, expert scores, or prevalence into a patient probability;
- compensate for a failed hard gate through weighted averaging;
- combine Reliability Model or Cross-Validation scores with Clinical Validation scores;
- use Omaha PRSO as validation confidence;
- expose unlicensed NANDA-I content in logs, fixtures, reports, or error messages;
- activate a NANDA–Omaha mapping through string similarity;
- permit profile write or Behavior Layer handoff while any gate is unknown, research-only, or blocked.

## Approval requirements

Every rule remains blocked until all of the following are recorded:

```text
source/version verified
AND license permits exact stored content and purpose
AND rule definition is complete
AND applicable population/context is explicit
AND measurements, units, and temporal windows are approved
AND independent reference standard is approved
AND contradiction/exclusion/conflict logic is approved
AND two qualified clinical reviewers approve
AND synthetic and regression tests pass
AND external Clinical Layer contract is confirmed
```

Passing prototype tests alone cannot change a rule from `RESEARCH_ONLY` to an operational state.
