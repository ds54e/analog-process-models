# APM development status

This is the compact persistent progress index. It is not validation evidence by itself.

## Overall state

- Project: Analog Process Models (APM)
- Repository: `https://github.com/ds54e/analog-process-models`
- Immutable releases: `v1.0.0`, `v2.0.0`, and annotated `v3.0.0`
- v2 released tag commit: `3cc6cfea4932cc40f2d693784d0a569926cdf399`
- v3 released tag commit: `995e0ce7cdd0c37ef9f3397008637f9d239c746e`
- v2 post-release exact-tag requalification: complete, 20/20 required gates passed
- v3 post-release exact-tag requalification: complete, 18/18 required gates passed
- Current development line: post-v3 release-evidence `main`
- Current target: human review and separate explicit authorization before any repository publicization
- Completed milestones: `V3-N0 Four-engine noise spike`; `V3-N1 Noise acquisition and fit-method qualification`; `V3-N2 Catalog-wide noise dataset and comparison qualification`; `V3-N3 v3.0.0 Release Hardening`
- Current milestone: `V3-N3 v3.0.0 Release Hardening` (complete)
- State: `V3_0_0_RELEASED`
- v3 release state: RELEASED — immutable exact tag independently requalified and GitHub Release created
- Blockers: none

APM v1.0.0, v2.0.0, and v3.0.0 are immutable. V3-N0, V3-N1, V3-N2, and
V3-N3 are complete. A later explicit release authorization created annotated
tag `v3.0.0` at the already-qualified candidate and authorized a GitHub Release
only after exact-tag post-release qualification and compact evidence. It did
not authorize a repository-visibility change.

Normative current release-hardening contract:

- `GOAL.md`;
- `RELEASE_V3.md`.

V3-N3 began from clean synchronized `main` at
`bbd4932d325270ddd37711e7e2c7e0b00e91670f`; both the V3-N2 implementation
commit `ca977af3ba08b9dfdee8556e5781f647f99cabdd` and evidence/status commit are
present. Package/runtime version is 3.0.0. Immutable annotated tag `v3.0.0`
has object `afecec29ea6ed0703ef441d4839fd40a238bef0b` and peels to candidate
`995e0ce7cdd0c37ef9f3397008637f9d239c746e`. Exact-tag post-release
requalification passed 18/18 from a genuine fresh HTTPS clone. GitHub Release:
created. Repository visibility: PRIVATE and unchanged. Publicization: not
performed.

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

## V3-N3 exact-candidate qualification

The active `GOAL.md` and `RELEASE_V3.md` freeze package/runtime version 3.0.0
and the ordered 18-gate current-main release contract. The immutable coherent
candidate and future `v3.0.0` tag target is:

`995e0ce7cdd0c37ef9f3397008637f9d239c746e`

It was pushed before qualification and was checked out detached from a genuine
fresh HTTPS network clone. Pre-bootstrap attestation proved an empty generated
state inventory, a clean worktree, exact authoritative origin and commit,
absence of `v3.0.0`, and the documented WSL2 / AlmaLinux 9.7 / x86_64 / ext4
environment. The attestation SHA-256 is:

`07c934c3419f73171d86080a39723e487fe2e42afa596a00cb6c34304bb6c52f`

The documented source bootstrap then produced ngspice 47 and OpenVAF Re-Loaded
v24.0.2mob, Python 3.9.25 and APM 3.0.0 were installed, all three required OSDI
artifacts were built, and `apm doctor` passed native BSIM3, native BSIM4,
PSP103 OSDI, and BSIM-CMG OSDI. Normal repository validation passed before the
release command.

The exact-candidate release run completed at 2026-08-30T07:28:25Z with every
required gate passing and every gate carrying valid existing evidence:

```text
release report schema       apm.release-validation.v3
release target              v3.0.0
candidate                   995e0ce7cdd0c37ef9f3397008637f9d239c746e
required/passed gates       18/18
release report SHA-256      13f95d50a1237b30fa907e0b9062ff32f8d11b0d4cca5f3caa7d2e79b70eab66
gate contract SHA-256       4cd09e1ba6c90611e0e15c9b4bfb955dd4d99943bc5e8e8cb7802ec696feeef7
normal validation SHA-256   df798a3ff23c6d2253484396b4207ec367421967bf4f9f7e42dbed11c13d8171
release static SHA-256      4b1ddd3874496452e36de53818bcb7edb36649eb6c378f57a41570baa26826b0
doctor SHA-256              52794d0532fd8f18af4a0ec9690410d342daafe71f84c2427cfe3327447f1369
```

