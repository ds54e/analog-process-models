# Analog Process Models

**Repository:** https://github.com/ds54e/analog-process-models

Analog Process Models (**APM**) is a self-contained open compact-model collection and characterization framework for cross-process and within-process analog device studies.

APM is not a manufacturable PDK and does not provide layout, PCells, DRC/LVS/PEX, signoff, foundry correlation, or reliability qualification.

## Release state

- Stable historical baseline: **v1.0.0**
- Current `main`: **breaking v2.0.0 development line**
- Current v2 implementation status: see [`STATUS.md`](STATUS.md)

The v1.0.0 tag remains the validated one-family-per-technology release. Current main intentionally changes the domain model and is not release-ready until all v2 gates pass.

## v2 direction

APM v2 adds first-class electrical device families while keeping compact-model-specific raw APIs out of the common cross-technology contract.

Canonical hierarchy:

```text
Technology
  -> Electrical Family
       -> Device
```

Orthogonal concepts:

- Operating Profile
- Backend Binding
- Variation
- Comparison Set

See [`DEVICE_FAMILY_MODEL.md`](DEVICE_FAMILY_MODEL.md) for the normative taxonomy.

Required v2 families:

- APM350: `general`
- APM130: `lv`, `hv`
- APM045: `vtl`, `vtg`, `vth`, `thkox`
- APM022: `lvt`, `svt`, `hvt`
- APM016F: `lvt`, `svt`, `hvt`

Total: 13 Electrical Families.

The cross-process anchor remains one representative family per technology:

`apm350/general -> apm130/lv -> apm045/vtg -> apm022/svt -> apm016f/svt`

Within-technology comparisons add threshold-sibling and gate-stack views without mixing those choices into the golden process-scaling axis.

## v2 characterization

The v1 terminal contract remains the base:

- Id-Vg / Id-Vd
- terminal finite-difference gm/gds
- gm/Id / gm/gds
- length scaling / DIBL
- raw 4x4 terminal complex Y matrix
- Y-derived Cgg/Cgd/Cgs
- -40/27/85/125 degC

v2 adds:

- Ion
- Ioff
- `log10(Ion/Ioff)`
- subthreshold swing
- threshold-family equal-bias and equal-inversion comparisons
- gate-stack native-profile and validated common-overlap-bias comparisons

Planar current/capacitance normalization remains per width and FinFET normalization remains per fin; APM does not invent a universal effective width.

## v2 variation terminology

APM synthetic benchmark variation is explicitly separated from upstream/native variation.

v2 benchmark modes are:

- **Benchmark Global** — synthetic shared observable stress
- **Benchmark Local** — synthetic instance-local mismatch stress
- **Benchmark All** — Global + Local

Benchmark Global is not a claim of real foundry family-to-family process correlation.

Upstream/native corner/statistical/mismatch profiles retain their actual upstream names and semantics.

## Reference backend

The validated v1 development baseline is reused for v2 implementation:

- WSL2 + AlmaLinux/RHEL-compatible EL9 x86_64
- ngspice 47 with OSDI/predictor
- project-local OpenVAF-ReLoaded where Verilog-A-to-OSDI is required
- native BSIM3/BSIM4 plus PSP103 and BSIM-CMG OSDI execution

Existing project-local toolchain/cache/OSDI state may be reused during v2 development when verified. The final v2 release still requires a genuinely fresh-clone source/bootstrap validation.

Spectre remains model-only **experimental/unverified** unless real Spectre execution occurs. Virtuoso integration is user-managed and out of scope.

## Implementation specification

Long-running implementation agents must read:

- [`AGENTS.md`](AGENTS.md)
- [`GOAL.md`](GOAL.md)
- [`DEVICE_FAMILY_MODEL.md`](DEVICE_FAMILY_MODEL.md)
- [`RESULT_CONTRACT.md`](RESULT_CONTRACT.md)
- [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md)
- [`ENVIRONMENT.md`](ENVIRONMENT.md)
- [`RESEARCH_BASELINE.md`](RESEARCH_BASELINE.md)
- [`UNATTENDED_EXECUTION.md`](UNATTENDED_EXECUTION.md)
- [`STATUS.md`](STATUS.md)
- [`validation/release_gates.toml`](validation/release_gates.toml)

The current specification commit may intentionally make the old v1 release validator/tests fail until the v2 migration is implemented. Do not interpret old v1 green status as v2 completion and do not weaken v2 requirements to restore v1 compatibility.

## Licensing/provenance

Third-party model files require exact-file redistribution/provenance review. APM-authored generic models remain clearly distinguished from upstream/open model families.

Official PTM/PTM-MG cards are not shipped or used as numeric source material for APM022/APM016F authored families.

See `THIRD_PARTY.md`, `LICENSES/`, `REUSE.toml`, and per-technology provenance files for current source/license boundaries.
