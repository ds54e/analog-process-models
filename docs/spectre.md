# Spectre model-only compatibility

## Status: EXPERIMENTAL / UNVERIFIED

APM v4 supplies model files for all 15 Electrical Families and 30 public MOS
devices. Cadence Spectre is not available in the reference environment, so the
files have **not been parsed or simulated by Spectre**. APM does not claim
parse validity, numerical agreement with ngspice, or compatibility with any
particular Spectre release. `apm spectre-check` is a static, deterministic
consistency audit—not simulator validation.

Check the compact-model capabilities of the destination installation before
use (`spectre -h bsim3v3`, `spectre -h psp103`, `spectre -h bsim4`, and
`spectre -h bsimcmg`).

The deliverable contains no analyses, sources, or testbenches. It also contains
no SKILL, CDF, symbols, OA libraries, ADE/Maestro state, OCEAN, or Virtuoso
automation. Virtuoso integration is entirely user-managed.

## Family bindings

Every `family.toml` binds a family-qualified
`models/<technology>/families/<family>/spectre/model.scs` artifact. The files
preserve the same public names and terminal/sizing contracts as ngspice:

- planar: `(d g s b)` with `w,l`;
- FinFET: `(d g s b)` with `l,nfin`;
- no public `m`, `nf`, or `ng` sizing parameters.

Names beginning with `apm__` are private adapter parameters and are not stable
user inputs. APM350 uses the SPICE level-49/BSIM3 route, APM045 and APM022 use
the level-54/BSIM4 route, APM130 uses deterministically transformed native
PSP103 cards, and APM016F uses a mechanical Spectre-native BSIM-CMG
transcription. Those routes remain unverified until a real Spectre run exists.

## Nominal operation and benchmark corners

Include exactly one section from the common variation library before including
one or more family bindings and optional passives. For example:

```text
include "variation/spectre/benchmark_variation.scs" section=bench_tt
include "models/apm045/families/vtg/spectre/model.scs"
include "passives/spectre/benchmark_passives.scs"
```

The deterministic sections are `bench_tt`, `bench_ff`, `bench_ss`, `bench_fs`,
and `bench_sf`. They reproduce the fixed Benchmark Global vectors in
`variation/benchmark_v2.toml`. Each technology/polarity has its own global
threshold and drive latent; sibling Electrical Families in that technology
reference the same latent. Different technologies, N/P, threshold/drive, MOS,
R, and C have distinct variables and no invented partial correlation.

## Benchmark Global, Local, and All

Select `bench_mc`, then use the user-owned Spectre Monte Carlo analysis:

- **Benchmark Global** maps to `variations=process`;
- **Benchmark Local** maps to `variations=mismatch`;
- **Benchmark All** maps to `variations=all`.

This naming is APM's observable benchmark contract. Spectre's `process` and
`mismatch` words are only the backend mechanism. Spectre owns its samples and
run seed; seed-for-seed identity with the ngspice Python PCG64 sampler is not
required in v2.

Every `vary` statement uses a zero-mean, unit-standard-deviation Gaussian with
`percent=no`. Frozen severities are:

| Intent | Benchmark Global sigma | Benchmark Local sigma at reference size |
| --- | ---: | ---: |
| MOS threshold-magnitude shift | 0.012 V | 0.008 V |
| MOS drain-current-magnitude shift | 0.03 | 0.025 |
| R value scale | 0.02 | 0.01 |
| C value scale | 0.02 | 0.01 |

Planar matching size is `(W*L)/(Wref*Lref)`. FinFET matching size is
`(NFIN*L)/(NFINref*Lref)`. Passive `match_size` is a positive dimensionless
input. Every local sigma scales as `1/sqrt(match_size)`; four times the matching
size halves local sigma.

Threshold shifts compose additively. Drive and passive factors compose
multiplicatively. No adapter silently clips a draw. IHP-native APM130 Monte
Carlo remains a separate ngspice-validated flow; it is not exposed or claimed
through these Spectre benchmark files.

## Observable adapters

Each family/device wrapper embeds the coefficients frozen in
`variation/adapters_v2.toml`. For raw delta `x` and requested terminal
observable shift `y`, the measured fit is:

```text
y = a*x + b*x^2
```

The wrapper selects the inverse root continuous through `x=0`. Threshold uses
`delvto` for BSIM3/BSIM4/PSP or `delvtrand` for BSIM-CMG; drive uses `mulu0`,
`factuo`, or `ids0mult`. The coefficients were calibrated with real ngspice
runs. Only future real-Spectre characterization can establish the resulting
Spectre observable distributions or cross-simulator numerical conformance.

## Generated source boundary

`tools/generate_spectre_psp.py` selects the pinned IHP LV and HV TT N/P QS
model blocks, changes only the OpenVAF module name `psp103va` to Spectre's
native `psp103`, and fixes wrapper-only nominal inputs. It preserves upstream
parameter values and the Apache-2.0 notice.

`tools/generate_spectre_v2.py` deterministically emits all 15 family wrappers,
the BSIM-CMG transcription, benchmark variation sections, and benchmark
passives from the family manifests and frozen v2 TOML specifications. Audit
both generated layers with:

```text
python tools/generate_spectre_psp.py --check
python tools/generate_spectre_v2.py --check
```

## Static audit

Run:

```text
apm spectre-check --output .apm/results/spectre-structural
```

The report verifies all family/device bindings, exact adapter coefficients,
Global/Local/All and corner declarations, passive semantics, deterministic
generation, and the model-only boundary. Its success status is
`structurally_checked`; backend status remains `experimental_unverified`, with
real-tool validation, parse validity, and numerical conformance all explicitly
false.
