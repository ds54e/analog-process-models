# APM V3-N2 Catalog-Wide Noise Dataset Goal

## 0. Repository state

Work on the existing repository:

- repository: `https://github.com/ds54e/analog-process-models`
- project: Analog Process Models (APM)
- released baseline: `v2.0.0` at `3cc6cfea4932cc40f2d693784d0a569926cdf399`
- completed V3-N0 implementation commit: `9c9f5b132829bda0e06045981e34e0dd2a41deb4`
- completed V3-N1 implementation commit: `0aab87b98697bd8806d13d244595a989cd81a0e3`
- V3-N0 exact-commit evidence: `validation/evidence/v3_n0_noise_spike.json`
- V3-N1 exact-commit evidence: `validation/evidence/v3_n1_noise_method.json`

APM v2.0.0 is complete, released, and immutable. V3-N0 and V3-N1 are complete. Current `main` is the post-v2 development line.

Do not change repository visibility. Do not move/rewrite the v2 tag. Do not create/tag v3.0.0 as part of this goal.

## 1. Goal

Implement and validate **V3-N2: Catalog-Wide Noise Dataset and Comparison Qualification**.

Read and follow `NOISE_N2.md` completely. It is the normative technical contract for this milestone. `NOISE_CHARACTERIZATION.md` and `NOISE_N1.md` define the already validated measurement/acquisition/fitting foundations that N2 must preserve.

The main deliverable is a manifest-driven, resumable, machine-readable stationary-noise dataset covering the current 26 public MOS devices, plus auditable temperature/inversion/geometry and family/process comparison summaries.

N2 characterizes the noise predictions of the existing compact models. It does not create a new process-noise calibration.

## 2. Preserve validated baselines

Do not redesign or weaken V2, V3-N0, or V3-N1 behavior.

Preserve:

- Technology -> Electrical Family -> Device manifest architecture;
- released `apm.characterization.v2` behavior;
- `apm.noise-characterization.v1` per-device result domain;
- the 1-ohm CCVS external drain-current probe;
- canonical external drain-terminal and gate-referred PSD semantics;
- precise bounded gm/Id bias resolution;
- parameter-level effective noise provenance;
- raw backend source breakdown;
- `apm.noise-fit.contiguous-regions@1.0.0`;
- `apm.noise-acquisition.bounded-white-search@1.0.0`;
- the V3-N0 analytic harness fixtures;
- the V3-N1 low-VDS/correlation capability regression;
- ngspice 47 normal Sparse solver reference path;
- existing model cards and immutable v2 tag.

V3-N0 and V3-N1 exact-commit qualification flows must remain reproducible and green after N2 changes.

## 3. Manifest-driven all-device expansion

Discover the public catalog from manifests; do not hand-code 26 runtime selectors.

Current expected baseline:

```text
5 technologies
13 electrical families
26 public MOS devices
```

Build an explicit deterministic catalog job plan and bind it to a stable plan hash.

## 4. Required dataset matrix

Implement all required datasets in `NOISE_N2.md`.

### Canonical temperature matrix

All 26 public devices at:

```text
T = -40, 27, 85, 125 degC
L/Lmin = 2
Planar W = default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
gm/Id = 15 1/V target
```

Use the frozen adaptive acquisition independently at each point.

### Inversion sweep

All 26 public devices at 27 degC:

```text
gm/Id = 5, 10, 15, 20, 25 1/V
L/Lmin = 2
VOUT = 0.5 * reference_vdd
```

Reuse identical requests rather than rerun them.

### Length scaling

At 27 degC and gm/Id=15, run every manifest-declared valid characterization length for every public device, with planar W default and FinFET NFIN=1.

### FinFET NFIN scaling

For all APM016F public devices at 27 degC and gm/Id=15, use L/Lmin=2 and all manifest-declared `characterization_nfin` values.

Do not invent planar width sweeps in N2.

## 5. Target reachability

Do not force requested gm/Id values at invalid bias endpoints.

Every logical request must have an explicit result status such as:

- validated;
- target_not_reachable;
- simulation_failed.

