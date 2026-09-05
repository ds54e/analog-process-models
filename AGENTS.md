# AGENTS.md

This file is mandatory repository policy for implementation and maintenance
agents.

## Repository identity

This repository is **Analog Process Models (APM)**:

- repository: `https://github.com/ds54e/analog-process-models`;
- acronym: **APM = Analog Process Models**.

Within this repository, APM always means this project. Work in this existing
repository; do not create or substitute another project authority.

## Released baseline and current line

APM v1.0.0, v2.0.0, v3.0.0, and v4.0.0 are released and immutable.

- v2.0.0 commit: `3cc6cfea4932cc40f2d693784d0a569926cdf399`;
- v3.0.0 annotated-tag object:
  `afecec29ea6ed0703ef441d4839fd40a238bef0b`;
- v3.0.0 tagged commit:
  `995e0ce7cdd0c37ef9f3397008637f9d239c746e`;
- v3.0.0 exact-tag requalification: 18/18 required gates passed;
- GitHub Release: `Analog Process Models v3.0.0`;
- post-tag evidence:
  `validation/evidence/v3_post_release_requalification.json`.
- v4.0.0 annotated-tag object:
  `797cdf9462db9dd634bff558802bcadaaeb70015`;
- v4.0.0 tagged commit:
  `d224f279921c7e1ae637fd867e00d450067766c6`;
- v4.0.0 exact-tag requalification: 16/16 required gates passed;
- GitHub Release: `Analog Process Models v4.0.0`;
- v4 candidate and post-tag evidence:
  `validation/evidence/v4_release_candidate.json` and
  `validation/evidence/v4_post_release_requalification.json`.

Do not modify, move, recreate, or delete a released tag. Do not amend tagged
commits, rewrite published history, or force-push. Current `main` is the active
v5 implementation line under `GOAL.md`, not the immutable v4 release source.
The v5 bootstrap migrated the handoff identity `4.0.0+main` and current checks
to `5.0.0.dev0`; implementation now uses the authorized v5 lifecycle.
Use plain `5.0.0` only for a frozen candidate. Exact source identity is a Git
commit plus clean-tree/snapshot and input hashes, not a version label alone.
Creating or publishing v5 requires the separate candidate approval specified in
`GOAL.md`; implementation and release-readiness work are already authorized.

The repository is public. Publication followed a passing pre-publication audit
and is recorded in `validation/evidence/publication_v3.json`. Do not change the
repository owner, name, default branch, visibility, or security settings
without explicit authorization for that exact action.

## Current mission and instruction hierarchy

Implement the current `GOAL.md` faithfully. For v5, read
`V5_RESEARCH_VARIATION.md`, `validation/release_gates_v5.toml` and
`variation/research/apm045/sources.toml`. Full v5 runtime/API/schema work and the
narrow compiler-provenance repair are authorized; the completed preflight-only
ban on those changes is no longer the active mission. No released nominal model,
Benchmark/native semantics or historical evidence may be changed to achieve v5.

Read before substantive work:

1. `AGENTS.md`;
2. `GOAL.md` and its active technical/gate/source contracts;
3. `APM045_POSITIONING.md` when APM045 scope or claims are involved;
4. `README.md`;
5. `STATUS.md` and the completed preflight findings/source audit;
6. the preserved contracts relevant to the change;
7. `THIRD_PARTY.md` and `CONTRIBUTING.md` when models, provenance or shipped
   assets are involved;
8. `ENVIRONMENT.md` and applicable validation documentation for real-tool work.

Authority on conflict:

1. applicable safety/security requirements and explicit user instructions;
2. `AGENTS.md`;
3. current `GOAL.md` and its named active technical/gate contracts;
4. `APM045_POSITIONING.md` for current APM045 positioning;
5. preserved technical contracts, including `DEVICE_FAMILY_MODEL.md`,
   `RESULT_CONTRACT.md` and `NOISE_CHARACTERIZATION.md`;
6. current user and validation documentation.

Active goal changes may require updating mutable current validators and tests
that hardcode the old maintenance mission. Replace those assertions with explicit
v5 lifecycle tests, not blanket bypasses. Never weaken legitimate legacy integrity,
numerical or provenance tests merely to produce a pass.

