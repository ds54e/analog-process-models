# Changelog

All notable changes to Analog Process Models (APM) are documented in this file.

## [1.0.0] - 2026-08-30

The first APM release provides five self-contained N/P compact-model kits:
APM350 (BSIM3), APM130 (IHP SG13G2/PSP103), APM045 (FreePDK45/BSIM4),
APM022 (independently authored BSIM4 parameters), and APM016F (independently
authored parameters with the BSIM-CMG 112.1.0 engine).

It includes:

- a reproducible WSL2/RHEL-compatible EL9 x86_64 reference toolchain using
  ngspice 47 with OSDI and OpenVAF-ReLoaded;
- terminal-level Id-Vg, Id-Vd, finite-difference gm/gds, gm/Id, gm/gds,
  length scaling, DIBL, four-temperature, raw 4x4 Y-matrix, and terminal
  capacitance characterization for every kit;
- normalized all-kit comparison at documented `L/Lmin`, `VOUT/VDD`, and
  `gm/Id` coordinates, with planar-per-width and FinFET-per-fin quantities kept
  distinct;
- deterministic APM benchmark corners and process/mismatch/all variation,
  plus technology-neutral Rbench/Cbench passives;
- separately identified IHP-native APM130 corners, process variation, and
  local mismatch validation;
- exact-file model provenance, retained upstream licenses/notices, REUSE/SPDX
  metadata, and a self-contained source distribution; and
- a fail-closed 16-gate release validator and exact-commit clean-clone
  attestation flow.

The Spectre layer is model-only and **experimental/unverified**. It was checked
structurally but was not parsed or simulated with a real Spectre installation.
APM is not a manufacturable PDK, and no APM-authored generic kit carries a
foundry- or silicon-correlation claim.