A valid spectrum with a null white/flicker/corner fit remains a valid characterization result.

Never silently clip a target or drop a device from a summary because a derived metric is unavailable.

## 6. Stable request identity, deduplication, and resume

Implement the strict request identity and resume semantics defined in `NOISE_N2.md`.

Overlapping requests from temperature, inversion, geometry, and comparison views must reuse one validated physical result when semantic/tool/model/request hashes match.

Prefer a command such as:

```text
apm noise-catalog-check --output <dir>
apm noise-catalog-check --output <dir> --resume
```

The command must plan before execution, persist job identity/coverage, safely reuse only verified matching completed results, and reject stale/mismatched artifacts.

Do not require a complete restart after an interrupted large catalog run.

## 7. Required comparisons

Generate machine-readable comparison outputs referencing exact source result identities/hashes.

### Threshold siblings

At 27 degC for both polarities where present:

- APM045 `vtl/vtg/vth`;
- APM022 `lvt/svt/hvt`;
- APM016F `lvt/svt/hvt`.

Provide distinct:

- equal-inversion gm/Id=15 view;
- equal-bias VCTRL=0.5*VDD, VOUT=0.5*VDD view.

Do not impose a required noise ordering across Vt families.

### Cross-process anchors

Compare separately by polarity:

```text
apm350/general
apm130/lv
apm045/vtg
apm022/svt
apm016f/svt
```

at canonical gm/Id=15, L/Lmin=2, VOUT=0.5*each reference VDD, 27 degC.

Preserve planar-versus-FinFET geometry/basis differences. Do not create fake cross-basis drain-noise ratios.

## 8. Summary quantities

At minimum expose comparison values/status at common frequencies:

```text
1 Hz
1 kHz
1 MHz
10 MHz
```

plus valid fit metrics such as white floor, flicker coefficient/exponent, corner, and `gamma_eff_total`.

Also provide common-band integrated gate-referred noise over:

```text
1 Hz -> 10 MHz
```

with explicit V^2 integral and optional V RMS presentation value.

Raw spectra remain authoritative.

## 9. Interpretation boundaries

Do not claim:

- silicon/foundry noise accuracy for APM-authored families;
- universal multi-Vt noise ordering;
- universal monotonic temperature behavior;
- exact width/NFIN scaling laws;
- universal planar/FinFET effective width;
- process-noise coefficient variation/correlation.

APM022/APM016F multi-Vt comparisons are controlled generic-model experiments, not foundry multi-Vt noise characterization.

## 10. Implementation and validation

Prefer a new orchestration/comparison layer over bloating `characterize.py` or duplicating the low-level N1 noise engine.

Continue through implementation, real-tool execution, restart/resume qualification, debugging, unit/property/integration tests, regression tests, provenance checks, model-immutability checks, and exact-commit evidence.

At minimum rerun:

- V3-N0 regression;
- V3-N1 method regression;
- V3-N2 catalog qualification;
- full pytest suite;
- Ruff;
- REUSE;
- provenance audit;
- repository static validation.

No required `.noise` job may use KLU.

## 11. Evidence and completion

Commit compact exact-implementation-commit evidence, preferred path:

```text
validation/evidence/v3_n2_noise_catalog.json
```

Large raw simulator output remains reproducible/ignored.

Update `STATUS.md` with at least:

- exact implementation commit/evidence hash;
- planned and completed unique request counts;
- fresh versus safely reused job counts;
- target_not_reachable and simulation-failure counts;
- adaptive frequency-stop distribution;
- fit-status coverage;
- temperature/inversion/length/NFIN coverage;
- threshold-family comparison highlights;
- cross-process-anchor comparison highlights;
- regression/test/static/provenance hashes;
- model immutability result;
- evidence-based recommendation for the next milestone.

V3-N2 may recommend v3 release hardening next if catalog-wide behavior is stable. That recommendation does not authorize a package version bump, tag, public release, or process-noise coefficient tuning.

Do not stop at planning or scaffolding. Complete the current goal with real-tool evidence.
