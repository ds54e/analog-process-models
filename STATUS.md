# APM project status

This is the current progress index. Compact evidence, not this file alone,
supports validation and release claims.

## Current state

```text
Released baseline: v3.0.0
Target release: v4.0.0
State: RELEASE-CANDIDATE PORTABILITY FIX

V4 development/integration gates proven before release qualification:
  12/16

Current milestone:
  MIXED-VOLTAGE RUNTIME INTEGRATION COMPLETE / RELEASE VALIDATOR ACTIVE

Public-readiness cleanup:
  COMPLETE

Current-tree sensitive-data audit:
  PASS

Whole-history secret scan:
  PASS

Historical proprietary-model audit:
  PASS

Third-party redistribution/provenance:
  PASS

Current normal repository validation:
  PASS (pre-portability-fix clean snapshot a2f5b4c)

v3.0.0 tag / GitHub Release:
  IMMUTABLE / unchanged

v4.0.0 tag / GitHub Release:
  NOT YET CREATED / NOT YET CREATED

Repository visibility:
  PUBLIC

Publicization:
  COMPLETE

main protection:
  ENABLED

Private Vulnerability Reporting:
  ENABLED

Secret scanning / push protection:
  ENABLED / ENABLED

Current real-tool baseline:
  apm doctor PASS (ngspice 47; 2026-09-04)

V4 release qualification:
  PORTABILITY FIX IMPLEMENTED; NEW CANDIDATE AND EXACT-TAG RUNS PENDING

V4 stop state:
  none
```

The current goal is the APM v4.0.0 mixed-voltage release defined by `GOAL.md`,
`V4_MIXED_VOLTAGE.md`, and `validation/release_gates_v4.toml`. Upstream goal
commit `0e216fe` was fast-forwarded into this development checkout on
2026-09-04. The required local ngspice 47, OpenVAF-Re-Loaded, PSP103, and
BSIM-CMG toolchain passed `apm doctor` before v4 implementation began.

The `evidence.public_matrix` and `modelgen.reconstruction` gates are proven.
Kernel 1.2.0 removes a stray continuation token that ngspice ignored with a
warning in 1.1-rendered cards. Its unfiltered exact-clean-commit run at
`6773e0c6d8382723e9041a8d19034173e5242875` passed all four APM022/SVT and
APM045/VTG N/P reconstruction records. Terminal hashes, metrics, parameters,
and counts remained identical to kernel 1.1 while the corrected rendered card
bytes changed. Compact evidence is
`validation/evidence/v4_modelgen_foundation.json`.

Mixed-voltage generation/qualification epoch 1 failed closed after its first
clean-commit unseal. All charge, Y-matrix, body-effect, and circuit candidate
checks passed, as did every io18 device candidate. The epoch-1 method required
17.5 1/V at every io25 high-temperature curve; all io25 candidate pairs were
therefore rejected when subsets explicitly returned `target_not_reachable`.
No epoch-1 candidate was repaired, no failed holdout is reused, and no passing
subdomain is promoted. Compact failure evidence is
`validation/evidence/v4_qualification_epoch1_failure.json`.

Generation/qualification epoch 2 also failed closed. All five new seed pairs
for both families passed device, charge, Y-matrix, body-effect, circuit, and
structural qualification. Every reachable comparison passed all three
required distinctness claims, with minimum io18/io25 capacitance- and
current-density ratios of 1.335 and 1.299. The extra epoch-2 method nevertheless
required all candidate-pair equal-inversion comparisons to be reachable;
20 1/V coverage was 60--75% by polarity while targets 5/10/15 had 100%
coverage. The report therefore failed, no candidate was promoted or repaired,
and compact evidence is
`validation/evidence/v4_qualification_epoch2_failure.json`.

Generation and qualification epoch 3 passed from clean commit
`65d00b1489ef67f43d38926eba15f1824b2ef81b`. Exact calibration retained all
five independently seeded N/P candidate pairs for each family across 344
ngspice 47 batches. The first one-shot unseal then passed all 20 candidate
device-domain records, all 10 circuit candidate pairs, all 150 structural
comparisons, and all three required io18/io25 distinctness claims across 502
additional batches. Minimum io18/io25 capacitance- and current-density ratios
were 1.322 and 1.306; minimum per-view/polarity/target reachability coverage
was 60%, above the predeclared 50% floor. Observable-space medoid selection
chose io18 seed 54003 and io25 seed 54002 only after circuit results were
available. Compact evidence is
`validation/evidence/v4_generation_epoch3_calibration.json` and
`validation/evidence/v4_mixed_voltage_qualification.json`.

