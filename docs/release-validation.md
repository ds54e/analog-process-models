# Release validation

APM 2.0.0 has one authoritative machine-readable gate contract:
`validation/release_gates.toml`. Its 20 required gates cover:

- the WSL2 + RHEL-compatible EL9 x86_64 runtime and ngspice 47 compact-model
  execution;
- manifest-driven catalog behavior and all five technologies/13 families;
- APM130 LV/HV, APM045 VTL/VTG/VTH/THKOX, APM022 multi-VT, and APM016F
  multi-VT/NFIN behavior;
- v2 characterization and all required comparison views;
- Benchmark Global/Local/All, Rbench/Cbench, and independent IHP-native
  APM130 LV/HV variation;
- model-only experimental/unverified Spectre structure;
- exact-file licensing/provenance and a self-contained source distribution;
- removal of v1 runtime single-source/alias dependencies;
- 2.0.0 metadata, exact-commit clean-clone execution, and a hash-bound public
  claim audit.

Historical v1 evidence is never accepted for a v2 gate.

## Fail-closed evaluator

`apm validate --release` loads required gate IDs from the contract and refuses
to run if the implemented set differs. At report time, a required gate passes
only when:

1. its status is exactly `pass`;
2. its evidence list is nonempty; and
3. every evidence path exists as a file.

`missing`, `not_run`, skipped, blocked, failed, evidence-free, or unimplemented
gates make the command exit nonzero. Component failures are recorded and later
independent components continue where possible, so a failed run still produces
an inspectable report.

The final report uses schema `apm.release-validation.v2` and records target,
contract hash, exact Git commit, component reports/durations/errors, every
ordered gate result, evidence validity, and required/pass counts.

## Repository validation

Without `--release`, `apm validate` runs the source/audit layer and writes
`apm.repository-validation.v2`:

- the complete Pytest suite;
- Ruff and Python compile audits;
- REUSE/SPDX licensing audit;
- exact-file provenance, independent-authorship, and redistribution audit;
- manifest/catalog contract and v1-migration audits;
- tracked source/include closure, generated-output, large-file, and credential
  audits;
- 2.0.0 metadata/placeholder audit;
- hash-bound public-claim review; and
- deterministic Spectre structural audit.

Release mode repeats that static layer in the current checkout, then runs the
doctor, all 13 family characterizations, five required comparison jobs, all
benchmark modes/corners/passives, and both IHP-native APM130 family cohorts.
No prior milestone report substitutes for current execution.

## Exact-commit clean-clone attestation

The clean-clone gate cannot be satisfied by deleting outputs in a development
checkout. Immediately after cloning—while Git is clean and `.apm/` does not
exist—run:

```console
python3 tools/attest_clean_clone.py
```

The standard-library-only command records schema
`apm.clean-clone-attestation.v2` and verifies:

- origin `https://github.com/ds54e/analog-process-models`;
- an initially clean tracked/untracked worktree;
- absence of project state before attestation;
- exact commit and branch;
- a WSL2 kernel;
- RHEL-compatible EL9 identity;
- x86_64; and
- a Linux-filesystem checkout outside `/mnt/c`, with observed mount data.

It writes ignored `.apm/clean-clone-attestation.json`. Release validation
requires the same checkout path, origin, commit, qualifying platform, and a
still-clean worktree. Copying the attestation elsewhere or committing a later
change invalidates it.

## Reproducible fresh-clone sequence

On the designated WSL2 + EL9 x86_64 host and Linux filesystem:

```console
git clone https://github.com/ds54e/analog-process-models.git
cd analog-process-models
python3 tools/attest_clean_clone.py
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm build-models
.venv/bin/apm doctor
.venv/bin/apm validate
.venv/bin/apm validate --release --output .apm/results/v2-release
```

Bootstrap installs/builds project-local dependencies and OpenVAF/ngspice
artifacts as required. The explicit build, doctor, and repository validation
give useful early diagnostics. The release command repeats every automatic
release check and real-tool component; success means all 20 gates passed in the
same exact-commit checkout.

Generated OSDI binaries, toolchain sources, raw simulator runs, and detailed
reports stay below ignored `.apm/` paths. Transistor-model source inputs are
all tracked; no separate model download is needed.

## Real-tool components

The release execution produces:

- doctor report with native BSIM3/BSIM4 and PSP103/BSIM-CMG OSDI real-device
  smokes;
- fresh complete characterization for all 13 families/26 devices;
- five-anchor, APM045 threshold, APM045 gate-stack, APM022 multi-VT, and
  APM016F multi-VT comparison reports;
- Benchmark Global/Local/All, five corners, adapter/replay/statistical, and
  Rbench/Cbench validation;
- independent APM130 LV and HV corner/process/mismatch reports; and
- static provenance, distribution, regression, Spectre, metadata, and claims
  evidence.

The release report hash-links those component reports. A failed component
remains evidence of a failure, never a pass.

## Public-claim review

`validation/release_review.toml` records the manual decisions and SHA-256
hashes for the README, changelog, status, third-party policy, core v2 docs, and
release-readiness summary. Editing any reviewed text invalidates the claim
gate until it is reviewed and rehashed.

The review must record no real Spectre execution, no foundry/silicon correlation
claim for APM-authored decks, no physical family-correlation claim for
Benchmark Global, no repository visibility change, and no unresolved finding.
Spectre structural success remains model-only `experimental_unverified`; real
Spectre validation is not a v2 gate.

## Release decision

A version string, completed run, or historical success cannot authorize a tag.
Tag `v2.0.0` only when the exact-commit fresh clone reports
`status = "pass"`, `required_gate_count = 20`, and
`passed_required_gate_count = 20`, with every required gate's
`evidence_valid = true` and `passed = true`.
