# APM V3-N3 — v3.0.0 Release-Hardening Contract

This document is normative for V3-N3 together with `AGENTS.md` and `GOAL.md`.
The existing electrical and noise specifications remain normative for the
capabilities they define. On conflict, `AGENTS.md` and `GOAL.md` win.

## 1. Purpose and release boundary

V3-N3 converts the completed post-v2 stationary-noise development line into a
rigorously validated v3.0.0 release candidate.

This milestone is primarily release-contract, reproducibility, documentation,
provenance, regression, and clean-clone work. Add no characterization feature
unless a release-blocking defect requires a narrow correction.

V3-N3 stops before the final release action:

- package/runtime/release-candidate version: `3.0.0`;
- future tag target: one exact qualified candidate commit;
- `v3.0.0` tag: not created;
- GitHub Release: not created;
- repository visibility: unchanged.

## 2. Preserved capability contract

The candidate must preserve and regress:

1. the manifest-driven Technology -> Electrical Family -> Device hierarchy;
2. five technologies, 13 electrical families, and 26 public MOS devices;
3. native planar `w,l` and FinFET `l,nfin` geometry;
4. `apm.characterization.v2` and its terminal finite-difference/Y-matrix
   semantics;
5. `apm.noise-characterization.v1` and its external drain-terminal,
   gate-referred, source-breakdown, and parameter-provenance semantics;
6. `apm.noise-comparison.v1` with exact source-result identity;
7. V3-N0 resistor, CCVS, OSDI white/flicker, and correlated-network harnesses;
8. `apm.noise-fit.contiguous-regions@1.0.0`;
9. `apm.noise-acquisition.bounded-white-search@1.0.0`;
10. deterministic manifest-driven V3-N2 planning, deduplication, strict resume,
    and stale/incomplete/tampered-result rejection;
11. ngspice 47 with normal Sparse required `.noise` execution and no required
    KLU noise job;
12. native BSIM3/BSIM4 and PSP103/BSIM-CMG OSDI engine paths;
13. immutable v1.0.0/v2.0.0 tags and v2 model-card baseline.

Schema identities do not track package versions. Do not rename working
electrical/noise/comparison schemas during release hardening.

## 3. v3.0.0 included scope

### 3.1 Existing v2 electrical baseline

- manifest-driven 5/13/26 catalog;
- Id-Vg, Id-Vd, finite-difference gm/gds, gm/Id, and gm/gds;
- Vth, DIBL, Ion/Ioff, log10(Ion/Ioff), and SS;
- full complex terminal Y matrix and Y-derived Cgg/Cgd/Cgs;
- required temperature characterization;
- Benchmark Global/Local/All and passive variation;
- selected upstream/native APM130 variation;
- electrical comparison framework;
- exact model provenance/licensing;
- model-only experimental/unverified Spectre compatibility.

### 3.2 New v3 stationary-noise capability

- stationary small-signal MOS-noise characterization;
- analytically qualified external drain-current harness;
- external drain-terminal total PSD;
- gate-referred PSD using actual complex transfer;
- parameter-level effective noise provenance;
- raw backend/model source names without false universal mapping;
- fail-closed flicker/white/corner metrics;
- bounded adaptive frequency acquisition;
- temperature, inversion, length, and integer-NFIN datasets;
- threshold-family equal-bias/equal-inversion comparisons;
- polarity-separated cross-process anchors;
- stable request identity, deduplication, strict resume, and stale rejection.

## 4. Explicit claim exclusions

The candidate documentation, metadata, evidence, and reports must not imply:

- silicon/foundry noise accuracy for APM-authored families;
- process-noise calibration introduced by v3;
- noise-coefficient variation or noise Monte Carlo;
- RTS/RTN or transient noise;
- PSS/PNoise or oscillator phase noise;
- full terminal noise-correlation matrices;
- reliability/breakdown qualification;
- layout/PCells/DRC/LVS/PEX/signoff coverage;
- real Spectre parsing or numerical validation;
- Virtuoso integration/automation;
- a universal effective-width conversion between planar devices and FinFETs;
- a universal ordering law across threshold families, temperature, or geometry.

APM350/APM022/APM016F noise values remain compact-model-default predictions
unless a parameter is explicitly recorded otherwise. Do not tune them for
release appearance.

## 5. Active release metadata

Current-main release metadata must consistently identify `3.0.0`:

