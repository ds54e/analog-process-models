# APM V3-N2 — Catalog-Wide Noise Dataset and Comparison Qualification

This document is normative for the V3-N2 milestone together with `AGENTS.md`, `GOAL.md`, `NOISE_CHARACTERIZATION.md`, and `NOISE_N1.md`.

APM v2.0.0 remains immutable. V3-N0 and V3-N1 are complete. V3-N2 expands the frozen stationary-noise measurement and fitting method across the manifest-discovered public MOS catalog and produces auditable comparison datasets. It does not calibrate new process-noise coefficients and it is not a v3.0.0 release.

## 1. Purpose

V3-N2 shall answer whether the V3-N1 method can operate as a catalog-wide APM characterization domain rather than a four-engine spike.

The milestone must:

1. execute the frozen noise method across all 26 public MOS devices discovered from manifests;
2. add temperature and inversion-level coverage without silently clipping unreachable targets;
3. add geometry-native length scaling and FinFET NFIN scaling where the manifest already defines those geometries;
4. produce explicit within-technology threshold-family and cross-process-anchor comparison datasets;
5. preserve parameter-level noise provenance, raw spectra, source breakdown, and fail-closed fit semantics;
6. remain resumable/reproducible without blindly repeating already validated catalog jobs;
7. record an evidence-based decision on whether the project is ready for a later v3 release-hardening milestone.

## 2. Frozen V3-N0/V3-N1 foundations

Do not redefine the validated foundations.

Keep:

- `apm.noise-characterization.v1` per-device result semantics;
- canonical external drain-terminal total short-circuit current-noise PSD;
- canonical gate-referred PSD using the actual small-signal transfer;
- persisted `y_dg_real_s` and `y_dg_imag_s`;
- the 1-ohm ideal CCVS drain-current probe;
- bounded gm/Id bias refinement and finite-difference gm/gds;
- effective noise-parameter provenance;
- raw backend source breakdown without a universal source-name taxonomy;
- ngspice 47 normal Sparse solver for required `.noise` jobs;
- `apm.noise-fit.contiguous-regions@1.0.0`;
- `apm.noise-acquisition.bounded-white-search@1.0.0`;
- base sweep 1 Hz to 100 MHz at 20 points/decade;
- bounded complete-sweep extensions to 1 GHz, 10 GHz, and 100 GHz when needed;
- fail-closed nulls when no valid region is observed.

V3-N0 and V3-N1 regressions must remain reproducible and passing.

## 3. Catalog discovery

The N2 execution plan must be manifest-driven.

At the current baseline the catalog contains:

- five technologies;
- 13 Electrical Families;
- 26 public MOS devices.

Do not hand-code the 26 selectors as the runtime source of truth. Discover Technology -> Electrical Family -> Device from the catalog and build the job plan from manifest metadata.

Validation may assert the current expected totals of 5 technologies, 13 families, and 26 public devices so accidental omissions are fail-closed.

A future normally shaped family/device addition should require manifest data and generic orchestration, not a new technology-specific Python branch.

## 4. Stable request identity and deduplication

N2 contains many overlapping requested operating points. Do not rerun the same physical request merely because it belongs to more than one dataset view.

Define a stable machine-readable request identity from at least:

- schema/method identity;
- technology/family/device selector;
- operating-profile identity and resolved reference VDD;
- temperature;
- exact geometry;
- output/drain-bias definition;
- bias mode and gm/Id target or explicit effective VCTRL;
- acquisition policy/version;
- fit method/version;
- simulator/backend/model/provenance semantic hashes that make reuse safe.

Persist a deterministic request hash/ID.

The same canonical 27 degC gm/Id=15 result, for example, may satisfy the temperature matrix, inversion sweep, and comparison datasets without being simulated three times.

Never reuse a result solely because filenames happen to match.

## 5. Plan / execute / resume model

The catalog command must create a deterministic explicit job plan before running simulations.

Preferred high-level artifacts:

```text
plan.json
coverage.json
job_index.csv
results/<request_id>/...
summary/
report.json
```

For a fresh output directory, execute the plan normally.

A resumable mode is required for N2 because a catalog run may contain hundreds of device operating points. A form such as:

