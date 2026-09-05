<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# V5 exact-tag qualification and publication

**PASS: 17/17 required gates**, followed by [GitHub Release publication](https://github.com/ds54e/analog-process-models/releases/tag/v5.0.0).

Annotated tag object: `b1a4246b9189fe33915d457e9d7f2938869b8fdf`.
Peeled approved commit: `381517fda5107fabf98af7801d5a5103f38e230c`.
Candidate tree: `8751c3ed03dc31c87f52d3eb3c5c0b4da903ed65`.

The full fresh 16-gate rerun completed inside the exact-tag procedure at 2026-09-05T08:31:30.071039+00:00; publication followed at 2026-09-05T08:32:51Z.
The external procedure on main checked the tag identity before and after the unchanged
candidate validator ran in a new GitHub clone, new venv and new OSDI/numerical state.
No candidate code, gate, coefficient or seed changed. The tag was never moved or replaced.
The source remained detached and clean. Existing v1–v4 tags and published v3/v4
GitHub releases remained unchanged; v1/v2 had no GitHub Release at the approval boundary.

| Polarity | Mapping geometries / targets | SPICE pairs / failures | Circuit realizations / failures | Sigma-CI range |
| --- | --- | --- | --- | --- |
| N | 11 / 286 PASS | 45,056 / 0 | 6,144 / 0 | 0.9480–1.0541 |
| P | 11 / 286 PASS | 45,056 / 0 | 6,144 / 0 | 0.9515–1.0565 |

Both polarities passed hierarchical application/readback, untouched-twin isolation,
mechanism-specific negative controls, maximum-gm convergence and two-observable mapping.
The 65,536-pair pure sampler passed. All eight saved-realization temperature replays
passed DC/AC/transient consistency and native charge conservation. The public CLI passed.
All 194 tagged repository tests and 39 separate preflight tests passed without skips;
legacy electrical/Benchmark/native/noise checks, Ruff, REUSE and provenance checks passed.

Actual OpenVAF provenance remains VERIFIED at the unchanged required pin
`fdf2522b70f42793f64b1c72f0195c96dea0cc19`. This rerun used the same recorded
ngspice 47 binary, compiler receipt and pinned companion source as the approved candidate.

Original Hart/ST40 beta remains **BLOCKED_NORMALIZATION_CONFLICT** for N and P.
The independent Hart/TSMC40 profile remains a **source-transfer hypothesis**, not a
correction, foundry correlation, yield or reliability claim. Source/geometry/extraction
limits and unquantified process/interpolation uncertainty remain explicit. All four
IO18/25 assessments executed and remain **UNRESOLVED_WITH_EVIDENCE**, with no default
mismatch profile. Research Global/All are unsupported; Spectre is model-only/unverified.

Independent P, later N and circuit/replay/IO suites acquired fresh tag-run data concurrently
with the master’s N statistics. The master revalidated those same source/seed-bound
runs; no candidate numerical directories or environments were reused.
The fixed seeds reproduce candidate realizations: this independently reruns the
execution, and does not add statistical sample size or pool candidate/tag cohorts.

The [machine-readable record](v5_post_release_requalification.json) binds tag objects,
fresh-clone identity, every component/report hash, tools/source inputs, all acquisition
schedules and release metadata. Raw runs remain ignored under
.apm/v5/fresh-exact-tag-1/.apm/v5/exact-tag/. The evidence commit on main is not the
release source. Subsequent mutable maintenance uses 5.0.0+main.
