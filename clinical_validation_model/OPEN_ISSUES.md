# Open issues

1. **Production contract** — the actual Clinical Diagnosis Engine candidate schema,
   Profile contract, and Behavior handoff API are not implemented.
2. **Reference standard** — no independently adjudicated clinical case set exists;
   clinical performance remains blocked.
3. **NANDA licensing** — protected terminology/rule content requires written
   permission and independent clinical governance approval.
4. **Omaha operational mapping** — public-domain terminology does not make SiBC
   evidence mappings, thresholds, or conflict rules official or clinically valid.
5. **Survey source** — only a placeholder interface exists.
6. **Artifact quality metadata** — non-wear, sync, permission, device, source app,
   algorithm, timezone, manual-entry, and duplicate flags are unavailable.
7. **DB mode** — managed read-only query and repeatable-read components exist, but
   snapshot extraction remains disabled pending approval and integration tests.
8. **Metric governance** — score weights are prototype-only; confidence has not
   been calibrated; CDEI needs independent explanation review.
9. **Conflict governance** — no approved NANDA/Omaha crosswalk or clinical
   candidate-set adjudication matrix exists.
10. **Repository reproducibility** — the parent worktree was already dirty and
    mostly untracked; run manifests therefore include a source-tree hash.