```text
apm noise-catalog-check --output <dir> --resume
```

is preferred.

Resume semantics must be strict:

- reuse only a completed result whose request identity and bound semantic/tool/model hashes match the current planned request;
- validate the existing result contract before reuse;
- incomplete or stale results must not be silently accepted;
- a stale completed result may be rerun into a clean replacement location or cause a clear fail-closed diagnostic;
- record whether each planned request was freshly executed or safely reused;
- the final report must be independent of execution order.

Do not weaken per-run non-overwrite protections merely to add resume.

Parallel execution is optional. Deterministic sequential execution is acceptable.

## 6. Required dataset A — canonical temperature matrix

Run every public MOS device at four temperatures:

```text
-40 degC
27 degC
85 degC
125 degC
```

Canonical geometry and bias:

```text
L/Lmin = 2
Planar W = device/family default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
gm/Id target = 15 1/V
```

Use the frozen N1 adaptive acquisition/fitting method independently at each temperature.

Expected planned coverage at the current catalog baseline is 26 devices x 4 temperatures = 104 logical canonical requests before deduplication with other datasets.

### Target reachability

Do not force gm/Id=15 if the legal operating profile cannot reach it.

Persist one of at least:

- `validated` with achieved gm/Id and error;
- `target_not_reachable` with bracketing/range evidence;
- `simulation_failed` with real-tool evidence.

`target_not_reachable` is scientifically different from an execution failure and must not be hidden. Comparison rows depending on an unreachable target become explicit null/not-comparable rows.

No target may be silently clipped to the nearest VCTRL endpoint.

## 7. Required dataset B — inversion-level sweep

At 27 degC, for every public MOS device, characterize:

```text
gm/Id targets = 5, 10, 15, 20, 25 1/V
```

with:

```text
L/Lmin = 2
Planar W = default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
```

Reuse the 15 1/V request from dataset A when identical.

Each requested target has the same explicit reachability semantics as dataset A.

The purpose is to expose noise versus inversion, not to claim every technology can span the complete target set.

The resulting dataset must preserve at least:

- target and achieved gm/Id;
- Id, gm, gds, gm/gds;
- exact VCTRL/VOUT;
- raw external drain PSD;
- gate-referred PSD;
- complex Ydg transfer;
- white/flicker/corner/gamma fit status and values where valid;
- integrated noise over explicitly defined common bands;
- effective noise-model provenance;
- adaptive acquisition attempt history.

## 8. Required dataset C — length scaling

At 27 degC and target gm/Id=15 1/V, characterize every device at each manifest-declared `characterization_lengths_m` value that is valid for that device.

Use:

```text
Planar W = default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
```

Do not invent technology-wide lengths when N/P/device ranges differ.

The existing L/Lmin=2 point should be reused when it coincides with a declared length request.

Persist scaling observations/derived exponents as descriptive metrics only. Do not impose monotonic white-noise, flicker-noise, or corner-frequency ordering unless evidence establishes a legitimate universal rule.

## 9. Required dataset D — FinFET NFIN scaling

For every APM016F public NFET/PFET device, at 27 degC and gm/Id=15 1/V:

- use `L/Lmin = 2`;
- characterize all manifest-declared `characterization_nfin` values;
- preserve integer NFIN semantics;
- do not fabricate a planar effective width.

At the current baseline this normally exercises NFIN 1, 2, and 4 where declared.

Compute descriptive NFIN scaling trends/exponents, but do not make exact proportionality a release requirement.

## 10. Planar width scaling is explicitly deferred

N2 does not invent a planar width grid.

The current family manifests provide default planar width and model bounds, but do not provide a common research-backed `characterization_widths_m` set analogous to FinFET NFIN.

Therefore V3-N2 keeps planar W at the device/family default.

A later milestone may add a manifest-backed width grid if there is a clear comparison need and validity rationale.

## 11. Diagnostic low-VDS coverage

Retain the V3-N1 50 mV low-VDS diagnostics as regression evidence.

N2 does not require a 50 mV run for all 26 devices.

Add the missing cross-process anchor-family diagnostic coverage at 27 degC when useful so both planar/FinFET generations are represented, but keep low-VDS data labeled `diagnostic` rather than replacing the canonical half-VDD operating point.

