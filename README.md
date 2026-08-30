# Analog Process Models

Analog Process Models (**APM**) is a self-contained collection of open compact
models and a terminal-characterization framework for cross-process and
within-process analog device studies. This repository is the APM project;
within it, APM always means Analog Process Models.

Version **2.0.0** introduces first-class electrical families, 13 characterized
families across five technologies, and a fail-closed 20-gate release flow.
Post-v2 `main` also contains the V3-N0 stationary small-signal MOS-noise
characterization foundation. V3-N0 is a development milestone, not a v3.0.0
release or a silicon-noise calibration claim.

## Scope

APM supplies family-qualified MOS model wrappers, manifest-driven discovery,
ngspice characterization, comparison tools, synthetic benchmark variation,
technology-neutral benchmark R/C devices, and exact model provenance.

APM is **not a manufacturable PDK**. It does not provide layout, PCells, DRC,
LVS, PEX, standard cells, signoff, reliability qualification, foundry
correlation, yield prediction, RF devices, silicon-calibrated process-noise
models, AMS integration, or Virtuoso automation. V3-N0 characterizes the noise
predictions already present in the compact models and preserves their
parameter provenance.

## Device-family domain model

The canonical hierarchy is:

**Technology → Electrical Family → Device**

Operating Profile, Backend Binding, Variation, and Comparison Set are
orthogonal concepts. Family identity describes a nominal electrical
parameterization, not merely an intended use such as core or I/O. The
manifest-driven catalog currently contains:

| Technology | Electrical families | Compact model |
| --- | --- | --- |
| APM350 | `general` | BSIM3 |
| APM130 | `lv`, `hv` | PSP103 |
| APM045 | `vtl`, `vtg`, `vth`, `thkox` | BSIM4 |
| APM022 | `lvt`, `svt`, `hvt` | BSIM4 |
| APM016F | `lvt`, `svt`, `hvt` | BSIM-CMG 112.1.0 |

Every planar device exposes terminals `d g s b` and public sizing parameters
`w,l`. Every FinFET exposes `d g s b` and `l,nfin`. APM deliberately omits a
common multiplicity/finger API. Public model names are family-qualified, for
example `apm045_vtg_nmos` and `apm016f_svt_nfet`.

The normative taxonomy is in [`DEVICE_FAMILY_MODEL.md`](DEVICE_FAMILY_MODEL.md).

## Quick start

The validated reference host is WSL2 with AlmaLinux/RHEL-compatible EL9 on
x86_64, using ngspice 47 with OSDI and a project-local OpenVAF-Re-Loaded build.
Keep the checkout and generated state on the Linux filesystem, not `/mnt/c`.

```console
git clone https://github.com/ds54e/analog-process-models.git
cd analog-process-models
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm build-models
.venv/bin/apm doctor
```

The setup is project-local below ignored `.apm/` and `.venv/` paths. APM does
not depend on `~/.spiceinit` or GUI state.

Discover and inspect the catalog:

```console
.venv/bin/apm list technologies
.venv/bin/apm list families apm045
.venv/bin/apm list devices apm045/vtg
.venv/bin/apm describe apm045/vtg/nmos
```

Characterize a family, execute a manifest-defined comparison set, or compare
the five cross-process anchors:

```console
.venv/bin/apm characterize apm045/vtg --output .apm/results/apm045-vtg
.venv/bin/apm compare-set apm045 threshold --output .apm/results/apm045-threshold
.venv/bin/apm compare-set apm045 gate_stack --output .apm/results/apm045-gate-stack
.venv/bin/apm compare-anchors --output .apm/results/anchors
```

Commands refuse to overwrite a non-empty result directory. Generated OSDI
binaries and full simulator results are intentionally untracked.

## Operating profile versus validity

An APM Operating Profile is a documented characterization choice, not a model
validity or reliability rating. Family manifests separately record supported
geometry evidence, a default profile, and any common-overlap comparison
profile. Unknown validity bounds remain unknown rather than being treated as
unlimited.

The APM045 THKOX native profile is an APM-selected 2.0 V behavior profile; its
gate-stack comparison with VTG uses an explicitly validated 1.0 V common
overlap. APM130 HV uses a 3.3 V native profile and a 1.2 V LV/HV common overlap.
These voltages do not imply breakdown, lifetime, or safe-operating-area claims.

## Characterization

`apm characterize` produces schema `apm.characterization.v2` and retains the
raw simulator inputs, logs, signed terminal currents, and complete complex 4×4
terminal Y matrices. Derived results include Id–Vg/Id–Vd, finite-difference
gm/gds and convergence, gm/Id, gm/gds, length scaling, DIBL, Y-derived
capacitance, Ion, Ioff, `log10(Ion/Ioff)`, and a frozen/versioned subthreshold
swing extraction at −40, 27, 85, and 125 °C.

N/P comparisons use explicit effective-voltage and positive-current-magnitude
coordinates while preserving raw signed terminal quantities. Planar current,
gm, and capacitance normalize per drawn width; FinFET values normalize per fin.
Those bases are never silently equated. See
[`docs/characterization.md`](docs/characterization.md).

## Stationary noise characterization

The independent `apm.noise-characterization.v1` domain preserves the released
`apm.characterization.v2` DC/Y/capacitance behavior. Run one public device or
the complete V3-N0 four-engine qualification with:

