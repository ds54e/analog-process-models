# Contributing to Analog Process Models

APM welcomes focused issues and pull requests that improve open compact-model
provenance, terminal characterization, reproducibility, tests, or
documentation within the project's stated scope.

Before a substantial change, open an issue describing the problem, proposed
claim boundary, affected model/family/schema, and validation plan. Keep pull
requests small enough to review and link them to the relevant issue or
evidence.

## Development checks

Use the project-local environment documented in `README.md` and run checks
appropriate to the change. The normal full set is:

```console
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/reuse lint
.venv/bin/apm provenance-check --output .apm/results/provenance
.venv/bin/apm validate --output .apm/results/validation
```

Changes to simulator orchestration, models, or electrical/noise claims also
need relevant real ngspice/OpenVAF/OSDI regression evidence. Do not weaken a
valid test or replace a failed real-tool check with a static-only claim.

## Models, provenance, and claims

- Do not contribute proprietary PDK/model files, official PTM/PTM-MG cards,
  private oracle decks, credentials, or content whose redistribution rights
  are unclear.
- Every new third-party asset requires an authoritative source, exact revision
  and path, file-level license review, retained notices, exact hashes, and an
  updated provenance inventory before it can be shipped.
- Do not introduce foundry/silicon accuracy, calibration, reliability, or
  manufacturing claims without direct evidence adequate for that claim.
- Preserve native geometry: planar devices use `w,l`; FinFET devices use
  `l,nfin`. Do not invent a universal planar/FinFET effective width.
- Keep Spectre claims experimental/unverified unless a real Spectre
  environment supplies reproducible evidence.

Generated OSDI binaries, virtual environments, caches, raw simulator results,
and large derived datasets belong under ignored `.apm/` or other documented
ignored paths and must not be committed.

Contributions should carry Apache-2.0-compatible authorship metadata through
the repository's REUSE configuration. Third-party files retain their own
licenses and must never be silently relicensed.
