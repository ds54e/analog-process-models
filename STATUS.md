<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM project status

Execution evidence, not this index alone, supports validation and release claims.

## Current mission: post-v5 maintenance

State: **v5.0.0 RELEASED / EXACT TAG QUALIFIED 17/17**.

The separately approved immutable annotated tag is
`b1a4246b9189fe33915d457e9d7f2938869b8fdf`, peeling exactly to
`381517fda5107fabf98af7801d5a5103f38e230c`. The current main HEAD was not tagged.
A genuinely fresh detached GitHub clone reran the complete 16-gate candidate
validator with a new environment and new OSDI/numerical state. The external
procedure added tag identity, freshness, clean before/after worktree and report
bindings as the seventeenth gate. All **17/17 passed** before
[GitHub publication](https://github.com/ds54e/analog-process-models/releases/tag/v5.0.0).

See [exact-tag findings](validation/evidence/v5_post_release_requalification.md)
and the [hash-linked record](validation/evidence/v5_post_release_requalification.json).
Frozen v5 evidence authority: `150084368815f6a57eae9f3e707f685149e920d3`. Raw exact-tag evidence remains
ignored under `.apm/v5/fresh-exact-tag-1/.apm/v5/exact-tag/`.

The exact-tag run independently repeated all counts below: N and P each passed
45,056/45,056 SPICE pairs and 6,144/6,144 circuit realizations, zero failures;
all 194 tagged repository tests and 39 separate preflight tests passed without
skips. Fixed seeds intentionally reproduce the same candidate realizations;
candidate/tag runs are not pooled as additional statistical sample size.
IO execution passed with all four outcomes UNRESOLVED_WITH_EVIDENCE.

Pre-tag procedure validation passed `apm validate`: 216 tests, no skips, including
22 tag/evidence fault cases, plus Ruff, REUSE and repository audits. Its report
is hash-linked in the authorization record. It is separate from the fresh
exact-tag numerical run. Post-release main now uses `5.0.0+main`.

Current bookkeeping validation passed unflagged `apm validate`: **224 tests,
zero skips**, Ruff, REUSE, provenance, distribution, all legacy maintenance
regressions, package identity and all 30 frozen-v5 artifacts. Eight new cases
cover successful preservation and rejection of byte, index-mode, tag-object,
inventory and obsolete-version drift. The full check used worktree snapshot
`3c1acbd074bcf66898e2450f4ded7e32131e6f7ebffbc87a0afd88b76c36ebd3` above
frozen evidence commit `150084368815f6a57eae9f3e707f685149e920d3`.
See `validation/evidence/post_v5_maintenance.json`; the raw report SHA-256 is
`30ad47f86541aced0501def97ad52695f697951ce21a58dc8acee4cd1bdf6776`.
Only this status/result bookkeeping followed that full check, with focused
final document, license and frozen-byte audits. These current-main checks do
not replace or relabel the separate exact-tag 17/17 qualification.

## Preserved candidate qualification

Exact qualified candidate: `381517fda5107fabf98af7801d5a5103f38e230c`.
Tree: `8751c3ed03dc31c87f52d3eb3c5c0b4da903ed65`.
At candidate qualification source/runtime/CLI identity was plain `5.0.0`,
then untagged and unreleased. All 16
candidate-required gates passed from an independent GitHub clone with a fresh
environment and clean source before/after execution. The later documentation and
evidence commit records this result; it is not a newly qualified candidate.

See [candidate findings](validation/evidence/v5_release_candidate.md) and the
[hash-linked summary](validation/evidence/v5_release_candidate.json). Raw reports,
simulator runs, failure controls and cohort inventories remain ignored under
`.apm/v5/fresh-candidate-1/.apm/v5/`. The frozen plan was executed without changing
coefficients, seeds, sample counts or acceptance limits. Independent suites and
later P cohorts ran concurrently in separate directories; the main evaluator
revalidated those same candidate-bound runs and their hashes.

| Required work | Executed result |
| --- | --- |
| Hierarchical application | N and P each passed 9 mechanism controls and untouched-twin checks. |
| MG extraction / two-observable mapping | N and P each passed 11 geometries and 286 targets; all errors within declared budgets. |
| Pure sampler | 65,536 artificial pairs passed; separate from source qualification. |
| Source-profile SPICE statistics | N 45,056/45,056; P 45,056/45,056; zero failed pairs. All simultaneous sigma intervals inside 0.90–1.10. |
| Circuits | N and P each passed six families at 1,024 realizations each; zero failures, including unit-bank scaling. |
| Saved-realization replay | Eight N/P temperature cases passed DC/AC/transient, raw readback, terminal KCL and native charge conservation. |
| IO transfer assessment | io18/io25 N/P execution passed; all four numerical outcomes UNRESOLVED_WITH_EVIDENCE. No IO beta/default profile. |
| Repository quality | 194 current tests and 39 separate preflight tests passed, no skips; Ruff, REUSE, provenance and distribution checks passed. |
| Legacy real-tool compatibility | Benchmark, native and electrical passed; noise method 10/10 and noise catalog 16/16 passed. |
| Immutable inputs | 161 released inputs/modes plus all 52 frozen v4 files and the frozen preflight snapshot passed exact comparison. |

The reference environment was EL9 x86_64/WSL2, ngspice 47. The actual controlled
OpenVAF build at required pin `fdf2522b70f42793f64b1c72f0195c96dea0cc19`
is VERIFIED with source/submodule, Rust/LLVM, binary and OSDI receipt bindings.
The original system compiler and expected pin were preserved.

The independent Hart/TSMC40 companion is approved as a quantitative transfer
hypothesis; original Hart/ST40 beta remains **BLOCKED_NORMALIZATION_CONFLICT for
N and P**. See [source decisions](validation/evidence/v5_source_decision.md).
The explicit geometry inference and source-extraction transfer are recorded;
source confidence/digitization bounds are separate from random variation, while
process-transfer and log-L interpolation uncertainty remain unquantified.

The candidate-readiness task created no tag or release and did not count the
post-tag gate. Separate approval and the completed 17/17 exact-tag qualification
now support publication, as recorded above. Spectre remains model-only
experimental/unverified.

Result-document maintenance validation also passed `apm validate` with 194 tests
and no skips. The first README update accidentally omitted its `5.0.0.dev0`
development-history statement: that check and one test failed (193 passed).
Restoring the accurate statement passed the unchanged checks. Both reports and
their source snapshots are hash-linked under `result_record_validation` in the
candidate summary; these checks are separate from candidate qualification.

## Bootstrap evidence (historical development stage)

Executed bootstrap validation: `apm validate` passed, including 120 pytest tests
(no skips), Ruff, REUSE, provenance, the 92-check v3 regression and structural
Spectre checks. This is current repository compatibility evidence, not v5
candidate qualification. See `validation/evidence/v5_bootstrap.json` and its
hash-bound raw report under `.apm/v5/bootstrap-validation/`.

The toolchain repair has separate evidence in
`validation/evidence/v5_toolchain_repair.json`, including four native/OSDI smoke
tests and nine targeted provenance regressions. Those development checks remain
distinct from the completed independent candidate qualification above.

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
the companion TSMC40 standard-Vt data. At preflight completion the companion was an unapproved independent candidate.
The current independent adoption decision is linked above; it does not correct
or unblock the original ST40 data. Source uncertainty remains separate from
artificial implementation tests.

The prior host used source `6a93e9500c07830d1e8a19abdeda8f447f935556`
versus expected `fdf2522b70f42793f64b1c72f0195c96dea0cc19`.
The former `src/apm/model_build.py` wrote the configured revision unconditionally.
The current implementation repairs that defect using observed build receipts,
without changing the expected pin or the historical reports.

## Runtime development evidence

The source-aware sample/run/replay CLI, versioned MG mapper, UID-keyed sampler,
hierarchy verification, cache rejection and qualification executors are implemented.
The mirror example resolves through the public CLI. Development execution includes
18 successful mechanism-specific negative controls (both polarities), same-raw
DC/AC/transient/temperature replay, and executed io18/io25 N/P capacitance assessments.
The IO outcomes are UNRESOLVED_WITH_EVIDENCE, with no numeric mismatch profile.
Small 8-pair and 4-circuit development cohorts are **not statistical passes**.

At that development stage, 166 repository tests passed without skips; Ruff and
REUSE passed. A public
summary initially contained generic workspace paths; the distribution check failed,
and the live summary now uses relative paths while retaining unchanged raw hashes.
`apm validate` also passed against the implementation snapshot; its hash and
development run references are in `validation/evidence/v5_runtime_development.json`.
The initial committed confirmation passed the sampler, all 22 mapping cases
and all 11 N statistics cases. It was deliberately interrupted to complete run
context hardening before the exact candidate. Its P statistics and later suites
are not passes. The independent fresh candidate subsequently reran the full fixed
plan; the incomplete earlier cohort is not candidate evidence.
Raw development runs are under `.apm/v5/development/`.

The numerical plan, legacy real-tool gates and v5 evaluator completed at the
exact candidate above. At that development stage publication was not authorized;
subsequent explicit approval and exact-tag evidence are recorded separately.

## Preserved released history

APM v1.0.0 through v5.0.0 remain released and immutable. The nominal catalog is
unchanged at 15 families / 30 MOS devices. APM045 positioning remains generic
40/45 nm-class; technical namespace remains 45 nm FreePDK45-based.

- v4 tag object: `797cdf9462db9dd634bff558802bcadaaeb70015`.
- Tagged commit: `d224f279921c7e1ae637fd867e00d450067766c6`.
- Frozen post-tag authority: `02959d4a095062873fa2a3a53936af3cb4598ee3`.
- Preflight records/tool snapshot are preserved at the completed preflight commit.

The complete previous status and phase-specific restrictions remain in Git at
`bbb585306f13614b7649c36dd5b7510c845daed9:STATUS.md` and `GOAL.md`.
Post-release maintenance does not retroactively change their evidence or authorize any
rewrite of v4 model-generation or release history.

## Candidate evaluator development

The v5 evaluator and fresh-clone attestation helper are implemented. Twenty-three
focused acceptance tests reject missing, duplicate, stale, corrupt and non-PASS
evidence; post-tag approval is not a candidate dependency. A charge-conservation
regression includes a deliberately nonconserving negative control. Eight local
N/P temperature replays passed native terminal-charge conservation and unchanged
raw readbacks. These are development checks, not fresh-candidate qualification.
The procedure is `docs/release-readiness-v5.md`.

The tightened runtime has 194 passing repository tests and 39 separate preflight
tests, with no skips. The first separate-suite evaluator invocation failed
collection because its import path was omitted; the corrected documented path
passes. Same-raw N/P replay and charge checks and all four IO assessments passed
execution after startup binding changes. Initial confirmation/interruption and
legacy real-tool evidence are hash-linked in
`validation/evidence/v5_evaluator_development.json`.

## Frozen released scope

Methods, profiles, source decisions, code and the full confirmation plan are
frozen in the released source at `381517fda5107fabf98af7801d5a5103f38e230c`.
Plain `5.0.0` denotes this immutable release. All 16 candidate-required gates
passed, then all 17 exact-tag gates passed in a separate fresh clone. Later
bookkeeping commits neither alter that source nor qualify a different release.
No additional version, tag or release is authorized by routine maintenance.
