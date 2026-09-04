# Analog Process Models

Analog Process Models (**APM**) is a self-contained collection of open compact
models and a terminal-characterization framework for cross-process and
within-process analog device studies. This repository is the APM project;
within it, APM always means Analog Process Models.

Version **4.0.0** preserves the released v3 electrical and stationary-noise
contracts and adds independently APM-authored `apm045/io18` and
`apm045/io25` mixed-voltage research families. The live catalog contains 15
electrical families and 30 public MOS devices across five technologies.

The immutable annotated `v3.0.0` release remains unchanged. A v4 release is
complete only after the exact candidate passes 15 pre-tag gates, the annotated
`v4.0.0` tag is created at that candidate, and a second fresh clone of the
exact tag passes all 16 gates before the GitHub Release is created.

## Scope

APM supplies family-qualified MOS model wrappers, manifest-driven discovery,
ngspice characterization, comparison tools, synthetic benchmark variation,
technology-neutral benchmark R/C devices, and exact model provenance.

APM is **not a manufacturable PDK**. It does not provide layout, PCells, DRC,
LVS, PEX, standard cells, signoff, reliability qualification, foundry
correlation, yield prediction, RF devices, silicon-calibrated process-noise
models, AMS integration, or Virtuoso automation. The noise datasets
characterize compact-model predictions already present in the cards and
preserve their parameter provenance; they do not establish silicon or foundry
noise accuracy. The retained io18/io25 feasible ensemble describes
model-construction uncertainty, not process variation, mismatch, yield, or
silicon statistics. Noise Monte Carlo, RTS/RTN, transient noise, PSS/PNoise,
oscillator phase noise, and full terminal noise-correlation matrices remain
outside v4.0.0.

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
| APM045 | `vtl`, `vtg`, `vth`, `thkox`, `io18`, `io25` | BSIM4 |
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
.venv/bin/apm compare-set apm045 mixed_voltage --output .apm/results/apm045-mixed-voltage
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
APM045 io18 uses nominal 1.8 V plus a common 1.0 V profile. APM045 io25 uses
nominal 2.5 V plus common 1.8 V and 1.0 V profiles. These voltages do not imply
breakdown, lifetime, or safe-operating-area claims.

The qualified io18 model-supported range is L = 0.08–2 µm and W = 0.25–16 µm;
the io25 range is L = 0.18–2 µm and W = 0.25–16 µm. These are tested compact-
model behavior ranges, not foundry design-rule minima or layout rules.

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
`apm.characterization.v2` DC/Y/capacitance behavior. Schema versions identify
data contracts rather than package releases. Run one public device with:

```console
.venv/bin/apm noise apm130/lv/nmos --output .apm/results/noise-apm130-lv-nmos
```

Maintainer/research qualification commands are also available for the analytic
harness, frozen acquisition/fit method, and catalog-wide dataset:

```console
.venv/bin/apm noise-check --output .apm/results/v3-n0-noise-spike
.venv/bin/apm noise-method-check --output .apm/results/v3-n1-noise-method
.venv/bin/apm noise-catalog-check --output .apm/results/v3-n2-noise-catalog
.venv/bin/apm noise-catalog-check --output .apm/results/v3-n2-noise-catalog --resume
```

The harness first qualifies the 1-ohm drain-current probe against an analytic
resistor, APM-owned OSDI white/flicker fixtures, and a decisive correlated
internal-noise network. It then runs native BSIM3, PSP103 OSDI, native BSIM4,
and BSIM-CMG OSDI with ngspice's normal Sparse solver. The canonical point is
27 °C, `L/Lmin=2`, `VOUT/VDD=0.5`, and resolved `gm/Id=15 1/V`. The released
acquisition starts at 1 Hz through 100 MHz and 20 points/decade, then repeats
the complete sweep with bounded upper endpoints of 1 GHz, 10 GHz, and 100 GHz
only while no valid white region is observed. Absence at the 100 GHz cap
remains an explicit null result rather than a fabricated fit.

Each result preserves the exact refined bias, finite-difference gm/gds, raw
spectrum, complex external gate-to-drain transfer, backend source names, and
parameter-level effective noise provenance. Canonical spectrum fields are
`s_idrain_terminal_a2_per_hz`, `s_vgate_equivalent_v2_per_hz`,
`y_dg_real_s`, and `y_dg_imag_s`. Fits are secondary, versioned, and fail
closed when a white or flicker region is not observed. The released frozen
`apm.noise-fit.contiguous-regions@1.0.0` method uses an approximately
half-decade centered local log-slope, deterministic contiguous-region
selection, span/point/quality gates, and can select an interior white plateau
before later high-frequency shaping. The qualification also retains four-engine 50 mV
VOUT diagnostics and a runtime-only BSIM-CMG `TNOIMOD=1` capability check
without modifying the production card. See
[`NOISE_CHARACTERIZATION.md`](NOISE_CHARACTERIZATION.md) and the frozen
historical [`NOISE_N1.md`](NOISE_N1.md) contract for method details and claim
boundaries.

