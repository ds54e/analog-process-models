<!-- SPDX-FileCopyrightText: APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM v4.0.0 — APM045 Mixed-Voltage Electrical Families

This document is the technical contract for the APM v4.0.0 mixed-voltage
model-development goal. `AGENTS.md` and `GOAL.md` remain higher authority.
Released v1/v2/v3 tags and their historical evidence are immutable.

## 1. Purpose

APM v4.0.0 extends only APM045 with two independently APM-authored planar
BSIM4 electrical families:

- `apm045/io18`: a generic 1.8 V-class mixed-voltage analog/I/O family;
- `apm045/io25`: a generic 2.5 V-class mixed-voltage analog/I/O family.

The existing FreePDK45-derived `vtl`, `vtg`, `vth`, and `thkox` families remain
unchanged. `thkox` is retained as an upstream legacy thick-oxide/high-threshold
reference, not reinterpreted as the new 1.8 V or 2.5 V family.

The objective is a reproducible 45/55 nm-class mixed-voltage analog research
palette that captures useful device-level tradeoffs for later circuit studies.
It is not a TSMC, UMC, or other foundry model recreation.

## 2. Claim boundary

The public v4 release may claim only that the new families are:

- generic APM-authored 45/55 nm-class planar bulk BSIM4 research models;
- constrained by public technology-class evidence and explicit APM behavior
  contracts;
- qualified against terminal behavior, numerical consistency, sealed holdout,
  selected circuit fixtures, stationary small-signal noise execution, and APM
  benchmark variation.

The release must not claim or imply:

- TSMC55, UMC55, or any foundry PDK correlation;
- silicon calibration, yield prediction, or production accuracy;
- reliability, TDDB, HCI, breakdown, SOA, lifetime, or voltage-rating
  qualification;
- that the selected APM geometry floors are foundry design-rule minima;
- a standalone 3.3 V MOS electrical family;
- real Spectre numerical qualification;
- calibrated gate leakage, GIDL, layout-dependent parasitics, mismatch, or
  process-noise accuracy unless separately established by future evidence.

## 3. Public evidence policy

Before parameter synthesis, add a machine-readable public-evidence matrix for
APM045 mixed-voltage work. Each evidence item must record:

- stable identifier and title;
- source kind, preferably `official_foundry`, `measured_device_paper`, or
  `standards_document`;
- public URL/identifier and retrieval date;
- a concise observed fact;
- confidence;
- explicit `allowed_use` statements;
- explicit `forbidden_use` statements.

Evidence roles must remain distinct:

1. **Source fact** — a statement directly supported by a public source, such as
   the existence of 1.8 V/2.5 V I/O classes or an underdrive/overdrive option.
2. **Engineering prior** — an APM search range or ordering motivated by source
   facts, such as a thicker gate stack than VTG.
3. **APM behavior contract** — a research-use requirement chosen by APM, such
   as gm/Id reachability without endpoint clipping.

Do not silently promote an engineering prior into a foundry fact.

Physical dielectric thickness reported in literature must not be copied
verbatim into BSIM `TOXE`. It may constrain gate-stack ordering and broad
search priors only unless a source explicitly establishes the corresponding
BSIM electrical parameter.

Private/proprietary PDK information must never enter the public source matrix,
model cards, generation targets, evidence, comments, or derived public files.

## 4. Family matrix

The v4 APM045 family matrix is:

| Family | Origin | Intended role |
| --- | --- | --- |
| `vtl` | upstream FreePDK45 | existing low-VT thin-oxide reference |
| `vtg` | upstream FreePDK45 | existing 1.0 V-class core reference and cross-process anchor |
| `vth` | upstream FreePDK45 | existing high-VT thin-oxide reference |
| `thkox` | upstream FreePDK45 | legacy thick-oxide/high-threshold extreme reference |
| `io18` | APM-authored | generic 1.8 V-class mixed-voltage analog/I/O family |
| `io25` | APM-authored | generic 2.5 V-class mixed-voltage analog/I/O family |

