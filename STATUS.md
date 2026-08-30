# APM development status

This is the compact persistent progress index. It is not validation evidence by itself.

## Overall state

- Project: Analog Process Models (APM)
- Repository: `https://github.com/ds54e/analog-process-models`
- Released baseline: `v2.0.0`
- Released tag commit: `3cc6cfea4932cc40f2d693784d0a569926cdf399`
- v2 post-release exact-tag requalification: complete, 20/20 required gates passed
- Current development line: post-v2 `main`
- Current target: v3 stationary small-signal MOS-noise characterization foundation
- Current milestone: `V3-N0 Four-engine noise spike`
- State: `V3_NOISE_FOUNDATION_NOT_STARTED`
- v3 release eligible: NO
- Blockers: none recorded before implementation

APM v2.0.0 is immutable history and remains the validated electrical/DC/Y/capacitance/variation baseline. Current v3 work does not invalidate or modify the v2 release.

## Reference toolchain to reuse

Validated v2 development/reference environment:

- WSL2
- AlmaLinux 9.7 x86_64
- Linux ext4 workspace
- Python 3.9.25
- ngspice 47 with predictor/OSDI
- project-local OpenVAF-ReLoaded v24.0.2mob
- native BSIM3
- native BSIM4
- PSP103 OSDI
- BSIM-CMG 112.1.0 OSDI

The v3 noise spike should inventory and reuse this environment rather than rebuild solved infrastructure without reason.

Required `.noise` reference runs use the normal Sparse solver path, not KLU.

## Released v2 family matrix

| Technology | Families | v2 state |
| --- | --- | --- |
| APM350 | `general` | released/validated |
| APM130 | `lv`, `hv` | released/validated |
| APM045 | `vtl`, `vtg`, `vth`, `thkox` | released/validated |
| APM022 | `lvt`, `svt`, `hvt` | released/validated |
| APM016F | `lvt`, `svt`, `hvt` | released/validated |

Catalog total: five technologies, 13 Electrical Families, 26 public family-qualified MOS devices.

## v3 noise design state

Normative design:

- `GOAL.md`
- `NOISE_CHARACTERIZATION.md`

Current design decisions:

- keep `apm.characterization.v2` intact;
- add an independent noise domain, preferred schema `apm.noise-characterization.v1`;
- stationary small-signal noise only for the initial phase;
- ngspice remains the validated reference backend;
- Spectre remains model-only experimental/unverified;
- canonical common result is external drain-terminal total short-circuit current-noise PSD, not compact-model internal `sid`;
- persist gate-referred PSD using actual small-signal transfer;
- persist parameter-level effective noise-model provenance;
- distinguish backend execution capability from physical/calibration claims;
- do not tune new APM350/APM022/APM016F process-noise coefficients during the initial spike;
- do not add noise variation/mismatch/correlation models in the initial phase;
- do not create/tag v3.0.0 from the spike alone.

## V3-N0 required four-engine spike

Required model paths:

| Engine | Selector |
| --- | --- |
| native BSIM3 | `apm350/general/nmos` |
| PSP103 OSDI | `apm130/lv/nmos` |
| native BSIM4 | `apm045/vtg/nmos` |
| BSIM-CMG OSDI | `apm016f/svt/nfet` |

Provisional common operating point:

```text
T = 27 degC
L/Lmin = 2
Planar W = family/device default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
gm/Id target = 15 1/V
frequency = 1 Hz ... 100 MHz
20 points/decade
```

The gm/Id point must be actively resolved/revalidated rather than taken from the nearest old DC sweep row.

## V3-N0 harness validation required before MOS acceptance

1. analytic resistor current-noise reference;
2. candidate 1-ohm CCVS/current-probe transparency;
3. OpenVAF/OSDI white-noise fixture;
4. OpenVAF/OSDI flicker-noise fixture;
5. analytic correlated internal-noise network through OpenVAF -> OSDI -> ngspice.

The correlated fixture is intended to decide capability from real evidence rather than from OSDI-version assumptions.

## Noise provenance baseline to verify during implementation

### APM130

Pinned IHP PSP cards contain explicit family-specific noise parameters. Treat as upstream-explicit parameterization, but do not overstate silicon calibration without stronger authoritative evidence.

### APM045

Pinned FreePDK45 BSIM4 cards explicitly select some noise modes such as `FNOIMOD`/`TNOIMOD`, while some coefficients may resolve from BSIM defaults. Provenance therefore needs to be parameter-level.

### APM350 / APM022 / APM016F

Current APM-authored cards were not intentionally process-noise calibrated. Compact-model default noise behavior may still produce valid simulator spectra; such results must be labeled compact-model-default predictions rather than APM process-noise calibration.

## V3-N0 planned output contract

Preferred per-run artifacts:

```text
metadata.json
operating_points.csv
noise_spectrum.csv
noise_metrics.csv
source_breakdown.json
noise_model_snapshot.json
```

Canonical spectrum fields include:

```text
s_idrain_terminal_a2_per_hz
s_vgate_equivalent_v2_per_hz
y_dg_real_s
y_dg_imag_s
```

Derived metrics such as flicker exponent, white floor, flicker corner, `gamma_eff_total`, and integrated noise are secondary to raw spectra and must be null/invalid when fitting is not justified.

## Decisions intentionally unfrozen until V3-N0 evidence

- final required frequency range;
- final points/decade;
- final white/flicker fitting method and thresholds;
- exact PSP/BSIM-CMG correlated-noise support claim through current OSDI path;
- reliable effective-parameter interrogation mechanism per engine;
- whether all 26 devices can use one required frequency profile;
- whether a low-VDS diagnostic profile becomes required;
- whether APM-authored generic noise coefficients should be researched later;
- whether a full terminal noise-correlation matrix is worth a later extension.

Do not resolve these by guesswork before the spike.

## v2 release evidence retained

The immutable `v2.0.0` tag independently passed the documented exact-commit fresh-clone release flow on WSL2 + AlmaLinux 9.7 x86_64. The post-release evidence remains:

`validation/evidence/v2_post_release_requalification.json`

The existing `validation/release_gates.toml` remains the historical/current implementation of the v2 release-gate contract until a later v3 release goal introduces separate v3 release gates. Do not rewrite it merely to start the spike.