This proves `modelgen.deterministic_regeneration`, `models.io25`,
`models.io18`, `mixed_voltage.distinctness`, and
`mixed_voltage.circuit_holdout`, bringing the qualification milestone total to
7/16.

Exact clean integration commit
`42502c522401b92dde16dcad57d849ffab94f33b` then promoted the four byte-frozen
cards through the manifest catalog. Real-ngspice characterization passed all
15 families; Benchmark Global/Local/All passed all 15 families and 30 devices;
and the versioned mixed-voltage comparison passed all required views with 130
observations, 126 validated observations, four explicit
`target_not_reachable` observations, and zero simulation failures. Its maximum
gm/gds finite-difference errors were 0.004904/0.006889, maximum native-oracle
gm/gds differences were 0.009506/0.002319, and maximum normalized Y-matrix KCL
residual was 5.616e-9.

The same integration source passed exact provenance/REUSE checks and all-family
Spectre structure; Spectre remains model-only **experimental/unverified** with
no real backend execution. These results prove `mixed_voltage.comparison`,
`variation.v4`, `spectre.model_only`, and `licensing.provenance`, bringing the
pre-release integration total to 11/16. Compact evidence is
`validation/evidence/v4_runtime_integration.json`.

The live stationary-noise planner derives 424 logical memberships from all 30
devices and deduplicates them to 330 physical requests (94 memberships
deduplicated). This planning result alone is not the `noise.v4_catalog` gate.
The first candidate attempt later completed a fresh 330-request execution,
strict 330/330 reuse, tamper qualification, and v3 compatibility regression,
but that attempt did not qualify the candidate because an earlier modelgen
replay component failed. Those noise checks must therefore run again inside
the next complete successful candidate.

The separate phase-aware validator implements all 16 declared v4 gates.
Candidate success requires 15/15 pre-tag gates and leaves only the exact-tag
gate pending; a second fresh clone at the annotated tag must pass 16/16 before
the GitHub Release is authorized. The released v3.0.0 tag, tagged commit,
cards, evidence, validator contract, and GitHub Release remain unchanged.

Clean validator-hardening commit
`7e336a6899df22f73610412404f7cbedf1ef1071` passed ordinary v4 repository
validation, including 114 current tests, Ruff, REUSE, all static audits, and an
isolated install/test of the exact v3 tagged source. A direct release-component
exercise then replayed the frozen epoch-3 qualification in 502 ngspice batches:
all 20 candidate-domain records, all 10 circuit pairs, structural/distinctness
checks, both five-seed ensembles, and all four canonical card hashes passed.
Together with the complete hash-bound public review, this proves
`release.claim_audit_v4` at the development/static level and brings the
pre-release milestone total to 12/16. The candidate still must independently
rerun every component from its attested fresh clone.

Fresh candidate attempt `a2f5b4c7a2b7218ebcc4263ba56b89b9501e832e`
correctly failed closed before replaying any device or circuit holdout. Its
fresh calibration report was scientifically byte-equivalent to the original
after excluding only build-local metadata, but the original canonical hash
also covered the source-built ngspice path, binary hash, and creation-time
banner. Those values necessarily changed in a new clone. Reconstruction,
calibration, all 15 characterizations, v3 regressions, mixed-voltage
comparison, Benchmark Global/Local/All, the fresh/resumed noise catalog, and
all four tamper/staleness tests passed; the blocked replay cascaded into the
four model/holdout gates and the aggregate clean-clone gate, leaving 10/15
candidate-required gates passed. No `v4.0.0` tag was created.

The release-replay fix preserves the immutable epoch-3 calibration and
first-unseal hashes. A separate committed portability binding proves that the
original and fresh calibration reports have the same scientific content when
only `created_utc` and the three rebuild-local ngspice identity fields are
excluded. It separately requires the fresh path, executable SHA-256, complete
version banner, and major version to match the executable actually used.
Candidate parameters, holdout definitions, qualification criteria, and
electrical results remain exact and are all rerun. Because the failed attempt
stopped before opening a holdout, this repairs no candidate against a failed
holdout result and creates no new generation epoch.

A second fresh-clone attempt at
`7743da68a6e22d5d77f2b04e0f530e10d8e1674b` exposed a separate public-hygiene
defect before the release command ran: the first portability implementation
stored the original workstation's absolute ngspice path in its tracked replay
contract. Ordinary validation rejected that path, including its explicit
distribution-audit regression test, so the attempt was abandoned and no tag
was created. The revised adapter contains no historical absolute path and does
not synthesize or rewrite a calibration report. It verifies the raw fresh
report, the narrowly defined portable science hash, and the executable's full
current identity, then adapts only the immutable qualifier's legacy hash
callback. The final report records the actual fresh hash separately from the
preserved first-unseal binding; electrical evaluation code remains unchanged.