The catalog-wide dataset discovers all 30 public MOS devices from the
five-technology/15-family
manifest catalog and plans the complete temperature, inversion, length, NFIN,
threshold-sibling, and cross-process-anchor matrix before simulation. Its
stable request hash binds the exact selector/profile/bias/geometry, frozen
acquisition/fit methods, implementation, compact-model/provenance files,
generated OSDI artifacts, and reference-tool binaries. Identical physical
requests are simulated once even when several dataset/comparison views use
them.

This dataset is a reproducible audit of the existing compact-model predictions
at the recorded temperature, inversion, bias, and native geometry—not a
silicon-calibrated process-noise model or a reliability statement. Every
logical request retains an explicit `validated`,
`target_not_reachable`, or `simulation_failed` state. Resume accepts only a
completed result whose request identity and complete artifact inventory still
hash-match; incomplete, tampered, or semantically stale results are rejected
and never silently reused. Machine-readable `apm.noise-comparison.v1` outputs
reference exact source request/result hashes, expose 1 Hz, 1 kHz, 1 MHz, and
10 MHz values plus 1 Hz–10 MHz gate-referred integration, preserve native
planar-W versus integer-NFIN geometry, and produce no fake cross-basis ratios.
See the frozen historical [`NOISE_N2.md`](NOISE_N2.md) milestone contract for
the complete dataset specification.

At exceptionally low transconductance, ngspice 47's convenience
`inoise_spectrum` vector exhibits an empirically audited gain-squared clamp
near `1e-20`. APM retains that raw vector but qualifies it as an oracle only
above the floor; canonical gate-referred PSD always uses the separately
persisted actual complex external transfer. Likewise, internal model OP
`gm/gds` values remain diagnostic oracles for N2 while converged terminal
finite differences remain canonical.

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

APM045's versioned mixed-voltage result,
`apm.mixed-voltage-comparison.v1`, keeps native-relative-geometry,
common-1.0 V, common-1.8 V, equal-physical-length, equal-relative-length, and
equal-inversion views separate. It preserves raw source identities and labels
whether a metric is a native-family result or a common-bias terminal result;
scientifically valid `target_not_reachable` states are not clipped into data.

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

APM130 and the four upstream APM045 families retain exact-file provenance to
pinned, redistributable IHP SG13G2 and FreePDK45 sources. APM045 io18/io25 are
deterministic outputs of an offline APM model-generation flow whose public
source-fact matrix is `models/apm045/mixed_voltage_evidence.toml`; neither
private PDK inputs nor the FreePDK45 cards supply their numeric parameters.
The PSP103 and BSIM-CMG compiler sources retain their upstream licenses and
notices. APM350, APM022, and the APM016F parameter deck are independently
authored APM assets.

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
a reliability or manufacturing guarantee. V4 claims no standalone io33
family, foundry design-rule minimum, calibrated gate-leakage/GIDL or
process-noise accuracy, layout-dependent accuracy, or physical interpretation
of the epistemic model ensemble as process variation.

Spectre files are model-only and **experimental/unverified**. They have not
been parsed or simulated by a real Spectre installation, and static checks do
not establish numerical equivalence with ngspice. See
[`docs/spectre.md`](docs/spectre.md).

## Release validation

For normal installation and current-tree confidence, users should run:

```console
.venv/bin/apm doctor
.venv/bin/apm validate
```

The current fail-closed v4 contract is
[`validation/release_gates_v4.toml`](validation/release_gates_v4.toml).
Maintainers attest a fresh detached HTTPS clone before bootstrap, then run
`apm validate --release-v4 candidate`; a successful candidate report passes
15/15 candidate-required gates and explicitly leaves the sixteenth exact-tag
gate pending. After the annotated tag is pushed, a second fresh clone runs
`apm validate --release-v4 exact-tag`, which must pass 16/16 before release
publication. Both v4 phases regenerate calibration and use a hash-bound
portable replay projection that excludes only clone-local ngspice build
metadata while still matching the fresh executable exactly. The frozen
`apm validate --release` command and
[`validation/release_gates.toml`](validation/release_gates.toml) retain their
historical v3 meaning. See
[`docs/release-validation.md`](docs/release-validation.md) for the exact
commands and evidence semantics.

Repository policy, implementation scope, and result semantics are defined by
[`AGENTS.md`](AGENTS.md), [`GOAL.md`](GOAL.md), and
[`RESULT_CONTRACT.md`](RESULT_CONTRACT.md).

Security or provenance concerns should follow [`SECURITY.md`](SECURITY.md).
Contribution guidance is in [`CONTRIBUTING.md`](CONTRIBUTING.md).
