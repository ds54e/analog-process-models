# M7 integrated characterization and normalized comparison

Status: `validated`

Run time: 2026-08-29 17:32 UTC (2026-08-30 JST)

## Commands and integrated contract

The final real-tool commands were:

`apm characterization-check --output .apm/results/m7-allkits-20260830-final`

`apm compare apm022 apm016f --output .apm/results/m7-compare-apm022-apm016f-final`

Both exited zero with status `validated`. The all-kit runner generated every
nominal result from the current checkout using the M0-qualified ngspice 47
toolchain, rather than combining historical snapshots. It then audited the
persisted `apm.characterization.v1` contract and produced a portable
`apm.characterization-validation.v1` report with output-relative artifact
paths.

For every kit, the audit verifies model and public-device identity, exact
-40/27/85/125 degC coverage, nominal variation metadata, required CSV fields,
planar `w,l` versus FinFET `l,nfin` geometry, raw signed current versus
canonical positive-magnitude current, full 4x4 complex terminal Y storage,
artifact and model hashes, all per-kit numerical requirements, and simulator
log diagnostics. All result-contract and normalized-comparison checks passed.

## Persisted coverage and simulator logs

The five generated result trees contain 336 real ngspice jobs. Every log is
present; no log contains a warning token or critical error, fatal,
unsupported-parameter, singular-matrix, or convergence diagnostic.

| Kit | Id-Vg | Id-Vd | derived | DIBL | Y | capacitance | length | NFIN | Logs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| APM350 | 42,168 | 24,096 | 5,928 | 24 | 48 | 48 | 24 | — | 48 |
| APM130 | 10,248 | 5,856 | 1,368 | 24 | 48 | 48 | 24 | — | 48 |
| APM045 | 16,968 | 9,696 | 2,328 | 24 | 48 | 48 | 24 | — | 48 |
| APM022 | 27,048 | 7,776 | 3,768 | 24 | 48 | 48 | 24 | — | 48 |
| APM016F | 81,144 | 23,328 | 11,304 | 72 | 144 | 144 | 72 | 72 | 144 |

The all-kit report and normalized CSV hashes are:

- `report.json`:
  `d9d8572495d403db93f568cf48feb2dabbb161b13b639a633e2a9fb4d8746296`;
- `normalized_comparison.csv`:
  `78177cad910c3a02cfa0ddb57fd1ae7a4a813e7827b04505e6806758ac824748`.

## Normalized terminal comparison

The common comparison coordinate is 27 degC, `L/Lmin=2`,
`VOUT/VDD=0.5`, and the available gate-grid point nearest `gm/Id=15 1/V`.
All ten rows are within 2 1/V of the gm/Id target. Planar current and
capacitance are reported per micrometre of drawn width; FinFET values are per
fin. The current and Cgg columns below therefore retain their basis explicitly
and are not universal-denominator rankings.

| Kit | Pol. | gm/Id (1/V) | gm/gds | DIBL (V/V) | `|Vth|` (V) | normalized Id | normalized Cgg |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| APM350 | N | 15.3802 | 59.7239 | 0.020006 | 0.485743 | 1.51697 uA/um | 3.29368 fF/um |
| APM350 | P | 14.3270 | 59.2731 | 0.021370 | 0.617236 | 0.650743 uA/um | 3.34596 fF/um |
| APM130 | N | 15.5054 | 21.7211 | 0.055266 | 0.273263 | 4.27962 uA/um | 2.71013 fF/um |
| APM130 | P | 15.2570 | 67.1924 | 0.026788 | 0.379329 | 1.65050 uA/um | 2.53036 fF/um |
| APM045 | N | 15.0050 | 85.0096 | 0.018755 | 0.296825 | 23.1791 uA/um | 2.17421 fF/um |
| APM045 | P | 14.6456 | 67.7376 | 0.024901 | 0.322173 | 12.8249 uA/um | 2.23878 fF/um |
| APM022 | N | 15.0240 | 16.2094 | 0.102410 | 0.520001 | 26.2199 uA/um | 0.874107 fF/um |
| APM022 | P | 15.2157 | 17.7995 | 0.108124 | 0.544058 | 13.5068 uA/um | 0.888762 fF/um |
| APM016F | N | 15.2554 | 106.323 | 0.010352 | 0.297686 | 5.27277 uA/fin | 0.0394741 fF/fin |
| APM016F | P | 15.1723 | 101.567 | 0.011254 | 0.292518 | 3.28941 uA/fin | 0.0436295 fF/fin |

The explicit APM022/APM016F pairwise run independently regenerated and audited
both result sets. Its report and CSV SHA-256 values are respectively
`2a9a543551a2c4cad138a4d0ed95f99365c26f707a103e30d81698c2559aa9cb`
and `8418867a713b7afac2aa23e473bc8963a4ed5b3acd560345823bec22f9451234`.
At the common coordinate, FinFET/planar DIBL ratios are 0.10109 N and 0.10409
P, while gm/gds ratios are 6.5593 N and 5.7062 P. Width-to-fin current and
capacitance ratios are deliberately `null`, with status
`not_reported_across_per_width_and_per_fin_bases`; the comparison does not
invent a width equivalence.

## Regression and milestone boundary

Ruff, all 41 repository tests, `git diff --check`, and REUSE 3.3 lint pass;
REUSE reports license and copyright information for 110/110 files. Tests cover
the concrete CLI, complete all-kit set, geometry semantics, suppression of
cross-basis ratios, same-basis planar ratios, and rejection of an identical-kit
comparison in addition to all earlier contracts.

This completes M7. IHP-native variation remains distinct from the APM
benchmark distribution and is M8 work. Experimental/unverified Spectre files,
the full release validator, clean-clone execution, and v1.0.0 release metadata
remain unclaimed.
