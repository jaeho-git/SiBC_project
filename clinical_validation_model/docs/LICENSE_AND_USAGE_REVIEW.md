# License and Usage Review

## Review metadata

- `scope`: NANDA-I and Omaha System use in the SiBC Clinical Validation Model prototype
- `accessed_at`: `2026-08-06`
- `review_type`: Research-stage rights and usage assessment; not legal advice
- `overall_status`: `OPERATION_BLOCKED`
- `required_next_reviews`: `FORMAL_LICENSE_REVIEW`, `CLINICAL_GOVERNANCE_REVIEW`, `SECURITY_AND_PRIVACY_REVIEW`

## Executive decision

| taxonomy / material | rights position established from official source | prototype allowance | operation gate |
|---|---|---|---|
| NANDA-I bibliographic and edition metadata | May be cited with attribution | Store source ID, title, edition, publisher, URL, access date, and license state | `RESEARCH_ONLY` |
| NANDA-I diagnosis content, definitions, indicators, taxonomy tables, mappings, or derived rule set | Protected IP; systematic digital reuse, software/database/EHR/decision-support integration, text mining, and commercial use require written authorization or formal licensing | Do not store or extract; use synthetic opaque placeholders only | `BLOCKED_BY_LICENSE` |
| NANDA® name and marks | Trademark use is limited to identifying the source and must not imply endorsement or affiliation | Factual source attribution only; do not use in product/feature branding | `BLOCKED_BY_LICENSE` if branding or endorsement risk exists |
| Omaha System terms, definitions, and codes | Official FAQ states they are public domain and may be used without permission or fee, provided the structure is used as published and a reliable source is cited | May be represented canonically with provenance | `BLOCKED_BY_CLINICAL_REVIEW` |
| Omaha System User’s Guide, case narratives, book explanations, examples, and other protected book sections | Outside the official public-domain term/definition/code scope and copyrighted by Health Connections Press | Do not copy; paraphrase only where necessary and seek permission for reuse | `BLOCKED_BY_LICENSE` for protected material |
| Peer-reviewed articles | Bibliographic citation and limited paraphrase only unless the article license permits more | Store citation metadata and scoped methodological claims | `RESEARCH_ONLY` |

## Controlling official sources

### NANDA-I / INKA