Do not globally enable `TNOIMOD=1`. The V3-N1 BSIM-CMG runtime-only capability experiment remains diagnostic and must not alter production model cards.

## 12. Comparison result domain

Add a machine-readable catalog/comparison layer without changing per-device `apm.noise-characterization.v1` results.

A separate schema such as:

```text
apm.noise-comparison.v1
```

is preferred.

Comparison outputs must reference source request/result identities and hashes rather than copying unauditable detached numbers.

Plots are derived presentation only; machine-readable numeric tables are authoritative.

## 13. Required threshold-family comparisons

At 27 degC compare threshold sibling families for both polarities where present:

- APM045: `vtl`, `vtg`, `vth`;
- APM022: `lvt`, `svt`, `hvt`;
- APM016F: `lvt`, `svt`, `hvt`.

Produce two distinct views.

### 13.1 Equal inversion

Use the catalog results at:

```text
gm/Id = 15 1/V
L/Lmin = 2
VOUT = 0.5 * reference_vdd
```

Do not force noise ordering across Vt flavors.

APM022/APM016F derived variants intentionally isolate threshold/workfunction behavior and share other model foundations; present observed noise similarities/differences as APM generic-model behavior, not foundry multi-Vt noise truth.

### 13.2 Equal bias

Add an explicit 27 degC threshold-family equal-bias view using effective coordinates:

```text
VCTRL = 0.5 * reference_vdd
VOUT  = 0.5 * reference_vdd
L/Lmin = 2
```

Planar W remains default; FinFET NFIN remains 1.

This view is separate from equal inversion. Persist actual resulting Id/gm/gm/Id alongside noise so the reason for differences is visible.

## 14. Required cross-process anchor comparison

At 27 degC compare the existing cross-process anchor families:

```text
apm350/general
apm130/lv
apm045/vtg
apm022/svt
apm016f/svt
```

Use the canonical equal-inversion point:

```text
L/Lmin = 2
VOUT = 0.5 * each family's reference_vdd
gm/Id = 15 1/V
```

Produce N and P comparison rows separately.

Required comparison quantities should include, where valid:

- raw `s_idrain_terminal_a2_per_hz` at explicit common reference frequencies;
- `s_vgate_equivalent_v2_per_hz` at explicit common reference frequencies;
- white floor;
- flicker coefficient and exponent;
- flicker corner;
- `gamma_eff_total`;
- explicitly band-limited integrated gate-referred noise;
- geometry and operating-profile identity;
- fit/reachability status.

Suggested common reference frequencies, which all base acquisitions cover, are:

```text
1 Hz
1 kHz
1 MHz
10 MHz
```

Use exact-grid values when present; if interpolation is needed, freeze and record a deterministic log-frequency interpolation method.

### Cross-basis restriction

Planar drain-noise results are tied to drawn-W geometry while FinFET results are tied to NFIN geometry.

Do not report planar-per-width versus FinFET-per-fin drain-noise ratios as though the normalization bases were physically equivalent.

Side-by-side raw/gate-referred results with explicit geometry are allowed. Ratios whose interpretation depends on a nonexistent universal effective-width conversion must be null/absent.

## 15. Integrated noise bands

At minimum produce one common-band integrated gate-referred result over a band guaranteed to exist in every base acquisition:

```text
1 Hz -> 10 MHz
```

Persist the integral in V^2 and an optional derived RMS display value in V.

Do not integrate beyond the actual acquired spectrum. Any additional integration band must be explicit in field names/metadata.

Raw spectrum remains authoritative over integrated summaries.

## 16. Temperature interpretation

Temperature results are descriptive; avoid ungrounded monotonic requirements.

Changing temperature while re-solving gm/Id also changes the bias point. Therefore a rise/fall in total terminal noise is not automatically a simple `kT` test.

Persist actual bias, gm, Id, white/flicker statuses, and model parameters so users can interpret the trend.

Do not claim physical temperature calibration for APM-authored noise defaults.

## 17. Geometry interpretation

Length/NFIN results must preserve geometry-native semantics.

For every scaling summary record:

