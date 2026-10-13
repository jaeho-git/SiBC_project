# Architecture

```text
User Data
  ↓
Cross-Validation Layer (upstream eligibility/provenance only)
  ↓
Clinical Layer
  ├── Clinical Diagnosis Engine → DiagnosisCandidate (not downstream-eligible)
  └── Clinical Validation Model
       ├── contract/rule integrity
       ├── evidence linkage + temporal/data-quality gates
       ├── exclusions/contradictions/candidate-set conflicts
       ├── score + decision-stability metadata + CDEI
       └── ValidatedClinicalOutput + handoff permission
  ↓
Profile / Behavior Layer (only when operational rule and status permit)
```

The module is not exposed as a separate system Workflow layer. Reliability Model
logic and scores are not imported or combined.

The engine is pure and deterministic for a candidate, criteria set, evidence-link
snapshot, rule registry, and policy version. The release-only pipeline adds fixture
generation, artifact immutability checks, safety-first comparison/selection,
PNG/SVG and MD/DOCX reporting, privacy scanning, checksum verification, and atomic
publication. Dev/stg execution and fallback are disabled.
