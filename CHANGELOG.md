# Changelog

All notable changes to Analog Process Models (APM) are documented here.

## Post-v2 development — V3-N2 catalog-wide noise qualification

- added a deterministic manifest-driven plan for all five technologies, 13
  electrical families, and 26 public MOS devices, covering temperature,
  inversion, manifest-declared length, and integer-NFIN datasets plus
  threshold-family and cross-process comparison views;
- added stable semantic request identity, cross-dataset physical-request
  deduplication, complete terminal status, and strict resumable execution that
  reuses only exact request/artifact hash matches and quarantines stale or
  incomplete results;
- added `apm.noise-comparison.v1` machine-readable threshold equal-inversion,
  threshold equal-bias, and separate N/P cross-process-anchor outputs with
  exact source-result references, common-frequency values, and 1 Hz–10 MHz
  gate-referred integration;
- added geometry-native descriptive length/NFIN scaling observations without
  invented planar-width grids, universal monotonic laws, or planar/FinFET
  effective-width ratios;
- retained converged terminal finite-difference gm/gds as canonical while
  recording native OP disagreements diagnostically at numerical floors, and
  qualified ngspice's input-referred-noise convenience oracle above its
  observed gain-squared clamp while retaining all raw data; and
- added `apm noise-catalog-check --output DIR [--resume]` with nested V3-N0/N1
  regression, Sparse/no-KLU audit, model-card immutability, resume/stale-result
  qualification, comparison/coverage indexes, and compact report hashes.

V3-N2 characterizes existing compact-model predictions. It does not tune
process-noise coefficients, establish silicon/foundry accuracy, change package
version, or create a v3 release/tag.

## Post-v2 development — V3-N1 noise method qualification

- replaced provisional fixed review windows with the versioned
  `apm.noise-fit.contiguous-regions@1.0.0` detector, including centered local
  log-slope classification, deterministic contiguous-region selection,
  explicit quality gates, and fail-closed null metrics;
- added bounded complete-sweep acquisition at 100 MHz, 1 GHz, 10 GHz, and
  100 GHz, stopping at the first valid white region and retaining every
  attempt's raw spectrum, fit diagnostics, model/source provenance, and
  Sparse/no-KLU attestation;
- qualified deterministic pure-white, pure-flicker, known-corner,
  interior-plateau/high-frequency-rise, truncated, no-flicker,
  insufficient-span, and malformed-input cases;
- added four-engine 50 mV VOUT diagnostics and a runtime-only BSIM-CMG
  `TNOIMOD=1` correlated-noise capability run without modifying the production
  APM016F card; and
- added `apm noise-method-check` for combined V3-N0 regression and V3-N1
  real-tool qualification.

V3-N1 does not expand to all 26 devices, tune process-noise coefficients,
change package version, or create a v3 release/tag.

## Post-v2 development — V3-N0 stationary MOS-noise foundation

- added the independent `apm.noise-characterization.v1` domain without
  changing released `apm.characterization.v2` behavior;
- added precise gm/Id bias refinement, canonical external drain/gate-referred
  PSD and complex transfer persistence, raw source breakdown, and
  engine-specific effective-parameter provenance;
- qualified the 1-ohm current probe with analytic resistor, APM-owned OSDI
  white/flicker, and decisive correlated-network fixtures using ngspice's
  normal Sparse solver;
- exercised native BSIM3, PSP103 OSDI, native BSIM4, and BSIM-CMG OSDI at the
  provisional four-engine spike point; and
- added fail-closed provisional spectrum fitting and explicit next-milestone
  recommendations without tuning APM-authored process-noise coefficients.

V3-N0 is a development milestone, not a v3.0.0 release or a silicon-noise
calibration claim. The package remains version 2.0.0 and `v2.0.0` remains
immutable.

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
