# Changelog

All notable changes to Analog Process Models (APM) are documented here.

## [4.0.0] - 2026-09-05

APM 4.0.0 preserves the immutable v3 electrical and stationary-noise
contracts and adds two APM-authored, planar-bulk BSIM4 mixed-voltage research
families to APM045.

### APM045 mixed-voltage families

- added family-qualified `apm045/io18` and `apm045/io25` N/P devices, expanding
  the manifest-driven catalog to five technologies, 15 electrical families,
  and 30 public MOS devices;
- added nominal 1.8 V and 2.5 V Operating Profiles plus explicit common-1.0 V
  and common-1.8 V comparison profiles; these are characterization choices,
  not safe-voltage, breakdown, lifetime, or reliability ratings;
- qualified model-supported L/W ranges, width scaling, body effect, bias
  reachability, temperature behavior, intrinsic gate charge, complete terminal
  Y matrices, and finite-difference convergence with ngspice 47; and
- supplied ngspice cards/wrappers and model-only Spectre artifacts for both
  families while preserving every released upstream APM045 family/card byte.

### Public model-generation and sealed qualification

- added a deterministic offline model-generation kernel, public source-fact
  matrix, staged bounded search, parameter-sensitivity checks, hard-constraint
  rejection, and byte-identical regeneration of the four canonical cards;
- qualified the generator against held-out APM022/SVT and APM045/VTG terminal
  behavior without requiring original-parameter recovery;
- preserved failed epochs 1 and 2 as fail-closed evidence, then qualified epoch
  3 on its first unseal using separately sealed device and circuit holdouts;
- retained five feasible N/P candidate pairs per family and selected the
  canonical pair by a predeclared observable-space medoid only after circuit
  results were available; and
- reports that retained ensemble as model-construction uncertainty, never as
  process variation, mismatch, yield, or foundry statistics.

### Circuit and comparison coverage

- added sealed MOS-diode, 1:1 mirror, source-follower, resistive-load
  common-source, and bounded parallel-unit PMOS pass-device fixtures;
- established io18/io25 capacitance-density, current-density, and
  design-realization distinction at common 1.8 V without forcing unrelated
  leakage, noise, gm/gds, or total-charge ordering; and
- added `apm.mixed-voltage-comparison.v1` with native-relative-geometry,
  common-bias, equal-physical-length, equal-relative-length, and
  equal-inversion views, exact source identities, explicit metric bases, and
  honest `target_not_reachable` states.

### Variation, noise, provenance, and release validation

- integrated all 15 families and 30 devices into Benchmark Global/Local/All,
  exact adapter calibration, full characterization, and Spectre structural
  generation;
- extended live stationary-noise planning to io18/io25 while preserving
  `apm.noise-characterization.v1`, `apm.noise-comparison.v1`, the frozen fit and
  acquisition identities, Sparse/no-KLU execution, strict resume, and tamper
  rejection;
- added exact public-generation lineage and license/provenance checks for all
  new APM-authored assets; and
- added a separate 16-gate v4 release validator with phase-aware clean-clone
  attestation: 15 pre-tag gates authorize tag creation, while all 16 gates must
  pass from a second fresh exact-tag clone before the GitHub Release.

APM 4.0.0 is not a manufacturable PDK. It adds no foundry or silicon
correlation, standalone io33 family, foundry design rules, reliability rating,
layout-dependent accuracy, calibrated gate-leakage/GIDL or process-noise
accuracy, noise Monte Carlo, or real Spectre validation.

## [3.0.0] - 2026-08-30

APM 3.0.0 preserves the v2 electrical-family/catalog and terminal-
characterization contracts and adds a separately versioned stationary
small-signal MOS-noise domain.

### Stationary-noise measurement foundation

- added `apm.noise-characterization.v1` with precise gm/Id bias refinement,
  canonical external drain-terminal total PSD, gate-referred PSD using the
  actual complex transfer, raw backend source breakdown, and parameter-level
  effective noise provenance;
- analytically qualified the 1-ohm CCVS drain-current probe using resistor,
  APM-owned OSDI white/flicker, and decisive correlated-network fixtures;
- qualified native BSIM3, PSP103 OSDI, native BSIM4, and BSIM-CMG OSDI paths
  with ngspice 47's normal Sparse solver; and
- retained APM350/APM022/APM016F production cards unchanged from v2.0.0.

### Acquisition and fail-closed fitting

- added `apm.noise-fit.contiguous-regions@1.0.0` with centered local log-slope
  classification, deterministic contiguous-region selection, explicit
  span/quality gates, and null metrics when a physical region is not observed;
- added `apm.noise-acquisition.bounded-white-search@1.0.0`, starting at
  1 Hz–100 MHz and 20 points/decade and extending complete sweeps only as
  needed through bounded 1 GHz, 10 GHz, and 100 GHz endpoints;