## Immutable releases

| Release | Tagged commit | State |
| --- | --- | --- |
| v1.0.0 | `e7bba6aaba1487a1116459a6b7b2c3c5add93318` | immutable |
| v2.0.0 | `3cc6cfea4932cc40f2d693784d0a569926cdf399` | immutable; exact-tag 20/20 PASS |
| v3.0.0 | `995e0ce7cdd0c37ef9f3397008637f9d239c746e` | immutable; exact-tag 18/18 PASS |

v3.0.0 release identity:

```text
annotated tag object  afecec29ea6ed0703ef441d4839fd40a238bef0b
peeled commit         995e0ce7cdd0c37ef9f3397008637f9d239c746e
tag message           Analog Process Models v3.0.0
signature             unsigned annotated tag
GitHub Release        Analog Process Models v3.0.0
release URL           https://github.com/ds54e/analog-process-models/releases/tag/v3.0.0
```

The release candidate passed all 18 gates from a genuine fresh HTTPS clone.
The exact annotated tag was then independently requalified from another fresh
HTTPS clone with all 18 gates passing. The GitHub Release was created only
after compact post-tag evidence was pushed to `main`.

Post-tag evidence:

`validation/evidence/v3_post_release_requalification.json`

Whole-file SHA-256:

`7001b976642ee1296e3bdea18af86381eddc56d4363f99bf2b32409049b3814b`

Exact-tag release-report SHA-256:

`8c506183ad09e655021349430ebf57cb82f7ba815b61c2c73118066096dc94af`

The candidate-era validator's local-tag-absence requirement and the disposable
fresh-clone local-ref compatibility procedure are documented transparently in
`docs/release-validation.md` and the post-tag evidence. The authoritative tag,
tag object, detached candidate, and remote history were never modified.

## Released technical baseline

APM v3.0.0 provides:

- five technologies, 13 electrical families, and 26 public MOS devices;
- manifest-driven `Technology -> Electrical Family -> Device` discovery;
- preserved `apm.characterization.v2` DC, finite-difference gm/gds, Y-matrix,
  capacitance, temperature, comparison, and variation behavior;
- `apm.noise-characterization.v1` external drain-terminal and gate-referred
  stationary-noise results with actual complex transfer;
- analytically qualified resistor, 1-ohm CCVS, OSDI white/flicker, and
  correlated-network harnesses;
- `apm.noise-fit.contiguous-regions@1.0.0` and
  `apm.noise-acquisition.bounded-white-search@1.0.0`;
- `apm.noise-comparison.v1` catalog-wide temperature, inversion, length,
  integer-NFIN, threshold-family, and polarity-separated anchor datasets;
- deterministic request identity, deduplication, strict resume, and
  stale/tampered/incomplete rejection;
- parameter-level effective noise provenance and raw backend source names;
- normal Sparse/no-KLU required `.noise` execution.

The release catalog contained 376 logical memberships deduplicated to 290
physical requests: 261 validated, 29 explicitly `target_not_reachable`, and
zero `simulation_failed`. Strict resume reused 290/290, and exact reuse plus
mismatch/tamper/incomplete rejection passed 4/4.

Milestone evidence retained as frozen engineering history:

| Milestone | Implementation | Compact evidence |
| --- | --- | --- |
| V3-N0 foundation | `9c9f5b132829bda0e06045981e34e0dd2a41deb4` | `validation/evidence/v3_n0_noise_spike.json` |
| V3-N1 method | `0aab87b98697bd8806d13d244595a989cd81a0e3` | `validation/evidence/v3_n1_noise_method.json` |
| V3-N2 catalog | `ca977af3ba08b9dfdee8556e5781f647f99cabdd` | `validation/evidence/v3_n2_noise_catalog.json` |
| V3-N3 candidate | `995e0ce7cdd0c37ef9f3397008637f9d239c746e` | `validation/evidence/v3_release_candidate.json` |

## Reference environment

- WSL2;
- AlmaLinux 9.7 / RHEL-compatible EL9 x86_64;
- Linux ext4 workspace;
- Python 3.9.25;
- ngspice 47 with predictor/OSDI;
- OpenVAF-Re-Loaded v24.0.2mob;
- native BSIM3 and BSIM4;
- PSP103 QS/NQS OSDI;
- BSIM-CMG 112.1.0 OSDI.

