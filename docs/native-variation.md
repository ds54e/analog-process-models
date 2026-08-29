# APM130 IHP-native variation

APM130 exposes a selected, real-ngspice subset of the statistical behavior in
the pinned IHP SG13G2 low-voltage MOS deck. This is model-owned behavior, not
the synthetic cross-kit APM benchmark distribution. Every persisted row uses
`variation_origin = "native"` and the exact upstream library-section name.

Run the complete native check after building the OSDI models:

```console
apm build-models
apm apm130-native-check --output results/apm130-native
```

The command refuses to overwrite a non-empty directory and runs ngspice with
`-n`, so no `.spiceinit` or other user-global simulator setup participates.

## Selected upstream profiles

The v1 selection is deliberately narrow and explicit:

| Native mode | Upstream `cornerMOSlv.lib` section(s) |
| --- | --- |
| deterministic corners | `mos_tt`, `mos_ss`, `mos_ff`, `mos_sf`, `mos_fs` |
| statistical process | `mos_tt_stat` |
| local mismatch | `mos_tt_mismatch` |

There is no selected stochastic process-plus-mismatch `all` profile. The
upstream deck does not expose a `mos_tt_stat_mismatch` section, so APM does not
invent or synthesize one. This differs from APM benchmark variation, whose
`all` mode is required and defined by the APM benchmark specification.

## Native process semantics

`mos_tt_stat` includes `sg13g2_moslv_stat.lib`. Its 34 low-voltage N/P
`gauss(...)` expressions resolve model-global parameters when ngspice reads the
deck. The upstream file sets `num_sigmas=1` and describes each listed
deviation as one sigma. Separate identically sized devices therefore share the
same resolved process model within a sample.

The validator passes an explicit integer through `.option seed=<integer>`,
records all 34 resolved values and their upstream-normalized z values, and
simulates duplicate N/P devices. Python does not sample or reinterpret the
IHP-native distribution. This seed mechanism is independent of the NumPy
PCG64 sampler used by APM benchmark variation.

IHP assigns PMOS `dphiblw` a relative deviation of only `1e-9`. ngspice 47
serializes evaluated statistical values into its expanded deck with `%g`, so
this one entry resolves to its nominal value at available precision. APM keeps
it in the raw sample table and labels it
`upstream_negligible_effectively_fixed_in_ngspice47`; it is not falsely counted
as a nonzero-spread parameter. The other 33 process parameters remain subject
to the empirical mean/spread checks.

## Native mismatch semantics

`mos_tt_mismatch` includes IHP's mismatch coefficients and mismatch-enabled
device subcircuits. APM selects the profile with
`apm130_native_mismatch_wrappers.inc`, an alternate thin wrapper file that
retains the public `apm130_nmos`/`apm130_pmos` names and public `w,l` sizing but
fixes upstream `mm_ok=1` internally. It must be included instead of the nominal
wrapper file for a native mismatch run.

The upstream subcircuit resolves independent local `agauss(...)` draws for
each instance's `w`, `l`, `delvto`, and `factuo`. With W and L expressed in
metres, the threshold and drive standard deviations are:

`sigma(delvto) = delvto_mm / sqrt(W*L*1e12)`

`sigma(factuo) = factuo_mm / sqrt(W*L*1e12)`

The factor converts area to square micrometres. APM does not translate these
raw PSP parameters into the benchmark `vth_shift` or `drive_shift` intents.
The validator reads the resolved internal PSP instance values, checks local
pair independence, and verifies that fourfold device area gives approximately
half the `delvto`/`factuo` spread.

## Persisted result layout

The command writes:

- `native_corners.csv`: N/P threshold and on-current observations for every
  selected corner;
- `native_process_samples.csv`: seed, exact upstream parameter identity,
  nominal/deviation inputs, resolved value, and normalized z value;
- `native_process_observations.csv`: duplicate-device terminal observations
  demonstrating model-global sharing;
- `native_mismatch_samples.csv`: per-instance resolved geometry,
  `delvto`/`factuo`, expected scaling, normalized values, and raw/canonical
  terminal current;
- `report.json`: schema `apm.native-variation-validation.v1`, source/artifact
  hashes, statistical summaries, log audit, replay checks, and pass criteria;
- reproducibility netlists, raw corner curves, and ngspice logs.

Raw voltage-source currents retain simulator sign; positive `idmag` fields are
canonical magnitudes. No IHP-native Spectre Monte Carlo compatibility is
claimed for v1.0.
