# APM development status

This is the compact persistent progress index. It is not validation evidence by itself.

## Overall state

- Project: Analog Process Models (APM)
- Repository: `https://github.com/ds54e/analog-process-models`
- Released baseline: `v2.0.0`
- Released tag commit: `3cc6cfea4932cc40f2d693784d0a569926cdf399`
- v2 post-release exact-tag requalification: complete, 20/20 required gates passed
- Current development line: post-v2 `main`
- Current target: v3.0.0 release candidate hardening
- Completed milestones: `V3-N0 Four-engine noise spike`; `V3-N1 Noise acquisition and fit-method qualification`; `V3-N2 Catalog-wide noise dataset and comparison qualification`
- Current milestone: `V3-N3 v3.0.0 Release Hardening`
- State: `V3_N3_IN_PROGRESS`
- v3 release eligible: NO
- Blockers: none

APM v2.0.0 is immutable. V3-N0, V3-N1, and V3-N2 are complete. V3-N3 is
authorized to prepare and exactly qualify a package/runtime v3.0.0 candidate,
but not to create the final v3 tag, GitHub Release, or visibility change.

Normative current release-hardening contract:

- `GOAL.md`;
- `RELEASE_V3.md`.

V3-N3 began from clean synchronized `main` at
`bbd4932d325270ddd37711e7e2c7e0b00e91670f`; both the V3-N2 implementation
commit `ca977af3ba08b9dfdee8556e5781f647f99cabdd` and evidence/status commit are
present. Candidate commit: not yet created. Final `v3.0.0` tag: not created.
GitHub Release: not created. Repository visibility: unchanged.

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

## Frozen V3-N2 contract

Historical milestone specification:

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

## V3-N2 exact-commit qualification

The coherent implementation commit is:

`ca977af3ba08b9dfdee8556e5781f647f99cabdd`

It was rerun from a fresh empty output directory with a clean worktree on the
documented WSL2 / AlmaLinux 9.7 x86_64 environment using ngspice 47, OpenVAF
Re-Loaded v24.0.2mob, and the normal Sparse `.noise` solver. The fresh run and
strict all-reuse run each pass all 16 N2 checks.

The manifest-derived plan contains 376 logical memberships deduplicated to 290
physical requests:

```text
temperature     104
inversion       130
length           78
NFIN             18
threshold views  36
anchor views     10
```

Exact unique terminal states are 261 `validated`, 29
`target_not_reachable`, and zero `simulation_failed`. The unreachable points
remain explicit bracketed results; none was clipped. Logical dataset coverage
is temperature 97/7, inversion 110/20, length 72/6, and NFIN 18/0
(validated/unreachable). All 36 threshold-view and ten anchor memberships are
validated.

Adaptive selected stops for the 261 valid spectra are 124 at 100 MHz, 96 at
1 GHz, 37 at 10 GHz, and four at 100 GHz. The four cap cases are APM045
VTL/VTG/VTH/THKOX NMOS at gm/Id=5 1/V; each observes a valid white region.
All 261 white fits are valid. Flicker and corner fits are valid for 234, with
27 explicit `invalid_not_observed` nulls.

All 12 threshold-family comparison groups are complete. APM022/APM016F
equal-inversion results are identical across the controlled generic threshold
variants, while their equal-bias results differ. APM045 differs in both views.
No universal noise ordering is imposed, and the generic APM022/APM016F results
are not presented as foundry multi-Vt truth.

Both polarity-separated five-anchor groups are complete. Their exact hashed
comparison artifact provides 1 Hz, 1 kHz, 1 MHz, and 10 MHz values, all valid
fit metrics, and 1 Hz–10 MHz gate-referred integration with explicit geometry.
No planar-per-width versus FinFET-per-fin ratio is produced.

Strict resume qualification passes the exact, request-mismatch, artifact-tamper,
and incomplete-result cases 4/4. The exact unchanged rerun safely reused
290/290 with zero fresh catalog simulations. A separate real stale-result
exercise quarantined a deliberately mismatched result, reused 289, and reran
only the rejected request.

