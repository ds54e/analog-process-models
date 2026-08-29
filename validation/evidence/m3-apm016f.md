# M3 APM016F independently authored FinFET kit

Status: `validated`

Run time: 2026-08-29 16:01 UTC (2026-08-30 JST)

## Identity, provenance boundary, and command

- Host/toolchain: validated M0 WSL2 + AlmaLinux 9.7 x86_64, ngspice 47,
  OpenVAF-ReLoaded `v24.0.2mob`
- Engine: UC Berkeley BSIM-CMG 112.1.0, compiled and loaded through OSDI
- Engine archive SHA-256:
  `9c70a7c9fcfafe66fb1582655bbfd36714b90ecba137a9dd83c76b3a0bd9e50a`
- Engine license: exact upstream ECL-2.0 `LICENSE.txt` and `NOTICE.txt`
- APM parameter revision: `apm016f-params-v1-2026-08-30`, Apache-2.0
- Parameter-card SHA-256:
  `afd4b6905d4176e4f0f7802d8f0434fd6f2d51a2dd40abf28cddaa8fe104a323`
- Public devices: `apm016f_nfet` and `apm016f_pfet`, terminals `d,g,s,b`,
  parameters only `l,nfin`
- Command:
  `apm characterize apm016f --output .apm/results/apm016f-m3-20260830d`
- Exit status: 0; result status: `validated`

The BSIM-CMG engine is an exact pinned upstream import. The parameter cards are
independently authored APM assets and are explicitly not foundry-correlated.
No official PTM-MG card was copied, transcribed, interpolated, fitted, or used
as a numerical parameter source. No PTM-MG file is shipped.

The documented physical inputs are public primary sources: the open 16 nm bulk
HKMG FinFET study at DOI `10.1186/s11671-015-0739-0`, the TSMC IEDM 2014 paper
at DOI `10.1109/IEDM.2014.7046970`, and the official BSIM-CMG specification and
112.1.0 implementation. They support the selected bulk triple-gate topology,
16 nm Lmin, 32 nm fin height, 8 nm fin thickness, 48 nm pitch, 1 nm EOT,
representative doping, and 0.8 V supply. `parameter_generation.md` records every
authored choice and the observable-only calibration procedure. Self-heating is
explicitly disabled with `SHMOD=0`.

`models/apm016f/provenance.toml` contains exact hashes for the complete vendored
engine and the authored card, wrapper, kit contract, and generation document.
REUSE 3.3 lint passes for all 87 repository files.

## Geometry and persisted coverage

The run used `L/Lmin=1,2,4`, legal integer `NFIN=1,2,4`, both polarities, and
-40/27/85/125 degC. This is 72 device cases for DC and 72 for terminal Y
analysis. All 144 ngspice log files completed without warning, error, parameter,
or convergence text.

No APM016F result schema or CSV contains `w_m`; geometry is stored only as
`l_m`, `l_over_lmin`, and integer `nfin`. Raw signed voltage-source current and
current entering the device are retained separately from positive `IDMAG`.

| Artifact | Rows / records | SHA-256 |
| --- | ---: | --- |
| `idvg.csv` | 81,144 | `8ac66473b1d20b2e925bc8c56bb4e946082a77c313bad3cab8be95b8db85eb64` |
| `idvd.csv` | 23,328 | `8a9fad5b7dcb63b8c1bfd1cbc3c3c196588d85b9c4306ec2fefcc35992adf09d` |
| `derived.csv` | 11,304 | `58138559aa491b0c0ab9976dadcb8e252f69c6248c31ba6b7c8eace7c56edc87` |
| `dibl.csv` | 72 | `65eb47bab9e1096006f8e83aa23ff56f82e44b5c7c73870c810643bbd0494ff9` |
| `y_matrix.json` | 144 full 4x4 matrices | `3e8f09263cef72629c056bb447f735b23ad543caa74ec40802514ef7059c3231` |
| `capacitance.csv` | 144 | `77ea1799f7a8bac9016520ce5e26ff0cb80a58d5bd9e206688131a983ec41e3b` |
| `length_scaling.csv` | 72 | `0202857bf9b88e7f2255e66f25f1f9d3259a1c59adb8cbb7cccbf565077dc479` |
| `nfin_scaling.csv` | 72 | `510fdae2bf57dfbf5dfa0ab4d07c70f9f74271c00b5a8d38e8fdcc9ab005fb98` |
| `metadata.json` | complete run contract | `8b7266099cbd44e65a54d524ae297ee312645d27ef0e07a718faaaa30b607d68` |

