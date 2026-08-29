# APM benchmark variation and passives

APM benchmark variation is a synthetic, technology-neutral comparison basis. It
is not a foundry statistical model, a Pelgrom model, a yield prediction, or a
substitute for a kit's native variation. The frozen v1 values live in
`variation/benchmark_v1.toml`; the technology-neutral passive contract lives in
`passives/benchmark_v1.toml`; and measured compact-model mappings live in
`variation/adapters_v1.toml`.

Every persisted benchmark result uses `variation_origin = "benchmark"`.
PDK/model-native results use `variation_origin = "native"` and retain their
actual upstream corner/profile identity. The two systems must not be overlaid or
silently translated into one another.

## Observable MOS intents

The common MOS variables describe terminal behavior, not a shared raw compact
model API:

- `vth_shift`: a positive value means a larger threshold-voltage magnitude for
  both N and P devices.
- `drive_shift`: a positive value means a larger drain-current magnitude at the
  kit's documented reference bias.

Each kit maps those intents to model-family-specific instance parameters. The
v1 mapping is a measured quadratic fit,

`observable_shift = linear*raw_delta + quadratic*raw_delta^2`,

which the resolver inverts using the root nearest zero. Equal raw compact-model
parameter changes are not treated as equal observable changes.

The calibration point is 27 degC, `L=2*Lmin`, `VOUT=0.5*VDD`, and the nominal
VCTRL grid point nearest `gm/Id=15 1/V`. Threshold mapping is measured with the
kit's constant-current criterion at `VOUT=0.8*VDD`. Raw threshold offsets from
-40 mV through +40 mV and raw drive multipliers from 0.8 through 1.2 are swept
in real ngspice 47.

| Kit/model | N raw handles | P raw handles | Raw sign for positive `vth_shift` | Small-signal drive response |
| --- | --- | --- | --- | ---: |
| APM130 / PSP103 | `delvto`, `factuo` | `delvto`, `factuo` | N `+`, P `+` | N 0.9948, P 0.9865 |
| APM045 / BSIM4 | `delvto`, `mulu0` | `delvto`, `mulu0` | N `+`, P `-` | N 0.8574, P 0.8953 |
| APM022 / BSIM4 | `delvto`, `mulu0` | `delvto`, `mulu0` | N `+`, P `-` | N 1.0007, P 1.0121 |
| APM016F / BSIM-CMG | `DELVTRAND`, `IDS0MULT` | `DELVTRAND`, `IDS0MULT` | N `-`, P `-` | N 1.0000, P 1.0000 |

Here the drive response is observable fractional Id change per unit raw
multiplier change near nominal. `variation/adapters_v1.toml` is authoritative
for all coefficients, residuals, reference currents, geometry, biases, raw
parameter paths, and calibrated ranges. The remaining APM350 adapter is added
at its implementation milestone; the benchmark specification itself does not
change per kit.

## Frozen v1 distributions

All normalized variables are independent standard normal variables unless an
explicit profile says otherwise.

| Variable | Process sigma | Local mismatch sigma at `match_size=1` |
| --- | ---: | ---: |
| N/P `vth_shift` | 0.012 V | 0.008 V |
| N/P `drive_shift` | 0.04 fractional Id | 0.025 fractional Id |
| `Rbench` value scale | 0.02 fractional value | 0.01 fractional value |
| `Cbench` value scale | 0.02 fractional value | 0.01 fractional value |

These modest synthetic values were frozen after PSP103, BSIM4, and BSIM-CMG
were operational and their observable mappings had been measured. They make
cross-kit perturbations visible while keeping the fixed three-sigma corners
inside the measured raw ranges. They do not describe manufacturing statistics.

The six process variables are mutually independent: N threshold, N drive, P
threshold, P drive, resistor scale, and capacitor scale. Each is global within
one resolved sample for its device/passive class. Local threshold/drive or
passive variables are independent per APM instance, independent of one another,
and independent of all process variables. There is no undocumented
cross-correlation.

The three Monte Carlo modes are:

- `process`: apply global process draws and retain local draws as inactive audit
  data;
- `mismatch`: apply local mismatch draws and retain global draws as inactive
  audit data;
- `all`: apply both from the same canonical draw sequence.

