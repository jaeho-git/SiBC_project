# Project discovery report

- Repository branch observed: `develop`
- Existing worktree: dirty; user changes preserved
- Root `PROJECT_RULES.md`: empty
- Existing Clinical Validation assets: concept DOCX and presentation manuscript only
- Production Clinical Layer/Profile/Behavior contract: not found
- Medical Checkup prototype: available with env/config/DB/SQL/security/transform/
  pipeline/reporting/tests and two release artifact runs
- Latest medical artifact run: `release_20260730_091530_9a87173`
- Medical model status: `BLOCKED_BY_DATA`; no model binary or valid performance claim

The prototype was added only under `clinical_validation_model`, except for a narrow
root `.gitignore` exception that permits deterministic synthetic fixtures. Existing
medical source and artifact files were not edited.

