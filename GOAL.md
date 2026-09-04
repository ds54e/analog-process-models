# APM v4.0.0 — APM045 Mixed-Voltage Electrical Families (complete)

## Current state

APM v4.0.0 is released and immutable. The release completed the goal below
without changing its technical or claim boundary.

- annotated tag: `v4.0.0`;
- annotated-tag object: `797cdf9462db9dd634bff558802bcadaaeb70015`;
- tagged commit: `d224f279921c7e1ae637fd867e00d450067766c6`;
- pre-tag candidate qualification: 15/15 candidate-required gates PASS;
- exact-tag post-release qualification: 16/16 required gates PASS;
- GitHub Release: `Analog Process Models v4.0.0`;
- release URL:
  `https://github.com/ds54e/analog-process-models/releases/tag/v4.0.0`;
- compact evidence: `validation/evidence/v4_release_candidate.json` and
  `validation/evidence/v4_post_release_requalification.json`;
- repository visibility: PUBLIC.

APM v1.0.0 through v3.0.0 remain released and immutable. Current `main` is the
post-v4 development and public-maintenance line. Do not modify, recreate, move,
or delete released tags, tagged commits, historical release evidence, or
existing GitHub Releases.

## Goal

Complete and release **APM v4.0.0** by extending only APM045 with two new,
independently APM-authored planar BSIM4 electrical families:

- `apm045/io18` — generic 1.8 V-class mixed-voltage analog/I/O MOS;
- `apm045/io25` — generic 2.5 V-class mixed-voltage analog/I/O MOS.

Preserve the existing FreePDK45-derived APM045 `vtl`, `vtg`, `vth`, and
`thkox` families byte-for-byte. Preserve the released v2/v3 electrical/noise
contracts and the APM045 `vtg` cross-process anchor.

The authoritative v4 technical contract is [`V4_MIXED_VOLTAGE.md`](V4_MIXED_VOLTAGE.md).
The authoritative v4 machine-readable completion contract is
[`validation/release_gates_v4.toml`](validation/release_gates_v4.toml).

## Technical intent

V4 is not a TSMC55 or UMC55 model recreation. It creates a reproducible generic
45/55 nm-class mixed-voltage research palette using:

1. public technology-class evidence with explicit allowed/forbidden use;
2. independently APM-authored BSIM4 4.8.2 parameter decks;
3. deterministic behavior-constrained model synthesis;
4. canonical terminal finite-difference/Y-matrix measurements;
5. sealed device and circuit holdouts;
6. a retained feasible-candidate ensemble that exposes model-construction
   uncertainty separately from APM benchmark variation;
7. explicit io18/io25 electrical-distinctness qualification.

The objective is useful analog-design behavior and transparent evidence, not a
hidden approximation to any proprietary PDK.

## Required scope

### APM045 families

The v4 catalog must contain:

```text
vtl
vtg
vth
thkox
io18
io25
```

Do not add `io33` in v4.

### Required operating profiles

`io18`:

- `nominal_1v8`;
- `common_overlap_1v0`.

`io25`:

- `nominal_2v5`;
- `common_overlap_1v8`;
- `common_overlap_1v0`.

Do not treat 3.3 V as a normal v4 device operating profile. Future 3.3 V
stacking/tolerance/level-shifting work belongs to circuit research and does not
constitute device reliability qualification.

### Model-generation method

Before accepting either new family, qualify a deterministic offline
model-generation kernel against known APM terminal behavior. It must reconstruct
held-out behavior for at least APM022/SVT and APM045/VTG without requiring
recovery of the original compact-model parameter values.

The new canonical model cards must be byte-identically reproducible from frozen
public generation inputs, deterministic seeds, generator code, and the
reference toolchain used for release qualification.

### Geometry

Do not invent foundry design-rule minima. Determine and freeze APM-supported
L/W floors only after real terminal qualification. Public planar parameters
remain `w,l` only.

### Qualification

Both new families must pass:

- existing `apm.characterization.v2` terminal characterization;
- the v4 mixed-voltage supplemental qualification contract;
- numerical and geometry qualification;
- sealed device holdout;
- stationary small-signal noise execution under the existing v3 semantics;
- APM Benchmark Global/Local/All integration;
- model-only Spectre structural integration with the existing
  `experimental_unverified` claim boundary.

