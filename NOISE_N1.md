# APM V3-N1 — Noise Acquisition and Fit-Method Qualification

This document is normative for the V3-N1 milestone together with `AGENTS.md`, `GOAL.md`, and `NOISE_CHARACTERIZATION.md`.

APM v2.0.0 remains immutable. V3-N0 is complete and validated by `validation/evidence/v3_n0_noise_spike.json`. V3-N1 must preserve the V3-N0 measurement contract while resolving the remaining acquisition/fitting uncertainties before catalog-wide noise characterization.

## 1. Purpose

V3-N1 shall freeze a reproducible acquisition policy and a fail-closed spectrum-region detector for stationary small-signal MOS noise.

The milestone answers three questions:

1. How should APM extend the frequency range when the base sweep does not expose a white-noise plateau?
2. How should flicker and white regions be detected without assuming fixed absolute-frequency windows?
3. What does a low-VDS diagnostic reveal before the framework is expanded from the four engines to all 26 public MOS devices?

V3-N1 is not the all-device characterization milestone and is not a v3.0.0 release.

## 2. Preserve V3-N0 semantics

Do not redefine or weaken the validated V3-N0 measurement contract.

Keep:

- schema `apm.noise-characterization.v1` unless a strictly additive compatible field is needed;
- the 1-ohm ideal CCVS external drain-current probe;
- canonical `s_idrain_terminal_a2_per_hz`;
- canonical `s_vgate_equivalent_v2_per_hz`;
- persisted complex `y_dg_real_s` / `y_dg_imag_s`;
- precise bounded gm/Id bias refinement and finite-difference gm/gds;
- parameter-level effective noise provenance;
- raw backend source breakdown without a fake universal source-name mapping;
- ngspice 47 normal Sparse solver for required `.noise` jobs;
- the V3-N0 analytic resistor, white, flicker, and correlated OSDI fixtures.

The V3-N0 exact-commit qualification must remain reproducible and passing.

## 3. Required engines

V3-N1 continues to qualify the four engine representatives:

| Engine | Selector |
| --- | --- |
| native BSIM3 | `apm350/general/nmos` |
| PSP103 OSDI | `apm130/lv/nmos` |
| native BSIM4 | `apm045/vtg/nmos` |
| BSIM-CMG OSDI | `apm016f/svt/nfet` |

Do not expand to all 26 devices in this milestone.

## 4. Canonical operating point

The canonical V3-N1 operating point remains:

```text
T = 27 degC
L/Lmin = 2
Planar W = family/device default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
gm/Id target = 15 1/V
relative gm/Id error <= 1%
```

Resolve/revalidate the bias actively. Do not select the nearest historical DC row.

## 5. Frequency acquisition policy

### 5.1 Base sweep

Every canonical job starts with:

```text
f_start = 1 Hz
f_stop = 100 MHz
points_per_decade = 20
```

Keep 1 Hz and 20 points/decade unless V3-N1 real-tool evidence shows a concrete problem.

### 5.2 Adaptive white-region extension

Do not assume that the final decade of a sweep is white.

If the frozen candidate region detector defined below does not find a valid white region in the base sweep, repeat the complete spectrum with progressively larger upper endpoints:

```text
100 MHz
1 GHz
10 GHz
100 GHz
```

Rules:

- use the same 1 Hz lower endpoint and 20 points/decade on every attempt;
- stop at the first attempt that contains a valid white region;
- never extend beyond 100 GHz in V3-N1;
- if no valid white region is found by 100 GHz, record `white_region_not_observed_within_search_cap` and keep white/corner/gamma metrics null;
- reaching the search cap is an evidence result, not a milestone failure by itself;
- preserve every attempted stop frequency, result status, and reason in machine-readable acquisition metadata;
- do not change model parameters/selectors to force a plateau to appear.

The intent is a bounded adaptive acquisition policy, not one mandatory giant frequency range for every technology.

### 5.3 Why an interior plateau is allowed

The white region may be an interior region rather than the highest-frequency region. Compact models such as BSIM4 can include high-frequency induced-gate/correlation and other frequency-shaped contributions. Therefore a valid thermal-like plateau may occur after flicker roll-off and before a later high-frequency rise.

Do not encode `highest decade == white` anywhere in the implementation.

## 6. V3-N1 fit method

Implement a new versioned method, preferred identity:

```text
apm.noise-fit.contiguous-regions@1.0.0
```

The V3-N0 fixed-window method remains historical evidence and must not be silently reinterpreted.

### 6.1 Inputs

Use the persisted canonical external drain-terminal PSD.

Require:

- strictly increasing positive frequency;
- finite non-negative PSD;
- enough points for each requested region;
- no interpolation or hidden replacement of invalid values.

Raw spectrum remains authoritative.

### 6.2 Local log-slope estimator

