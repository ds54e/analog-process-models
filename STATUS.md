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
- Current milestone: `V3-N2 Catalog-wide noise dataset and comparison qualification`
- State: `V3_N2_NOT_STARTED`
- v3 release eligible: NO
- Blockers: none recorded before V3-N2 implementation

APM v2.0.0 is immutable. V3-N0 and V3-N1 are complete. V3-N2 begins catalog-wide application of the already qualified noise measurement/acquisition/fitting method.

## Reference toolchain

Reuse the validated environment unless evidence requires repair:

- WSL2
- AlmaLinux 9.7 x86_64
- Linux ext4 workspace
- Python 3.9.25
- ngspice 47 with predictor/OSDI
- project-local OpenVAF-Re-Loaded v24.0.2mob
- native BSIM3
- native BSIM4
- PSP103 OSDI
- BSIM-CMG 112.1.0 OSDI

Required `.noise` reference jobs use the normal Sparse solver, not KLU.

## Frozen V3-N0 foundation

Normative base specification:

- `NOISE_CHARACTERIZATION.md`

Exact implementation commit:

`9c9f5b132829bda0e06045981e34e0dd2a41deb4`

Compact exact-commit evidence:

`validation/evidence/v3_n0_noise_spike.json`

Key retained conclusions:

- analytic resistor/probe/white/flicker/correlated OSDI fixtures passed;
- native BSIM3, PSP103 OSDI, native BSIM4, and BSIM-CMG OSDI execute real stationary noise;
- canonical external drain-terminal/gate-referred noise semantics are established;
- parameter-level effective noise provenance is available;
- APM-authored model cards were not noise-tuned.

## Frozen V3-N1 method

Normative method specification:

- `NOISE_N1.md`

Exact implementation commit:

`0aab87b98697bd8806d13d244595a989cd81a0e3`

Compact exact-commit evidence:

`validation/evidence/v3_n1_noise_method.json`

Frozen identities:

```text
apm.noise-fit.contiguous-regions@1.0.0
apm.noise-acquisition.bounded-white-search@1.0.0
```

Frozen acquisition starts at:

```text
1 Hz -> 100 MHz
20 points/decade
```

and extends complete sweeps only as needed to:

```text
1 GHz
10 GHz
100 GHz
```

stopping at the first valid white region. Missing fit regions remain explicit null results.

V3-N1 exact qualification passed 10/10, nested V3-N0 13/13, deterministic fit cases 8/8, 79 pytest tests, Ruff, REUSE 236/236, provenance, and static validation.

Representative canonical selected stops from V3-N1:

| Selector | Selected stop |
| --- | ---: |
| `apm350/general/nmos` | 100 MHz |
| `apm130/lv/nmos` | 1 GHz |
| `apm045/vtg/nmos` | 10 GHz |
| `apm016f/svt/nfet` | 100 MHz |

The APM045/VTG 10 GHz attempt found an interior white plateau around 79.43 MHz through 5.623 GHz, demonstrating why fixed terminal review windows are not used.

The 50 mV diagnostic profile remains diagnostic. A runtime-only BSIM-CMG `TNOIMOD=1` diagnostic demonstrated the correlated path without modifying the production APM016F card.

## V3-N2 normative contract

Current goal/specification:

- `GOAL.md`
- `NOISE_N2.md`

V3-N2 applies the frozen N1 method to the full manifest-discovered public MOS catalog.

Current catalog baseline:

```text
5 technologies
13 Electrical Families
26 public MOS devices
```

Runtime orchestration must discover these from manifests rather than use a hard-coded 26-device list.

## V3-N2 required dataset plan

### A. Canonical temperature matrix

Every public device:

```text
T = -40, 27, 85, 125 degC
L/Lmin = 2
Planar W = default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
gm/Id = 15 1/V target
```

Current logical request count before cross-dataset deduplication: 104.

### B. Inversion sweep

Every public device at 27 degC:

```text
gm/Id = 5, 10, 15, 20, 25 1/V
```

