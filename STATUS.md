# APM v1.0 Implementation Status

This file is the compact persistent progress index for unattended execution.

It is **not** evidence by itself. Validation claims must point to committed summaries under `validation/evidence/` or to reproducible commands/tests.

## Overall state

- Project: Analog Process Models (APM)
- Repository: https://github.com/ds54e/analog-process-models
- Target: v1.0.0
- Current state: `NOT_STARTED`
- Current milestone: `M0 Runtime qualification`
- Release eligible: `NO`

## Milestones

| Milestone | Status | Evidence / notes |
| --- | --- | --- |
| M0 Runtime qualification | NOT_STARTED | — |
| M1 APM130 | NOT_STARTED | — |
| M2 APM045 | NOT_STARTED | — |
| M3 APM016F | NOT_STARTED | — |
| M4 Benchmark R/C + variation | NOT_STARTED | — |
| M5 APM022 | NOT_STARTED | — |
| M6 APM350 | NOT_STARTED | — |
| M7 Common characterization completion | NOT_STARTED | — |
| M8 IHP-native variation | NOT_STARTED | — |
| M9 Spectre model-only compatibility | NOT_STARTED | — |
| M10 License/provenance + clean-clone release review | NOT_STARTED | — |

Allowed milestone status values:

- `NOT_STARTED`
- `IN_PROGRESS`
- `VALIDATED`
- `BLOCKED`

Do not mark a milestone `VALIDATED` when its required real-tool checks have not run successfully.

## Validated reference environment

Not yet established.

Record actual validated values when M0 runs:

- WSL version / host context:
- EL9 distribution and version:
- architecture:
- Python version:
- ngspice version/build options:
- OpenVAF-ReLoaded version:
- PSP103 source/revision:
- BSIM-CMG source/revision:

## Release-gate summary

The normative gate definition is `validation/release_gates.toml`.

Current summary: **no v1.0 release gates have been validated yet.**

Do not convert absence of evidence into PASS.

## Current blockers

None recorded yet.

A blocker entry should state:

- affected milestone/gate;
- exact blocker;
- investigation performed;
- compliant alternatives considered;
- whether independent work can continue.

## Material decisions made during implementation

None yet.

Only record decisions that materially affect public API, model provenance/fidelity, characterization semantics, variation semantics, supported runtime, or release claims. Do not use this section as a verbose work diary.

## Evidence index

No implementation evidence yet. See `validation/evidence/README.md` for the evidence format.

## Final-review fields

Complete these only during M10:

- clean clone path/environment:
- clean-clone setup result:
- `apm doctor` result:
- complete test-suite result:
- `apm validate --release` result:
- all-five-kit comparison result:
- provenance/license audit result:
- README claim audit result:
- Spectre status confirmed experimental/unverified:
- final release commit:
- v1.0.0 tag created: NO
