# APM v4.0.0 release validation and reproducibility

APM v4 uses a phase-aware, fail-closed 16-gate contract. It preserves the
released v3 validator and evidence as immutable history while making ordinary
`apm validate` follow the live v4 repository.

## V4 release invariants

The authoritative contract is `validation/release_gates_v4.toml`. Candidate
and exact-tag release runs require WSL2, RHEL-compatible EL9 Linux, x86_64, a
Linux-filesystem checkout, ngspice 47, and project-pinned OpenVAF-Re-Loaded.
Each starts in a different genuine HTTPS clone and is checked out detached.

The pre-bootstrap attestation is standard-library-only and must run before
`.apm`, `.venv`, compiled OSDI, cache, or result state exists. It binds:

- the exact `https://github.com/ds54e/analog-process-models` origin;
- detached `HEAD` and the observed `origin/main` commit;
- the immutable annotated v3 tag object and peeled commit;
- initial clean worktree and absent generated state; and
- the exact WSL2/EL9/x86_64/Linux-filesystem platform observations.

Generated build and result state remains below ignored project-local paths.
The validator rechecks commit, origin/main snapshot, remote tag state,
worktree, and platform before and after the complete run.

## V4 pre-tag candidate qualification

Push the coherent candidate to `origin/main`, then use a new directory while
the `v4.0.0` tag is absent both locally and remotely:

```console
git clone https://github.com/ds54e/analog-process-models.git
cd analog-process-models
git checkout --detach origin/main
python3 tools/attest_clean_clone_v4.py --phase candidate
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm build-models
.venv/bin/apm doctor
.venv/bin/apm validate --output .apm/results/v4-static
.venv/bin/apm validate --release-v4 candidate \
  --output .apm/results/v4-release-candidate
```

The release command independently reruns its static suite; the preceding
normal validation is an explicit current-tree sanity check, not substitute
evidence. The candidate run also performs fresh real-tool reconstruction and
canonical-card regeneration, replays every frozen epoch-3 sealed device and
circuit holdout without modifying candidates, runs all-family characterization,
v3 comparison and native-variation regressions, the versioned mixed-voltage comparison,
Benchmark Global/Local/All, and a fresh 330-request live noise catalog followed
by strict 330/330 resume and four-way tamper/staleness qualification.

Success has status `candidate_pass`, passes 15/15 candidate-required gates,
reports 15 of the 16 total gates passed, and leaves only
`release.exact_tag_requalification` explicitly `pending`. This is not a hidden
skip: exact-tag requalification is impossible until the tag exists. Only that
precise result authorizes creation and push of one annotated `v4.0.0` tag at
the reported candidate commit. Force-push, tag movement, tag replacement, or a
tag at a later evidence commit is forbidden.

## V4 exact-tag requalification

After pushing the annotated tag, start again from an unrelated fresh HTTPS
clone:

```console
git clone https://github.com/ds54e/analog-process-models.git
cd analog-process-models
git checkout --detach v4.0.0
python3 tools/attest_clean_clone_v4.py --phase exact-tag
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm build-models
.venv/bin/apm doctor
.venv/bin/apm validate --output .apm/results/v4-tag-static
.venv/bin/apm validate --release-v4 exact-tag \
  --output .apm/results/v4-release-exact-tag
```

This phase requires an annotated local tag, a matching authoritative remote tag
object and peeled commit, detached `HEAD` at that commit, and the tagged commit
on `origin/main` history. It repeats the entire candidate workload from empty
generated state. Success must report `pass`, 16/16 gates, and
`github_release_creation_authorized = true`. The GitHub Release named
`Analog Process Models v4.0.0` may be created only after that result. Compact
candidate and exact-tag summaries record full generated report hashes on
post-tag `main`; the large raw runs stay untracked.

## Fail-closed evidence semantics

The evaluator loads all required gate IDs in contract order. A gate passes only
with a passing current-run component and nonempty evidence paths that exist.
Missing, skipped, blocked, failed, stale, evidence-free, or hash-mismatched
gates fail the command. A scientifically valid `target_not_reachable` point or
null noise fit remains an honest result where the relevant contract permits it;
silent clipping, fabricated values, or any `simulation_failed` catalog job
fails release qualification.

`validation/release_review_v4.toml` hash-binds the reviewed public and
technical documents. It records explicit negative decisions for foundry or
silicon correlation, reliability/safe voltage, standalone io33, foundry design
rules, calibrated leakage/GIDL or process-noise, layout-dependent accuracy,
real Spectre validation, process-variation interpretation of the epistemic
ensemble, and manufacturable-PDK scope.

## Ordinary current-tree validation

For normal installation and repository checks, bootstrap the project-local
toolchain and run doctor plus normal validation:

```console
git clone https://github.com/ds54e/analog-process-models.git
cd analog-process-models
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm build-models
.venv/bin/apm doctor
.venv/bin/apm validate --output .apm/results/validation
```

Normal validation runs current Pytest, Ruff, REUSE, exact provenance,
catalog/migration, distribution/privacy, hash-bound claim review, isolated v3
regression, and all-family Spectre structural checks. It does not claim to
replace either release-phase fresh-clone run.

## Frozen v3.0.0 release record

APM v3.0.0 is released and immutable.

