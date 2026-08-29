# M9 Spectre model-only compatibility

Milestone status: `structurally_checked`

Backend status: `experimental_unverified`

Run time: 2026-08-29 18:12 UTC (2026-08-30 JST)

## Scope and evidence boundary

The required `spectre.model_only` gate is structural. Cadence Spectre is not
installed in the reference environment (`command -v spectre` returned no
path), and the final report records `spectre_executable_detected=null` and
`real_tool_validation_performed=false`. No APM Spectre file has been parsed or
simulated by Spectre. This evidence does not claim parse validity, numerical
conformance, or a validated Spectre backend.

The final static command was:

`apm spectre-check --output .apm/results/m9-spectre-20260830-final`

It exited zero with report status `structurally_checked` and backend status
`experimental_unverified`. The report SHA-256 is
`3bc7db4b838ad4c470b8d11b7ada85927dfdc1db34aade0e51d2b75d22328158`.

## Model-only artifacts

Every file has the prominent `EXPERIMENTAL / UNVERIFIED` banner. The five MOS
files retain terminal order `(d g s b)` and exactly the public sizing names
used by the ngspice-facing interface: planar `w,l` and FinFET `l,nfin`.
Additional adapter intermediates use the reserved `apm__` prefix and are not
part of the public contract.

| Artifact | Native Spectre route | SHA-256 |
| --- | --- | --- |
| `models/apm350/spectre/apm350.scs` | BSIM3v3 via SPICE level 49 | `a655397c7287a878ddc67fcac01f9bc371406509affe013320199e0c4cf172d1` |
| `models/apm130/spectre/apm130.scs` | PSP103 | `fc783a1e3c963a5bdaf6db92700f67621e2fdaefaa67e8ac8d3cee9b6272cdea` |
| `models/apm045/spectre/apm045.scs` | BSIM4 via SPICE level 54 | `9b25d7b129f71d2775a2d6b54ad48a89997b05a4f4df22cfa5de67974ca156e6` |
| `models/apm022/spectre/apm022.scs` | BSIM4 via SPICE level 54 | `ddf97554eea15759a52793048e95975426a3e92494630548598b2f31e6831011` |
| `models/apm016f/spectre/apm016f.scs` | BSIM-CMG | `7e372cd832a86ee87554a744b1998d37407d291606fdba56a586858a4b2b0b4f` |
| `passives/spectre/benchmark_passives.scs` | resistor/capacitor primitives | `ee3e64763128686c9278ebab93ca0b5e0e2c1962d66f02a0e5cdc46aaec4ace3` |
| `variation/spectre/benchmark_variation.scs` | library sections + `statistics` | `af764d688c94e381d66c69659a69688a90d3f82d284e55ebac182fe47bbd38f0` |

The scope audit accounts for eight model artifacts including the translated
APM130 card. It found zero analyses, sources, testbenches, SKILL/CDF/OA/OCEAN
assets, or other Virtuoso integration. User-owned simulations must include
exactly one variation-library section plus the desired kit/passive files.

## Benchmark corners and Monte Carlo semantics

The common variation library contains `bench_tt`, `bench_ff`, `bench_ss`,
`bench_fs`, and `bench_sf`. The checker compares every one of their six global
normalized coordinates to `variation/benchmark_v1.toml`; all match exactly.
R/C process coordinates remain zero in these MOS corners as required.

The `bench_mc` section declares six distinct global standard-normal variables:
N/P threshold and drive plus R and C value scale. Its `process` block varies
each independently with `dist=gauss std=1 percent=no`. Its `mismatch` block
varies four distinct standard-normal variables for MOS threshold/drive and R/C
local scale. Those mismatch parameters are referenced from expressions inside
regular subcircuits, so the documented Spectre methodology applies a new draw
per subcircuit instance. There is no `correlate` statement and no undocumented
correlation.

The intended modes are selected by a user-owned Monte Carlo analysis with
`variations=process`, `variations=mismatch`, or `variations=all`. Spectre's RNG
does not need seed identity with the ngspice Python PCG64 sampler.

The wrappers apply the frozen 12 mV / 4% process and 8 mV / 2.5% reference
local MOS sigmas, plus the 2% / 1% passive sigmas. Planar local scaling uses
`(W*L)/(Wref*Lref)`, FinFET scaling uses
`(NFIN*L)/(NFINref*Lref)`, and passives use public dimensionless
`match_size`; every local sigma is divided by `sqrt(match_size)`.
Threshold intent composes additively and drive/passive factors compose
multiplicatively. No expression clips an invalid value.

For all ten N/P wrappers, the checker compares the four exact adapter fit
coefficients to `variation/adapters_v1.toml`, checks the calibrated near-zero
inverse root, the polarity-specific process variable, matching denominator,
raw handle, and artifact hash in provenance. These mappings preserve intended
observable distribution/sign semantics; they are not evidence of achieved
Spectre numerical sigma.

## APM130 translation and licensing

`tools/generate_spectre_psp.py` deterministically extracts the 34 TT N/P global
parameters and the two QS model blocks from the pinned IHP commit
`331c00484213b13414777eec1336ef5c29b969bd`. It changes only the OpenVAF model
type identifier `psp103va` to Spectre's native `psp103` identifier and fixes
upstream wrapper-scope `ng`, `pre_layout`, and `SWSOA` inputs. It does not fit
or alter a selected model parameter value. `--check` reports the generated file
up to date.

The generated card preserves the IHP Apache-2.0 copyright/license notice and
source hashes. Its SHA-256 is
`338936fe4fe8a6bbbf26b83941fa75a86aec77bfc697ece7d9c0dc44deabb752`;
the generator hash is
`fefb6ecf6856ef6b9e93094e83c23762760d2421f6de0d6e52de0e063758a9bd`.
Both transformation and hashes are in `models/apm130/provenance.toml`.
IHP-native Spectre Monte Carlo is explicitly not claimed; only APM benchmark
statistics are supplied.

## Regression and structural-gate conclusion

Ruff, all 49 repository tests, `git diff --check`, and REUSE 3.3 lint pass.
REUSE reports license and copyright information for 128/128 files. Tests cover
the CLI/status boundary, every model interface, exact adapter and corner drift,
Monte Carlo variable declarations, passive laws, model-only scope, per-kit
provenance hashes, and reproducible APM130 card generation.

This satisfies the required structural gate `spectre.model_only` and completes
M9's required work. It does not promote the backend beyond
`experimental_unverified`. M10 licensing/claim/release-metadata audits,
release-validator integration, real clean-clone execution, and the v1.0.0
release decision remain open.
