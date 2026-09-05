# AGENTS.md

Mandatory policy for agents working in **Analog Process Models (APM)**,
`https://github.com/ds54e/analog-process-models`. APM always means this project.
Work in this existing repository.

## Current mission and authority

The user explicitly selected the APM v6 implementation and qualification mission.
Read `GOAL.md`, `docs/maintainers/v6-plan.md` in full and `validation/acceptance.toml`
before substantive work. Read `STATUS.md`, current user/maintainer guides and the
relevant scientific contracts before modifying their consumers. APM045 work also
requires `APM045_POSITIONING.md`; model/provenance work requires `THIRD_PARTY.md`
and `CONTRIBUTING.md`; real-tool work requires `ENVIRONMENT.md`.

Authority: explicit user instructions and safety/security requirements, this file,
GOAL and its acceptance plan, APM045 positioning, preserved scientific contracts,
then current user documentation. Record material conflicts and departures in STATUS;
never silently drop a harder requirement.

This is implementation and qualification, not preflight or documentation-only work.
Continue through independent tasks and feasible gates to `V6_RELEASE_READY`, or a
precise evidenced blocker after independent work completes. Use `6.0.0.dev0` during
implementation, `6.0.0` for the exact frozen candidate. `6.0.0+main` is reserved for
maintenance after actual publication. Version labels alone are not source identity:
record exact commit/tree, clean or snapshot identity, inputs and observed tools.

## Immutable history and authorized migration

APM v1.0.0 through v5.0.0 are released and immutable. Read `releases/index.toml`
for exact annotated tags, peeled source commits/trees and separate evidence
commits. `releases/migration-v6.json` captures the pre-migration tree, old frozen
selectors, modes/blobs/hashes, roles and references. Its baseline is
`25140f57c4c3714f6ab4c9c9df44698ad7732662`; the reviewed maintenance predecessor is
`4cd57d98a54ad1cfe8deedf38de39a0b81a22d52`.

The selected v6 mission authorizes changing current-main policy and retiring
classified historical live copies **only after exact reconstruction/export and
closure verification**. Historical Git objects, scientific source decisions,
acceptance criteria and evidence statements cannot change. Retained runtime and
normative assets remain byte/mode exact at their public paths. A source tag and a
later evidence authority are distinct; preserve both. Do not keep a second entire
archive tree. Verify a self-contained Git bundle and restoration before retirement.
Missing/shallow history must fail strict checks, without becoming a runtime fetch.

Completed preflight, v3/v4/v5 contracts, release procedures, failed runs and evidence
are historical records. Their old phase language is neither current authorization
nor a reason to undo a completed release. Old qualification belongs to its exact
source. Do not import historical release implementations into current runtime or
relabel their validation as current. Keep a visible old-to-new check disposition;
replace obsolete mission/prose assertions with lifecycle tests, never bypass valid
scientific, licensing, provenance or corruption checks.

## Scientific invariants

Preserve `Technology -> Electrical Family -> Device`. Operating Profile, Backend
Binding, Variation and Comparison Set are orthogonal. Discovery is manifest-driven;
no technology-specific normal-family loaders or universal parameter abstraction.
The catalog remains five technologies, fifteen families and thirty public MOS.
Public planar geometry is `w,l`; FinFET is `l,nfin` with integer NFIN. Preserve
public names, terminals, includes, model/provenance manifests and support ranges.

Read `DEVICE_FAMILY_MODEL.md`, `RESULT_CONTRACT.md`, `NOISE_CHARACTERIZATION.md`
and the applicable frozen methodology. Preserve electrical v2, stationary-noise v1,
noise-comparison v1, contiguous-regions@1.0.0, bounded-white-search@1.0.0 and all
released Research/build-provenance schemas with explicit legacy-cache handling.
Canonical gm/gds are terminal finite differences; capacitances derive from raw
complex terminal Y. Preserve signed terminal quantities separately from magnitudes.

Preserve the 1-ohm CCVS drain-current probe, actual complex gate-to-drain transfer,
canonical drain-current/gate-equivalent PSDs, effective parameter provenance and
raw backend source names. Required `.noise` uses normal Sparse/no-KLU. Preserve
native planar-W and FinFET-NFIN bases. No fabricated fits, clipped gm/Id requests,
noise calibration or inference of silicon accuracy from simulator success.