A standalone `io33` family is explicitly outside v4.0.0.

### 4.1 Operating profiles

`io18` requires:

- `nominal_1v8`, reference VDD 1.8 V;
- `common_overlap_1v0`, reference VDD 1.0 V.

`io25` requires:

- `nominal_2v5`, reference VDD 2.5 V;
- `common_overlap_1v8`, reference VDD 1.8 V;
- `common_overlap_1v0`, reference VDD 1.0 V.

All release profiles use -40, 27, 85, and 125 degC.

Do not add a 3.3 V operating profile in v4. A future circuit study may examine
stacking, level shifting, tolerant interfaces, or other 3.3 V architectures,
but those are not device-voltage qualification in this release.

## 5. Compact-model basis

The new families use native ngspice BSIM4 with the already qualified APM
4.8.2 card dialect. Updating the BSIM4 equation/dialect version is a separate
future goal and must not be coupled to mixed-voltage family synthesis.

The initial model skeleton should keep unsupported high-complexity effects off
unless later evidence and qualification justify enabling them. The expected
starting point is conceptually:

```spice
mobmod=1 capmod=2
igcmod=0 igbmod=0 gidlmod=0
rbodymod=0 rgatemod=0
acnqsmod=0 trnqsmod=0
```

The exact final card may differ when required by real evidence, but any enabled
feature must have an explicit target, validation method, and provenance note.

Gate leakage, GIDL, distributed gate/body resistance, and layout-dependent
junction/parasitic behavior are not required v4 calibration domains.

N and P devices share family-level gate-stack and voltage-class semantics but
must be synthesized and qualified independently for threshold, electrostatics,
transport, output conductance, and temperature behavior. Do not create PMOS by
applying a fixed multiplier or sign change to an NMOS card.

## 6. Geometry selection

Do not freeze new-family `lmin_m` or `wmin_m` before the model-development
study demonstrates a supported electrical range.

Candidate L-floor search should initially include, unless real evidence
requires a documented revision:

- `io18`: 0.08, 0.10, 0.12, 0.15, 0.18, and 0.20 um;
- `io25`: 0.18, 0.20, 0.25, 0.30, 0.35, and 0.40 um.

For each candidate floor, qualify at least `L/Lfloor = 1, 2, 4` during
model-development evaluation.

The selected floor is the shortest candidate that satisfies the required
terminal, holdout, and margin rules without relying on endpoint clipping or
numerically fragile compensation. It is an **APM-supported model floor**, not
a foundry process/design-rule minimum.

Width-floor qualification must challenge at least 0.25, 0.5, 1, 2, 5, 10,
and 16 um where the candidate card supports them. Outcomes are:

- `WIDTH_INVARIANT_IN_SCOPE`;
- `WIDTH_VALIDITY_FLOOR_ESTABLISHED`.

Select the public `wmin_m` from qualified behavior, not from an unsupported
foundry-layout inference. Public planar device parameters remain only `w,l`;
do not add `m`, `nf`, finger, layout, or shared-diffusion semantics.

## 7. Observable contracts

V4 contracts are layered. Do not replace them with one weighted optimization
score.

### 7.1 Numerical hard contract

For every qualified new-family polarity and release profile:

- Id-Vg is monotonic over the qualified conduction region;
- Id-Vd is monotonic over the qualified region;
- canonical terminal-derived `gm` is positive where qualified;
- canonical terminal-derived `gds` is positive where qualified;
- finite-difference convergence is audited with multiple step sizes;
- the P95 relative disagreement between required finite-difference step pairs
  is below the frozen method threshold used by the release validator;
- native BSIM OP gm/gds remain diagnostic validation oracles only;
- raw signed terminal quantities and positive comparison quantities remain
  separate;
- the raw ordered complex 4x4 Y matrix uses terminal order `d,g,s,b`;
- Y-matrix KCL residuals are finite and below a frozen absolute and normalized
  criterion;
