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

APM v1.0.0, v2.0.0, and v3.0.0 are released and immutable.

- v2.0.0 commit: `3cc6cfea4932cc40f2d693784d0a569926cdf399`;
- v3.0.0 annotated-tag object:
  `afecec29ea6ed0703ef441d4839fd40a238bef0b`;
- v3.0.0 tagged commit:
  `995e0ce7cdd0c37ef9f3397008637f9d239c746e`;
- v3.0.0 exact-tag requalification: 18/18 required gates passed;
- GitHub Release: `Analog Process Models v3.0.0`;
- post-tag evidence:
  `validation/evidence/v3_post_release_requalification.json`.

Do not modify, move, recreate, or delete a released tag. Do not amend the
tagged commits, rewrite published history, or force-push. Current `main` is the
post-v3 development and public-maintenance line; it is not the v3.0.0 tag
target.

The repository is public. Publication followed a passing pre-publication audit
and is recorded in `validation/evidence/publication_v3.json`. Do not change the
repository owner, name, default branch, visibility, or security settings
without explicit authorization for that exact action.

## Current mission and instruction hierarchy

Implement the current `GOAL.md` faithfully. For post-v3 work, preserve the
released electrical/noise behavior and claim boundaries unless a later goal
explicitly and deliberately changes them.

Read before substantive work:

1. `AGENTS.md`;
2. `GOAL.md`;
3. `README.md`;
4. `STATUS.md`;
5. the technical contract(s) relevant to the change;
6. `THIRD_PARTY.md` and `CONTRIBUTING.md` when models, provenance, or shipped
   assets are involved;
7. `ENVIRONMENT.md` and the applicable validation documentation when real-tool
   execution is involved.

Authority on conflict:

1. applicable safety/security requirements and explicit user instructions;
2. `AGENTS.md`;
3. the current `GOAL.md`;
4. current preserved technical contracts, including
   `DEVICE_FAMILY_MODEL.md`, `RESULT_CONTRACT.md`, and
   `NOISE_CHARACTERIZATION.md`;
5. current user and validation documentation.

`RELEASE_V3.md`, `UNATTENDED_EXECUTION.md`, `PROJECT_CONTEXT.md`,
`RESEARCH_BASELINE.md`, `NOISE_N1.md`, and `NOISE_N2.md` are retained
historical/frozen milestone records. They provide design rationale and
reproducibility, but they are not current goals and do not prohibit or undo an
already-completed release.

Do not resolve a material conflict by silently dropping the harder
requirement. Record material departures and evidence in `STATUS.md`.

## Preserved architecture and result contracts

Preserve the manifest-driven domain model:

`Technology -> Electrical Family -> Device`

Operating Profile, Backend Binding, Variation, and Comparison Set remain
orthogonal. Do not reintroduce technology-specific normal-family loaders or
collapse electrical family, voltage profile, gate stack, threshold class,
backend, and usage labels into one type string.

Public geometry remains native:

- planar devices: `w`, `l`;
- FinFET devices: `l`, integer `nfin`.

Do not invent a universal planar/FinFET effective width or expose a fake common
compact-model parameter API. Preserve the released schemas unless a later goal
requires a versioned change:

- `apm.characterization.v2`;
- `apm.noise-characterization.v1`;
- `apm.noise-comparison.v1`;
- `apm.noise-fit.contiguous-regions@1.0.0`;
- `apm.noise-acquisition.bounded-white-search@1.0.0`.

Canonical gm/gds remain terminal finite differences. Canonical capacitance
remains derived from the raw complex terminal Y matrix. Preserve raw signed
terminal quantities separately from positive-magnitude comparison quantities.

## Noise and model-fidelity policy

Released v3 stationary-noise results characterize existing compact-model
predictions. They are not silicon/foundry calibration, reliability
qualification, or a manufacturable-PDK claim.

Preserve:

- the 1-ohm CCVS external drain-current probe and analytic harness evidence;
- canonical `s_idrain_terminal_a2_per_hz` and
  `s_vgate_equivalent_v2_per_hz` semantics;
