# APM V3-N1 Noise Method Qualification Goal

## 0. Repository state

Work on the existing repository:

- repository: `https://github.com/ds54e/analog-process-models`
- project: Analog Process Models (APM)
- released baseline: `v2.0.0` at `3cc6cfea4932cc40f2d693784d0a569926cdf399`
- completed V3-N0 implementation commit: `9c9f5b132829bda0e06045981e34e0dd2a41deb4`
- V3-N0 exact-commit evidence: `validation/evidence/v3_n0_noise_spike.json`

APM v2.0.0 is complete, released, and immutable. V3-N0 is complete. Current `main` is the post-v2 development line.

Do not change repository visibility. Do not move/rewrite the v2 tag. Do not create/tag v3.0.0 as part of this goal.

## 1. Goal

Implement and validate **V3-N1: Noise Acquisition and Fit-Method Qualification**.

Read and follow `NOISE_N1.md` completely. It is the normative technical contract for this milestone, with `NOISE_CHARACTERIZATION.md` providing the V3-N0/base noise semantics.

The purpose of V3-N1 is to freeze the acquisition and fitting methodology before expanding noise characterization to all 26 public MOS devices.

Specifically:

1. replace the provisional fixed-frequency fit windows with a versioned contiguous-region detector;
2. implement bounded adaptive upper-frequency extension when a white plateau is not observed;
3. diagnose FreePDK45 VTG above 100 MHz rather than forcing a white fit;
4. add low-VDS diagnostics on all four representative engines;
5. qualify a BSIM-CMG `TNOIMOD=1` low-VDS diagnostic without modifying the production APM016F card;
6. produce exact-implementation-commit evidence and a decision on readiness for V3-N2 all-device expansion.

## 2. Preserve validated baselines

Do not redesign or weaken working V2/V3-N0 functionality.

Preserve:

- Technology -> Electrical Family -> Device manifest architecture;
- released `apm.characterization.v2` behavior;
- independent `apm.noise-characterization.v1` domain;
- canonical 1-ohm CCVS drain-current probe;
- canonical external drain-terminal and gate-referred PSD semantics;
- precise gm/Id bias refinement;
- parameter-level noise provenance;
- raw source breakdown;
- the V3-N0 analytic harness fixtures;
- ngspice 47 + normal Sparse solver reference path;
- existing model cards and v2 tag.

The V3-N0 exact-commit qualification must remain reproducible and passing after V3-N1 changes.

## 3. Required four-engine set

Continue using:

- native BSIM3: `apm350/general/nmos`
- PSP103 OSDI: `apm130/lv/nmos`
- native BSIM4: `apm045/vtg/nmos`
- BSIM-CMG OSDI: `apm016f/svt/nfet`

Do not expand to all 26 devices in this milestone.

## 4. Canonical acquisition

Canonical operating point remains:

```text
T = 27 degC
L/Lmin = 2
Planar W = family/device default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
gm/Id = 15 1/V within 1%
```

Base spectrum remains:

```text
1 Hz -> 100 MHz
20 points/decade
```

If no valid white region is detected, extend the complete sweep in bounded decade steps through:

```text
1 GHz
10 GHz
100 GHz
```

Stop at the first valid white region. If none is observed by 100 GHz, record the explicit null result and do not force a fit.

## 5. Fit-method implementation

Implement the method specified in `NOISE_N1.md`, preferred identity:

```text
apm.noise-fit.contiguous-regions@1.0.0
```

The detector must use local log-slope plus contiguous span/point-count/quality checks. It must be capable of finding an interior white plateau before later high-frequency spectral shaping.

Do not reinterpret the historical V3-N0 fixed-window fit results. Persist new method identity/version and candidate-region diagnostics.

Add deterministic synthetic tests including pure white, pure flicker, known flicker+white corner, interior plateau with high-frequency rise, truncated no-white, no-flicker, insufficient-span, and malformed input cases.

## 6. Low-VDS diagnostics

Run the same four engines at:

```text
VOUT = 50 mV effective
gm/Id = 15 1/V within 1%
T = 27 degC
L/Lmin = 2
```

Preserve raw PSD, gate-referred PSD, complex transfer, source breakdown, provenance, fit status, bias diagnostics, and simulator-log audit.

Also run the diagnostic-only BSIM-CMG `TNOIMOD=1` low-VDS case required by `NOISE_N1.md`. Do not modify the production card.

## 7. Model/provenance boundaries

Do not tune or add APM-authored process-noise coefficients.

Do not alter FreePDK45 or IHP upstream model values.

Continue the V3-N0 effective-parameter provenance strategy unless real evidence requires a narrow documented correction.

A successful simulator spectrum remains a compact-model prediction, not a silicon/process-noise calibration claim.

## 8. Implementation and validation

Prefer extending the existing noise modules rather than adding noise logic to `characterize.py`.

A dedicated real-tool command such as:

```text
apm noise-method-check --output <dir>
```

is preferred.

Continue through implementation, real-tool simulation, debugging, unit/property tests, regression tests, provenance checks, and exact-commit qualification. Do not stop at planning/scaffolding.

At minimum rerun:

- V3-N0 noise/harness validation;
- V3-N1 real-tool method qualification;
- full pytest suite;
- Ruff;
- REUSE;
- provenance audit;
- repository static validation.

## 9. Evidence and completion

Commit compact exact-implementation-commit evidence, preferred path:

```text
validation/evidence/v3_n1_noise_method.json
```

Large raw simulator output should remain reproducible/ignored.

Update `STATUS.md` with:

- final acquisition policy;
- final fit-method identity/thresholds;
- APM045 upper-frequency diagnostic result;
- four low-VDS results;
- BSIM-CMG correlated low-VDS capability result;
- exact-commit validation hashes/status;
- evidence-based recommendation on V3-N2 all-26-device expansion.

V3-N1 may be complete even if a model does not expose a valid white plateau by the bounded search cap, provided the null result is explicit and the acquisition/fitting method behaved fail-closed.

Do not bump package version or create a v3 tag.