| Item | Released identity/status |
| --- | --- |
| Qualified candidate | `995e0ce7cdd0c37ef9f3397008637f9d239c746e` |
| Annotated tag | `v3.0.0` |
| Tag object | `afecec29ea6ed0703ef441d4839fd40a238bef0b` |
| Peeled tag commit | `995e0ce7cdd0c37ef9f3397008637f9d239c746e` |
| Candidate qualification | 18/18 PASS |
| Exact-tag post-release qualification | 18/18 PASS |
| GitHub Release | `Analog Process Models v3.0.0` |
| Post-tag evidence | `validation/evidence/v3_post_release_requalification.json` |

The later evidence/status commits on `main` are not release tag targets. The
tagged candidate, tag object, and GitHub Release are not modified by normal
post-release maintenance.

## Frozen v3 maintainer release-engineering workflow

`apm validate --release` implements the frozen 18-gate v3.0.0 release contract
in `validation/release_gates.toml`. It is a maintainer/release-engineering flow,
not a command ordinary users must run. Its complete execution includes:

- exact WSL2/EL9/x86_64 clean-clone identity and source-built tools;
- native BSIM3/BSIM4 and PSP103/BSIM-CMG OSDI execution;
- normal Sparse and no required KLU `.noise` path;
- five technologies, 13 electrical families, and 26 public devices;
- the complete v2 electrical, comparison, benchmark/passive, and APM130
  upstream-variation baseline;
- the analytic noise harness, frozen fit/acquisition method, diagnostics, and
  all eight synthetic fit cases;
- a fresh 290-request catalog run covering 376 logical memberships, followed
  by strict 290/290 reuse and stale/tampered/incomplete rejection;
- model-card immutability, provenance/licensing, distribution hygiene, release
  metadata, and public-claim review.

The candidate-era contract intentionally required the final tag to be absent
during qualification. It is preserved as release evidence, not silently
redefined for post-release maintenance. Normal current-main documentation-only
changes should use `apm validate`; they do not need to manufacture a pre-tag
state or weaken the frozen release gate.

## Historical v3.0.0 candidate qualification flow

Before the release tag existed, the coherent candidate was pushed and checked
out detached from a genuine HTTPS clone:

```console
git clone https://github.com/ds54e/analog-process-models.git
cd analog-process-models
git checkout --detach 995e0ce7cdd0c37ef9f3397008637f9d239c746e
python3 tools/attest_clean_clone.py
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm build-models
.venv/bin/apm doctor
.venv/bin/apm validate --output .apm/results/v3-static
.venv/bin/apm validate --release \
  --output .apm/results/v3-release-candidate
```

The standard-library-only pre-bootstrap attestation required the authoritative
HTTPS origin, exact detached commit, clean worktree, empty project-generated
state, WSL2/EL9/x86_64/Linux-filesystem identity, and absence of the future
`v3.0.0` tag. Bootstrap then created `.apm`, `.venv`, ngspice 47,
OpenVAF-Re-Loaded, PSP103 QS/NQS, and BSIM-CMG 112.1.0 OSDI artifacts from
documented sources.

The candidate qualification is recorded at
`validation/evidence/v3_release_candidate.json`. That evidence identified the
candidate as the future tag target; its later evidence commit was never a tag
target.

## Exact-tag post-release qualification

After the annotated tag was pushed, a second fresh authoritative HTTPS clone
independently established the tag object and peeled commit, checked out the tag
detached, attested empty generated state, rebuilt the complete toolchain, and
reran all 18 gates. The release report SHA-256 was:

`8c506183ad09e655021349430ebf57cb82f7ba815b61c2c73118066096dc94af`

The post-tag evidence whole-file SHA-256 was:

`7001b976642ee1296e3bdea18af86381eddc56d4363f99bf2b32409049b3814b`

### Frozen-validator compatibility detail

The immutable candidate-era clean-clone validator expected no local
`v3.0.0` ref. The post-tag run therefore first proved the authoritative
annotated tag object and peeled commit and checked out that exact commit
detached. It then temporarily removed **only the disposable fresh clone's local
tag ref** while detached `HEAD` stayed at the candidate. The authoritative
remote tag, tag object, candidate commit, and release were never modified.

After the unchanged 18-gate run, the fresh clone fetched the tag again and
reverified the same object and peeled commit. This compatibility detail is
explicit in `validation/evidence/v3_post_release_requalification.json`; it is
not hidden, and it does not weaken or reinterpret the frozen validator.

## Frozen v3 fail-closed evidence semantics

The release evaluator loads the required gate IDs in declaration order. A gate
passes only with `status = pass`, nonempty existing evidence, a passing
current-run component, and direct semantic observations. Missing, skipped,
blocked, failed, stale, evidence-free, or hash-mismatched gates fail the
command.

Tracked milestone summaries do not substitute for current real-tool release
execution. Conversely, scientifically valid `target_not_reachable` results and
null fit metrics remain honest outcomes; silent clipping, fabricated fit
values, or `simulation_failed` catalog jobs fail the release contract.

`validation/release_review.toml` hash-binds reviewed current user-facing and
technical documents. Post-release documentation changes must refresh that
review and keep these boundaries explicit:

- no silicon/foundry calibration claim for APM-authored models;
- no process-noise calibration, noise Monte Carlo, transient noise, RTS/RTN,
  PSS/PNoise, oscillator phase noise, or full terminal-correlation claim;
- no universal planar/FinFET effective-width conversion;
- no reliability, manufacturing, or signoff claim;
- no physical Benchmark Global family-correlation claim;
- no real Spectre parsing/simulation claim.

Current release, public-readiness, and completed publication state are
summarized in `STATUS.md`. The historical pre-publication audit remains in
`validation/evidence/public_readiness_v3.json`; the later controlled
visibility/protection/security transition is recorded separately in
`validation/evidence/publication_v3.json`.