- `pyproject.toml` distribution version;
- `src/apm/__init__.py` runtime version and `apm --version`;
- active release-gate target/schema/report;
- README current-release wording;
- CHANGELOG current release section;
- current release-validation documentation;
- status and release-review metadata.

Historical v1/v2 evidence remains unchanged. Historical version numbers and
schema names remain correct and must not be bulk-rewritten.

## 6. Authoritative v3 release gates

`validation/release_gates.toml` is the single active current-main v3 gate SSOT.
The v2 tag preserves the historical v2 contract.

The evaluator must implement exactly all required gate IDs in declaration
order. A required gate passes only if:

1. its status is exactly `pass`;
2. it has nonempty evidence;
3. every referenced evidence artifact exists;
4. its supporting current-run component passed;
5. its semantic checks are directly evidenced.

Missing, failed, skipped, blocked, unimplemented, stale, evidence-free, or
hash-mismatched required gates fail the command.

The preferred manageable gate groups are:

1. `runtime.reference_environment` — WSL2/EL9/x86_64/Linux filesystem,
   Python, exact clean clone, and toolchain identity;
2. `runtime.compact_models` — native BSIM3/BSIM4 and PSP103/BSIM-CMG OSDI;
3. `runtime.noise_sparse` — required `.noise` paths are normal Sparse/no-KLU;
4. `catalog.manifest_driven` — exact 5/13/26 discovery, native geometry, and
   no obsolete v1 runtime SSOT;
5. `characterization.v2` — full all-family electrical contract;
6. `comparison.v2` — all existing comparison views/basis constraints;
7. `variation.v2` — Benchmark Global/Local/All, passives, and APM130 native
   variation;
8. `noise.foundation` — all N0 harness fixtures and four engine paths;
9. `noise.method` — frozen identities, eight synthetic cases, four canonical
   engines, low-VDS diagnostics, and correlated BSIM-CMG capability;
10. `noise.catalog` — deterministic N2 plan, complete explicit statuses,
    temperature/inversion/length/NFIN coverage, comparisons, and raw evidence;
11. `noise.resume_integrity` — deduplication, exact reuse, and deliberate stale,
    incomplete, request-mismatch, and tamper rejection;
12. `models.claims_immutability` — APM350/APM022/APM016F cards unchanged from
    v2 plus provenance/default and claim boundaries;
13. `spectre.model_only` — all structural model artifacts remain explicitly
    experimental/unverified;
14. `licensing.provenance` — exact third-party provenance, notices, REUSE, and
    independent-authorship boundaries;
15. `distribution.public_hygiene` — self-contained sources, ignored generated
    state, credential/private-data/path/large-artifact hygiene;
16. `release.metadata_complete` — package/runtime/changelog/docs target 3.0.0
    with no release-critical placeholder;
17. `release.clean_clone` — exact-candidate fresh HTTPS clone, pre-bootstrap
    attestation, source bootstrap, fresh release run, clean post-state;
18. `release.claim_audit` — public wording matches evidence and exclusions.

One gate may cite several separately hashed component reports, but coherent
properties must not be hidden inside an unevidenced omnibus result.

## 7. Required current-run components

The v3 release evaluator must freshly produce or validate, in the exact
candidate checkout:

- clean-clone attestation;
- repository static/regression validation;
- doctor;
- all-family v2 characterization;
- v2 comparisons;
- benchmark and passive variation;
- APM130 native variation;
- V3-N0 noise regression;
- V3-N1 method regression, including its nested N0 result;
- V3-N2 full catalog qualification from empty output;
- V3-N2 strict unchanged-result resume after that fresh run;
- current model immutability and public-claim audits.

The release evaluator may invoke a component once and map its verified evidence
to several gates. It must not accept tracked milestone evidence as a substitute
for the required current-run real-tool work.

## 8. Documentation and result-contract audit

README must concisely provide:

1. what Analog Process Models is and is not;
2. five-technology/13-family/26-device scope;
3. validated WSL2 + EL9 + x86_64 reference environment;
4. bootstrap/setup commands;
5. basic electrical and noise commands;
6. what the v3 catalog-wide noise dataset means;
7. what it does not establish;
8. explicit model-only experimental/unverified Spectre status.

CHANGELOG must have a clear `3.0.0` section covering the stationary-noise
domain, harness qualification, adaptive method, complete catalog datasets,
comparisons, strict resume, and claim/provenance boundary. It must explicitly
state that v3 adds no silicon-calibrated generic process-noise model.

Audit documentation for obsolete current-main statements while retaining
historical milestone/release context.

