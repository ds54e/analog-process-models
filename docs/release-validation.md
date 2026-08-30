# APM v3.0.0 release validation and reproducibility

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

## Current reproducibility

For ordinary installation and repository checks, bootstrap the project-local
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

`apm doctor` executes native BSIM3/BSIM4 and PSP103/BSIM-CMG OSDI smoke tests.
Normal `apm validate` runs the current Pytest, Ruff/import, REUSE, exact
provenance, catalog/migration, distribution/privacy, claim-review, and Spectre
structural checks. Generated output remains under ignored `.apm/` paths.

The validated reference host is WSL2 with RHEL-compatible EL9 Linux on x86_64,
using ngspice 47 and the project-pinned OpenVAF-Re-Loaded. APM does not depend
on GUI state or user-global `~/.spiceinit` configuration.

## Maintainer release-engineering workflow

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

## Fail-closed evidence semantics

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
