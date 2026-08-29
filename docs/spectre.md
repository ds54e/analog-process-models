# Spectre model-only compatibility

## Status: EXPERIMENTAL / UNVERIFIED

The v1.0 Spectre deliverable is a set of model files only. Cadence Spectre is
not available in the APM reference environment, so these files have **not been
parsed or simulated by Spectre**. APM does not claim parse validity, numerical
conformance with ngspice, or compatibility with any particular Spectre release.
The automated `apm spectre-check` command is a static consistency audit, not a
simulator validation.

Check the compact-model capabilities of the Spectre installation that will run
the models before use:

```text
spectre -h bsim3v3
spectre -h psp103
spectre -h bsim4
spectre -h bsimcmg
```

The files intentionally contain no analyses, sources, or testbenches. They also
contain no SKILL, CDF, symbols, OA libraries, ADE/Maestro states, OCEAN, or
Virtuoso automation. Virtuoso integration is fully user-managed.

## Shipped files

| Purpose | Path | Compact-model route |
| --- | --- | --- |
| Common benchmark statistics and corners | `variation/spectre/benchmark_variation.scs` | Spectre `statistics` and library sections |
| Common benchmark passives | `passives/spectre/benchmark_passives.scs` | Spectre resistor/capacitor primitives |
| APM350 | `models/apm350/spectre/apm350.scs` | native Spectre BSIM3v3 through the SPICE level-49 mapping |
| APM130 | `models/apm130/spectre/apm130.scs` | native Spectre PSP103 with a deterministic IHP TT-card translation |
| APM045 | `models/apm045/spectre/apm045.scs` | native Spectre BSIM4 through the SPICE level-54 mapping |
| APM022 | `models/apm022/spectre/apm022.scs` | native Spectre BSIM4 through the SPICE level-54 mapping |
| APM016F | `models/apm016f/spectre/apm016f.scs` | native Spectre BSIM-CMG |

The public terminal order is `(d g s b)`. Planar public sizing is only `w,l`;
FinFET public sizing is only `l,nfin`. Names beginning `apm__` are reserved
implementation parameters needed to put local mismatch inside each subcircuit.
They are not part of the stable public interface and must not be set by users.

## Selecting nominal, corners, or Monte Carlo

Include exactly one section from the common variation library before including
the selected kit and passive files. For nominal benchmark operation, select:

```text
include "variation/spectre/benchmark_variation.scs" section=bench_tt
include "models/apm045/spectre/apm045.scs"
include "passives/spectre/benchmark_passives.scs"
```

The other deterministic sections are `bench_ff`, `bench_ss`, `bench_fs`, and
`bench_sf`. Their normalized values are exactly the five vectors frozen in
`variation/benchmark_v1.toml`; MOS fast/slow directions are defined by
observable threshold magnitude and drain-current magnitude, not by the sign of
a raw compact-model parameter. Benchmark R and C remain nominal in these five
MOS corners, as specified by the common benchmark contract.

For Monte Carlo, select `bench_mc`. The user-owned Spectre analysis then chooses
one of the normal modes:

- `variations=process` activates the six global process variables;
- `variations=mismatch` activates independent local variables per wrapper
  instance;
- `variations=all` activates both sets.

The repository does not ship that analysis or a Spectre testbench. Spectre's
own RNG and run seed are authoritative for this backend; seed-for-seed identity
with the ngspice Python PCG64 sampler is neither required nor claimed.

## Distribution and correlation contract

Every `vary` statement samples a zero-nominal, unit-standard-deviation Gaussian
with `percent=no`. Wrapper expressions apply the frozen benchmark sigmas:

| Observable | Process sigma | Local sigma at reference match size |
| --- | ---: | ---: |
| MOS threshold-magnitude shift | 0.012 V | 0.008 V |
| MOS drain-current-magnitude shift | 0.04 | 0.025 |
| R value scale | 0.02 | 0.01 |
| C value scale | 0.02 | 0.01 |

The four N/P MOS process variables and the R/C process variables are distinct
and global for one Monte Carlo point. No `correlate` statement is present, so
they are independent. The mismatch variables are declared in `bench_mc` and
referenced from expressions inside the MOS/R/C subcircuits, following Spectre's
documented regular-subcircuit methodology; Spectre therefore gives each
subcircuit instance its own local draw. Local threshold and drive variables are
distinct and independent. Process, mismatch, MOS, R, and C variables are
mutually independent by default. APM does not invent statistical correlation.

Planar matching uses
`match_size=(W*L)/(Wref*Lref)`. FinFET matching uses
`match_size=(NFIN*L)/(NFINref*Lref)`. Passive `match_size` is the public positive
dimensionless input. Every local sigma scales as `1/sqrt(match_size)`. Four
times the matching size therefore halves local sigma.

Threshold shifts compose additively. Drive and passive factors compose
multiplicatively. The files contain no clipping; invalid negative factors are
outside the benchmark's intended operating range and must be treated as an
error by a user-owned flow rather than silently changed.

## Observable-intent adapter

Spectre wrappers use the real-ngspice-calibrated coefficients from
`variation/adapters_v1.toml` without changing them. For a raw delta `x` and
requested observable shift `y`, each stored fit is

```text
y = a*x + b*x^2
```

and the wrapper selects the root continuous through `x=0`. Threshold applies
the resolved raw value to `delvto` (planar/PSP) or `delvtrand` (BSIM-CMG).
Drive applies the resolved multiplier to `mulu0`, `factuo`, or `ids0mult`.
These coefficients preserve APM's intended sign, distribution, geometry, and
composition semantics. Because they were calibrated against ngspice, only a
future real-Spectre characterization can establish the achieved Spectre
observable sigma or cross-simulator numerical conformance.

## APM130 translation boundary

The pinned IHP card names the OpenVAF module `psp103va`; Spectre's native model
is `psp103`. `tools/generate_spectre_psp.py` deterministically selects only the
TT N/P QS model blocks and their 34 TT global parameters, changes that model
type identifier, and fixes the upstream wrapper-only `ng`, `pre_layout`, and
`SWSOA` inputs to the values used by APM's thin public wrapper. It does not fit
or change a parameter value. The generated file retains the IHP Apache-2.0
notice and records both source hashes.

Regenerate or audit it with:

```text
python tools/generate_spectre_psp.py
python tools/generate_spectre_psp.py --check
```

APM130 supplies APM benchmark process/mismatch/all semantics only. IHP-native
Monte Carlo compatibility in Spectre is not claimed. The real ngspice-native
IHP flow described in `docs/native-variation.md` remains separate.

## Static audit

Run:

```text
apm spectre-check --output .apm/results/spectre-structural
```

The report verifies artifact presence and status banners, public names and
sizing, exact adapter/configuration consistency, all five corner vectors,
process/mismatch/all declarations, passive scaling, deterministic APM130 card
generation, model-only scope, and documentation. Its successful status is
`structurally_checked`; backend status remains `experimental_unverified`, and
the report records that real-tool validation was not performed.

## Spectre syntax basis

Cadence's public technical forum documents Spectre's native
[`bsim3v3`/`bsim4` model selection and language directives](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/30643/nmos4-is-an-undefined-primitive-device),
the built-in [`psp103` model name](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/27733/problems-to-run-psp-and-bsim3-compact-models-in-verilog-A),
the built-in [`bsimcmg` interface](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/24606/how-to-use-bsim-cmg-models-to-build-and-simulate-finfet-circuits),
and the requirement that a mismatch-varying parameter live
[`within a subckt`](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/63335/monte-carlo-voltage-source/1403110).
These are syntax/design inputs, not evidence that the APM files pass a real
Spectre parser.