Selected circuit fixtures must also qualify device usefulness and numerical
stability without becoming foundry fitting targets. Required fixture classes
include MOS diode, 1:1 current mirror, source follower, resistive-load
common-source, and PMOS pass-device fixtures.

### io18/io25 distinctness

At common 1.8 V, the two new families must demonstrate an evidence-consistent,
robust electrical distinction in at least:

- gate-capacitance density;
- drive/current-density behavior;
- fixed-requirement realization such as required width and/or control voltage.

Do not manufacture distinctness by imposing arbitrary gm/gds, noise, leakage,
or total-gate-charge ordering.

## Claim boundaries

APM remains not a manufacturable PDK.

V4 must not claim or imply:

- TSMC, UMC, or other foundry correlation;
- silicon calibration or yield prediction;
- reliability, TDDB, HCI, breakdown, SOA, lifetime, or safe voltage ratings;
- a standalone 3.3 V MOS family;
- foundry design-rule geometry minima;
- calibrated gate leakage/GIDL/layout parasitics/process noise unless future
  evidence explicitly establishes them;
- real Spectre qualification.

Physical oxide thickness from literature must not be copied directly into BSIM
`TOXE` unless a source explicitly supports that parameter mapping.

## Autonomy and decision policy

Implementation agents may autonomously determine from real evidence, while
recording the rationale and generated evidence:

- final supported L/W floors and maxima;
- final compact-model parameters;
- bounded parameter-search ranges and local optimizer details;
- calibration-grid refinements;
- ensemble size above the contract minimum;
- the minimum compact-model parameter set required to satisfy the observable
  contract.

Do not silently change fixed v4 decisions, weaken gates, fabricate evidence,
or convert failed/skipped checks into passes.

If a fixed assumption proves technically inconsistent, record:

1. the assumption that failed;
2. real simulator/source evidence;
3. plausible alternatives;
4. impact on v4 completion.

Only revise a lower-level technical contract when required to satisfy this
higher-level goal without weakening its public claim boundary.

## Required stop states

Stop rather than improvise when a genuine condition such as the following is
reached:

- `MODELGEN_RECONSTRUCTION_FAILED`;
- `IO25_CONTRACT_INCONSISTENT`;
- `IO18_CONTRACT_INCONSISTENT`;
- `IO18_DISTINCTNESS_NOT_ESTABLISHED`;
- `PARAMETER_IDENTIFIABILITY_FAILURE`;
- `EPISTEMIC_UNCERTAINTY_TOO_WIDE`;
- `DC_CHARGE_CONFLICT`;
- `CIRCUIT_HOLDOUT_FAILURE`;
- `PROVENANCE_BOUNDARY_AMBIGUOUS`;
- a credential/private/proprietary artifact or ambiguous redistribution right;
- any condition that would require rewriting released history.

A documented negative stop result is preferable to a cosmetically complete but
unsupported release.

## Required completion

V4.0.0 is complete only when all required gates in
`validation/release_gates_v4.toml` pass, including at least:

- public evidence/provenance qualification;
- `MODELGEN_KERNEL_QUALIFIED`;
- `IO25_DEVICE_QUALIFIED`;
- `IO25_APPLICATION_QUALIFIED`;
- `IO18_DEVICE_QUALIFIED`;
- `IO18_APPLICATION_QUALIFIED`;
- `IO18_IO25_DISTINCTNESS_ESTABLISHED`;
- `MIXED_VOLTAGE_COMPARISON_QUALIFIED`;
- `MIXED_VOLTAGE_NOISE_INTEGRATED`;
- `MIXED_VOLTAGE_VARIATION_INTEGRATED`;
- complete v3 regression/compatibility checks;
- exact-candidate fresh-clone qualification;
- release metadata and public-claim audit.

After every required candidate gate passes, creation of a new annotated
`v4.0.0` tag is authorized. Existing tags remain immutable.

After tag creation, run a fresh exact-tag qualification. Only after exact-tag
qualification passes is creation of the GitHub Release `Analog Process Models
v4.0.0` authorized.

## Status and progress recording

Keep `STATUS.md` current during implementation. Record completed milestones,
real evidence, unresolved issues, stop conditions, and the next actionable
step. Do not use `STATUS.md` to silently redefine this goal or its claim
boundary.

## Completion state

Status: **COMPLETE — RELEASED**

Released target: **APM v4.0.0**

Completion evidence: candidate 15/15 PASS; exact tag 16/16 PASS; GitHub Release
published only after exact-tag qualification.
