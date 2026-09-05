<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM v5.0.0: Research Local Mismatch

Status: IMPLEMENTATION AUTHORIZED; SOURCE PROFILE NOT APPROVED; RELEASE NOT READY.

## Current mission

Implement and qualify APM v5.0.0 in this existing repository. Move beyond the
completed preflight into a usable, optional Research Local Mismatch path for
APM045/VTG NMOS and PMOS. The intended interpretation remains generic
40/45 nm-class planar bulk CMOS, not a named-foundry statistical PDK.

The user has authorized this transition from preflight to full implementation
and release-readiness work. This supersedes the earlier preflight-only ban on
production code, new research schemas, and development-version changes. It does
not authorize altering released model bytes or historical evidence.

Current technical authority:

1. `AGENTS.md` and this goal;
2. `V5_RESEARCH_VARIATION.md`;
3. `validation/release_gates_v5.toml`;
4. `variation/research/apm045/sources.toml` for source/adoption state;
5. preserved electrical/result/noise contracts and current user documentation.

If these disagree materially, record the conflict; do not choose the easier
requirement. Chat history, an attachment, and an external ZIP are not required.

## Required outcome

- A documented, versioned terminal-extraction coordinate and two-observable
  instance mapping for VTG N/P, with bounded numerical error.
- At least one coherent, approved public-source Vth/beta local profile covering
  the declared v5 minimum domain. This is a transfer to a generic APM model,
  never a claim of APM silicon measurements or foundry correlation.
- Deterministic independent device sampling, persistent realizations, and
  same-realization replay across bias, temperature, and DC/AC/transient runs.
- Verified application inside hierarchical ngspice circuits, including readback,
  untouched-device isolation, reset/bad-path controls, and explicit unit banks.
- Source, numerical, statistical, circuit, and capability evidence kept separate.
- An io18/io25 Vth-transfer assessment with an explicit, predeclared outcome:
  either a bounded hypothesis or an evidence-backed unresolved result. No
  implicit beta=0, complete-IO-Monte-Carlo, or foundry-calibration claim.
- Correct observed OpenVAF provenance and a genuinely pinned release toolchain.
- Preserved Benchmark v2/native flows, nominal models, historical releases,
  and existing public electrical/noise schema semantics.
- A clean, independently reproduced v5 release candidate and honest documentation.

## Starting evidence and unresolved dependencies

Preflight is completed at `bbb585306f13614b7649c36dd5b7510c845daed9`.
Read `validation/evidence/v5_preflight_findings.json` and
`validation/evidence/v5_preflight_source_audit.md` before implementation.
N/P application, MG extraction and artificial mapping passed at nine W/L points.
Those results establish neither a measured coefficient nor a six-sigma domain.

The original Hart/ST40 LVT beta normalization remains blocked. Evaluate the
later Hart study as a separate source, not as a correction. Do not splice one
process's Vth coefficient with another's beta coefficient into an approved default.
Source resolution may proceed alongside artificial implementation tests.

The preflight host's compiler source did not match the repository pin, and
`model_build.py` wrote the expected commit as though observed. Native BSIM4
preflight results do not depend on OpenVAF; this defect still blocks complete
v5 reference-toolchain qualification.

## Authorized work and boundaries

Implement runtime modules, CLI commands, tests, source reanalysis, mapping caches,
current validators, a narrowly scoped toolchain-provenance repair, and new v5
schemas. Reuse useful preflight code by copying/adapting it into the implementation;
preserve the completed preflight snapshot and reports as baseline evidence.
Run real ngspice experiments, repair local tooling in ignored project paths, and
make coherent commits and normal fast-forward pushes to `main`.

Do not add a new nominal family, io33, Research Global/All, a mixed
Benchmark-Global/Research-Local default, passive mismatch, layout/PEX, noise MC,
RTN, aging, calibrated weak-inversion/SS variation, or real-Spectre integration.
Do not modify Benchmark v2 distributions, native variation semantics, nominal
model cards/wrappers/manifests, or frozen v1-v4 records. No author contact,
external messaging, paid data purchase, or repository security/visibility change.

Unresolved required-source data blocks quantitative adoption and release, not
unrelated implementation. Complete useful independent work, then report the
specific blocker; do not invent a coefficient, narrow scope silently, or claim
v5 complete with only artificial profiles.

## Bootstrap and version identity

The instruction handoff began with `4.0.0+main` source metadata. The completed
bootstrap migrated mission/version checks and mutable guidance to v5, set
project/runtime/CLI identity to `5.0.0.dev0`, and restored current validation
without weakening legacy integrity or numerical tests. Tests that
assert the old maintenance mission are not perpetual requirements; migrate those
specific assertions with explicit replacement tests. Do not run old release
workflows against new live guidance and then edit frozen records to make them pass.

Use `5.0.0.dev0` during development. Use plain `5.0.0` only for a frozen candidate
before candidate qualification. These are development states for one major
release, not v4.1/v5.1 or additional releases. Exact identity also requires a
Git commit, clean-tree or snapshot identity, input hashes, and observed tool hashes.

## Completion and publication authority

The autonomous finish state is `V5_RELEASE_READY`: all candidate-required gates
pass on an exact clean commit and an independent fresh clone. Do not stop merely
because one milestone is complete. A genuine scientific or infrastructure blocker
must be reported with the independent work already completed.

Creating `v5.0.0` and publishing a GitHub Release require a separate explicit user
approval of the candidate. The contract already defines post-tag requalification;
it is not part of the candidate gate dependency and must never be faked before a
tag exists. Do not move or replace an existing tag if later checks fail.

## Validation and progress

The normal current-tree command remains unflagged `apm validate`, after bootstrap
migration. Implement a separate v5 candidate-validation path; preserve historical
`--release` and `--release-v4` meanings. Use fresh output paths.

Run doctor/toolchain provenance, full pytest (no hidden required skips), Ruff,
REUSE, provenance/public-hygiene checks, legacy regression, and v5 real-tool gates.
Use WSL2/RHEL-compatible EL9 x86_64, ngspice 47 and the required pinned OSDI
compiler for release qualification. Local non-reference checks are useful but
must be labeled as such.

Keep `STATUS.md` current with source-adoption state, exact executed code identity,
completed gates, blockers, and the next actionable step. Keep raw runs/downloads
under ignored `.apm/v5/`; commit compact reproducible evidence. A planned,
missing, skipped, failed, unknown-provenance, or unexecuted check is not a pass.