```console
.venv/bin/apm noise apm130/lv/nmos --output .apm/results/noise-apm130-lv-nmos
.venv/bin/apm noise-check --output .apm/results/v3-n0-noise-spike
```

The spike first qualifies the 1-ohm drain-current probe against an analytic
resistor, APM-owned OSDI white/flicker fixtures, and a decisive correlated
internal-noise network. It then runs native BSIM3, PSP103 OSDI, native BSIM4,
and BSIM-CMG OSDI with ngspice's normal Sparse solver. The provisional point is
27 °C, `L/Lmin=2`, `VOUT/VDD=0.5`, and resolved `gm/Id=15 1/V`; the provisional
sweep is 1 Hz through 100 MHz at 20 points/decade.

Each result preserves the exact refined bias, finite-difference gm/gds, raw
spectrum, complex external gate-to-drain transfer, backend source names, and
parameter-level effective noise provenance. Canonical spectrum fields are
`s_idrain_terminal_a2_per_hz`, `s_vgate_equivalent_v2_per_hz`,
`y_dg_real_s`, and `y_dg_imag_s`. Fits are secondary, versioned, and fail
closed when a white or flicker region is not observed. See
[`NOISE_CHARACTERIZATION.md`](NOISE_CHARACTERIZATION.md) for the normative
contract and claim boundaries.

## Comparison methodology

The cross-process golden axis uses one manifest-selected family per technology:

`apm350/general → apm130/lv → apm045/vtg → apm022/svt → apm016f/svt`

It compares normalized coordinates such as `L/Lmin`, `VOUT/VDD`, and gm/Id.
Current/capacitance ratios are withheld across per-width and per-fin bases.

Within a technology, threshold-family sets report equal-bias and
equal-inversion views. Gate-stack sets report each family's native Operating
Profile and a separately simulated common-overlap profile. The required sets
cover APM045 VTL/VTG/VTH and VTG/THKOX, APM022 LVT/SVT/HVT, APM016F
LVT/SVT/HVT, and APM130 LV/HV.

## Benchmark versus upstream variation

APM benchmark variation is synthetic and observable: `vth_shift` changes
threshold magnitude and `drive_shift` changes terminal drain-current
magnitude. Its three modes are **Benchmark Global**, **Benchmark Local**, and
**Benchmark All**. Global MOS latents are shared by technology, polarity, and
intent across sibling families; local latents are independent per instance and
scale as `1/sqrt(match_size)`. ngspice samples are generated deterministically
in Python and persist their PCG64 seed and resolved latents.

Benchmark Global is a comparison design, not a claim of physical foundry
family correlation. IHP-native APM130 LV/HV corners, statistical/process
variation, and mismatch retain their upstream names and are validated in a
separate flow without invented cross-family correlation or a synthetic native
All mode. See [`docs/benchmark-variation.md`](docs/benchmark-variation.md) and
[`docs/native-variation.md`](docs/native-variation.md).

## Model provenance

APM130 and APM045 retain exact-file provenance to pinned, redistributable IHP
SG13G2 and FreePDK45 sources. The PSP103 and BSIM-CMG compiler sources retain
their upstream licenses and notices. APM350, APM022, and the APM016F parameter
deck are independently authored APM assets.

Official PTM/PTM-MG model cards are neither shipped nor used as numeric source
material for APM022 or APM016F. Every shipped model input is hash-declared in a
technology `provenance.toml`; `apm provenance-check` verifies exact inventory,
license boundaries, local include closure, independent-variant records, and
REUSE/SPDX compliance. See [`THIRD_PARTY.md`](THIRD_PARTY.md).

## Model fidelity and limitations

The APM-authored models are generic educational/comparison assets with explicit
terminal-behavior contracts. They are not calibrated to proprietary silicon.
Upstream-derived APM130 and APM045 expose only the audited model subset and do
not turn this repository into the upstream PDK. Characterization establishes
behavior only over recorded geometry, bias, and temperature points; it is not
a reliability or manufacturing guarantee.

Spectre files are model-only and **experimental/unverified**. They have not
been parsed or simulated by a real Spectre installation, and static checks do
not establish numerical equivalence with ngspice. See
[`docs/spectre.md`](docs/spectre.md).

## Release validation

The authoritative v2 contract is
[`validation/release_gates.toml`](validation/release_gates.toml). The release
command implements exactly its 20 required gates and fails for a missing,
skipped, evidence-free, or failed gate:

```console
.venv/bin/apm validate
.venv/bin/apm validate --release --output .apm/results/v2-release
```

The final release gate additionally requires an exact-commit clean-clone
attestation captured immediately after cloning on the designated WSL2 + EL9
host. See [`docs/release-validation.md`](docs/release-validation.md) for the
complete sequence. Historical v1 evidence does not satisfy a v2 gate.

V3-N0 does not change this released v2 contract, the package version, or any
release tag. Its separate `apm noise-check` command validates the development
spike and is not a substitute for `apm validate --release`.

Repository policy, implementation scope, and result semantics are defined by
[`AGENTS.md`](AGENTS.md), [`GOAL.md`](GOAL.md), and
[`RESULT_CONTRACT.md`](RESULT_CONTRACT.md).
