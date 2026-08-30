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
- State: `V3_N0_IMPLEMENTED_DEVELOPMENT_QUALIFICATION_PASS`
- v3 release eligible: NO
- Blockers: none; final exact-implementation-commit rerun and compact committed evidence remain before milestone closure

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

The v3 noise spike reused this environment and the verified existing OSDI build
cache; it did not rebuild solved infrastructure without reason.

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

## V3-N0 development qualification

A pre-commit integrated real-tool qualification completed on 2026-08-30:

```console
.venv/bin/apm doctor
.venv/bin/apm noise-check --output .apm/v3-n0-dev-check
```

- development report SHA-256: `a31d5db1ff1faf021edb2cda54fa5cf84f1e2237bc11724e9983e00f73746039`;
- acceptance result: 13/13 pass;
- all required jobs attested the normal Sparse solver and no required job used KLU;
- resistor `4*k*T/R` maximum relative error: `3.4954e-7`;
- probe DC current/voltage error: zero; gain-two PSD ratio: `4.000000006`; noise-free run PSD: zero;
- white fixture maximum relative error: zero;
- flicker fixture exponent: `1.25`; maximum relative error: `3.2134e-9`;
- correlated fixture observed the correlated result to `3.01e-16` relative error and decisively rejected the independent interpretation by a ratio of `181`.

This development report was generated before the implementation commit and is
not the final committed milestone evidence. The same flow must be rerun after
the implementation commit before V3-N0 is marked complete.

| Engine / selector | Achieved gm/Id | Relative target error | Drain PSD range (A^2/Hz) | Provisional fit observation |
| --- | ---: | ---: | ---: | --- |
| BSIM3 `apm350/general/nmos` | 14.99089 | 0.06071% | `3.397e-25` .. `3.397e-25` | white valid; flicker/corner not observed |
| PSP103 `apm130/lv/nmos` | 14.99458 | 0.03610% | `9.827e-25` .. `2.898e-18` | white/flicker/corner valid |
| BSIM4 `apm045/vtg/nmos` | 15.00039 | 0.002602% | `5.744e-24` .. `4.138e-17` | flicker valid; white/corner not observed |
| BSIM-CMG `apm016f/svt/nfet` | 14.99705 | 0.01969% | `1.240e-24` .. `7.130e-19` | white/flicker/corner valid |

Every run retained 161 points from 1 Hz through 100 MHz, the canonical
gate-referred PSD and complex transfer, raw backend source names, complete
refined finite-difference diagnostics, and an effective parameter snapshot.
All gm/gds step-convergence and native-oracle comparisons were below the
existing 2% v2 tolerances.

## Noise provenance findings

### APM130

OSDI `showmod` returned effective values for the 16 audited PSP103 noise
parameters. The snapshot distinguishes matching upstream card values from
pinned Verilog-A defaults. Native PSP oracles were finite and trend-consistent:
`sid=9.496017e-25 A^2/Hz`, `sfl=2.898328e-18 A^2/Hz` at 1 Hz, and
`cigid=0.4988225`; they are not treated as equal-by-contract to the external
terminal total.

### APM045

Native ngspice `showmod` resolved 16 of 17 audited BSIM4 values and kept card
selectors distinct from backend defaults. ngspice 47 returns an error sentinel
for BSIM4 `LINTNOI`; the adapter records the narrowly documented runtime
default `0` fallback. Selector-inactive correlation coefficients remain
explicitly not-applicable rather than invented.

### APM350 / APM022 / APM016F

Native BSIM3 `showmod` resolved nine audited backend defaults. OSDI `showmod`
plus pinned BSIM-CMG declarations resolved 20 explicit/default values. The
APM350, APM022, and APM016F model-card paths remain byte-for-byte unchanged
from `v2.0.0`; no spike-driven process-noise coefficient was added or tuned.

The analytic internal-node fixture proves correlation preservation through the
current OpenVAF-Re-Loaded -> OSDI -> ngspice Sparse path. Production PSP103
exercised nonzero `igig`/`idid` sources with `cigid`. A separate BSIM-CMG
diagnostic changed `TNOIMOD` from the production value 0 to 1 only at runtime,
observed nonzero `corl` and `id` sources, and verified the production card hash
was unchanged.

## V3-N0 implemented output contract

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

## Evidence-based next-milestone recommendations

- Keep 1 Hz and 20 points/decade provisionally. Do not freeze 100 MHz as the common upper endpoint: the APM045/VTG spectrum did not expose a white region in the fixed 10-100 MHz review window. Run a bounded higher-frequency diagnostic first.
- Replace the spike's versioned fixed review windows with a predeclared contiguous-region detector using slope, span, point-count, and quality rules. Preserve fail-closed nulls and refit the retained raw spectra without rerunning when possible.
- Treat the current internal-node correlation construction as demonstrated through PSP103 and a BSIM-CMG `TNOIMOD=1` diagnostic on this exact OSDI path. Do not generalize backend source names or claim production APM016F correlation when its unchanged selector is 0.
- Use `showmod` final values for native BSIM3/BSIM4, with only the documented BSIM4 `LINTNOI=0` fallback. For PSP103/BSIM-CMG, bind OSDI `showmod` values to explicit card occurrences or pinned Verilog-A default declarations.
- Do not expand to all 26 devices until the upper-frequency diagnostic and fit-region method are frozen. The raw schema and four engine paths are otherwise ready for catalog orchestration.
- Add a small low-VDS diagnostic before all-device expansion; the canonical `VOUT=0.5*VDD` point alone does not exercise linear-region thermal/correlation behavior.
- Consider generic APM-authored noise calibration only in a later evidence-backed milestone. Do not tune now: unchanged APM350 defaults produce no flicker (`KF=0`), while unchanged APM016F defaults produce strong flicker.
- Keep a full terminal noise-correlation matrix as a possible later extension, not a prerequisite for the next milestone.

## v2 release evidence retained

The immutable `v2.0.0` tag independently passed the documented exact-commit fresh-clone release flow on WSL2 + AlmaLinux 9.7 x86_64. The post-release evidence remains:

`validation/evidence/v2_post_release_requalification.json`

The existing `validation/release_gates.toml` remains the historical/current implementation of the v2 release-gate contract until a later v3 release goal introduces separate v3 release gates. Do not rewrite it merely to start the spike.
