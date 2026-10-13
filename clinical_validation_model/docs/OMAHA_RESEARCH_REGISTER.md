# Omaha System Research Register

## Register metadata

- `register_scope`: Omaha System structure, version, use conditions, and validation evidence for the SiBC Clinical Validation Model
- `accessed_at`: `2026-08-06`
- `all_source_rows.accessed_at`: `2026-08-06`
- `current_reference`: Martin, K. S. (2005), *The Omaha System: A Key to Practice, Documentation, and Information Management* (Reprinted 2nd ed.) plus the official website snapshot
- `canonical_source_version`: `Martin 2005 Reprinted 2nd ed + official website snapshot 2026-08-06`
- `default_rule_status`: `RESEARCH_ONLY`
- `default_license_status`: `PUBLIC_DOMAIN_TERMS_ONLY`
- `default_clinical_review_status`: `NOT_REVIEWED`
- `default_operation_gate`: `BLOCKED_BY_CLINICAL_REVIEW`

The official website does not publish a semantic version that would justify calling the terminology “Omaha 2026.” The website copyright year is not a taxonomy version. This register therefore pins the current book and an access-dated official website snapshot.

## Official sources

| source_id | title / organization | year / edition | source_type / official_status | url_or_identifier | applicable_population / clinical_context | evidence_level | license_status / allowed_use | extracted_claims | limitations | review_status |
|---|---|---|---|---|---|---|---|---|---|---|
| `OMAHA-OFFICIAL-001` | Omaha System Overview / The Omaha System | Current site; current book 2005 Reprinted 2nd ed. | Official overview / `OFFICIAL_PRIMARY` | [omahasystem.org/overview](https://www.omahasystem.org/overview) | Individuals, families, and communities across care settings; applicability still requires local review | Official taxonomy overview | `PUBLIC_DOMAIN_TERMS_ONLY`; use as published and cite source | The system comprises three related components: Problem Classification Scheme, Intervention Scheme, and Problem Rating Scale for Outcomes. The official site identifies the 2005 reprinted second edition as the current book. | Official claims of reliability/validity do not establish SiBC implementation performance or Korean cross-cultural validity. | `SOURCE_VERIFIED`; `NOT_APPROVED_FOR_OPERATION` |
| `OMAHA-LICENSE-001` | Frequently Asked Questions / The Omaha System | Current page at access date | Official licensing/use guidance / `OFFICIAL_PRIMARY` | [omahasystem.org/faq](https://www.omahasystem.org/faq) | Practice, education, research, and software | Official rights guidance | Terms, definitions, and codes are stated to be public domain and usable without fee or permission; canonical structure and citation are required | Public-domain scope covers the terms, definitions, and codes. The structure must be used as described in the 2005 book and referenced to the book or official website. | The User’s Guide and other book content are copyrighted by Health Connections Press. Software developers must avoid copying protected guidance/examples and should contact the publisher where necessary. | `SOURCE_VERIFIED`; `LEGAL_SCOPE_REVIEWED`; `CLINICAL_REVIEW_REQUIRED` |
| `OMAHA-PCS-001` | Problem Classification Scheme / The Omaha System | Current page at access date | Official component specification / `OFFICIAL_PRIMARY` | [Problem Classification Scheme](https://www.omahasystem.org/problemclassificationscheme) | Assessment of individuals, families, and communities | Official structural specification | Public-domain canonical structure; cite official source | Four-level hierarchy: four domains, 42 neutral client problems, two modifier axes, and signs/symptoms for actual problems. | This register intentionally omits the full problem list and definitions. Older publications may contain obsolete counts. Risk evidence for a potential modifier must not be invented from local thresholds or presumed to be a controlled official list. | `SOURCE_VERIFIED`; `STRUCTURE_ONLY`; `NOT_APPROVED_FOR_OPERATION` |
| `OMAHA-INTERVENTION-001` | Intervention Scheme / The Omaha System | Current page at access date | Official component specification / `OFFICIAL_PRIMARY` | [Intervention Scheme](https://www.omahasystem.org/interventionscheme) | Interprofessional care plans and services | Official structural specification | Public-domain canonical structure; cite official source | Three levels: four categories, 75 targets plus “other,” and client-specific information. | This register omits targets and definitions. Client-specific information must not be mistaken for a standardized term. Older studies with smaller target counts are not current structural authorities. | `SOURCE_VERIFIED`; `STRUCTURE_ONLY`; `NOT_APPROVED_FOR_OPERATION` |
| `OMAHA-PRSO-001` | Problem Rating Scale for Outcomes / The Omaha System | Current page at access date | Official component specification / `OFFICIAL_PRIMARY` | [Problem Rating Scale for Outcomes](https://www.omahasystem.org/problemratingscaleforoutcomes) | Problem-specific change during a period of service | Official outcome-measure structure | Public-domain canonical structure; cite official source | Uses three five-point scales for Knowledge, Behavior, and Status at regular or predictable times. | PRSO is an outcome/change measure, not diagnostic confidence, rule validity, CDEI, or `clinical_validation_score`. Detailed rating guidance in protected book sections must not be copied without review. | `SOURCE_VERIFIED`; `STRUCTURE_ONLY`; `NOT_APPROVED_FOR_OPERATION` |
| `OMAHA-CASE-001` | Case Studies Introduction / The Omaha System | Current page at access date | Official teaching guidance / `OFFICIAL_CONTEXTUAL` | [omahasystem.org/casestudies](https://www.omahasystem.org/casestudies) | Training and discussion | Expert teaching examples, not a formal reference standard | Cite at high level; do not reproduce cases without rights review | Expert “best answers” are intended for discussion and may change with the practice setting. | Cases are not an independent gold standard for automated validation. Website cases and book examples are not within the clearly stated public-domain term/code scope. | `SOURCE_VERIFIED`; `TEACHING_ONLY`; `NOT_APPROVED_FOR_OPERATION` |
| `OMAHA-REFS-001` | References / The Omaha System | Current page at access date | Official bibliography index / `OFFICIAL_DISCOVERY_SOURCE` | [omahasystem.org/references](https://www.omahasystem.org/references) | Broad practice, education, informatics, and research | Discovery index; no uniform evidence grade | Bibliographic discovery and citation | The page indexes hundreds of Omaha-related publications and identifies sources containing complete terms/codes. | Listing is not endorsement, quality appraisal, local validation, or operational approval. Each study requires independent appraisal. | `SOURCE_VERIFIED`; `DISCOVERY_ONLY` |

## Current canonical structure for schema validation

Only the following high-level structure is approved for research schema checks:

```text
Problem Classification Scheme
  domain -> problem -> modifier axes -> actual signs/symptoms

Intervention Scheme
  category -> target -> client-specific information

Problem Rating Scale for Outcomes
  problem-specific Knowledge / Behavior / Status ratings
```

The prototype must not:

- add, rename, merge, or reorder canonical Omaha elements;
- label local evidence thresholds as official Omaha criteria;
- use PRSO values as diagnosis probability or validator confidence;
- use a website copyright year as a taxonomy version;
- use counts or structures from older articles when they conflict with the current official site.

## Peer-reviewed validation and implementation sources

For every article below, `license_status=ARTICLE_RIGHTS_APPLY` and `allowed_use=BIBLIOGRAPHIC_CITATION_AND_SCOPED_PARAPHRASE_ONLY` unless a separately verified article license permits more.

| source_id | title / authors | year | source_type | url_or_identifier | applicable_population / clinical_context | evidence_level | extracted_claims | limitations | review_status |
|---|---|---:|---|---|---|---|---|---|---|
| `OMAHA-VAL-001` | *Psychometric analysis of the Problem Rating Scale for Outcomes* / Martin, Norris, Leak | 1999 | Peer-reviewed psychometric study | [Institutional record; PMID 9934194](https://researchworks.creighton.edu/esploro/outputs/journalArticle/Psychometric-analysis-of-the-problem-rating/991005929004902656) | PRSO knowledge, behavior, and status subscales | Primary psychometric evidence | Evaluated inter-rater reliability and content validity of PRSO subscales. | Old study; does not replace local rater training, current implementation checks, or cross-cultural validation. | `EVIDENCE_REVIEWED`; `RESEARCH_ONLY` |
| `OMAHA-REVIEW-001` | *The Omaha System: a systematic review of the recent literature* / Topaz, Golfenshtein, Bowles | 2014 | Peer-reviewed systematic review | [PubMed PMID 23744786](https://pubmed.ncbi.nlm.nih.gov/23744786/); [DOI](https://doi.org/10.1136/amiajnl-2012-001491) | Publications from 2004–2011 across practice, research, and education | Secondary evidence | Found a substantial literature base and identified needs for international/cultural validation, education, implementation, and interoperability research. | Search period is historical; current taxonomy structure must come from the official website, not counts reported in the review. | `EVIDENCE_REVIEWED`; `RESEARCH_ONLY` |
| `OMAHA-DQ-001` | *The Feasibility of Integrating the Omaha System Data Across Home Care Agencies and Vendors* / Westra et al. | 2010 | Peer-reviewed multisite implementation study | [DOI](https://doi.org/10.1097/NCN.0b013e3181d7812c); [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC3090219/) | 15 home-care agencies and multiple vendors | Primary implementation evidence | Demonstrated integration feasibility while identifying missing data and concerns about outcome-rating validity/documentation consistency. | Home-care context and older systems; demonstrates the need for data-quality gates rather than current SiBC performance. | `EVIDENCE_REVIEWED`; `RESEARCH_ONLY` |
| `OMAHA-TRENDS-001` | *Research Types and New Trends on the Omaha System Published From 2012 to 2019* / Tomotaki, Iwamoto, Yokota | 2022 | Peer-reviewed scoping review | [PubMed PMID 35929744](https://pubmed.ncbi.nlm.nih.gov/35929744/); [DOI](https://doi.org/10.1097/CIN.0000000000000887) | Omaha System research published 2012–2019 | Secondary evidence | Characterizes use in client problems, clinical process, outcomes, classification research, structured data, and information systems. | Trend mapping is not clinical validation or evidence for any SiBC operational threshold. | `EVIDENCE_REVIEWED`; `RESEARCH_ONLY` |
| `CROSSMAP-001` | *An examination of the coverage of the SNOMED CT coded nursing problem list subset* / Kim et al. | 2019 | Peer-reviewed terminology mapping study | [DOI](https://doi.org/10.1093/jamiaopen/ooz023) | Version-specific mappings among recognized nursing terminologies and SNOMED CT | Primary exploratory mapping evidence | Reports incomplete and equivocal coverage, supporting explicit mapping relations, versioning, and manual adjudication. | Uses historical releases and is not a current NANDA–Omaha crosswalk. It cannot authorize NANDA content reuse. | `EVIDENCE_REVIEWED`; `RESEARCH_ONLY` |

## Safe implementation interpretation

1. Preserve canonical Omaha codes and structure in a read-only reference layer.
2. Store SiBC measurement mappings, time windows, contradictions, and thresholds in a separate local rule layer.
3. Require source/version provenance and clinical review for every local mapping.
4. Keep taxonomy validity, implementation reliability, data quality, and validator performance as separate claims.
5. Keep all rules `RESEARCH_ONLY` until local clinical governance approves the exact population, setting, measurements, and intended action.