`RELEASE_V3.md`, `UNATTENDED_EXECUTION.md`, `PROJECT_CONTEXT.md`,
`RESEARCH_BASELINE.md`, `NOISE_N1.md`, and `NOISE_N2.md` are retained
historical/frozen milestone records. They provide design rationale and
reproducibility, but they are not current goals and do not prohibit or undo an
already-completed release.

Completed v4 artifacts are also frozen historical/release records. This
includes `V4_MIXED_VOLTAGE.md`, `RELEASE_V4.md`,
`validation/release_gates_v4.toml`, `validation/release_review_v4.toml`,
`validation/evidence/v4_*.json` and completed v4 model-generation contracts and
evidence. Their phase-specific wording is historical, not current instruction.
Do not rewrite it to remove candidate, pre-release or completion language.

The single byte authority for the completed v4 frozen scope is post-tag
commit `02959d4a095062873fa2a3a53936af3cb4598ee3`. It contains final candidate
and exact-tag evidence. The compared scope comprises release documents and
procedure, gate/review/comparison contracts, every `validation/evidence/v4_*.json`,
the full `tools/modelgen/apm045_mixed_voltage/` history, v4 clean-clone and
release-validator implementations, `models/apm045/families/io18/` and
`models/apm045/families/io25/` trees and their technology, provenance and evidence
manifests. This authority does not supersede the immutable tagged source.

The completed v5 preflight snapshot is
`bbb585306f13614b7649c36dd5b7510c845daed9`: preserve `V5_PREFLIGHT.md`,
`tools/v5_preflight/`, `validation/evidence/v5_preflight_preparation.json`,
`validation/evidence/v5_preflight_findings.json` and
`validation/evidence/v5_preflight_source_audit.md`. Production code may adapt a
copy of the exploratory algorithms; do not relabel or overwrite these records.

Do not resolve a material conflict by silently dropping the harder requirement.
Record material departures and evidence in `STATUS.md`.

## Preserved architecture and result contracts

Preserve the manifest-driven domain model:

`Technology -> Electrical Family -> Device`

Operating Profile, Backend Binding, Variation and Comparison Set remain
orthogonal. Do not reintroduce technology-specific normal-family loaders or
collapse family, voltage profile, gate stack, threshold class, backend and usage
labels into one type string.

Public geometry remains native:

- planar devices: `w`, `l`;
- FinFET devices: `l`, integer `nfin`.

Do not invent a universal planar/FinFET effective width or fake common compact-model
parameter API. Preserve these released schemas and semantics:

- `apm.characterization.v2`;
- `apm.noise-characterization.v1`;
- `apm.noise-comparison.v1`;
- `apm.noise-fit.contiguous-regions@1.0.0`;
- `apm.noise-acquisition.bounded-white-search@1.0.0`.

v5 may add separately versioned research schemas and truthful build-provenance
metadata with explicit legacy-cache handling. It may not silently reinterpret an
old result format or statistical profile.

Canonical gm/gds remain terminal finite differences. Canonical capacitance remains
derived from the raw complex terminal Y matrix. Preserve signed terminal data
separately from positive-magnitude comparison quantities.

## Noise and model-fidelity policy

Released v3/v4 stationary-noise results characterize existing compact-model
predictions. They are not silicon/foundry calibration, reliability qualification,
or a manufacturable-PDK claim.

Preserve:

- the 1-ohm CCVS external drain-current probe and analytic harness evidence;
- canonical `s_idrain_terminal_a2_per_hz` and
  `s_vgate_equivalent_v2_per_hz` semantics;
- actual complex external gate-to-drain transfer;
- parameter-level effective noise provenance;
- raw backend source names without false cross-engine equivalence;
- fail-closed bias, acquisition and fit semantics;
- normal Sparse/no-KLU required `.noise` execution;
- native planar-W and FinFET-NFIN comparison bases.

Do not infer calibration from successful simulator execution. Do not silently
fill unavailable fit metrics or clip unreachable gm/Id requests. Do not tune or
add process-noise coefficients for APM350, APM022 or APM016F without a later
explicit calibration goal. v5 local mismatch does not authorize noise calibration.