Threshold shifts add. MOS drive and passive factors compose
multiplicatively. Nonpositive resolved factors/values are rejected and never
silently clipped. The Gaussian distribution is not silently truncated; a
resolved adapter record explicitly reports whether its raw value lies inside
the characterized range.

## Matching-size law

Planar MOS matching size is

`match_size = (W*L)/(Wref*Lref)`.

FinFET matching size is

`match_size = (NFIN*L)/(NFINref*Lref)`.

Local sigma is `sigma_ref/sqrt(match_size)`, so four times the matching size
gives half the local sigma for the same normalized draw. FinFET requests use
only `l_m` and positive integer `nfin`; they never acquire a synthetic width.

Passive `match_size` is a positive dimensionless benchmark input, not layout
area. Its only v1 meaning is the same inverse-square-root mismatch law.

## Deterministic corners

Corners are fixed vectors of the process sigmas above and never consume RNG
draws:

| Corner | N threshold/drive | P threshold/drive | R/C scale |
| --- | --- | --- | --- |
| `bench_tt` | 0, 0 | 0, 0 | 0, 0 |
| `bench_ff` | -3 sigma, +3 sigma | -3 sigma, +3 sigma | 0, 0 |
| `bench_ss` | +3 sigma, -3 sigma | +3 sigma, -3 sigma | 0, 0 |
| `bench_fs` | -3 sigma, +3 sigma | +3 sigma, -3 sigma | 0, 0 |
| `bench_sf` | +3 sigma, -3 sigma | -3 sigma, +3 sigma | 0, 0 |

These names always mean APM benchmark corners. They are distinct from native
IHP or other upstream model corners.

## Resolved samples and replay

An input request uses schema `apm.benchmark-request.v1`. See
`examples/benchmark_request.json` for N/P planar, N/P FinFET, resistor, and
capacitor instances. Every ID is unique. A MOS request declares its kit,
polarity, public geometry, and the actual top-level ngspice X-instance name so
the resolver can emit exact instance-level `alter` commands.

Resolve a Monte Carlo sample or deterministic corner with:

```console
apm sample-variation \
  --request examples/benchmark_request.json \
  --mode all \
  --seed 20260830 \
  --output results/all.json

apm resolve-corner bench_fs \
  --request examples/benchmark_request.json \
  --output results/bench_fs.json
```

ngspice randomness is generated only in Python using NumPy
`Generator(PCG64)`. Six global draws are followed by sorted per-instance local
draws in a canonical order, regardless of the selected mode. A repeated
request/mode/seed/configuration produces byte-identical JSON; a differing seed
changes the sample. The JSON preserves the RNG algorithm, seed, NumPy version,
configuration paths/hashes, every normalized draw, sampled and applied values,
global/local identities, total observable intents, raw resolved adapter values,
and exact ngspice `alter` commands.

The content-derived `sample_id` covers the canonical payload. Loading verifies
that ID, and writing refuses to replace a different sample. Persisted samples,
not an assumed future RNG implementation, are the authoritative replay input.
Apply their `ngspice_alter_commands` after public device instantiation and
before the deterministic analysis. `apm benchmark-check --output DIR` builds
the real models, resolves all modes/corners, runs ngspice, repeats the `all`
sample, and writes a fully linked validation report.

## Benchmark passives

Include `passives/ngspice/benchmark_passives.inc` and instantiate:

```spice
Xr p n Rbench value=10k tc1=0.001 match_size=1
Xc p n Cbench value=1p tc1=0.0002 match_size=1
```

The Python resolver first applies process and local mismatch to the nominal
value. That resolved concrete value is passed to an ordinary simulator resistor
or capacitor primitive. Temperature then follows

`value(T) = resolved_value_at_27C * (1 + tc1*(T-27C))`,

where `tc1` is in `1/degC`. A temperature that produces a nonpositive value is
rejected. `Rbench` adds no custom noise source, so ordinary simulator resistor
Johnson noise is retained. Native technology passives, where available, are a
separate optional facility and are never the golden cross-process basis.

## Current limitations

Benchmark severities are comparison knobs, not assertions of silicon fidelity.
Mappings characterize the documented reference point and measured raw ranges;
they do not make compact models interchangeable away from that point. The
ngspice path uses deterministic resolved samples. Spectre benchmark statistics
are a separate model-only deliverable and remain experimental/unverified until
tested in a real Spectre environment.
