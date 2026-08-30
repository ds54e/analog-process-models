# APM V3-N3 v3.0.0 Release-Hardening Goal

## 0. Repository state

Work on the existing repository:

- repository: `https://github.com/ds54e/analog-process-models`;
- project: Analog Process Models (APM);
- immutable releases: `v1.0.0` and `v2.0.0`;
- released v2 commit: `3cc6cfea4932cc40f2d693784d0a569926cdf399`;
- completed V3-N0 implementation: `9c9f5b132829bda0e06045981e34e0dd2a41deb4`;
- completed V3-N1 implementation: `0aab87b98697bd8806d13d244595a989cd81a0e3`;
- completed V3-N2 implementation: `ca977af3ba08b9dfdee8556e5781f647f99cabdd`;
- completed V3-N2 evidence/status commit:
  `bbd4932d325270ddd37711e7e2c7e0b00e91670f`.

V3-N0, V3-N1, and V3-N2 are complete and exact-implementation-commit
qualified. Current `main` is authorized to advance to the v3.0.0 release
candidate line.

Do not change repository visibility, create a GitHub Release, or create/move
the final `v3.0.0` tag under this goal.

## 1. Goal

Implement and validate **V3-N3: v3.0.0 Release Hardening**.

Read and follow `RELEASE_V3.md` completely. It is the normative technical and
release contract for this milestone. The existing v2 and V3-N0/N1/N2
specifications remain authoritative for the capabilities they define.

The outcome is a coherent, immutable v3.0.0 release-candidate commit, followed
by a separate compact evidence/status commit proving that exact candidate from
a genuinely fresh HTTPS clone on the documented reference environment.

This goal prepares a release candidate only. Final human review and explicit
authorization remain required before tagging, publishing a GitHub Release, or
changing repository visibility.

## 2. Preserve validated functionality and history

Preserve:

- Technology -> Electrical Family -> Device manifest architecture;
- all 5 technologies, 13 families, and 26 public MOS devices;
- `apm.characterization.v2`;
- `apm.noise-characterization.v1`;
- `apm.noise-comparison.v1`;
- V3-N0 analytic harness and four-engine qualification;
- `apm.noise-fit.contiguous-regions@1.0.0`;
- `apm.noise-acquisition.bounded-white-search@1.0.0`;
- V3-N2 planning, request identity, deduplication, strict resume, and stale
  rejection;
- parameter-level noise provenance and raw backend source breakdown;
- native planar `w,l` and FinFET `l,nfin` geometry semantics;
- ngspice 47 normal Sparse solver for required `.noise` jobs;
- ngspice as the validated reference backend;
- Spectre as model-only experimental/unverified;
- immutable v1.0.0 and v2.0.0 tags/history.

Do not tune or add process-noise coefficients for release aesthetics. The
existing APM350/APM022/APM016F spectra remain compact-model predictions with
their recorded provenance/default boundaries.

## 3. Freeze v3.0.0 scope and claims

The v3 release includes the complete v2 electrical baseline plus stationary
small-signal MOS-noise characterization, analytically qualified harnesses,
fail-closed fitting, bounded acquisition, catalog-wide noise datasets,
threshold/cross-process noise comparisons, and strict resumable execution.

The release must explicitly exclude silicon/foundry noise-accuracy claims for
APM-authored models, new noise calibration, noise Monte Carlo, RTS/RTN,
transient noise, PSS/PNoise, oscillator phase noise, full terminal
noise-correlation matrices, reliability qualification, layout/signoff scope,
real Spectre numerical validation, Virtuoso automation, and any universal
planar/FinFET effective-width conversion.

## 4. Version and current-main contract transition

Update all current runtime/package/release metadata that represents the active
release line from `2.0.0` to `3.0.0`, including the Python package/runtime,
README, changelog, release validator, current status, and current release
documentation.

Do not rewrite historical v1/v2 evidence or historical text that correctly
describes an older release.

Schema names represent independent data contracts. Do not rename
`apm.characterization.v2`, `apm.noise-characterization.v1`, or
`apm.noise-comparison.v1` merely because the package becomes 3.0.0.

## 5. v3 release contract

Replace the active current-main v2 release-gate SSOT with a concise,
machine-readable v3 contract. The immutable v2 tag preserves the old v2 gate
implementation.

`apm validate --release` must implement the exact required v3 gate IDs and
fail closed on every missing, failed, skipped, unimplemented, or evidence-free
required gate.

Required coverage includes:

- reference runtime/toolchain and all four compact-model engine paths;
- normal Sparse/no-KLU required noise execution;
- manifest-driven 5/13/26 catalog and geometry semantics;
- full v2 electrical characterization/comparison/variation behavior;
- V3-N0 analytic resistor, CCVS, white, flicker, and correlated fixtures;
- V3-N1 method identities, synthetic cases, four engines, low-VDS, and
  correlation diagnostic;
- V3-N2 complete catalog plan/status/coverage/comparisons/resume integrity;
- model-card immutability and honest claims;
- provenance, licensing, REUSE, self-contained distribution, and public-repo
  hygiene;
- 3.0.0 metadata, exact clean-clone qualification, and final claim audit.

Keep the gate count manageable and auditable.

## 6. Documentation and hygiene

Harden README, CHANGELOG, release documentation, status, and user-facing
claims for a future public review. Remove obsolete current-main claims such as
"MOS noise is out of scope", "current release is 2.0.0", or "V3-N0/N1/N2 is
incomplete", while preserving explicitly historical statements.

Audit tracked content for credentials, tokens, private paths or personal data,
generated results/caches, editor/temp artifacts, unnecessary binaries, stale
planning material, unsupported claims, and licensing/provenance gaps.

Do not delete useful reproducibility metadata merely because it records normal
public tool versions or platform structure.

## 7. Development qualification

Before the candidate commit, run and require at minimum:

- `apm doctor`;
- V3-N0 regression;
- V3-N1 regression;
- fresh V3-N2 catalog qualification;
- strict V3-N2 resume qualification;
- full Pytest;
- Ruff;
- REUSE;
- provenance validation;
- normal repository validation;
- candidate `apm validate --release`.

Fix real failures. Do not weaken tests or gates to obtain a pass.

## 8. Candidate and exact fresh-clone qualification

Create one coherent v3.0.0 release-candidate implementation commit after the
development tree is internally consistent and green. Record its exact SHA and
do not amend or mutate it afterward. It is the future tag target, but do not
tag it under this goal.

From a genuinely fresh HTTPS clone on WSL2 + RHEL-compatible/AlmaLinux 9.x +
x86_64 on a Linux filesystem:

1. attest the clone before bootstrap, including exact candidate commit, clean
   state, environment/filesystem identity, and absence of project-local
   generated state;
2. bootstrap the documented toolchain and Python environment from source;
3. build PSP103 and BSIM-CMG OSDI models;
4. run doctor and normal validation;
5. run the complete release validator, including fresh V3-N0/N1/N2 evidence;
6. run the full V3-N2 catalog fresh; a prior development result may not
   substitute for the first release qualification;
7. exercise strict resume only after the fresh catalog run;
8. verify the exact candidate worktree remains clean and no v3 tag exists.

Do not copy `.apm`, `.venv`, OSDI binaries, raw results, or caches from the
development checkout.

## 9. Exact evidence and completion

After the exact candidate passes, commit compact evidence at:

`validation/evidence/v3_release_candidate.json`

The evidence must bind the exact candidate commit, clean-clone attestation,
environment/tool/bootstrap identities, ordered release gates, report hashes,
N0/N1/N2 hashes and catalog plan, fresh/reused counts, test/lint/REUSE/
provenance results, model-card immutability, package version, claim/hygiene
audit, clean worktree, and absence of a v3 tag during qualification.

Update `STATUS.md` and commit only compact evidence/status/review material
after the candidate. The evidence commit must not become the future tag target.

V3-N3 is complete only when:

- the v3 release contract is implemented and passes;
- version/docs/claims are coherent at 3.0.0;
- all development regressions pass;
- an immutable coherent candidate commit exists;
- that exact commit passes the genuine fresh-clone source/bootstrap flow;
- compact exact-candidate evidence is committed afterward;
- blockers are none;
- final `v3.0.0` tag is absent;
- GitHub Release is absent;
- repository visibility is unchanged.

At completion, report the candidate SHA, evidence commit SHA, gate count/result,
fresh-clone result, any non-blocking caveats, and the exact recommended next
human release action.

## 10. Explicit prohibitions

Do not:

- make the repository public or change visibility/security settings;
- create or move `v3.0.0`;
- create a GitHub Release;
- force-push or rewrite v1/v2 history/tags;
- add or tune process-noise calibration;
- add noise Monte Carlo, RTS/RTN, transient noise, PSS/PNoise, oscillator phase
  noise, or full terminal noise-correlation matrices;
- make real-Spectre claims without a real Spectre environment;
- invent silicon/foundry accuracy or planar/FinFET normalization claims;
- weaken fail-closed validation.