The release evaluator freshly ran the complete V2 electrical/comparison/
variation regression surface and the complete V3 noise surface. V3-N0 passed
13/13, V3-N1 passed 10/10 with its eight synthetic cases passing, and V3-N2
passed 16/16. The N2 release plan contained 376 logical memberships and 290
unique physical requests. The empty-output pass executed all 290; 261 were
validated, 29 were explicitly `target_not_reachable`, and none failed. The
unchanged resume pass safely reused all 290 with zero fresh or stale results,
and the exact/mismatch/tamper/incomplete adversarial qualifier passed 4/4.

```text
fresh N2 report             9db3e98c5e34f3bd47d36173814ea78aa3c6f7f0e60f86f151c828c9efa59895
resume N2 report            ca6c2f359d79e0545f9fca761f15c582cce1c9628005f6a7504e6810032a3775
plan file                   e8152efb6c0734ec8d730785d1b987d9d1977d708ffb687e103018f083f8d40d
plan semantic hash          79085abe1c469f42fc607ffdba033c8b388847d41e5ddf4aa946e48abeb58cad
coverage                    dace6846927b7181e183f083878bb129fae896b0e720a18756e1969166b52b89
comparisons                 94101e51808a23c2bb81b679dbdcaea7c2d0d4a7be464bd11ab93ace0d123812
resume qualification        b71babb536dd047cc9c4bd988c03ecccb7a2d0bed834a69946bee543c77ab8f7
V3-N1 regression            75adfb77af6a17066be5a226e4e113909f14ef076c4929bbc6f8fcd732cc9120
V3-N1 synthetic cases       a0eaa991f8de7fe111d9f272f737aea764f92373e370c68bd15bd502e52df2ac
nested V3-N0               287f051273e39fee07c0aedbd37c704432f41ca0b9f0f136be764df583c45145
```

All required noise jobs used normal Sparse and no KLU path. The ngspice binary
was compiled with optional KLU capability, but that capability was not selected
for any required `.noise` job. Pytest passed 92 tests, Ruff passed, REUSE passed
242/242 candidate files, provenance passed, the hash-bound public-claim review
passed, and the tracked-distribution hygiene audit found no credentials,
private paths, oversized artifacts, or unresolved model includes. Spectre
remains model-only, structurally checked, and experimental/unverified.

APM350/APM022/APM016F model cards remain byte-identical to `v2.0.0`; no
process-noise coefficient was tuned or added. The final exact-candidate
worktree remained clean and `v3.0.0` remained absent. The compact tracked
evidence is:

`validation/evidence/v3_release_candidate.json`

Its whole-file SHA-256 is:

`7099ea90d5cd51707f793ad19cf332dec9ec1f88776d34f6380fe2c60f07a589`

An initial candidate commit `0a411c4e316c74021055e71b3844c766344db1af`
was rejected before bootstrap because the attestation launcher created its own
`src/apm/__pycache__` before inventory. The gate failed closed. That rejected
commit remains unchanged and is not the future tag target.

V3-N3 candidate hardening is complete. Its candidate-stage prohibition on a
final tag was later superseded by explicit release authorization. The candidate
itself remains unchanged and is the exact `v3.0.0` tag target. The post-tag
release state is recorded below.

## v3.0.0 exact-tag post-release requalification

Final release state:

```text
Release: v3.0.0
Tag: CREATED / IMMUTABLE / ANNOTATED / UNSIGNED
Tag object: afecec29ea6ed0703ef441d4839fd40a238bef0b
Tag target: 995e0ce7cdd0c37ef9f3397008637f9d239c746e
Exact-tag post-release requalification: PASS
Release gates: 18/18 PASS
Repository visibility: PRIVATE
GitHub Release: CREATED
Publicization: NOT PERFORMED
Blockers: none
```

The tag was pushed without moving `main` or changing the immutable v1/v2 tags.
A new authoritative HTTPS clone fetched and detached-checkout the exact
annotated tag before bootstrap. The tag object, message, peeled commit, clean
worktree, empty generated state, package/runtime 3.0.0, WSL2 / AlmaLinux 9.7 /
x86_64 / ext4 environment, and private repository visibility were verified.

