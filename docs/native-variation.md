# APM130 IHP-native variation

APM130 exposes a selected real-ngspice subset of the pinned IHP SG13G2 LV and
HV MOS variation libraries. This is model-owned behavior, not APM synthetic
benchmark variation. Every persisted row uses
`variation_origin = "native"`, exact family identity, and the upstream
profile name.

```console
apm build-models
apm apm130-native-check --output .apm/results/apm130-native
```

The command refuses to overwrite a non-empty directory and invokes ngspice with
`-n`, so `~/.spiceinit` and GUI state do not participate.

## Selected profiles

Both `apm130/lv` and `apm130/hv` independently execute:

| Native mode | Upstream section |
| --- | --- |
| deterministic corners | `mos_tt`, `mos_ss`, `mos_ff`, `mos_sf`, `mos_fs` |
| statistical/process | `mos_tt_stat` |
| local mismatch | `mos_tt_mismatch` |

There is no selected stochastic process-plus-mismatch native All profile. The
pinned libraries do not expose one, so APM does not invent or synthesize it.
This differs from APM Benchmark All, which is defined by APM's separate
synthetic specification.

LV and HV use independent seed cohorts. Upstream cross-family correlation is
unspecified, so APM neither samples nor asserts one.

## Native process semantics

The selected statistical sections include the corresponding
`sg13g2_mos{lv,hv}_stat.lib`. ngspice resolves the upstream `gauss(...)`
expressions when it reads each model library. LV declares 34 N/P model-global
parameters and HV declares 37. Separate identical devices share the resolved
process model within a sample.

The validator passes an explicit integer through `.option seed=<integer>`,
records every resolved raw parameter and upstream-normalized z value, and
simulates duplicate N/P devices. Python does not sample or reinterpret the
IHP-native distributions. This seed mechanism is independent of the NumPy
PCG64 sampler used by APM benchmark variation.

Entries whose extremely small declared relative deviation resolves to nominal
at ngspice 47 expanded-deck precision remain in the raw table and are labeled
effectively fixed; they are not falsely counted as nonzero-spread parameters.
All empirically variable entries are checked for centered means and expected
spread across 128 samples.

## Native mismatch semantics

The selected mismatch sections include IHP mismatch coefficients and
mismatch-enabled device subcircuits. Family-qualified thin wrappers retain
public names `apm130_lv_{nmos,pmos}` or
`apm130_hv_{nmos,pmos}`, terminal order `d g s b`, and only `w,l` sizing
while fixing upstream `mm_ok=1` internally.

The upstream subcircuit resolves independent instance-local `agauss(...)`
draws for `w`, `l`, `delvto`, and `factuo`. With W/L in metres:

`sigma(delvto) = delvto_mm / sqrt(W*L*1e12)`

`sigma(factuo) = factuo_mm / sqrt(W*L*1e12)`

The factor converts area to square micrometres. APM does not relabel these raw
PSP variables as benchmark `vth_shift` or `drive_shift`. The validator reads
resolved internal PSP instance values, checks local-pair independence, and
checks that fourfold area approximately halves spread.

## Validation cohorts

Each family executes five corners plus independent 128-sample process and
128-sample mismatch cohorts, same-seed replay, and different-seed checks.
Required properties include:

- sane threshold and on-current values and expected FF/SS/FS/SF directions;
- model-global process sharing for duplicate devices;
- centered/nonzero process and mismatch distributions;
- independent local mismatch;
- inverse-square-root area scaling;
- raw versus canonical terminal-current sign semantics; and
- complete real-ngspice logs with no hidden native All mode.

The top-level schema is `apm.native-variation-validation.v2`; each family
report uses `apm.native-family-variation-validation.v2`.

## Persisted result layout

Under each family directory, the command writes:

- `native_corners.csv`;
- `native_process_samples.csv`;
- `native_process_observations.csv`;
- `native_mismatch_samples.csv`;
- reproducibility netlists, raw curves, and ngspice logs; and
- a hash-linked `report.json` with source/artifact identity, summaries, and
  all pass criteria.

The top-level `report.json` binds both independent family reports and records
that cross-family correlation is unspecified and a native combined mode is
absent.

## Boundaries

This validation covers the pinned LV/HV MOS subset only. It does not convert
native behavior to APM benchmark statistics, claim foundry yield, or establish
IHP-native Spectre Monte Carlo compatibility. The Spectre files remain
model-only experimental/unverified.