Spectre remains model-only, structurally checked, and
**experimental/unverified**.

## Public-readiness qualification

The public-readiness cleanup and audit passed. Compact exact-cleanup-commit
evidence is recorded at:

`validation/evidence/public_readiness_v3.json`

Key conclusions:

- Gitleaks 8.30.1 scanned all reachable commits with default history-aware
  rules and 100% redaction; it reported zero findings. Manual history review
  covered every historical path/blob, deleted path, commit identity, suspicious
  filename class, oversized/binary object, and proprietary-model marker.
- No commit contains an official PTM/PTM-MG card, proprietary PDK/private model
  deck, FreePDK45 SVRF/EULA asset, private oracle, or committed
  `external/`/`local/`/`scratch/` content. All historical vendor paths equal the
  current audited vendor inventory; deleted paths are expected APM-authored v1
  manifests/wrappers/model decks and benchmark specifications.
- Current tracked content contains no credential signature, private key,
  private URL/network address, personal contact data, generated OSDI/result/
  environment/cache state, binary blob, or oversized artifact. Two retained
  v1 evidence files contain generic historical checkout paths; these were
  reviewed as non-personal reproducibility metadata, not secrets.
- The pinned IHP model/PSP source Git blob IDs match the authoritative IHP
  commit. Si2 external-redistribution terms are preserved, and
  `THIRD_PARTY.md` now gives the required explicit NXP/Delft/CEA product
  acknowledgement.
- The shipped FreePDK45 README/license/manual/nominal cards match the pinned
  open-source-clean mirror; its complete 1,605-path tree contains no SVRF/EULA
  path. The BSIM-CMG 112.1.0 archive SHA-256 is
  `9c70a7c9fcfafe66fb1582655bbfd36714b90ecba137a9dd83c76b3a0bd9e50a`,
  and every shipped ECL-2.0 license/notice/source byte matches that archive.
- `AGENTS.md` and `GOAL.md` now describe post-release maintenance. Candidate
  and milestone procedures remain behind explicit historical/frozen banners.
  `SECURITY.md` and `CONTRIBUTING.md` are present.
- Pytest, Ruff, REUSE, provenance validation, current-tree public hygiene, and
  normal `apm validate` pass on the coherent cleanup commit. The frozen
  candidate-era release command was not weakened or used as a post-release
  documentation gate.
- GitHub description/topics were updated without changing repository
  visibility or unrelated features.

No history rewrite, force-push, tag/release mutation, or visibility change
occurred during that audit. Its PRIVATE/pre-publication observations remain
historically correct and were not rewritten after publication.

## Controlled publication

After the public-readiness audit passed with no blockers, the repository was
changed once from PRIVATE to PUBLIC through GitHub's authenticated repository
API. The unauthenticated GitHub API and public repository page independently
confirmed the new state. Compact publication evidence is recorded separately
at:

`validation/evidence/publication_v3.json`

The transition preserved repository name/owner, default branch `main`, all Git
history, the annotated `v3.0.0` tag object, its peeled commit, and GitHub
Release ID `379221176`. The two active repository rulesets are:

- `Protect main history` (ID `21850319`): `deletion` and
  `non_fast_forward` rules on `refs/heads/main`, with no bypass actor;
- `Require pull requests for main contributions` (ID `21850335`): a
  zero-approval pull-request rule on `refs/heads/main`, with an explicit owner
  bypass for practical normal maintenance and no invented required checks.

Private Vulnerability Reporting, secret scanning, and secret-scanning push
protection are enabled. The existing description and topics remain present.
Publication changes visibility and collaboration/security state only; it adds
no technical-fidelity, calibration, or release claim.

## Claim boundaries

APM is not a manufacturable PDK. APM-authored model and stationary-noise
predictions are not silicon/foundry calibrated and do not establish
reliability or manufacturing behavior. No process-noise calibration, noise
Monte Carlo, RTS/RTN, transient noise, PSS/PNoise, oscillator phase noise, full
terminal noise-correlation matrix, or universal planar/FinFET effective-width
conversion is claimed. Official PTM/PTM-MG cards are not shipped or used as
numeric source material for APM022/APM016F.

## Next action

Freeze the hash-bound v4 claim review on the coherent candidate, push it to
`origin/main`, and run the complete 15-gate pre-tag qualification from a fresh
detached HTTPS clone. Create no `v4.0.0` tag unless that report explicitly
authorizes it; create no GitHub Release unless a second fresh exact-tag clone
passes all 16 gates.