- NaN/Inf, silent clipping, fabricated fit metrics, or silent endpoint reuse
  are forbidden.

Near-off or numerically ambiguous points may be classified outside the
qualified region rather than forced through a hard pass.

### 7.2 Source-backed structural contract

Across comparable physical geometry and qualified bias:

- gate-stack/capacitance density must establish the intended ordering
  `VTG > io18 > io25` in an evidence-backed terminal metric such as long-L
  `Cgg/(W*L)`;
- the selected model-supported geometry floor must not contradict the intended
  core-versus-I/O geometry hierarchy without explicit evidence and review;
- native voltage-class ordering is `1.0 V < 1.8 V < 2.5 V` by construction,
  while no reliability rating is inferred.

### 7.3 Analog design-utility contract

For each new family and polarity, at representative qualified VDS/VDD values:

- gm/Id targets 5, 10, 15, and 20 1/V are reachable when physically meaningful;
- target solving must be bracketed and fail closed when unreachable;
- representative gm/Id points must not rely on a control-voltage endpoint;
- `ID/W`, `gds/ID`, `gm/gds`, and required control voltage are persisted;
- selected small-circuit qualification fixtures complete without numerical
  pathology.

Do not invent absolute TSMC/UMC targets for Ion, VTH0, gm/gds, or current
 density merely to make the family look plausible.

### 7.4 Sanity guardrails

Bounds on extracted Vth/VDD, DIBL, gm/gds, or current density may be used as
`RED_FLAG_REVIEW_REQUIRED` guards. They are not foundry-calibrated fit targets
unless public evidence explicitly supports them.

## 8. io18/io25 electrical distinctness

The release requires `io18` and `io25` to be meaningfully different electrical
families at 1.8 V, not duplicate cards with renamed parameters.

At common 1.8 V, common physical L, common W, common VDS/VDD, and equal gm/Id,
qualify separately:

1. `IO18_IO25_CAPACITANCE_DISTINCTION` — `io18` must show higher qualified
   gate-capacitance density than `io25` over the declared comparison scope;
2. `IO18_IO25_CURRENT_DENSITY_DISTINCTION` — `io18` must show higher drive or
   current-density behavior over a declared majority of the qualified common
   comparison points;
3. `IO18_IO25_DESIGN_REALIZATION_DISTINCTION` — the two families must imply a
   materially different required width and/or control-voltage tradeoff for a
   fixed current/inversion requirement in the qualification fixture.

Do not force ordering for gm/gds, noise, leakage, or total pass-bank gate
charge. Those may legitimately trade off or remain unresolved.

If distinctness does not emerge without arbitrary parameter distortion, stop
with `IO18_DISTINCTNESS_NOT_ESTABLISHED` rather than manufacturing a difference.

## 9. Offline model-generation kernel

Runtime APM must not depend on fitting/model-generation tools. Implement model
generation below `tools/modelgen/apm045_mixed_voltage/` or an equally explicit
non-runtime location.

Before synthesizing the new families, qualify the model-generation machinery
on known APM models without exposing their original parameters to the fitting
objective.

Required reconstruction fixtures:

1. APM022/SVT terminal-behavior reconstruction from a clean BSIM4 skeleton;
2. APM045/VTG terminal-behavior reconstruction from a clean BSIM4 skeleton.

Success does not require recovering the original compact-model parameter
values. It requires reproduction of held-out terminal behavior and trends
within frozen reconstruction criteria.

The model-generation kernel must support:

- deterministic parameter bounds and seeds;
- staged parameter release;
- real ngspice execution;
- terminal metric extraction;
- local parameter sensitivity;
- hard-constraint rejection;
- bounded candidate exploration and local refinement;
- sealed holdout;
- deterministic card rendering;
- generation-record hashing;
- byte-identical regeneration from the same frozen inputs.

Completion state: `MODELGEN_KERNEL_QUALIFIED`.

## 10. Staged parameter synthesis

The default synthesis order is:

### Stage 1 — electrostatics

Candidate groups include `TOXE/TOXP/TOXM`, `VTH0`, `K1/K2`, `NFACTOR`, `VOFF`,
`DVT*`, `ETA*`, and `DSUB`. Qualify threshold extraction, SS, body effect,
DIBL, length rolloff, and gm/Id reachability.

### Stage 2 — transport

Candidate groups include `U0`, mobility-degradation terms, `VSAT`, series
resistance, and selected transport coefficients. Qualify Id-Vg, `ID/W`, gm/Id,
strong-inversion behavior, and width scaling.

### Stage 3 — output conductance

Candidate groups include the minimum required set among `PCLM`, `PDIBLC*`,
`DROUT`, `FPROUT`, `PVAG`, and related terms. Qualify Id-Vd, `gds/ID`,
`gm/gds`, low-VDS transition, and length dependence.

### Stage 4 — charge

Candidate groups include oxide/charge refinement, overlaps, `XPART`, `CKAPPA*`,
`ACDE`, `MOIN`, and other required CAPMOD=2 terms. Qualify full Y, Cgg/Cgd/Cgs,
capacitance ratios, and intrinsic gate-charge trajectory without destroying the
previous DC contract.

### Stage 5 — temperature

Enable only the minimum required temperature coefficients. Qualify extracted
Vth, `ID/W`, gm/Id, gds/Id, and gm/gds at -40/27/85/125 degC.

### Stage 6 — optional leakage/noise refinement

Only add leakage/noise coefficients when a defensible target exists. Otherwise
keep their claim boundary explicit. Stationary `.noise` execution is still
required for catalog integration, but it characterizes model predictions, not
silicon accuracy.

At every stage, add free parameters only when existing parameters cannot meet
the held-out observable contract. Avoid large compensating parameter sets and
record parameter identifiability concerns.

## 11. Optimization and candidate selection

Hard failures are candidate rejection, not weighted penalties.

Soft interval targets should have zero penalty anywhere inside their accepted
range; do not force every observable to the center of an arbitrary interval.

Selection order is lexicographic:

1. numerical validity;
2. hard structural contract;
3. sealed device holdout;
4. io18/io25 distinctness;
5. circuit qualification;
6. epistemic-ensemble agreement;
7. lower unnecessary parameter complexity;
8. smoother and more stable terminal behavior.

The final canonical model must not be selected merely because it has the
lowest scalar fit loss.

## 12. Epistemic candidate ensemble

Because public evidence is incomplete, the release must preserve model-
construction uncertainty separately from circuit benchmark variation.

Generate multiple deterministic feasible candidates per new family. Retain at
least three independently seeded candidates that satisfy the frozen hard and
holdout contracts, unless the release stops because that is not achievable.
The exact search count and retained count above the minimum may be chosen from
runtime evidence and recorded in the generation contract.

For each retained candidate, summarize at least:

- extracted Vth and DIBL;
- `ID/W` versus gm/Id;
- `gds/ID` and gm/gds;
- Cgg/W or Cgg/(W*L);
- Cgd/Cgg;
- selected body-effect and temperature observations.

Select the public canonical card as an observable-space medoid or another
predeclared robust representative of the feasible ensemble, not an arbitrary
extreme candidate. Record the selection method before looking at downstream
circuit results.

Classify conclusions as:

- `ROBUST_ACROSS_ENSEMBLE`;
- `MAJORITY_ACROSS_ENSEMBLE`;
- `EPISTEMICALLY_UNRESOLVED`.

If a required structural/distinctness claim reverses across feasible retained
candidates, stop with `EPISTEMIC_UNCERTAINTY_TOO_WIDE`.

The epistemic ensemble is not process variation, Monte Carlo, mismatch, or a
foundry distribution.

## 13. Calibration and sealed holdout

Calibration and sealed holdout coordinates must be declared before final
candidate fitting.

The default calibration scaffold should cover 27 degC, multiple selected
lengths, multiple normalized VDS points, gm/Id targets 5/10/15/20 1/V, and a
reference width near 1 um.