For classification, estimate local slope in log(PSD) versus log(frequency) using centered ordinary least squares over a sliding window spanning approximately 0.5 decade.

At 20 points/decade, use 11 points as the nominal local window. If acquisition density changes later, derive the window from frequency span rather than hard-coding only an index count.

Do not classify edge points that lack a complete local window.

### 6.3 Flicker candidate points

A point is locally flicker-like when:

```text
0.5 <= -local_log_slope <= 1.5
```

Build contiguous runs from locally flicker-like points.

A flicker run is eligible only when:

- logarithmic frequency span >= 1.5 decades;
- point count >= 31 at the current 20-point/decade profile;
- whole-run log-log OLS gives `0.5 <= alpha <= 1.5`;
- whole-run log-log OLS `R^2 >= 0.98`.

If several eligible flicker runs exist:

1. choose the run with greatest logarithmic span;
2. then greatest point count;
3. then lowest geometric-center frequency.

Persist all candidate runs and the selection rationale, not only the winner.

### 6.4 White candidate points

A point is locally white-like when:

```text
abs(local_log_slope) <= 0.10
```

Build contiguous runs from locally white-like points.

A white run is eligible only when:

- logarithmic frequency span >= 1.0 decade;
- point count >= 21 at the current 20-point/decade profile;
- whole-run absolute log-log OLS slope <= 0.10;
- maximum PSD / minimum PSD <= 1.35.

If a valid flicker region exists, a selected white region must begin above the selected flicker region. If no flicker region exists, the lowest-frequency eligible white plateau may be selected.

If several eligible white runs remain:

1. choose the lowest-frequency eligible run after the flicker region;
2. then greatest logarithmic span;
3. then greatest point count.

This deliberately prefers the first thermal-like plateau before possible later high-frequency shaping.

Persist all candidate runs and selection rationale.

### 6.5 White floor

For a selected valid white region, use the median PSD of the selected region as `white_floor_a2_per_hz`.

Persist the selected region endpoints, point count, OLS slope, PSD ratio, and median.

### 6.6 Flicker fit

For the selected flicker region fit:

```text
S_flicker(f) = A_1Hz / f^alpha
```

Persist `alpha`, `A_1Hz`, `R^2`, selected region, and residual diagnostics.

### 6.7 Flicker corner

A corner may be reported only when both flicker and white fits are valid.

Compute the component intersection:

```text
A_1Hz / f_corner^alpha = white_floor
```

The candidate corner must lie between the selected flicker region and selected white region, allowing at most one local-slope half-window of numerical boundary tolerance. Otherwise record `fit_regions_inconsistent_with_corner` and leave the corner null.

Do not move the selected regions merely to force a valid corner.

### 6.8 Effective total gamma

`gamma_eff_total` remains:

```text
white_floor / (4*k*T*gm)
```

It is an external-terminal total-noise metric, not a claim that it equals a compact-model intrinsic channel-noise gamma.

Report it only when the white region and canonical gm are valid.

## 7. Required synthetic fit tests

The region detector must have deterministic tests for at least:

1. pure white PSD;
2. pure `1/f^alpha` PSD;
3. known `1/f + white` spectrum with a known corner;
4. `1/f + white + high-frequency rise`, where the correct white plateau is interior;
5. truncated spectrum with no observable white plateau;
6. spectrum with no observable flicker component;
7. insufficient-span candidate regions;
8. zero/non-finite/malformed input fail-closed behavior.

For constructed spectra with a known answer, define explicit tolerances and test the recovered region/alpha/floor/corner rather than merely testing that a status string exists.

## 8. Low-VDS diagnostic

Run a second diagnostic operating point on all four representative engines:

```text
T = 27 degC
L/Lmin = 2
Planar W = family/device default
FinFET NFIN = 1
VOUT = 50 mV effective drain/output bias
gm/Id target = 15 1/V
relative gm/Id error <= 1%
```

Use the same base frequency sweep and the same bounded adaptive acquisition policy where useful.

The low-VDS result is diagnostic. It does not replace the canonical `VOUT=0.5*VDD` result.

Required low-VDS evidence:

- exact resolved bias and gm/gds diagnostics;
- finite canonical PSD;
- gate-referred PSD and complex transfer;
- source breakdown;
- effective parameter snapshot;
- fit-method observation/status;
- no critical simulator diagnostics;
- Sparse solver attestation.

Do not impose an invented monotonic relationship between low-VDS and canonical noise.

## 9. BSIM-CMG correlated-noise low-VDS diagnostic

In addition to the unchanged production APM016F result, perform one diagnostic-only BSIM-CMG run with `TNOIMOD=1` at the low-VDS point.

Requirements:

- do not edit the APM016F model card;
- record the runtime selector override explicitly;
- verify the production model-card hash remains unchanged;
- capture nonzero correlated-noise source evidence when the model produces it;
- classify this as a backend/model-capability diagnostic, not the production APM016F noise result.

