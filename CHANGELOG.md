# Changelog

All notable changes to Analog Process Models (APM) are documented here.

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
