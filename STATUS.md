# APM development status

This is the compact persistent progress index. It is not validation evidence by itself.

## Overall state

- Project: Analog Process Models (APM)
- Repository: `https://github.com/ds54e/analog-process-models`
- Released baseline: `v2.0.0`
- Released tag commit: `3cc6cfea4932cc40f2d693784d0a569926cdf399`
- v2 post-release exact-tag requalification: complete, 20/20 required gates passed
- Current development line: post-v2 `main`
- Current target: v3 stationary small-signal MOS-noise characterization
- Completed milestones: `V3-N0 Four-engine noise spike`; `V3-N1 Noise acquisition and fit-method qualification`
- Current milestone: `V3-N1 complete`; V3-N2 has not started
- State: `V3_N1_COMPLETE`
- v3 release eligible: NO
- Blockers: none

APM v2.0.0 is immutable. V3-N0 is complete and does not modify the released v2 model-card baseline.

## Reference toolchain

Reuse the validated environment unless evidence requires repair:

- WSL2
- AlmaLinux 9.7 x86_64
- Linux ext4 workspace
- Python 3.9.25
- ngspice 47 with predictor/OSDI
- project-local OpenVAF-ReLoaded v24.0.2mob
- native BSIM3
- native BSIM4
- PSP103 OSDI
- BSIM-CMG 112.1.0 OSDI

Required `.noise` reference jobs use the normal Sparse solver, not KLU.

## V3-N0 retained baseline

Normative base specification:

- `NOISE_CHARACTERIZATION.md`

Exact implementation commit:

`9c9f5b132829bda0e06045981e34e0dd2a41deb4`

Compact exact-commit evidence:

`validation/evidence/v3_n0_noise_spike.json`

V3-N0 status:

- acceptance: 13/13 pass;
- repository regression: 68 tests passed;
- Ruff / REUSE / provenance / static validation passed;
- resistor `4*k*T/R` reference passed;
- 1-ohm CCVS current probe demonstrated transparent/noiseless behavior;
- OpenVAF -> OSDI white/flicker fixtures passed;
- internal correlated-noise fixture matched the correlated result and decisively rejected the independent interpretation;
- native BSIM3, PSP103 OSDI, native BSIM4, and BSIM-CMG OSDI all completed the canonical four-engine spike;
- parameter-level effective-noise provenance was captured;
- APM350/APM022/APM016F model cards remained unchanged from `v2.0.0`.

Canonical V3-N0 point:

```text
T = 27 degC
L/Lmin = 2
Planar W = family/device default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
gm/Id target = 15 1/V
1 Hz -> 100 MHz
20 points/decade
```

Representative V3-N0 observations:

| Engine / selector | gm/Id | Provisional fit result |
| --- | ---: | --- |
| BSIM3 `apm350/general/nmos` | 14.99089 | white valid; flicker/corner not observed |
| PSP103 `apm130/lv/nmos` | 14.99458 | white/flicker/corner valid; corner about 2.77 MHz |
| BSIM4 `apm045/vtg/nmos` | 15.00039 | flicker valid; white/corner not observed by 100 MHz |
| BSIM-CMG `apm016f/svt/nfet` | 14.99705 | white/flicker/corner valid; corner about 569 kHz |

The BSIM4 result is the primary reason V3-N1 must qualify the acquisition/fitting method before all-device expansion.

## V3-N1 normative contract

Current goal:

- `GOAL.md`
- `NOISE_N1.md`

V3-N1 preserves the V3-N0 measurement semantics and resolves the remaining method questions.

### Acquisition policy to implement/qualify

Every canonical job begins at:

```text
1 Hz -> 100 MHz
20 points/decade
```

If a valid white region is not observed, rerun the complete spectrum using bounded upper-frequency extension:

```text
1 GHz
10 GHz
100 GHz
```

Stop at the first valid white region. If no valid white region appears by 100 GHz, preserve an explicit null result; do not force a fit.

The intended long-term model is adaptive acquisition rather than forcing every technology to one unnecessarily large common frequency endpoint.

### Fit method to implement/qualify

Preferred identity:

`apm.noise-fit.contiguous-regions@1.0.0`

Required properties:

- local log-slope classification;
- contiguous flicker/white regions;
- minimum logarithmic spans and point counts;
- whole-region fit/flatness quality gates;
- deterministic candidate selection;
- support for an interior white plateau before later high-frequency shaping;
- fail-closed null metrics when no valid region exists;
- no silent movement of windows to manufacture a result.

The V3-N0 fixed-window method remains historical/provisional evidence only.

### Low-VDS diagnostics

Run all four representative engines at:

```text
VOUT = 50 mV effective
gm/Id = 15 1/V within 1%
T = 27 degC
L/Lmin = 2
```

Also run one diagnostic-only BSIM-CMG low-VDS case with runtime `TNOIMOD=1`, without editing the production APM016F card.

## V3-N1 completion criteria (satisfied)

The exact implementation commit was required to demonstrate, and did demonstrate:

1. V3-N0 regression remains green;
2. deterministic synthetic tests qualify the new region detector;
3. four canonical engines use bounded adaptive acquisition;
4. APM045/VTG receives the required >100 MHz diagnostic when necessary;
5. four low-VDS diagnostics complete with explicit raw/status evidence;
6. diagnostic BSIM-CMG `TNOIMOD=1` low-VDS capability is exercised without card modification;
7. effective parameter provenance remains complete;
8. Sparse/no-KLU requirements remain satisfied;
9. pytest, Ruff, REUSE, provenance, and static validation pass;
10. compact exact-commit evidence is committed, preferred path `validation/evidence/v3_n1_noise_method.json`;
11. the resulting method/acquisition policy is frozen in repository documentation;
12. an evidence-based V3-N2 all-26-device readiness decision is recorded.

