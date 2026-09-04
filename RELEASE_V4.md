# Analog Process Models v4.0.0

APM v4.0.0 extends the immutable v3 baseline with two independently
APM-authored planar-bulk BSIM4 research families: `apm045/io18` and
`apm045/io25`. The manifest-driven catalog now exposes five technologies, 15
electrical families, and 30 family-qualified public MOS devices.

This release preserves the existing `apm.characterization.v2`,
`apm.noise-characterization.v1`, and `apm.noise-comparison.v1` contracts, the
frozen v3 noise fit/acquisition identities, every released v3 tag object and
evidence file, and the exact bytes of the four upstream-derived APM045
families. APM045/VTG remains the cross-process anchor. V4 does not reinterpret
the frozen v3 release validator or its 18-gate evidence.

## New electrical families

`apm045/io18` is a generic 1.8 V-class family with `nominal_1v8` and
`common_overlap_1v0` Operating Profiles. `apm045/io25` is a distinct generic
2.5 V-class family with `nominal_2v5`, `common_overlap_1v8`, and
`common_overlap_1v0` profiles. Public devices retain four terminals `d g s b`
and expose only `w,l`; no public multiplicity, finger, layout, or parasitic
interface is implied.

The qualified io18 model-supported range is L = 0.08–2 µm and W = 0.25–16 µm.
The qualified io25 range is L = 0.18–2 µm and W = 0.25–16 µm. These are tested
compact-model behavior bounds, not foundry design-rule minima. Profile voltages
are characterization coordinates, not breakdown, lifetime, safe-operating-area,
or reliability ratings. A standalone io33 family is not part of v4.

## Public evidence and model generation

The machine-readable `models/apm045/mixed_voltage_evidence.toml` separates
public observed facts, engineering priors, and APM behavior contracts. Each
source fact records its locator, confidence, allowed uses, and forbidden uses.
No private or proprietary PDK input supplies model parameters, and physical
oxide observations are not copied directly into BSIM `TOXE` without an
explicit numerical basis.

The offline model-generation flow under
`tools/modelgen/apm045_mixed_voltage/` uses a deterministic observable kernel,
bounded staged parameter release, sensitivity checks, and hard-constraint
rejection. Its reconstruction prerequisite recovered held-out terminal
behavior for APM022/SVT and APM045/VTG N/P fixtures using ngspice 47; original
parameter recovery was neither required nor claimed.

Generation epochs are immutable experimental records. Epochs 1 and 2 failed
their predeclared reachability requirements and were neither repaired nor
promoted. Epoch 3 used new seeds and new sealed definitions. Calibration
retained five feasible N/P candidate pairs for each new family. The first
unseal passed the device holdout, structural checks, all circuit candidate
pairs, and the required io18/io25 distinction checks. Only then did the
predeclared observable-space medoid select io18 seed 54003 and io25 seed 54002.
Fresh release validation regenerates all epoch-3 candidates and requires the
four selected cards to be byte-identical to the shipped cards.

The retained epistemic ensemble measures model-construction uncertainty under
the public behavior contract. It is not process variation, device mismatch,
yield prediction, a probability distribution over silicon, or a replacement
for foundry statistical models.

## Sealed device and circuit qualification

Calibration and sealed holdout definitions were fixed before final fitting.
The device holdout includes non-calibration temperatures, intermediate lengths,
intermediate drain biases, intermediate gm/Id coordinates, and multiple widths.
The final successful epoch was not tuned after seeing those holdout results.

The separately sealed circuit suite covers MOS diodes, 1:1 current mirrors,
source followers, resistive-load common-source stages, and PMOS pass-device
fixtures. Pass-device cases include 1.8 V-to-1.0 V io18 operation, an io25
underdrive observation at 1.8 V-to-1.0 V, and 2.5 V-to-1.2 V io25 operation at
100 µA, 500 µA, and 1 mA. Results use explicit bounded parallel units and
report required VSG, total width, gm/Id, gds/Id, Ron×W, and intrinsic charge
metrics. These fixtures test self-consistency of compact-model predictions;
they are not foundry circuit targets, layout-area claims, or silicon
measurements.

## Mixed-voltage comparisons

The new `apm.mixed-voltage-comparison.v1` result keeps six views explicit:

- native relative geometry;
- common 1.0 V at equal physical length;
- common 1.0 V at equal relative length;
- common 1.8 V io18/io25 at equal physical length;
- common 1.8 V io18/io25 at equal relative length; and
- equal inversion at requested gm/Id values of 5, 10, 15, and 20 1/V.

