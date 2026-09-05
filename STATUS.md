<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM project status

Execution evidence, not this index alone, supports validation and release claims.

## Current mission: v5 full implementation

State: IMPLEMENTATION IN PROGRESS / RELEASE NOT READY.

Current source/runtime/CLI identity is `5.0.0.dev0`. The first implementation
change replaces obsolete maintenance-only assertions with the authorized v5
mission and adds an immutable preflight snapshot audit. All 52 frozen v4 files,
released compatibility checks and model inputs remain protected.

Executed bootstrap validation: `apm validate` passed, including 120 pytest tests
(no skips), Ruff, REUSE, provenance, the 92-check v3 regression and structural
Spectre checks. This is current repository compatibility evidence, not v5
candidate qualification. See `validation/evidence/v5_bootstrap.json` and its
hash-bound raw report under `.apm/v5/bootstrap-validation/`.

No measured research profile is approved. Controlled checkout of the required
OpenVAF commit succeeded; compiler build and provenance repair are in progress.
No v5 tag or release exists or is authorized by this implementation task.

## Completed preflight baseline

Commit: `bbb585306f13614b7649c36dd5b7510c845daed9`.
Reports: `validation/evidence/v5_preflight_findings.json` and
`validation/evidence/v5_preflight_source_audit.md`.

| Subject | Recorded result | Boundary |
| --- | --- | --- |
| Hierarchical instance application | N/P PASSED | Native BSIM4; raw readback and untouched twin. |
| MG extraction | N/P PASSED | 300 K, 50 mV, nine W/L anchors. |
| Two-observable mapping | N/P PASSED | 72 artificial +/-10 mV, +/-2% targets, not stochastic tail coverage. |
| Original Hart beta | N/P UNRESOLVED | No runtime coefficient approved. |
| Repository validation | Historical recorded PASS | 119 repository tests, 39 separate preflight tests, not a validation of this new handoff. |
| OpenVAF source-pin check | FAILED | Actual source differed from expected; native VTG experiments did not use it. |

The source audit retrieved the 2022 thesis and distinguished ST40 LVT data from
the companion TSMC40 standard-Vt data. The companion is the next independent
candidate, not a correction. Its numeric profile remains unapproved, including
geometry and extraction-transfer checks. Source uncertainty must remain separate
from artificial implementation tests.

The prior host used source `6a93e9500c07830d1e8a19abdeda8f447f935556`
versus expected `fdf2522b70f42793f64b1c72f0195c96dea0cc19`.
`src/apm/model_build.py` writes the configured revision unconditionally. The live
implementation may now repair this defect, but must preserve historical reports
and inspect the next host rather than assuming the old environment persists.

## Next actionable work

Bootstrap v5 mission/version validation; fix observed toolchain identity; audit a
coherent Vth/beta source set while implementing the core path with artificial tests.
Then approve a source profile, freeze its numerical plan, qualify tails/statistics/
circuits, assess IO transfer and qualify a clean release candidate. Do not re-run
only the completed preflight and declare v5 complete.

Required release blockers currently unresolved:

- no approved coherent quantitative VTG N/P Vth+beta profile;
- actual pinned OpenVAF build provenance not yet repaired/qualified;
- production research-local API, stochastic/circuit/tail evidence not implemented.

## Preserved released history

APM v1.0.0 through v4.0.0 remain released and immutable. The nominal catalog is
unchanged at 15 families / 30 MOS devices. APM045 positioning remains generic
40/45 nm-class; technical namespace remains 45 nm FreePDK45-based.

- v4 tag object: `797cdf9462db9dd634bff558802bcadaaeb70015`.
- Tagged commit: `d224f279921c7e1ae637fd867e00d450067766c6`.
- Frozen post-tag authority: `02959d4a095062873fa2a3a53936af3cb4598ee3`.
- Preflight records/tool snapshot are preserved at the completed preflight commit.

The complete previous status and phase-specific restrictions remain in Git at
`bbb585306f13614b7649c36dd5b7510c845daed9:STATUS.md` and `GOAL.md`.
This new mission does not retroactively change their evidence or authorize any
rewrite of v4 model-generation or release history.