- [Current 2024–2026, 13th-edition reference](https://nanda.org/nanda-book/)
- [INKA Use and Licensing](https://nanda.org/use-and-licensing/)
- [INKA Terms of Use](https://nanda.org/terms-and-conditions/)
- [Permissions and licensing contact](https://nanda.org/contact-us/): `admin@nanda.org`
- [Thieme digital licensing information](https://try-medone.thieme.com/medone-education/nanda-i/)

### Omaha System

- [Official overview and current reference](https://www.omahasystem.org/overview)
- [Official FAQ: public-domain scope and copyright boundary](https://www.omahasystem.org/faq)
- [Problem Classification Scheme](https://www.omahasystem.org/problemclassificationscheme)
- [Intervention Scheme](https://www.omahasystem.org/interventionscheme)
- [Problem Rating Scale for Outcomes](https://www.omahasystem.org/problemratingscaleforoutcomes)

## Required safeguards

### NANDA-I safeguards

1. Do not scrape, mine, transcribe, index, or systematically extract content from the official site, book, sample pages, or unauthorized copies.
2. Do not commit diagnosis definitions, diagnostic indicators, related/risk factors, taxonomy tables, or derived mappings to the repository without a signed license covering this exact use.
3. Buying a print/ebook copy or an authorized Korean translation is reference access, not software reuse permission.
4. Store an auditable license artifact with parties, territory, version, permitted fields, permitted environments, redistribution terms, duration, and termination obligations.
5. Do not name the model, module, API, or UI in a manner that implies INKA sponsorship, approval, or affiliation.
6. Until the signed scope is verified, use:

```yaml
taxonomy: NANDA_I
taxonomy_version: "2024-2026_13th"
diagnosis_reference: SYNTHETIC_OPAQUE_REFERENCE
status: RESEARCH_ONLY
license_status: LICENSE_REVIEW_REQUIRED
operation_gate: BLOCKED_BY_LICENSE
profile_write_allowed: false
behavior_handoff_allowed: false
```

### Omaha System safeguards

1. Use official terms, definitions, and codes only in the canonical hierarchy and with citation to Martin (2005) or the official website.
2. Do not claim that local thresholds, wearable metrics, checkup reference ranges, or evidence mappings are official Omaha criteria.
3. Keep canonical taxonomy data separate from SiBC operational rules and from client-specific free text.
4. Do not copy protected User’s Guide material, book explanations, or case narratives merely because the terminology itself is public domain.
5. Pin `Martin 2005 Reprinted 2nd ed + official website snapshot 2026-08-06`; do not invent a “2026 edition.”
6. Public-domain status does not remove the need for clinical review, local validation, security controls, or compliance with Korean law.

```yaml
taxonomy: OMAHA
source_version: "Martin_2005_Reprinted_2nd+official_web_2026-08-06"
status: RESEARCH_ONLY
license_status: PUBLIC_DOMAIN_TERMS_ONLY
clinical_review_status: NOT_REVIEWED
operation_gate: BLOCKED_BY_CLINICAL_REVIEW
profile_write_allowed: false
behavior_handoff_allowed: false
```

## Translation and localization

- An officially listed translation is not permission to extract it into software.
- Preserve the canonical source code and source-language term separately from a localized display string.
- Record translator/publisher, edition, license, locale, and review status.
- Do not produce an unofficial Korean NANDA-I or Omaha translation by machine translation and represent it as canonical.
- Differences between source and localized terms require bilingual clinical adjudication and regression tests.

## Cross-taxonomy mapping

No official current NANDA-I–Omaha crosswalk was identified on the official sources reviewed. A local crosswalk must therefore be an independent, versioned research artifact:

```yaml
mapping_status: RESEARCH_ONLY
mapping_relation: exact | narrower | broader | related | no_map
source_taxonomy_version: required
target_taxonomy_version: required
reviewers_required: 2
adjudication_required: true
automatic_equivalence_allowed: false
operation_gate: BLOCKED_BY_CLINICAL_REVIEW
```

String similarity, shared evidence, or a UMLS/SNOMED intermediary must not be treated as semantic equivalence. Version-specific mapping evidence is incomplete and does not transfer content rights.

## Safe public wording

### NANDA-I

> This prototype does not reproduce or distribute the NANDA-I classification. It stores only bibliographic/version metadata and synthetic opaque references. Any use of NANDA-I labels, definitions, diagnostic indicators, mappings, or derived rules remains `RESEARCH_ONLY` and `BLOCKED_BY_LICENSE` until written authorization and independent clinical governance approval are documented. SiBC is not affiliated with or endorsed by INKA.

### Omaha System

> This prototype references the public-domain Omaha System terms, definitions, and codes as published in Martin (2005) and the official Omaha System website. The canonical structure is not modified. SiBC evidence mappings, thresholds, conflict rules, and validation decisions are local research artifacts—not official Omaha System criteria—and remain `RESEARCH_ONLY` pending clinical review.

### Clinical-purpose limitation

> The module validates an upstream diagnosis candidate. It does not diagnose a person or estimate disease, diagnosis, risk, or prognosis probability. No profile write or Behavior Layer handoff is allowed until source version, evidence provenance, license status, independent reference standard, and clinical approval are complete.

## Release checklist

Every item must be true before any taxonomy-backed rule can move beyond research:

- [ ] Current source edition/version and access date are pinned.
- [ ] Intended fields and digital use are covered by a signed license where required.
- [ ] Trademark and attribution language has been reviewed.
- [ ] Canonical taxonomy content is separated from local operational logic.
- [ ] Population, clinical context, measurement method, units, and time window are explicit.
- [ ] Reference standard is independent of the diagnosis engine and validator.
- [ ] Two qualified clinical reviewers approved the rule and conflict logic.
- [ ] Local reliability, data-quality, fairness, and regression tests passed.
- [ ] Human override, audit trail, rollback, and incident response are implemented.
- [ ] `profile_write_allowed` and `behavior_handoff_allowed` were explicitly approved.

If any item is false or unknown, the rule remains `RESEARCH_ONLY` and operation remains blocked.
