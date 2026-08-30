# v3.0.0 release-candidate validation

APM 3.0.0 has one active machine-readable release contract:
`validation/release_gates.toml`. Its 18 required gates cover:

- the exact WSL2 + RHEL-compatible EL9 x86_64 runtime, ngspice 47, project-
  pinned OpenVAF, and native/OSDI compact-model execution;
- normal Sparse/no-KLU required noise execution;
- manifest-driven five-technology/13-family/26-device discovery and native
  planar/FinFET geometry;
- the complete existing v2 electrical characterization, comparison, benchmark,
  passive, and APM130 upstream-variation baseline;
- V3-N0 analytic harness/four-engine qualification;
- the frozen V3-N1 acquisition/fit method, synthetic cases, low-VDS, and
  correlation diagnostics;
- fresh V3-N2 catalog-wide temperature/inversion/length/NFIN datasets,
  comparisons, explicit statuses, raw spectra/provenance, and strict resume;
- model-card immutability and honest model/default claim boundaries;
- Spectre's model-only experimental/unverified boundary;
- exact licensing/provenance, REUSE, self-contained distribution, public-
  repository hygiene, 3.0.0 metadata, exact clone, and claim review.

Historical v1/v2 evidence remains immutable and useful context, but never
satisfies a v3 gate.

## Fail-closed evaluator

`apm validate --release` loads required gate IDs in declaration order and
refuses to run when the implemented set differs. A required gate passes only
when:

1. status is exactly `pass`;
2. evidence is nonempty;
3. every evidence path exists;
4. the supporting current-run component passed; and
5. its semantic observations satisfy the frozen contract.

Missing, skipped, blocked, failed, unimplemented, stale, evidence-free, or
hash-mismatched required gates make the command exit nonzero. Independent
components continue after many failures so the report remains diagnostic.

The final report uses `apm.release-validation.v3` and binds the target, exact
Git commit, gate-contract hash, component report paths/hashes/durations, every
ordered gate result, evidence validity, and required/pass counts.

## Repository validation

Without `--release`, `apm validate` writes
`apm.repository-validation.v3` and runs:

- the full Pytest suite;
- Ruff and Python import/compile coverage through the tests;
- REUSE/SPDX;
- exact provenance, notices, independent-authorship, and redistribution
  audits;
- manifest/catalog/geometry and v1-runtime-migration audits;
- tracked source/include closure and generated-output checks;
- credential, secret-signature, inappropriate private-path, editor/temp,
  oversized-artifact, and ignore-policy audits;
- 3.0.0 package/runtime/CLI/changelog/placeholder checks;
- hash-bound public-claim review; and
- deterministic Spectre structural checking with no real-tool claim.

Release mode repeats this static layer from the exact candidate and then runs
every required real-tool component.

## Pre-bootstrap clean-clone attestation

The clean-clone gate cannot be satisfied by deleting outputs from a development
checkout. From a genuinely new HTTPS clone, immediately after selecting the
candidate commit and before any setup command, run:

```console
python3 tools/attest_clean_clone.py
```

The standard-library-only command writes ignored
`.apm/clean-clone-attestation.json` with schema
`apm.clean-clone-attestation.v3`. It verifies and records:

- exact origin `https://github.com/ds54e/analog-process-models`;
- initially clean tracked/untracked worktree;
- exact commit and branch/detached state;
- absence of `.apm`, `.venv`, model OSDI binaries, caches, build/results, and
  other project-local generated state before attestation;
- absence of a `v3.0.0` tag;
- WSL2 kernel, RHEL-compatible EL9, x86_64, and Linux-filesystem checkout
  outside `/mnt/c`, with observed filesystem/mount identity.

Release validation later requires the same checkout path, origin, exact commit,
qualifying platform, clean worktree, and continued absence of the final tag.
Copying the attestation or committing a later change invalidates it.

## Reproducible exact-candidate sequence

The coherent candidate must already be reachable from the authoritative origin
so the qualification is a real network clone rather than a copied local tree:

```console
git clone https://github.com/ds54e/analog-process-models.git
cd analog-process-models
git checkout --detach <exact-candidate-sha>
python3 tools/attest_clean_clone.py
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm build-models
.venv/bin/apm doctor
.venv/bin/apm validate --output .apm/results/v3-static
.venv/bin/apm validate --release \
  --output .apm/results/v3-release-candidate
```

Bootstrap builds or verifies project-local ngspice 47, OpenVAF-Re-Loaded,
PSP103 QS/NQS, and BSIM-CMG 112.1.0 OSDI artifacts from documented sources.
No `.apm`, `.venv`, OSDI artifact, simulator result, or cache may be copied
from another checkout.

## Real-tool components

One release execution produces and hash-links:

- initial and final exact clean-clone verification;
- repository static/regression report;
- doctor report for native BSIM3/BSIM4 and PSP103/BSIM-CMG OSDI;
- complete 13-family/26-device electrical characterization;
- five required electrical comparison jobs;
- Benchmark Global/Local/All, fixed corners, Rbench/Cbench, adapter/replay, and
  statistical validation;
- independent APM130 LV/HV upstream corner/process/mismatch validation;
- a fresh 290-unique-request V3-N2 catalog execution from empty output, whose
  nested regression executes the complete V3-N1 method and V3-N0 harness;
- a second unchanged V3-N2 invocation that must safely reuse all 290 physical
  results and freshly requalify strict mismatch/tamper/incomplete/stale
  rejection.

The first catalog execution cannot be satisfied by reuse. Valid
`target_not_reachable` results and fail-closed null fit metrics remain valid
scientific outcomes; `simulation_failed`, silent clipping, missing request
states, or forced fit values fail the release contract.

## Public claims and model immutability

`validation/release_review.toml` records decisions and SHA-256 hashes for all
reviewed current user-facing/release/noise documents. Editing reviewed content
invalidates the claim gate until the review is refreshed.

The review and automated audit require:

- no silicon/foundry noise-accuracy claim for APM-authored models;
- no new process-noise calibration/tuning;
- no unsupported noise Monte Carlo, RTS/RTN, transient-noise, PSS/PNoise,
  oscillator phase-noise, or full terminal-correlation claim;
- no universal planar/FinFET effective-width claim;
- no reliability/manufacturing/signoff claim;
- no real Spectre parsing/simulation claim;
- no physical Benchmark Global family-correlation claim;
- APM350/APM022/APM016F production cards byte-identical to `v2.0.0`.

## Candidate/evidence boundary

Once development regressions pass, create one coherent candidate commit. That
exact commit is the future `v3.0.0` tag target and must not be amended after
qualification starts.

After its fresh clone reports `status = "pass"`, 18 required gates, 18 passed
required gates, and valid evidence for every gate, add only compact evidence
and final status/review changes on `main`, preferably at
`validation/evidence/v3_release_candidate.json`. The later evidence commit is
not the future tag target.

V3-N3 does not authorize a tag, GitHub Release, or visibility change. The next
human action is explicit review/authorization to create immutable tag
`v3.0.0` at the already-qualified candidate commit. Post-tag requalification,
GitHub Release creation, and any publication/visibility decision are separate.