The sealed device holdout must include conditions not used in calibration,
including:

- -40, 85, and 125 degC;
- intermediate lengths such as 1.5x and 3x the selected supported floor;
- intermediate VDS/VDD points;
- intermediate gm/Id targets;
- multiple widths across the qualified width range.

After unsealing, a failed candidate must not be repaired against the same
sealed set. A model/contract revision requires a new recorded generation epoch
and a newly sealed holdout definition.

## 14. Supplemental mixed-voltage qualification

Preserve `apm.characterization.v2`. Do not overload it with every v4-specific
research metric.

Add a versioned supplemental result contract, conceptually
`apm.mixed-voltage-qualification.v1`, that can persist:

- width scaling;
- body-effect sweeps;
- bias/gm-Id reachability;
- intrinsic gate-charge trajectory;
- epistemic ensemble summary;
- sealed device holdout;
- selected circuit qualification;
- io18/io25 distinctness;
- exact artifact and generation identities.

The exact persisted filenames may evolve during implementation, but the
semantic contents above are required.

## 15. Circuit qualification

Circuit fixtures qualify the usefulness and numerical stability of the model;
they are not fitting targets for a foundry circuit.

Required fixture classes:

- MOS diode;
- 1:1 current mirror;
- source follower;
- resistive-load common-source;
- ideal/behavioral-control plus PMOS pass-device fixture.

Development fixtures may expose missing contracts. Final promotion must include
a sealed circuit qualification using unseen intermediate conditions.

For PMOS pass-device qualification, exercise at least:

- `io18` at VIN 1.8 V, VOUT around 1.0 V;
- `io25` underdriven at VIN 1.8 V, VOUT around 1.0 V;
- `io25` nominal at VIN 2.5 V, VOUT around 1.2 V;
- representative loads spanning approximately 0.1, 0.5, and 1 mA.

Use explicit parallel unit devices within the public W range rather than an
unbounded virtual single transistor. Persist required VSG, total width,
conductance/inversion metrics, and intrinsic charge metrics.

Do not claim layout area, extracted gate resistance, shared-diffusion
capacitance, or production pass-FET gate charge. Public wrappers remain W/L
only.

## 16. Mixed-voltage comparisons

Preserve the existing v3 APM045 `threshold` and `gate_stack` comparison-set
meaning. Add new mixed-voltage comparison functionality rather than silently
changing the old VTG/THKOX comparison contract.

Required v4 comparison views include:

1. native profile at relative geometry (`L/Lfloor`);
2. common 1.0 V at equal physical L;
3. common 1.0 V at equal relative L;
4. common 1.8 V, `io18` versus `io25`, at equal physical L;
5. common 1.8 V, `io18` versus `io25`, at equal relative L;
6. equal-inversion views over gm/Id 5/10/15/20 1/V where reachable.

Persist raw source result identities and do not mix native-profile family
metrics with common-overlap terminal metrics without explicit labeling.

APM v4 comparisons remain device-level. Solving complete LDO performance,
optimizing pass-bank area, or topology comparison belongs to later circuit
research, not APM v4.

## 17. Intrinsic charge boundary

Because the public planar wrapper exposes only W/L, v4 charge qualification is
limited to intrinsic/model terminal charge and model-provided overlap effects.
It does not represent a complete physical pass-bank layout.

Prefer normalized quantities such as:

- intrinsic gate charge per width;
- intrinsic gate charge per drain current;
- Cgg/W;
- Cgd/W;
- Cgd/Cgg.

Future circuit/layout research may add separately declared synthetic or
extracted parasitics outside the APM device contract.

## 18. Noise and variation integration

Both new families must integrate with the existing stationary small-signal
noise dataset and comparison infrastructure.

Required noise semantics remain those of released v3:

- raw spectra are authoritative;
- acquisition/fit is fail closed;
- unobserved white/flicker/corner regions remain explicit null results;
- no process-noise calibration is implied;
- strict request identity and resume/tamper rejection remain mandatory.