with canonical geometry and half-VDD output bias.

Reuse the identical 15 1/V request from the temperature matrix.

### C. Length scaling

Every public device at 27 degC / gm/Id=15 using each manifest-declared valid `characterization_lengths_m`, default planar W, and FinFET NFIN=1.

### D. FinFET NFIN scaling

Every APM016F public NFET/PFET at 27 degC / gm/Id=15 / L/Lmin=2 using every manifest-declared `characterization_nfin`.

Planar width scaling is explicitly deferred because the current manifests do not define a research-backed characterization width grid.

## V3-N2 request orchestration

N2 must create a deterministic job plan and stable request identity before execution.

Overlapping physical requests from temperature/inversion/geometry/comparison views should be simulated once and reused only when the request and semantic/tool/model hashes match.

N2 must support strict resume semantics for a large interrupted catalog run. Preferred interface:

```text
apm noise-catalog-check --output <dir>
apm noise-catalog-check --output <dir> --resume
```

Resume must reject stale/mismatched artifacts rather than silently treating them as current evidence.

## V3-N2 reachability semantics

Requested gm/Id targets are not silently clipped.

Every logical request must have an explicit terminal state, including at least:

- `validated`;
- `target_not_reachable`;
- `simulation_failed`.

A valid spectrum with unavailable white/flicker/corner metrics remains a valid spectrum result and must remain visible in summaries.

## V3-N2 required comparisons

### Threshold-family comparisons

At 27 degC, both polarities where present:

```text
APM045: vtl / vtg / vth
APM022: lvt / svt / hvt
APM016F: lvt / svt / hvt
```

Produce separate:

- equal-inversion gm/Id=15 view;
- equal-bias VCTRL=0.5*VDD, VOUT=0.5*VDD view.

No universal multi-Vt noise ordering is assumed.

### Cross-process anchors

At canonical 27 degC equal inversion, compare N and P separately:

```text
apm350/general
apm130/lv
apm045/vtg
apm022/svt
apm016f/svt
```

Do not create planar-per-width versus FinFET-per-fin drain-noise ratios.

Common comparison frequencies are intended to include 1 Hz, 1 kHz, 1 MHz, and 10 MHz. Common-band integrated gate-referred noise is 1 Hz through 10 MHz.

## V3-N2 explicit exclusions

Do not add in this milestone:

- new/tuned process-noise coefficients;
- noise Monte Carlo/variation;
- process-noise correlation models;
- transient noise;
- RTS/RTN;
- PSS/PNoise;
- oscillator phase noise;
- full terminal noise-correlation matrices;
- invented planar width sweeps;
- fake planar/FinFET effective width conversion;
- real Spectre validation;
- package version bump;
- v3 tag/release;
- repository visibility changes.

## V3-N2 completion evidence required

V3-N2 is not complete until a coherent implementation commit is qualified from fresh output and compact exact-commit evidence is committed, preferred path:

`validation/evidence/v3_n2_noise_catalog.json`

At minimum the exact implementation commit must demonstrate:

1. V3-N0 regression green;
2. V3-N1 method regression green;
3. 5/13/26 manifest coverage;
4. complete explicit-status temperature plan;
5. complete explicit-status gm/Id plan;
6. length and NFIN scaling coverage;
7. threshold-family equal-bias/equal-inversion comparisons;
8. N/P cross-process anchor comparisons;
9. strict resume/reuse qualification including stale-result rejection;
10. Sparse/no-KLU compliance;
11. pytest/Ruff/REUSE/provenance/static validation pass;
12. APM350/APM022/APM016F model-card immutability relative to v2.0.0;
13. final coverage/fit/adaptive-stop/comparison summary in `STATUS.md`;
14. an evidence-based recommendation for the next milestone.

## Current next action

Implement `GOAL.md` completely using `NOISE_N2.md` as the N2 technical contract. Produce real-tool catalog evidence and then decide whether the next milestone should be v3 release hardening or additional characterization work.
