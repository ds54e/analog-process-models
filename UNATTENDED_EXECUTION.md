# Unattended Execution Protocol for APM V3-N3

This document defines the long-running execution procedure for the current
v3.0.0 release-hardening goal. It is subordinate to `AGENTS.md`, `GOAL.md`, and
`RELEASE_V3.md`.

## 1. Authority

Use this order on conflict:

1. safety/security requirements and explicit user instructions;
2. `AGENTS.md`;
3. `GOAL.md`;
4. `RELEASE_V3.md`;
5. the preserved N0/N1/N2 and device/result contracts;
6. this file;
7. informative project/environment/research context.

Do not silently weaken a requirement. Record material departures and evidence
in `STATUS.md`.

## 2. Continuation and toolchain reuse

V3-N3 begins after exact-commit qualification of V3-N0, V3-N1, and V3-N2 in
the same WSL2/AlmaLinux workspace. Development may reuse valid project-local:

- ngspice 47;
- OpenVAF-Re-Loaded;
- LLVM/Rust/source caches;
- compiled PSP103 and BSIM-CMG OSDI artifacts;
- Python virtual environment;
- ignored simulator results for diagnostic comparison only.

Before rebuilding, inspect `.apm`, `.venv`, tool versions, `apm doctor`, Git
state, origin, HEAD, and tags. Repair or rebuild only when evidence shows that
the local development state is missing, stale, or incompatible.

Development reuse never satisfies final clean-clone qualification.

## 3. Startup sequence

1. Confirm the authoritative GitHub origin.
2. Inspect status and preserve unrelated/user work.
3. Pull only by fast-forward.
4. Read every file required by `AGENTS.md` completely.
5. Confirm V3-N0/N1/N2 exact evidence and immutable v1/v2 tags.
6. Advance `GOAL.md`/`STATUS.md` and add the dedicated release contract before
   substantive implementation.
7. Inventory release/version/claim/validator code and current documentation.
8. Continue into implementation; do not stop at a release plan.

## 4. Release-hardening loop

For each coherent change:

1. map it to a named V3-N3 requirement and evidence source;
2. preserve working electrical/noise schemas unless a release-blocking defect
   requires a narrowly compatible correction;
3. update tests together with fail-closed behavior;
4. run the smallest relevant static/unit check immediately;
5. run real ngspice/OpenVAF/OSDI validation when the changed behavior reaches
   simulator orchestration or evidence semantics;
6. investigate failures rather than weakening properties;
7. keep `STATUS.md` current at milestone boundaries;
8. keep large generated results under ignored `.apm` paths.

## 5. Release contract migration

Current `validation/release_gates.toml` is the active v3 release SSOT. The
historical v2 implementation remains available at immutable tag `v2.0.0`; do
not maintain a second active current-main v2 gate list.

The v3 evaluator must:

- implement exactly every required contract gate;
- fail missing/skipped/unimplemented/evidence-free gates;
- run current electrical and noise components rather than trusting tracked
  milestone summaries;
- verify current 3.0.0 metadata and hash-bound public claims;
- require exact candidate clean-clone attestation;
- retain diagnostic output after failures where safe.

One fresh V3-N2 catalog run may supply nested current V3-N1/V3-N0 evidence.
The subsequent strict resume run may reuse that freshly produced catalog; the
first release catalog run may not reuse development output.

## 6. Public-repository and provenance discipline

Before the candidate, audit:

- exact third-party file hashes, terms, and notices;
- complete self-contained model/include closure;
- independent APM022/APM016F authorship boundaries;
- REUSE/SPDX;
- credentials, tokens, private keys, personal/private paths, and suspicious
  filenames;
- accidentally tracked generated results, caches, virtual environments,
  OSDI binaries, editor/temp files, or unnecessary large artifacts;
- obsolete current-main claims/planning statements;
- Spectre, silicon/foundry, reliability, correlation, and geometry-basis
  wording.

Do not remove legitimate historical evidence or harmless public platform/tool
metadata merely because it contains a reproducibility path or version.

## 7. Development qualification before candidate

Run from clean/controlled output directories:

- doctor;
- complete N0 regression;
- complete N1 regression;
- fresh N2 catalog qualification;
- unchanged strict N2 resume;
- full Pytest;
- Ruff;
- REUSE;
- provenance validation;
- normal repository validation;
- all release components possible before exact-clone attestation.

Never treat a prior V3-N2 evidence JSON as current release execution.

## 8. Candidate commit discipline

After implementation, documentation, release metadata, review hashes, tests,
and development real-tool qualification are coherent:

1. verify `git diff --check`, status, version, tag immutability, and no generated
   files staged;
2. create one clear v3.0.0 release-candidate commit;
3. record and push its exact SHA to the authoritative origin so HTTPS clone can
   retrieve it;
4. do not amend, rebase, or otherwise mutate it after qualification starts;
5. do not tag it yet.

The candidate, not the later compact evidence commit, is the future tag target.

## 9. Exact-candidate fresh clone

Use a newly created Linux-filesystem directory. Clone over HTTPS from the
authoritative origin and check out the exact candidate. Before bootstrap:

1. require clean tracked/untracked state;
2. prove `.apm`, `.venv`, OSDI artifacts, build/caches/results are absent;
3. record origin, exact SHA, branch/detached state;
4. record WSL2/EL9/x86_64/filesystem/mount identity;
5. prove `v3.0.0` does not exist;
6. run `python3 tools/attest_clean_clone.py`.

Then use only repository-documented bootstrap/setup/build commands. Do not
copy any state from the development checkout. Run doctor, normal validation,
and `apm validate --release`. Poll long-running commands and preserve the live
process rather than restarting after an observation timeout.

## 10. Evidence and failure handling

Every release component report must identify exact commit, tool/model/method
identity, status, commands or reproducible invocation, and report/artifact
hashes. Missing or stale evidence is failure.

If a component fails:

- retain its generated report/logs under ignored output;
- classify the real cause;
- continue independent checks where useful;
- fix the candidate only through a new coherent commit;
- qualify the new commit from another genuine fresh clone;
- never move a release tag or waive a gate.

## 11. Compact post-candidate evidence

After all 18 gates pass on the exact candidate, commit only compact
`validation/evidence/v3_release_candidate.json`, final `STATUS.md`, and any
required hash-bound review refresh. Bind the exact candidate, attestation,
environment/tools, release report, N0/N1/N2, catalog plan/fresh/resume counts,
static tests, immutability, claims, and tag absence.

Do not add raw simulator output or generated binaries. Do not reinterpret the
evidence commit as the candidate future tag target.

## 12. Completion report

Leave `STATUS.md` sufficient for an independent reviewer and report:

- candidate SHA;
- later evidence commit SHA;
- exact fresh-clone 18/18 result and report hash;
- package/runtime 3.0.0;
- blockers/caveats;
- immutable v1/v2 tags;
- absent final v3 tag and GitHub Release;
- unchanged visibility;
- exact next human authorization/action.