The immutable candidate-era validator requires the local `v3.0.0` ref to be
absent. After the exact annotated tag was proved and checked out detached, only
that fresh clone's disposable local tag ref was temporarily removed; HEAD
remained at the candidate and the authoritative remote tag was untouched. The
unchanged candidate attestation then passed 9/9 before bootstrap. After the
unchanged 18-gate release run, the authoritative tag ref was fetched back and
the same object/peeled identities were independently reverified. This
compatibility detail is explicit in the compact evidence and does not weaken or
modify the frozen validator, candidate, or remote tag.

The documented source bootstrap produced ngspice 47 and OpenVAF-Re-Loaded
v24.0.2mob, installed Python 3.9.25 and APM 3.0.0, rebuilt PSP103 QS/NQS and
BSIM-CMG 112.1.0 OSDI, and passed all four doctor smokes. Normal validation and
the complete release validator passed:

```text
pre-bootstrap attestation  1c28cf73701d2f052b71193682c69ab9fa5ed3f9d357d8a911875cf5784decdf
normal validation          0e6b968f8d2c82be01d1de9ba94a545ac6239d9dcd2ff39406e999c2dd2bda60
doctor (release component) 9de90f8034c10bf629948bc5bf2da2d153f97b88c0831682c26dca681ff1d7b9
release static audit       39d971b9e228975cf718a5faf8f96236f86f1eb4a7cd2a11ada7b8684f64edd0
release report             8c506183ad09e655021349430ebf57cb82f7ba815b61c2c73118066096dc94af
gate contract              4cd09e1ba6c90611e0e15c9b4bfb955dd4d99943bc5e8e8cb7802ec696feeef7
```

The current run freshly established the full v2 electrical/comparison/
variation surface and all v3 noise milestones. V3-N0 passed 13/13, V3-N1
passed 10/10 and all eight synthetic fit cases, and V3-N2 passed 16/16. The
manifest plan again contained 376 logical memberships and 290 unique physical
requests. All 290 ran freshly: 261 validated, 29 explicitly
`target_not_reachable`, and zero `simulation_failed`. Strict resume then safely
reused 290/290 with zero fresh work; exact reuse and mismatch/tamper/incomplete
rejection passed 4/4.

```text
fresh N2 report             92c8dda51cd2b853527831920ca142b956405bd8162285b09d60404c6d8483d6
resume N2 report            10aa5ed709b78b66bf98bf4c7a1965838c3abe4c1ae2074b6e5e9ff2d638cb59
plan file                   375bd60a1058b8a7ddb9d75c4a2388d1f861bbbdfc8b67b2054791d568ec18de
plan semantic hash          04b84359e8dbf741ba91b83841d22ff63de95398e1c70f1241aa6def097e2505
coverage                    25dacecf2efbffa216aa04ef414b7b9e55e4cbc94524f2718d1b8c5e850e3cc3
comparisons                 c825b202e83271041f7377cbe3af0742279b3db691be620611261e8a9af6ed69
resume qualification        e9367609048216090d2062229785303967889337687775d9393c3391e41ade5b
V3-N1 regression            cbdfc7d52a1afe2c820149c07ef4cc6e7adc92a1444e48d62d0ef603510cba7f
V3-N1 synthetic cases       a0eaa991f8de7fe111d9f272f737aea764f92373e370c68bd15bd502e52df2ac
nested V3-N0                5ef29438007eb904fc49bb6c1798702fe80c00d81217ea7362097e00fcc9252d
```

Pytest passed 92 tests, Ruff passed, REUSE passed 242/242 files, provenance,
claim review, and distribution/public-hygiene audits passed. All required
noise used normal Sparse and no KLU path. APM350/APM022/APM016F model cards
remain byte-identical to `v2.0.0`; no process-noise coefficient was tuned.
Spectre remains model-only, structurally checked, and experimental/unverified.

Compact post-tag evidence:

`validation/evidence/v3_post_release_requalification.json`

Whole-file SHA-256:

`7001b976642ee1296e3bdea18af86381eddc56d4363f99bf2b32409049b3814b`

The GitHub Release did not exist during validation and was not used as evidence.
After the compact evidence/status commit was pushed, GitHub Release
`Analog Process Models v3.0.0` was created at the existing tag and published at
2026-08-30T08:22:17Z:

`https://github.com/ds54e/analog-process-models/releases/tag/v3.0.0`

The Release is neither draft nor prerelease and has no attached generated
simulator artifacts. The tag still has object
`afecec29ea6ed0703ef441d4839fd40a238bef0b` and peels to
`995e0ce7cdd0c37ef9f3397008637f9d239c746e`. Repository visibility remained
PRIVATE throughout. Making the repository public is the only next action and
requires separate explicit human authorization.