APM022 and APM016F remain independently authored generic models. Official
PTM/PTM-MG parameter cards must not be copied, transcribed, interpolated,
optimized against as a numeric fitting target, or used as numeric source
material for their decks or variants.

v5 preserves Benchmark v2 and native variation independently. Source coefficient
uncertainty and the v4 model-construction ensemble are not device/process draws.
Unknown beta is not zero. Unapproved sources, excluded effects and transfer
hypotheses must not acquire a calibrated statistical label through a passing test.

## Reference backend and Spectre boundary

ngspice 47 remains the reference simulator. The reference environment is WSL2
with RHEL-compatible EL9 Linux on x86_64, using project-local OpenVAF-Re-Loaded
and pinned PSP103/BSIM-CMG sources. Keep normal build/run state on a Linux
filesystem and below ignored project-local paths.

The current goal authorizes repairing observed compiler provenance and building
the existing pinned compiler in an ignored local prefix. Never report a configured
revision as observed, change the pin to fit a host, replace a system tool without
permission, or overwrite historical evidence. Bind source/build receipts to actual
binaries. Native-BSIM4 and OSDI-dependent evidence must be distinguished.

Spectre remains model-only **experimental/unverified**. Do not claim real Spectre
parsing, simulation or numerical equivalence without a real Spectre environment.
Do not add Virtuoso/ADE/OA automation for this goal.

## Licensing, provenance and public hygiene

License correctness is mandatory. Before adding a third-party asset:

1. identify the authoritative upstream source;
2. pin exact revision/imported path or exact document bytes;
3. inspect file-level licensing and redistribution terms;
4. preserve notices, acknowledgements and license text;
5. record source/output hashes and modifications;
6. only then ship the asset.

Do not infer rights from a root license when file-specific terms differ. Do not
relicense third-party material. If rights are ambiguous, do not ship the file.
Derived figure datasets require source/adaptation credit and appropriate licensing,
not automatic relicensing as APM-authored code.

Never commit proprietary PDK/model content, private comparison/oracle decks,
credentials, tokens, passwords, personal/private data, generated OSDI binaries,
virtual environments, caches or large simulator output. Keep legitimate local
artifacts below ignored paths. Preserve the completed public-hygiene audit boundary;
no history rewrite is authorized. No author contact, external messages or paid data
purchase is authorized by the v5 goal.

## Scope discipline

APM is not a manufacturable PDK. Unless a later goal explicitly expands scope,
do not add layout/PCells/DRC/LVS/PEX, standard cells, reliability/signoff claims,
noise Monte Carlo, RTS/RTN, transient noise, PSS/PNoise, oscillator phase noise,
full terminal noise-correlation matrices, real Spectre claims or Virtuoso automation.

Keep the repository small and explicit. Avoid speculative plugin systems, generic
factories and premature abstraction. Prefer straightforward Python, TOML,
SPICE/Spectre model files and small shell helpers.

## Tests, evidence and Git discipline

Prefer property/regression/analytic-reference tests over fragile exact snapshots.
Missing, skipped, static-only, stale or unavailable required real-tool evidence is
not a pass. Do not clip/redraw/discard bad samples, reinterpret statistical
unknowns as zeros, or silently shrink the promised domain. Continue independent
work when one scientific dependency is blocked; retain precise negative findings.

Write compact summaries under `validation/evidence/`; keep raw data ignored and
reproducible. After the v5 bootstrap, unflagged `apm validate` checks the current
mission. Historical `--release` and `--release-v4` workflows retain their original
meaning and must not be edited to accept new live guidance. The v5 gate document
is declarative until its evaluator is implemented and executed.

High autonomy is authorized for in-scope research, implementation, local toolchain
repair, tests, documentation, coherent commits and normal pushes. Do not force-push,
rewrite history, alter released tags/releases or change repository security settings.
Complete candidate qualification, then stop at `V5_RELEASE_READY` for explicit
candidate/tag/publication approval. A genuine blocked required source or toolchain
must not be disguised as completion.

Stop and report a credential, proprietary model, ambiguous redistribution right,
personal/private history artifact or issue requiring released-history rewriting.
Do not hide such a finding by deleting only the current-tree copy.