Each observation binds exact source artifacts, preserves raw signed terminal
quantities and complete Y matrices, and labels native-family versus common-bias
terminal metrics. A requested inversion point may honestly be
`target_not_reachable`; silent endpoint clipping and fabricated values are
forbidden. The qualified common-1.0 V view preserves the declared
VTG > io18 > io25 capacitance-density hierarchy. At common 1.8 V, io18 and io25
establish capacitance-density, current-density, and design-realization
distinction. V4 does not force a universal ordering for noise, leakage, gm/gds,
or total gate charge.

## Characterization, variation, and noise

All 15 families retain raw simulator inputs/logs, signed terminal currents,
finite-difference gm/gds with convergence checks, and full complex 4×4 terminal
Y matrices at −40, 27, 85, and 125 °C. Native compact-model gm/gds values are
diagnostic oracles; converged terminal finite differences remain canonical.

Benchmark Global, Benchmark Local, and Benchmark All include io18/io25 through
observable `vth_shift` and `drive_shift` adapters. Benchmark Global is a
synthetic comparison design, not physical process variation or foundry family
correlation. The epoch-3 epistemic ensemble remains separate from benchmark
variation. APM130's upstream-native process/mismatch flow remains separate and
does not gain an invented cross-family correlation or native All mode.

Stationary-noise planning is derived from the live 15-family/30-device catalog.
It preserves the v3 fit/acquisition method identities, normal Sparse/no-KLU
execution, explicit `validated`/`target_not_reachable`/`simulation_failed`
states, exact request identity, deduplication, strict resume, and stale/tamper
rejection. These outputs characterize compact-model predictions; v4 performs
no process-noise tuning and claims no silicon-calibrated process-noise
accuracy. Unobserved fit regions remain null. Noise Monte Carlo, RTS/RTN,
transient noise, PSS/PNoise, oscillator phase noise, and full terminal
noise-correlation matrices remain outside scope.

## Provenance and backend boundary

The new cards, wrappers, manifests, model-generation sources, configuration,
and evidence are APM-authored assets under the repository license. Exact
generation inputs, canonical seeds, hashes, public evidence, and derivation
relationships are recorded in `models/apm045/provenance.toml`. Upstream IHP,
FreePDK45, PSP103, and BSIM-CMG files retain their own exact inventory,
revisions, notices, redistribution terms, and modification status. Official
PTM/PTM-MG cards are neither shipped nor used as numeric source material for
APM-authored models.

ngspice 47 is the required real reference backend. Spectre files exist for all
15 families but remain model-only and **experimental/unverified**: no real
Spectre installation parsed or simulated them, and no Virtuoso integration is
claimed.

## Release qualification

The machine-readable v4 contract is `validation/release_gates_v4.toml`. It is
independent of the frozen v3 contract. The candidate workflow starts from an
untouched detached HTTPS clone of exact `origin/main`, with the future v4 tag
absent. Pre-bootstrap attestation binds origin, commit, v3 tag identity,
platform, clean worktree, and absence of generated project state. The full
candidate command then rebuilds/validates the toolchain, reruns current and v3
regressions, reconstructs modelgen fixtures, regenerates all canonical cards,
freshly replays all frozen epoch-3 device and circuit holdouts without changing
candidate parameters, characterizes all families, runs every comparison and
variation flow, executes a fresh live noise catalog followed by strict
resume/tamper qualification, and audits provenance, distribution hygiene,
metadata, claims, and model-only Spectre structure.

A successful candidate report passes 15/15 candidate-required gates and
explicitly leaves `release.exact_tag_requalification` pending. That result
authorizes one annotated `v4.0.0` tag at the qualified commit. A second fresh
HTTPS clone checks out that tag detached and must pass all 16/16 gates before
the GitHub Release is authorized. Missing, skipped, stale, hash-mismatched, or
evidence-free required results fail closed. Exact commands are in
`docs/release-validation.md`.

## Claim boundaries

APM v4.0.0 is not a manufacturable PDK. The io18/io25 cards are generic
research models, not TSMC, UMC, or other foundry models. The release claims no
foundry or silicon correlation, manufacturing/yield prediction, reliability or
safe-voltage qualification, foundry design-rule minimum, layout-dependent
accuracy, calibrated gate-leakage/GIDL accuracy, calibrated process-noise
accuracy, standalone io33 qualification, or real Spectre validation.