Each of 504 Id-Vg groups has 161 points on an exact 5 mV grid; each of 288
Id-Vd groups has 81 points on an exact 10 mV grid. Both endpoints are included.

## Numerical-method and terminal checks

Checks cover 5,994 above-criterion operating points from 0.25 to 0.9 VDD.

| Check | Median relative difference | 95th percentile | Criterion |
| --- | ---: | ---: | ---: |
| gm, 5 mV vs 10 mV central difference | 0.0202% | 0.615% | p95 < 2% |
| gds, 8 mV vs 16 mV central difference | 0.0651% | 0.267% | p95 < 2% |
| terminal gm vs native BSIM-CMG gm oracle | 0.0119% | 0.385% | p95 < 2% |
| terminal gds vs native BSIM-CMG gds oracle | 0.0179% | 0.139% | p95 < 2% |

Native BSIM-CMG values are validation oracles only; the stored terminal finite
differences remain canonical. Every full-range and conduction-region Id-Vg and
Id-Vd group is monotonic. There are no N/P raw-current sign violations.

All 144 raw Y records preserve 16 complex entries at 100 kHz or 1 MHz. Both
frequencies exist for every case. Maximum terminal KCL column-sum residual is
`6.707e-18 S`; every Cgg/Cgd/Cgs is positive, and the maximum relative change
between frequencies is `2.18e-16`.

## Threshold rolloff, DIBL, and output behavior

All 72 DIBL extractions use `Id=100 nA * NFIN`, VOUT low=50 mV, and VOUT
high=0.64 V. The coefficient and NFIN normalization are stored in each row and
run metadata. DIBL is positive throughout all temperatures and geometries,
spanning 0.00553..0.05827 V/V.

At 27 degC and NFIN=1, high-drain threshold magnitude increases with length
while DIBL falls sharply from minimum length:

| Polarity | Metric | L/Lmin=1 | L/Lmin=2 | L/Lmin=4 |
| --- | --- | ---: | ---: | ---: |
| N | `|Vth_high|` (V) | 0.25657 | 0.29769 | 0.31677 |
| N | DIBL (V/V) | 0.03723 | 0.01035 | 0.01003 |
| P | `|Vth_high|` (V) | 0.24998 | 0.29252 | 0.31350 |
| P | DIBL (V/V) | 0.03823 | 0.01125 | 0.01142 |

At gm/Id approximately 15 1/V, minimum-length gm/gds is 27.04 N and 25.24 P;
at 2*Lmin it rises to 106.32 N and 101.57 P. This supplies the required
positive, finite output-conductance and length-scaling behavior without making
a silicon-correlation claim.

## Discrete NFIN behavior

At 27 degC, L=16 nm, VCTRL=0.64 V, and VOUT=0.4 V:

| Polarity | NFIN | Id (uA) | gm (uS) | gm/Id (1/V) | gm/gds |
| --- | ---: | ---: | ---: | ---: | ---: |
| N | 1 | 39.106 | 177.036 | 4.5271 | 17.5477 |
| N | 2 | 78.213 | 354.073 | 4.5271 | 17.5477 |
| N | 4 | 156.425 | 708.145 | 4.5271 | 17.5477 |
| P | 1 | 31.788 | 147.594 | 4.6430 | 15.8249 |
| P | 2 | 63.577 | 295.189 | 4.6430 | 15.8249 |
| P | 4 | 127.154 | 590.377 | 4.6430 | 15.8249 |

Across every temperature, length, and polarity group, the worst relative
spreads are `1.668e-7` for Id per fin, `1.640e-7` for gm per fin, `1.906e-7`
for gm/Id, `2.237e-6` for gm/gds, and `5.587e-9` for reported capacitance per
fin. These are all far below their documented 2% or 5% limits and demonstrate
genuine discrete BSIM-CMG NFIN scaling rather than a wrapper-level planar width
conversion.

## Regression and scope

After separating planar and FinFET geometry types in the terminal harness,
complete APM130 and APM045 characterization reruns both retained `validated`
status. Ruff, all 24 repository tests, and REUSE lint pass.

This evidence validates the nominal APM016F kit and its ngspice BSIM-CMG OSDI
execution. Full numerical result directories remain untracked and are
regenerated by the command above. The required APM016F-versus-APM022
electrostatic comparison is deferred until the independent APM022 deck exists;
benchmark variation is M4 work, and Spectre remains experimental/unverified M9
work. No all-kits or release-readiness gate is claimed by this evidence alone.