- geometry values;
- operating point and gm/Id accuracy;
- raw PSD metrics;
- gate-referred metrics;
- source fit statuses;
- provenance;
- any descriptive scaling exponent and the exact points used.

No fake universal effective width is permitted.

## 18. Result/status semantics

Every logical request in the plan must end in an explicit state. At minimum distinguish:

- `validated`;
- `target_not_reachable`;
- `invalid_fit_region_not_observed` only as a metric status inside an otherwise valid spectrum result;
- `simulation_failed`;
- `stale_result_not_reused` / equivalent orchestration diagnostics when resume encounters incompatible artifacts.

A valid spectrum whose white/flicker fit is null remains a valid characterization result.

A missing metric must never cause the entire device to disappear from summary tables.

## 19. Catalog summary artifacts

Preferred top-level outputs include:

```text
plan.json
coverage.json
job_index.csv
operating_point_index.csv
noise_metrics_index.csv
noise_temperature.csv
noise_inversion.csv
noise_length_scaling.csv
noise_nfin_scaling.csv
noise_comparisons.csv
report.json
```

Exact filenames may differ if a smaller structure is clearly better, but equivalent machine-readable coverage is required.

Every summary row must carry enough identity to trace back to the exact per-run source.

## 20. CLI / orchestration

Prefer a dedicated command such as:

```text
apm noise-catalog-check --output <dir>
apm noise-catalog-check --output <dir> --resume
```

A separate comparison-only command may be added if useful, but one integrated fail-closed catalog qualification command is preferred for exact-commit evidence.

The command must not mutate model cards.

## 21. Acceptance criteria

V3-N2 is complete only when an exact implementation commit, rerun from fresh output, demonstrates:

1. V3-N0 regression passes;
2. V3-N1 method regression passes;
3. manifest discovery covers exactly the current 5 technologies / 13 families / 26 public devices;
4. the canonical four-temperature matrix is fully planned and every request has an explicit terminal status;
5. the 27 degC five-target gm/Id matrix is fully planned and every request has an explicit terminal status;
6. manifest-declared length scaling runs across the catalog with explicit status;
7. APM016F NFIN scaling runs across all public FinFET devices with explicit status;
8. threshold-family equal-inversion and equal-bias comparison datasets are generated;
9. the five cross-process anchors are compared separately by polarity without illegal planar/FinFET normalization ratios;
10. all valid per-device spectra use the frozen N1 acquisition/fit method and retain raw/provenance/source evidence;
11. resume/reuse semantics are exercised by an automated test or qualification run and reject a deliberately stale/mismatched result;
12. no required `.noise` job uses KLU;
13. pytest, Ruff, REUSE, provenance, catalog/distribution/claim/static validation pass;
14. APM350/APM022/APM016F model cards remain unchanged relative to the v2.0.0 baseline unless a separate explicit goal later authorizes changes;
15. compact exact-commit evidence is committed, preferred path `validation/evidence/v3_n2_noise_catalog.json`;
16. `STATUS.md` records observed coverage, unreachable-target counts, adaptive frequency-stop distribution, comparison highlights, validation hashes, and the recommended next milestone.

Do not define success as "every requested fit returned a number." Explicit nulls and unreachable targets are valid if the framework records them honestly.

## 22. Explicit non-goals

V3-N2 does not include:

- process-noise coefficient tuning/calibration;
- silicon/foundry correlation claims for APM-authored families;
- noise Monte Carlo or noise-parameter variation;
- RTS/RTN;
- transient noise;
- PSS/PNoise;
- oscillator phase noise;
- full terminal noise-correlation matrices;
- universal planar/FinFET effective-width conversion;
- invented planar width sweeps;
- real Spectre validation;
- package-version bump;
- v3 release/tag creation;
- repository visibility changes.

## 23. Completion evidence

Preferred compact evidence path:

```text
validation/evidence/v3_n2_noise_catalog.json
```

Large raw simulator outputs remain ignored/reproducible.

The evidence must bind the exact implementation commit, toolchain, frozen method identities, plan hash, coverage counts, source result hashes, comparison outputs, regression status, model immutability check, and final recommendation.

V3-N2 may recommend release hardening next if catalog-wide behavior is stable. That recommendation does not itself authorize a v3 tag or public release.