Benchmark v2, APM130 native and APM045 VTG Research Local remain distinct. Read
`V5_RESEARCH_VARIATION.md`, `validation/v5_confirmation_plan.toml`,
`variation/research/apm045/sources.toml` and its hashed decision before research
maintenance. Preserve draws, raw realizations, profiles, coefficients, distributions,
methods, seeds, tolerances and denominators. No clipping, redraw, discarded samples,
post-hoc tolerance relaxation, new covariance or silent stale-cache acceptance.
Legacy realization replay retains its previously supported identical input/path
context; arbitrary relocation is not promised.

VTG N/P Research Local remains W=1–4 um, L=0.12–0.40 um, 300 K statistical anchor,
|VDS|=50 mV, VBS=0. Temperature replay is uncalibrated. Hart/TSMC40 is a transfer
hypothesis; original Hart/ST40 beta remains `BLOCKED_NORMALIZATION_CONFLICT` for
N/P. IO18/25 remains `UNRESOLVED_WITH_EVIDENCE`, without numeric default profiles.
Unknown beta is not zero. Source uncertainty and model-construction ensembles are
not physical device/process draws. Research Global/All remains unsupported.

APM022/APM016F are independently authored generic models. Official PTM/PTM-MG
cards must not be copied, transcribed, interpolated, optimized against as numeric
fitting targets or used as numeric source material for their decks/variants.

## Tools, scope, licensing and public hygiene

Reference: EL9 x86_64/WSL2, Linux filesystem, ngspice 47, pinned PSP103/BSIM-CMG,
OpenVAF-Re-Loaded `fdf2522b70f42793f64b1c72f0195c96dea0cc19`. Preserve the pin;
observe actual clean source/build receipts, compiler and OSDI binary hashes.
Configured identity is not observed identity. Local toolchain repairs/new ignored
prefixes are authorized; preserve valid existing state and system tools. Distinguish
cold bootstrap, verified reuse, native-BSIM4 and OSDI-dependent evidence.

APM is not a manufacturable PDK. No new physics, nominal models, statistical
coefficients, IO statistics, LDO/OTA optimization, agent/plugin frameworks, cloud
services, platform expansion, layout/PCells/DRC/LVS/PEX, standard cells, signoff,
reliability/yield, RTS/RTN, noise MC, transient noise, PSS/PNoise, phase noise or
full terminal noise correlation. Spectre remains model-only experimental/unverified;
no real parsing, simulation, equivalence or Virtuoso/ADE/OA automation claim.

Before adding third-party assets: identify authoritative upstream, pin exact bytes
or revision/path, inspect file-level rights, retain notices/acknowledgements/license,
and record source/output hashes and modifications. Never infer rights from a root
license or relicense third-party material. Derived figure data needs source/adaptation
credit and its appropriate license. Keep legitimate local outputs under ignored
project paths; never commit papers without reviewed rights, proprietary PDK/models,
private oracle decks, credentials, personal/private data, OSDI binaries, environments,
caches or large raw results. Preserve the completed public-hygiene audit boundary.
Stop and report a credential/proprietary/private-history artifact, ambiguous rights
or a required history rewrite; deleting only its live copy does not resolve it.

## Validation and Git

Unflagged `apm validate` is the current maintainer check. Report scope and unavailable
checks explicitly. A bounded product check may work without Git; it cannot imply
history or release qualification. Missing, skipped, stale, static-only or unavailable
required real-tool evidence is never a pass. Avoid recursive pytest/release runners.
Retain exact negative mechanisms and failures; raw runs stay ignored and compact
summaries under `validation/evidence/` are hash-linked to their subject source.

Autonomous in-scope implementation, local repairs, tests, documentation, coherent
commits and normal fast-forward pushes are authorized. Never force-push, rewrite
published history, amend tagged commits, move/recreate/delete released tags, or
change owner/name/default branch/visibility/security settings. No external messages,
author contact, paid data, GitHub About update, tag/release creation or release edits
are authorized. Stop before `v6.0.0` creation/publication; both need separate approval.