Exact report/hash index:

```text
fresh catalog report    dc95641e451829a2711b23a116292786414b7f5d520e2c0e3b030137db3e59c2
all-reuse report        f99cc9993cf09f2869d51120a152181bd3a2167b9fcbc8390bfcbf845bf7c700
plan file               434012583652ff57ca4c6bf01ab73668a0c2c56c380955dd315f6cd6e4238a3a
plan semantic hash      b4e8d792de5b2da9f7bc8612a79333b501693f83162987560c5df8af1c00cc6d
coverage                ef9ef3f0b780fe4cbab69793fd3d5df09c6f55604c9ffa81922de076aca87bb0
comparisons             521bd982077e800139595be3682540551aa1fca60de9cbc48783baa44bac2c55
scaling observations    240a94688a50297cdc228e062f8a8b0a9cbb018816d3a327fe70db46361a47a9
resume qualification    d1357ce97f6001b5ac7dacea02c1d6365807258f00da7c15a8371626b6ecb3c3
V3-N1 regression        50eae0cd8e6777c74a746b3fd5c8445a6dea5a6294b33f6cbcf456b8345baa8f
nested V3-N0            4c22eadbc97dda592ed1b728aed30a021697ecfb0dcbfabf05c6f1d4f74d4132
provenance              4c8fd79cc0b4835105016f9312398f3a9bd16b869e0a37fba10b65c71a1c7635
static validation       7fbab3f2a10bc7f793a84abbec37890148babc37f1621eb5dfbd387d39e1e1b9
tracked compact evidence a33ad320671e2611aa6b31ac7a833a4f7bf3385880655a2462f5c894796b68bc
```

V3-N0 passes 13/13, V3-N1 passes 10/10, pytest passes 88 tests, Ruff passes,
REUSE passes 240/240 files, provenance passes, repository static validation
passes, and `apm doctor` passes all native/OSDI smokes. APM350/APM022/APM016F
model cards remain byte-identical to `v2.0.0`; no process-noise coefficient was
tuned or added.

Tracked compact evidence:

`validation/evidence/v3_n2_noise_catalog.json`

## V3-N3 release-hardening progress

The active `GOAL.md` and `RELEASE_V3.md` freeze package/runtime candidate
version 3.0.0 and an 18-gate current-main release contract. The candidate tree
now contains the v3 contract/evaluator, strengthened clean-clone attestation,
hash-bound claim review, public-hygiene audit, 3.0.0 package/CLI metadata, and
release documentation. The electrical/noise/comparison result schema
identities remain unchanged.

Development real-tool qualification on the documented environment currently
passes:

- `apm doctor` for native BSIM3/BSIM4 and PSP103/BSIM-CMG OSDI;
- fresh V3-N2 16/16 with 290 fresh executions, nested V3-N1 10/10, nested
  V3-N0 13/13, and zero simulation failures;
- unchanged strict resume 16/16 with 290 safe reuses and zero fresh/stale
  executions;
- all-family electrical characterization, all five comparison suites,
  Benchmark variation/passives, and APM130 native LV/HV variation.

An initial candidate commit `0a411c4e316c74021055e71b3844c766344db1af`
was rejected before bootstrap: the standard-library attestation launcher
imported the project before inventory and thereby created its own
`src/apm/__pycache__`. The gate failed closed as designed. That commit remains
unchanged and is not the future tag target; the launcher now disables bytecode
creation before importing the inventory implementation, and a new exact
candidate must be committed and requalified from another fresh clone.

Remaining work is to finish the final static/hash audit, create and push one
immutable candidate future tag-target commit, qualify that exact commit from a
genuine fresh HTTPS clone, and commit compact exact-candidate evidence/status
afterward.

Process-noise calibration remains unauthorized. Final `v3.0.0` tag, GitHub
Release, and repository visibility changes remain explicitly unperformed.