## 10. Acquisition metadata

Add a machine-readable acquisition record per result, either inside `metadata.json` or a separate `acquisition.json`.

Persist at least:

```text
policy_id
policy_version
base_start_hz
base_stop_hz
points_per_decade
extension_stop_sequence_hz
attempts[]
selected_attempt
search_cap_hz
search_cap_reached
white_region_observed
fit_method_id
fit_method_version
```

Each attempt records its stop frequency, spectrum hash, fit statuses, and reason for continuing/stopping.

## 11. Preserve parameter provenance

Do not change the V3-N0 effective-parameter strategy unless real N1 evidence requires a narrow correction.

Current expected strategy:

- native BSIM3: targeted ngspice `showmod` final values;
- native BSIM4: targeted `showmod`, retaining the documented ngspice-47 `LINTNOI=0` fallback only;
- PSP103 OSDI: OSDI `showmod` final values bound to explicit upstream-card values or pinned vendored Verilog-A defaults;
- BSIM-CMG OSDI: OSDI `showmod` final values bound to explicit APM-card values or pinned vendored Verilog-A defaults.

Do not create a universal raw compact-model parameter API.

## 12. Model immutability

V3-N1 must not tune or add process-noise coefficients to APM350, APM022, or APM016F.

The relevant APM-authored model-card paths must remain byte-for-byte unchanged from `v2.0.0` unless a separate explicit goal later authorizes calibration work.

Do not change FreePDK45 or IHP upstream model values.

## 13. Implementation shape

Prefer extending the existing V3-N0 modules rather than merging noise back into `characterize.py`.

Expected areas:

```text
src/apm/noise.py
src/apm/noise_fit.py
src/apm/noise_validate.py
src/apm/noise_provenance.py
tests/test_noise.py
```

A separate `noise_method_validate.py` is acceptable if it keeps responsibilities clearer.

Preferred command for real-tool milestone qualification:

```text
apm noise-method-check --output <dir>
```

Do not repurpose `apm validate --release` for V3-N1.

## 14. V3-N1 acceptance criteria

V3-N1 is complete only when all of the following have current exact-implementation-commit evidence:

1. all V3-N0 harness and four-engine acceptance checks still pass;
2. the new contiguous-region fit method passes its deterministic synthetic tests;
3. canonical four-engine runs use the bounded adaptive acquisition policy;
4. APM045/VTG is explicitly diagnosed beyond 100 MHz when needed, rather than being forced into a fixed-window white fit;
5. all four low-VDS diagnostic runs complete with valid raw canonical spectra or an explicit evidence-backed unsupported/invalid status;
6. the diagnostic BSIM-CMG `TNOIMOD=1` low-VDS run is executed without changing the production card;
7. parameter-level provenance remains complete;
8. no required noise job uses KLU;
9. existing repository regression, Ruff, REUSE, provenance, and static validation pass;
10. compact exact-commit evidence is committed under `validation/evidence/`;
11. `STATUS.md` records the evidence-based acquisition policy and fit-method decision;
12. the implementation provides a concrete recommendation on whether V3-N2 may expand to all 26 public MOS devices.

A missing white plateau at the bounded 100 GHz search cap is a legitimate null result and does not by itself fail V3-N1.

## 15. Evidence to retain

Prefer compact evidence:

```text
validation/evidence/v3_n1_noise_method.json
```

Large raw simulator results remain ignored/reproducible rather than committed.

The compact evidence must bind the exact implementation commit and hashes of the full generated reports.

## 16. Explicit non-goals

V3-N1 does not include:

- all 26-device catalog expansion;
- APM-authored noise calibration/tuning;
- noise Monte Carlo / benchmark variation;
- transient noise;
- RTS/RTN modeling;
- PSS/PNoise;
- oscillator phase-noise characterization;
- full 4-terminal noise correlation matrices;
- real Spectre validation;
- package version bump or v3 release/tag.

## 17. Research rationale

The V3-N0 result showed that a fixed 10–100 MHz white-review window works for some engines but not FreePDK45 VTG. The next method must therefore detect observed spectral behavior rather than encode one absolute white-frequency window.

Ngspice `.noise` supports squared PSD via `set sqrnoise`; required runs must continue to avoid KLU because the ngspice manual states KLU is not compatible with noise simulation.

BSIM4 explicitly models flicker noise, channel thermal noise, induced gate noise and correlation, physical-resistance thermal noise, and gate-tunneling shot noise. Consequently, high-frequency total external-terminal PSD need not remain flat indefinitely. The acquisition policy therefore searches for a valid contiguous plateau and permits a later high-frequency rise rather than treating the highest-frequency decade as intrinsically white.

Reference sources used for this decision include the ngspice 47 documentation and the Berkeley BSIM4 noise-model documentation. The repository implementation/evidence, not these references alone, determines V3-N1 pass/fail.