Verify outputs bind enough selector/profile/bias/geometry, tool/model/source,
request/result, method/policy, and artifact hashes to reproduce public claims.
Make no unnecessary incompatible schema change.

## 9. Public-repository hygiene

The release static layer must inspect tracked files and relevant metadata for:

- credentials, API tokens, passwords, private keys, and suspicious secret
  signatures or filenames;
- personal data or host/user-specific secrets;
- absolute private workspace paths where not legitimate ignored runtime
  evidence;
- accidentally tracked raw simulation results, `.apm`, virtual environments,
  caches, compiled/generated OSDI binaries, editor artifacts, or temp files;
- unnecessary large/binary artifacts;
- unresolved local/remote model includes and incomplete distributed sources;
- stale internal planning notes or unsupported public claims;
- exact third-party licensing, notices, provenance, and independent-authorship
  gaps.

Normal public tool versions, documented platform structure, generic command
paths, and compact reproducibility hashes are not sensitive by themselves.

## 10. Coherent candidate commit

Before committing the candidate, run at least doctor, N0, N1, fresh N2,
strict resume, full Pytest, Ruff, REUSE, provenance, repository validation, and
candidate release validation in the development checkout.

Once coherent, create one release-candidate commit and record its SHA. Do not
amend it after exact qualification starts. The candidate—not the later compact
evidence commit—is the future `v3.0.0` tag target.

## 11. Genuine fresh-clone qualification

Use a new directory on the designated WSL2/AlmaLinux 9.x x86_64 Linux
filesystem and clone over HTTPS from the authoritative origin. The candidate
must already be reachable from that origin before cloning.

Immediately after clone/checking out the exact candidate and before bootstrap:

- record clone URL and exact commit;
- require an empty tracked/untracked status;
- record kernel/distribution/architecture/filesystem/mount identity;
- prove `.apm`, `.venv`, generated OSDI binaries, caches, and result directories
  are absent;
- record that no `v3.0.0` tag exists.

Then use only repository-documented commands and network/source inputs:

```text
python3 tools/attest_clean_clone.py
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm build-models
.venv/bin/apm doctor
.venv/bin/apm validate --output .apm/results/v3-static
.venv/bin/apm validate --release --output .apm/results/v3-release-candidate
```

The first N2 release catalog must start with an empty output and execute all
unique requests freshly. Test strict resume only after the fresh run. Do not
copy any project-local state from another checkout.

The final release report and each required component must pass, all evidence
paths must exist, the worktree must remain clean, the release target/package/
runtime must be 3.0.0, and no v3 tag may exist.

## 12. Compact post-candidate evidence

After successful exact-candidate qualification, add only compact evidence,
status, and hash-bound review changes on `main`.

Preferred evidence path:

`validation/evidence/v3_release_candidate.json`

It records at least:

- schema/milestone/status/date;
- repository/candidate exact SHA and future-tag-target statement;
- fresh HTTPS clone and pre-bootstrap attestation facts/hash;
- WSL2/EL9/x86_64/Linux-filesystem identity;
- Python/ngspice/OpenVAF/OSDI versions and hashes;
- exact commands and exit statuses;
- release report schema/target/hash and ordered 18/18 gate result;
- all component report hashes;
- N0/N1/N2 report and catalog plan/result hashes;
- N2 fresh/reused/terminal-state counts;
- Pytest/Ruff/REUSE/provenance/static results;
- APM350/APM022/APM016F card immutability;
- package/runtime 3.0.0;
- claim/public-hygiene audit outcome;
- final clean worktree and absence of `v3.0.0` during qualification;
- explicit tag/GitHub Release/visibility boundary.

The later evidence commit is not the future tag target and need not be
requalified as though it were the candidate; all public executable/model/
release-contract content must already be frozen in the candidate.

## 13. Completion and next human action

V3-N3 passes only if the exact candidate fresh clone reports every required
gate passed with valid evidence and compact post-candidate evidence is committed
on `main`.

Final `STATUS.md` must record:

- V3-N0/N1/N2 complete;
- V3-N3 complete;
- package/runtime candidate version 3.0.0;
- exact future tag-target candidate commit;
- exact fresh-clone qualification pass and report hash;
- blockers none;
- `v3.0.0` tag not yet created;
- GitHub Release not yet created;
- visibility unchanged.

The next human action is an explicit review/authorization to create the
immutable `v3.0.0` tag at the already-qualified candidate commit. Post-tag
requalification, GitHub Release creation, and any visibility/publicity change
remain separate decisions.