## Current exclusions

V3-N1 does not include:

- all 26-device noise expansion;
- process-noise coefficient tuning/calibration;
- noise variation/Monte Carlo;
- transient noise;
- RTS/RTN;
- PSS/PNoise;
- oscillator phase noise;
- full terminal noise-correlation matrices;
- real Spectre validation;
- package version bump or v3 tag.

## V3-N1 completion freeze

Exact implementation commit:

`0aab87b98697bd8806d13d244595a989cd81a0e3`

Compact exact-commit evidence:

`validation/evidence/v3_n1_noise_method.json`

Evidence SHA-256:

`687841b8f912812e511be7af741cf90ed283325808b4926b816969c78967a5f7`

Frozen implementation:

- fit identity `apm.noise-fit.contiguous-regions@1.0.0`;
- centered approximately 0.5-decade local log-slope estimator (11 points at
  20 points/decade);
- exact flicker and white thresholds from `NOISE_N1.md`, deterministic
  contiguous-run selection, candidate diagnostics, median white floor,
  boundary-checked corner, and fail-closed null metrics;
- frozen acquisition policy
  `apm.noise-acquisition.bounded-white-search@1.0.0` with complete sweeps at
  100 MHz, 1 GHz, 10 GHz, and 100 GHz, stopping at the first valid white
  region;
- per-attempt raw spectrum, source breakdown, parameter snapshot, fit
  diagnostics, hashes, and Sparse/no-KLU audit;
- `apm noise-method-check` combining the retained V3-N0 regression, eight
  deterministic synthetic cases, four canonical adaptive runs, four 50 mV
  VOUT adaptive runs, and the low-VDS BSIM-CMG `TNOIMOD=1` diagnostic.

The fresh-output exact-implementation-commit run passed all 10 N1 checks, the
nested V3-N0 regression passed 13/13, and the deterministic synthetic fit
qualification passed 8/8. Exact results:

| Selector | Canonical selected stop | 50 mV selected stop | Canonical white result | 50 mV white result |
| --- | ---: | ---: | --- | --- |
| `apm350/general/nmos` | 100 MHz | 100 MHz | valid | valid |
| `apm130/lv/nmos` | 1 GHz | 1 GHz | valid | valid |
| `apm045/vtg/nmos` | 10 GHz | 1 GHz | valid | valid |
| `apm016f/svt/nfet` | 100 MHz | 100 MHz | valid | valid |

APM045 canonical acquisition did not expose an eligible plateau in the
100 MHz or 1 GHz attempts. The 10 GHz attempt selected the first eligible
interior plateau, approximately 79.43 MHz through 5.623 GHz, and stopped
without a 100 GHz run. The white floor was about
`5.392e-24 A^2/Hz` and the fitted corner about 9.28 MHz.

All four low-VDS biases resolved within 0.071% of gm/Id=15 1/V.
The runtime-only low-VDS BSIM-CMG diagnostic changed effective `TNOIMOD` from
the production value 0 to 1, exposed a nonzero `corl` source, used Sparse, and
left the production APM016F card hash unchanged.

Exact generated-report hashes:

- V3-N1 full report:
  `b986f93b9844628627ccbd4e8446f58fb4552e2e7a4662904e747f497f6442dd`;
- nested V3-N0 report:
  `8f6e723069ce94d32deb112cfa232109d4c8f6b0766c07b2973ea80274d6fa46`;
- retained V3-N0 harness report:
  `78ee676ffda3eb17520c23505350c9b0737b122886c2159ff0b519a039c8ff70`;
- synthetic fit report:
  `a0eaa991f8de7fe111d9f272f737aea764f92373e370c68bd15bd502e52df2ac`;
- exact static validation:
  `591037e3c3db60c95c52d68a6ccff685aa1d09f1d1e7fa50627e978a8dfd0811`;
- exact provenance validation:
  `cebed1aecf4b55b4a3e946f9d674283758ae939047ec001cd877dc72ef473c63`;
- exact doctor report:
  `de97c84171d304b1362c5f21bd1dfd9498d74b9f8efd60fe0eb37c47f76d0f4f`.

Exact-commit repository validation also passed 79 tests, Ruff, REUSE 236/236,
provenance, claim/distribution/catalog/migration audits, and static Spectre
structure. Every required acquisition attempt attested normal Sparse, no
attempt selected KLU, and no critical simulator diagnostic was retained.

Parameter interrogation remains frozen per engine: targeted final `showmod`
values for native BSIM3/BSIM4 (with only the documented ngspice-47 BSIM4
`LINTNOI=0` query fallback), and OSDI `showmod` values bound to explicit card
occurrences or pinned Verilog-A defaults for PSP103/BSIM-CMG. Raw backend
source names remain model-specific and are not mapped into a fake universal
taxonomy.

The N1 method is ready for V3-N2 expansion to all 26 public MOS devices. That
recommendation covers characterization of existing compact-model predictions;
it does not authorize process-noise coefficient tuning or a silicon accuracy
claim. Retain the 50 mV VOUT case as a diagnostic profile, not a replacement
for the canonical half-VDD point.

## Current next action

Await the next repository goal for V3-N2 all-device expansion. Do not change
package version, create a v3 tag, or begin process-noise calibration from the
V3-N1 capability result alone.
