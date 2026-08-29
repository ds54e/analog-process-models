# M8 APM130 IHP-native variation

Status: `validated`

Run time: 2026-08-29 17:46 UTC (2026-08-30 JST)

## Selected upstream contract and command

The final command was:

`apm apm130-native-check --output .apm/results/m8-apm130-native-20260830-final3`

It exited zero with status `validated` on the M0-qualified WSL2 / AlmaLinux
9.7 x86_64 host using ngspice 47 and PSP103 OSDI. The selected pinned-IHP
profiles are:

- corners: `mos_tt`, `mos_ss`, `mos_ff`, `mos_sf`, `mos_fs`;
- process: `mos_tt_stat`;
- mismatch: `mos_tt_mismatch`.

Every persisted result has `variation_origin=native`, mode
`corner`/`process`/`mismatch`, and the exact upstream section name. These names
are not translated into APM benchmark corners or observable-intent variables.
The selected upstream deck has no stochastic `mos_tt_stat_mismatch` profile,
so APM deliberately exposes no native `all` mode.

## Native corners

All ten N/P corner curves ran at 27 degC, W=1 um, L=0.26 um, VOUT=0.6 V, on
gate magnitude 1.2 V, and threshold criterion 384.615 nA. Curves are finite
and monotonic from criterion through strong conduction. Slow/fast directions
match each polarity's upstream corner identity.

| Profile | N `|Vth|` (V) | N on Id (uA) | P `|Vth|` (V) | P on Id (uA) |
| --- | ---: | ---: | ---: | ---: |
| `mos_tt` | 0.285331 | 297.704 | 0.382521 | 89.5663 |
| `mos_ss` | 0.346184 | 248.152 | 0.433275 | 79.2887 |
| `mos_ff` | 0.228614 | 341.225 | 0.329034 | 103.699 |
| `mos_sf` | 0.315789 | 272.270 | 0.355832 | 96.4585 |
| `mos_fs` | 0.256957 | 319.589 | 0.407944 | 84.3975 |

Raw voltage-source current is negative for N and positive for P in every
corner, while canonical `idmag` remains positive.

## Native process statistics

The validator used 128 seeds starting at 20260830. ngspice evaluated IHP's
native `gauss(...)` expressions from `.option seed=<integer>`; Python did not
sample this distribution. All 34 low-voltage N/P process parameters and 256
duplicate-device terminal observations are persisted. Same-seed replay was
exact, a different seed differed, and duplicate identical devices had zero
current difference in every sample, confirming model-global sharing.

Across the 33 empirically variable parameters, the normalized sample standard
deviation range is 0.91538..1.12946 and the largest absolute normalized mean is
0.22727. N current mean/std are 5.0592/3.0784 uA (CV 0.6085); P values are
1.7177/0.3614 uA (CV 0.2104). All currents are finite with correct raw signs.

The 34th parameter, `mc_sg13g2_lv_pmos_dphiblw`, has an upstream relative
deviation of only `1e-9`. ngspice 47's expanded-deck `%g` serialization resolves
all of its samples to the nominal value. It remains present in the sample table
with explicit role `upstream_negligible_effectively_fixed_in_ngspice47`; it is
not falsely credited with nonzero spread.

## Native local mismatch statistics

The mismatch cohort contains 1,024 per-instance observations: 128 seeds, N/P,
two independent instances, and W/L of 1 um/0.26 um versus 2 um/0.52 um
(fourfold area). The alternate APM wrapper retains the public
`apm130_nmos`/`apm130_pmos` names and `w,l` only, while fixing IHP `mm_ok=1`
inside the wrapper.

For resolved `w`, `l`, `delvto`, and `factuo`, the largest absolute normalized
mean is 0.15789 and normalized sample standard deviations span
0.88943..1.07482. All eight small-pair correlations for N/P resolved `w`, `l`,
`delvto`, and `factuo` lie between -0.14794 and 0.15417; the maximum magnitude
0.1542 is below the 0.3 independence criterion. Every seed produced distinct
local terminal pair currents and all raw current signs passed.

Observed fourfold-area large/small sigma ratios are:

| Polarity | Variable | Observed ratio | Upstream law |
| --- | --- | ---: | ---: |
| N | `delvto` | 0.52670 | 0.5 |
| N | `factuo` | 0.50399 | 0.5 |
| P | `delvto` | 0.47171 | 0.5 |
| P | `factuo` | 0.53179 | 0.5 |

This directly validates IHP's raw `1/sqrt(W*L in um^2)` local scaling; it is
not described as the APM benchmark matching law.

## Artifacts, logs, and regression

All 268 ngspice logs completed with `ngspice-47 done`; no warning, error,
unsupported-parameter, singular-matrix, or convergence token occurred.

| Artifact | Rows | SHA-256 |
| --- | ---: | --- |
| `native_corners.csv` | 10 | `7354500f1632898d9dc998257d5e809815c30617a9392c8e839302669003e456` |
| `native_process_samples.csv` | 4,352 | `eddbb4794dba23ca05802ea85a95a3155f9f7420d8c46e7af758b5f7f9974e57` |
| `native_process_observations.csv` | 256 | `b412490c790c5e39201a5564ffed0659550f258cef0a92d36411465c5f4575ed` |
| `native_mismatch_samples.csv` | 1,024 | `b1c807a2f52e7d12ac13c59a53b8d33ca6f8c30ccdad131c5d412da77abb5ed9` |
| `report.json` | complete native contract | `bf9cb7caa4ab4ad64301acb39349980da5f9df0812f360e1bdb8ee4a664cf6d4` |

The native mismatch wrapper SHA-256 is
`598448e47d358ebd2e427170a6bd48cff587c94e7b5812f0e4a7fcf12964fddc`.
The report also records exact hashes for all participating upstream IHP files.

Ruff, all 45 repository tests, `git diff --check`, and REUSE 3.3 lint pass;
REUSE reports license and copyright information for 115/115 files. Tests cover
the exact CLI profiles, absence of native `all`, parsing all 34 upstream process
entries and eight mismatch coefficients, the sub-resolution process entry,
native-wrapper public geometry, and the Python 3.9-compatible correlation
calculation in addition to all earlier contracts.

This completes required gate `variation.apm130_native`. APM130 native Spectre
Monte Carlo is explicitly not claimed. M9 experimental/unverified Spectre
model-only artifacts and M10 release/clean-clone gates remain open.
