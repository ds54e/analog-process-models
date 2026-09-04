# APM project status

This is the current progress index. Compact evidence, not this file alone,
supports validation and release claims.

## Current state

```text
Released baseline: v3.0.0
Target release: v4.0.0
State: ACTIVE DEVELOPMENT

V4 required gates:
  0/16 proven

Current milestone:
  MODELGEN KERNEL IMPLEMENTED / EXACT-COMMIT REQUALIFICATION PENDING

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
  PASS

v3.0.0 tag:
  IMMUTABLE / unchanged

GitHub Release:
  CREATED / unchanged

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

V4 stop state:
  none
```

The current goal is the APM v4.0.0 mixed-voltage release defined by `GOAL.md`,
`V4_MIXED_VOLTAGE.md`, and `validation/release_gates_v4.toml`. Upstream goal
commit `0e216fe` was fast-forwarded into this development checkout on
2026-09-04. The required local ngspice 47, OpenVAF-Re-Loaded, PSP103, and
BSIM-CMG toolchain passed `apm doctor` before v4 implementation began.

No v4 gate is claimed complete yet. The offline model-generation kernel and
machine-readable public-evidence matrix are implemented. An unfiltered
development-tree run passed all four APM022/SVT and APM045/VTG N/P
reconstruction records with real ngspice 47, external-terminal finite
differences, terminal-Y-derived Cgg, deterministic card rendering, hard
candidate rejection, and sealed holdouts. The implementation must now be
committed and rerun from that exact clean commit before compact milestone
evidence claims `modelgen.reconstruction`. The released v3.0.0 tag, tagged
commit, cards, evidence, and GitHub Release remain unchanged.

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

Commit the model-generation/public-evidence foundation, rerun the unfiltered
four-record reconstruction from that exact clean implementation commit, and
record compact hash-bound evidence. Do not promote io18/io25 into the runtime
catalog until this prerequisite has exact-commit real-ngspice reconstruction
evidence.