- actual complex external gate-to-drain transfer;
- parameter-level effective noise provenance;
- raw backend source names without false cross-engine equivalence;
- fail-closed bias, acquisition, and fit semantics;
- normal Sparse/no-KLU required `.noise` execution;
- native planar-W and FinFET-NFIN comparison bases.

Do not infer calibration from successful simulator execution. Do not silently
fill unavailable fit metrics or clip unreachable gm/Id requests. Do not tune or
add process-noise coefficients for APM350, APM022, or APM016F without a later
explicit calibration goal backed by defensible targets. Process-noise
calibration is not implicitly authorized by maintenance work.

APM022 and APM016F remain independently authored generic models. Official
PTM/PTM-MG parameter cards must not be copied, transcribed, interpolated,
optimized against as a numeric fitting target, or used as numeric source
material for their decks or variants.

## Reference backend and Spectre boundary

ngspice 47 remains the validated reference simulator. The documented reference
environment is WSL2 with RHEL-compatible EL9 Linux on x86_64, using the
project-local OpenVAF-Re-Loaded and pinned PSP103/BSIM-CMG sources. Keep normal
build/run state on a Linux filesystem and below ignored project-local paths.

Spectre remains model-only **experimental/unverified**. Do not claim real
Spectre parsing, simulation, or numerical equivalence without evidence from a
real Spectre environment. Do not add Virtuoso/ADE/OA automation unless a later
goal explicitly requires it.

## Licensing, provenance, and public hygiene

License correctness is mandatory. Before adding a third-party asset:

1. identify the authoritative upstream source;
2. pin the exact revision and imported path;
3. inspect exact file-level licensing and redistribution terms;
4. preserve notices, acknowledgements, and license text;
5. record source/output hashes and modifications;
6. only then ship the asset.

Do not infer rights from a repository root license when file-specific terms may
differ. Do not relicense third-party material. If rights are ambiguous, do not
ship the file.

Never commit proprietary PDK/model content, private comparison/oracle decks,
credentials, tokens, passwords, personal/private data, generated OSDI
binaries, virtual environments, caches, or large simulator output. Keep those
under ignored local paths where legitimate. Public maintenance must preserve
the completed current-tree and whole-history audit boundary; do not rewrite
history unless a real sensitive or redistribution-blocking artifact is found
and separate human remediation is authorized.

## Scope discipline

APM is not a manufacturable PDK. Unless a later goal explicitly expands scope,
do not add layout/PCells/DRC/LVS/PEX, standard cells, reliability/signoff
claims, noise Monte Carlo, RTS/RTN, transient noise, PSS/PNoise, oscillator
phase noise, full terminal noise-correlation matrices, real Spectre claims, or
Virtuoso automation.

Keep the repository small and explicit. Avoid speculative plugin systems,
generic factories, and premature abstraction. Prefer straightforward Python,
TOML, SPICE/Spectre model files, and small shell helpers.

## Tests, evidence, and Git discipline

Prefer property/regression/analytic-reference tests over fragile exact
snapshots. Do not weaken legitimate tests to match broken behavior. Missing,
skipped, static-only, stale, or unavailable real-tool evidence is not a pass.

Write compact auditable summaries under `validation/evidence/`; keep raw
simulator data ignored and reproducible. `apm validate` is the normal
current-tree validation path. The frozen `apm validate --release` contract is a
maintainer/release-engineering workflow and must not be reinterpreted as an
ordinary post-release user requirement.

High autonomy is authorized for in-scope research, implementation, local
toolchain repair, tests, documentation, coherent commits, and normal pushes.
Do not force-push, rewrite history, alter released tags/releases, or change
repository visibility/security settings without explicit authorization for
that exact action.

Stop and report a genuine credential, proprietary model, ambiguous
redistribution right, personal/private history artifact, or any issue that
would require rewriting released history. Do not hide such a finding by
deleting only the current-tree copy.
