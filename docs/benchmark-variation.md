# APM benchmark variation and passives

APM benchmark variation is a synthetic, technology-neutral comparison basis.
It is not a foundry statistical model, Pelgrom extraction, yield prediction, or
substitute for upstream/native variation.

The frozen v2 contracts are:

- `variation/benchmark_v2.toml` — distributions, correlations, corners, and
  observable-intent semantics;
- `variation/adapters_v2.toml` — real-ngspice-calibrated mappings for all 13
  families and 26 devices; and
- `passives/benchmark_v2.toml` — technology-neutral Rbench/Cbench behavior.

Persisted benchmark rows use `variation_origin = "benchmark"`.
Model-owned results use `variation_origin = "native"` and retain upstream
profile names. The two systems are not translated into one another.

## Observable MOS intents

The stable variables describe terminal behavior, not raw compact-model knobs:

- `vth_shift`: positive means a larger threshold-voltage magnitude for N and
  P devices.
- `drive_shift`: positive means a larger drain-current magnitude at the
  declared family/device reference bias.

Each family/device adapter maps those intents to the appropriate raw instance
handles (`delvto`, `mulu0`, `factuo`, `DELVTRAND`, or `IDS0MULT`) and
accounts for polarity-specific sign and scale. The measured fit is

`observable_shift = linear*raw_delta + quadratic*raw_delta^2`.

The resolver selects the inverse root continuous through zero. Raw compact
parameters are not treated as universal physical quantities.

Every adapter was calibrated in real ngspice 47 at 27 °C under the family's
native profile, `L=2*Lmin`, `VOUT=0.5*VDD`, and the gate-grid point nearest
gm/Id = 15 V⁻¹. Threshold mappings use the declared constant-current criterion
at `VOUT=0.8*VDD`. Coefficients, residuals, model/manifest identities, raw
ranges, reference current, geometry, and bias are frozen in
`variation/adapters_v2.toml`.

## Benchmark Global, Local, and All

The three public modes are:

- **Benchmark Global** (`global`): apply shared Global draws; Local draws are
  retained as inactive audit data.
- **Benchmark Local** (`local`): apply instance-local draws; Global draws are
  retained as inactive audit data.
- **Benchmark All** (`all`): apply both from the same canonical draw sequence.

For MOS, one Global latent is shared by every requested sibling family with the
same technology, polarity, and intent. Global threshold/drive, N/P, different
technologies, MOS/passives, and R/C are independent by default. Local
threshold/drive variables are independent per instance and independent of all
Global variables. There are no family-residual latents or undocumented partial
correlations in v2.

This sharing is a benchmark design for equal observable stress. It is not a
claim that real family parameters have fully correlated physical process
variation.

Threshold shifts add:

`vth_shift_total = vth_shift_global + vth_shift_local`.

Drive and passive factors compose multiplicatively. Nonpositive resolved
factors/values are rejected and never silently clipped. The Gaussian
distribution is not silently truncated; a resolved adapter record identifies
whether a draw stays within the real-tool-calibrated raw range.

## Frozen distributions

All latents are independent standard normal variables except for the explicit
Global sibling-family sharing above.

| Intent | Global sigma | Local sigma at reference size |
| --- | ---: | ---: |
| N/P threshold magnitude | 0.012 V | 0.008 V |
| N/P drain-current magnitude | 0.03 fractional | 0.025 fractional |
| Rbench value | 0.02 fractional | 0.01 fractional |
| Cbench value | 0.02 fractional | 0.01 fractional |

The 12 mV Global threshold prior remained inside every measured ±40 mV adapter
range at three sigma. Global drive was frozen at 3%, rather than the historical
4% prior, so every three-sigma corner remains within every measured mapping.
These are comparison severities, not manufacturing statistics.

## Matching-size law

Planar MOS matching size is

`match_size = (W*L)/(Wref*Lref)`.

FinFET matching size is

`match_size = (NFIN*L)/(NFINref*Lref)`.

Local sigma is `sigma_ref/sqrt(match_size)`; four times the matching size
therefore halves the local sigma. FinFET requests contain only `l_m` and
positive integer `nfin`; no synthetic continuous width is introduced.
Passive `match_size` is a positive dimensionless benchmark input, not layout
area.

## Deterministic corners

Corners are fixed Global vectors and consume no random draw:

| Corner | N threshold/drive | P threshold/drive | R/C Global scale |
| --- | --- | --- | --- |
| `bench_tt` | 0, 0 | 0, 0 | 0, 0 |
| `bench_ff` | −3σ, +3σ | −3σ, +3σ | 0, 0 |
| `bench_ss` | +3σ, −3σ | +3σ, −3σ | 0, 0 |
| `bench_fs` | −3σ, +3σ | +3σ, −3σ | 0, 0 |
| `bench_sf` | +3σ, −3σ | −3σ, +3σ | 0, 0 |

These names always identify APM benchmark corners, never an IHP/upstream
corner.

## Requests, sampling, and replay

Input uses schema `apm.benchmark-request.v2`; each MOS entry declares a
`technology/family/device` selector, legal public geometry, and its top-level
ngspice X-instance name. See `examples/benchmark_request.json`.

```console
apm sample-variation \
  --request examples/benchmark_request.json \
  --mode all \
  --seed 20260830 \
  --output .apm/results/sample-all.json

apm resolve-corner bench_fs \
  --request examples/benchmark_request.json \
  --output .apm/results/bench-fs.json
```

ngspice benchmark randomness is generated in Python with NumPy
`Generator(PCG64)`. A canonical order generates all Global latents followed
by sorted per-instance Local latents regardless of selected mode. The resolved
`apm.resolved-variation.v2` JSON persists the integer seed, NumPy/algorithm
identity, configuration paths/hashes, normalized draws, sampled/applied
values, latent scope, total observable intents, raw adapter values, range
status, and exact ngspice `alter` commands.

The content-derived `sample_id` covers the canonical payload. Loading verifies
it; writing refuses to replace a different sample. Persisted samples, not an
assumed future RNG implementation, are the replay authority.

`apm benchmark-check --output DIR` resolves all three modes and five corners,
checks replay/different-seed behavior and statistical cohorts, runs every
family/device through real ngspice, and validates passives. Its report schema is
`apm.benchmark-validation.v2`.

## Benchmark passives

Include `passives/ngspice/benchmark_passives.inc` and instantiate:

```spice
Xr p n Rbench value=10k tc1=0.001 match_size=1
Xc p n Cbench value=1p tc1=0.0002 match_size=1
```

The resolver applies Global and/or Local factors before temperature:

`value(T) = resolved_value_at_27C * (1 + tc1*(T-27C))`.

`tc1` is in °C⁻¹; nonpositive results are rejected. Rbench resolves to an
ordinary simulator resistor and therefore retains native Johnson noise rather
than adding a custom source. Native technology passives remain separate and
are not the golden comparison basis.

## Native and Spectre boundaries

IHP-native APM130 LV/HV validation is documented in
[`native-variation.md`](native-variation.md). It uses ngspice evaluation of
the pinned upstream random expressions and does not adopt the benchmark
correlation contract.

The Spectre model-only layer expresses the same intended Global/Local/All
distributions, geometry scaling, and explicit correlations using Spectre's own
process/mismatch sampling. Seed-for-seed identity is not required. It remains
experimental/unverified until executed in a real Spectre environment.