Update catalog request planning from the live manifest catalog rather than
copying frozen v3 request counts into new code. Freeze the final v4 counts only
in release evidence after the exact candidate plan is generated.

APM benchmark Global/Local/All variation is required for the new families.
There is no native/foundry variation for the APM-authored io18/io25 families.
Do not equate the epistemic candidate ensemble with benchmark variation.

## 19. Spectre boundary

Generate model-only Spectre artifacts for both new families through the
existing structural path. Spectre remains `experimental_unverified` until a
real Spectre installation executes and is separately qualified.

## 20. Provenance and reproducibility

The shipped canonical model cards, family manifests, evidence matrix,
parameter-generation documentation, frozen generator inputs, and generation
records must be hash-bound by provenance.

The exact canonical card must be byte-identically reproducible from the frozen
public generation inputs, deterministic seeds, generator implementation, and
reference ngspice identity used for the release candidate.

Large raw search output, local optimizer state, virtual environments, generated
binaries, and simulator result directories remain untracked.

## 21. Required stop states

Do not improvise around a genuine failure. Record and stop on applicable states
such as:

- `MODELGEN_RECONSTRUCTION_FAILED`;
- `IO25_CONTRACT_INCONSISTENT`;
- `IO18_CONTRACT_INCONSISTENT`;
- `IO18_DISTINCTNESS_NOT_ESTABLISHED`;
- `PARAMETER_IDENTIFIABILITY_FAILURE`;
- `EPISTEMIC_UNCERTAINTY_TOO_WIDE`;
- `DC_CHARGE_CONFLICT`;
- `CIRCUIT_HOLDOUT_FAILURE`;
- `PROVENANCE_BOUNDARY_AMBIGUOUS`.

A stop state is preferable to weakening a gate, inventing a source, or fitting
a model to hidden/proprietary information.

## 22. Codex implementation latitude

The following are fixed v4 decisions unless real evidence demonstrates an
internal contradiction with the higher-level goal:

- add `io18` and `io25` only to APM045;
- do not add `io33`;
- preserve existing APM045 upstream families unchanged;
- use independently APM-authored BSIM4 4.8.2 cards;
- use ngspice 47 as the reference simulator;
- synthesize N/P independently;
- qualify a deterministic model-generation kernel first;
- use sealed device and circuit holdouts;
- retain an epistemic feasible-candidate ensemble;
- establish io18/io25 electrical distinctness;
- preserve v3 claim and Spectre boundaries.

Implementation may determine from real evidence, with recorded rationale:

- final supported L/W floors and maxima;
- final TOXE and other BSIM parameters;
- bounded search ranges and local optimizer details;
- exact calibration grid refinements;
- number of generated candidates above the required retained minimum;
- the minimum set of compact-model coefficients needed to satisfy the contract.

If a fixed assumption proves technically inconsistent, do not silently work
around it. Record the failing assumption, real evidence, alternatives, and
impact. Revise this contract only when necessary to satisfy the higher-level
`GOAL.md` without weakening the public claim boundary.

## 23. Completion states

Required successful states are:

- `MODELGEN_KERNEL_QUALIFIED`;
- `IO25_DEVICE_QUALIFIED`;
- `IO25_APPLICATION_QUALIFIED`;
- `IO18_DEVICE_QUALIFIED`;
- `IO18_APPLICATION_QUALIFIED`;
- `IO18_IO25_DISTINCTNESS_ESTABLISHED`;
- `MIXED_VOLTAGE_COMPARISON_QUALIFIED`;
- `MIXED_VOLTAGE_NOISE_INTEGRATED`;
- `MIXED_VOLTAGE_VARIATION_INTEGRATED`;
- `V4_CANDIDATE_QUALIFIED`;
- `V4_TAG_REQUALIFIED`.

The authoritative machine-readable release gates live in
`validation/release_gates_v4.toml`.