- preserved interior white plateaus before later high-frequency shaping and
  never substitutes the last frequency point for a white floor;
- qualified eight deterministic synthetic fit cases, all four engines at the
  canonical and 50 mV diagnostic points, and a runtime-only correlated
  BSIM-CMG `TNOIMOD=1` capability check without editing the production card.

### Catalog-wide datasets and comparisons

- added deterministic manifest-driven planning across all five technologies,
  13 electrical families, and 26 public MOS devices;
- added temperature, inversion, manifest-declared length, and integer-NFIN
  datasets with explicit `validated`, `target_not_reachable`, or
  `simulation_failed` terminal states and no silent gm/Id clipping;
- added `apm.noise-comparison.v1` threshold-family equal-inversion/equal-bias
  and polarity-separated cross-process anchor outputs, including common-
  frequency values and 1 Hz–10 MHz gate-referred integration;
- retained native drawn-width versus integer-NFIN geometry and produced no
  artificial planar/FinFET effective-width ratio;
- added stable semantic request identity, cross-dataset deduplication, and
  strict resumable execution that accepts only complete exact artifact/hash
  matches and rejects stale, incomplete, mismatched, or tampered results.

### Release hardening

- migrated the current release SSOT and fail-closed evaluator to an auditable
  18-gate v3 contract covering the reference toolchain, complete v2 electrical
  baseline, N0/N1/N2 noise evidence, model-card immutability, distribution
  hygiene, licensing/provenance, metadata, claims, and exact clean-clone
  qualification;
- updated package/runtime/CLI and current release documentation to 3.0.0 while
  preserving historical v1/v2 evidence and independent schema identities; and
- strengthened pre-bootstrap attestation and public-repository hygiene checks
  for generated state, secrets/private artifacts, private paths, large files,
  tag absence, and claim boundaries.

APM 3.0.0 does **not** introduce silicon-calibrated generic process-noise
models. It does not add process-noise tuning, noise Monte Carlo, RTS/RTN,
transient noise, PSS/PNoise, oscillator phase noise, full terminal
noise-correlation matrices, real Spectre validation, layout/signoff scope, or
a universal planar/FinFET effective width.

## [2.0.0] - 2026-08-30

APM 2.0.0 is an intentional breaking release that replaces the v1
one-family-per-technology runtime with the manifest-driven hierarchy
Technology → Electrical Family → Device.

Highlights:

- five technologies, 13 electrical families, and 26 family-qualified public
  MOS devices with sparse-capable manifest discovery;
- APM130 IHP SG13G2 LV/HV PSP103 families, APM045 FreePDK45
  VTL/VTG/VTH/THKOX families, independently authored APM022 LVT/SVT/HVT BSIM4
  families, and independently authored APM016F LVT/SVT/HVT BSIM-CMG families;
- characterization schema `apm.characterization.v2`, adding family/device
  identity, Ion, Ioff, `log10(Ion/Ioff)`, and frozen subthreshold-swing
  extraction while retaining signed currents, finite-difference gm/gds, and
  full raw complex terminal Y data;
- manifest-defined threshold equal-bias/equal-inversion, gate-stack
  native/common-overlap, and five-anchor cross-process comparisons;
- Benchmark Global/Local/All variation with technology/polarity sibling-family
  latent sharing, family/device-calibrated observable adapters, deterministic
  ngspice replay, and v2 Rbench/Cbench semantics;
- independently validated IHP-native APM130 LV and HV corners, process
  statistics, and mismatch, without invented native cross-family correlation;
- model-only Spectre structure for every family, explicitly
  **experimental/unverified** and not parsed or simulated by a real Spectre
  installation;
- exact shipped-file provenance, generated-asset reproducibility, license
  boundary checks, and repository-wide REUSE/SPDX compliance; and
- a fail-closed 20-gate release validator with exact-commit WSL2 + EL9
  clean-clone attestation.

The v1 `kit.toml` source of truth, unqualified wrapper aliases, canonical v1
result/benchmark schemas, and process/mismatch benchmark naming are not part of
the v2 runtime contract. Backward compatibility was intentionally not required.

APM remains not a manufacturable PDK. APM-authored generic decks make no
foundry- or silicon-correlation claim.

## [1.0.0] - 2026-08-30

The first APM release provided one N/P compact-model kit for each of APM350,
APM130, APM045, APM022, and APM016F; terminal characterization; deterministic
benchmark process/mismatch variation; selected IHP-native APM130 validation;
model-only experimental/unverified Spectre files; exact-file provenance; and a
16-gate release flow. Its evidence remains historical and does not satisfy v2
release gates.
