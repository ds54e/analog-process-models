# Release validation

APM v1.0.0 has one authoritative machine-readable contract:
`validation/release_gates.toml`. Its 16 required gates cover the reference
runtime, OSDI engines, all five kits, terminal characterization, benchmark and
native variation, FinFET integrity, model-only Spectre structure, licensing,
the self-contained distribution, metadata, exact-commit clean-clone execution,
and public-claim review.

## Fail-closed behavior

`apm validate --release` loads the gate list from the contract rather than
using a separately maintained expected count. The validator refuses to start
if its implemented gate set and the required contract set differ. At report
time a required gate passes only when its status is exactly `pass` and it has
nonempty evidence. Missing, `not_run`, skipped, blocked, failed, or
evidence-free gates make the command exit nonzero.

The release report uses schema `apm.release-validation.v1` and records the
contract hash, exact Git commit, component durations/report hashes, all ordered
gate results, and required/pass counts. Failure still produces `report.json`
under the selected output directory so the unsuccessful evidence is
inspectable.

Without `--release`, `apm validate` runs the repository regression and audit
layer only:

- complete Pytest suite;
- Ruff source audit;
- REUSE/SPDX licensing audit;
- exact-file provenance and redistribution audit;
- self-contained-model, local-include, tracked-binary/result, large-file, and
  credential audit;
- version/changelog/release-placeholder audit;
- hash-bound manual public-claim review; and
- model-only Spectre structural audit.

The release mode runs all of those checks, then adds the ngspice 47/OSDI doctor,
real five-kit benchmark/passive validation, IHP-native APM130 variation, and
complete regenerated all-kit characterization/normalized comparison. No prior
milestone report is accepted in place of the current execution.

## Exact-commit clean-clone attestation

The clean-clone gate is intentionally impossible to satisfy by merely deleting
some build outputs in a development checkout. Immediately after cloning, while
the worktree is clean and `.apm/` does not yet exist, run:

```console
python3 tools/attest_clean_clone.py
```

The standard-library-only script verifies and records:

- origin `https://github.com/ds54e/analog-process-models`;
- clean initial tracked and untracked status;
- absence of project state before attestation;
- exact Git commit and checkout branch;
- WSL2 kernel;
- RHEL-compatible EL9 identity;
- x86_64 architecture; and
- a Linux-filesystem path outside `/mnt/c`, including observed mount data.

It writes ignored `.apm/clean-clone-attestation.json`. Release validation
requires the same origin and exact commit, a still-clean Git worktree, and the
same qualifying platform. Moving the attestation to another checkout or
committing a later change invalidates it.

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
.venv/bin/apm validate --release
```

The explicit build, doctor, and repository-validation commands provide a clear
new-user diagnostic sequence. The final release command repeats every required
automatic check and all real-tool release validations; it does not trust those
earlier successes. All generated OSDI binaries, raw simulator runs, toolchain
sources, and detailed reports remain below ignored `.apm/` paths.

The all-kit component persists full raw signed terminal results and normalized
views for APM350, APM130, APM045, APM022, and APM016F. Thus the release command
itself satisfies the representative all-five-technology comparison step. A
reviewer can additionally run a focused pair with, for example:

```console
.venv/bin/apm compare apm045 apm022 --output .apm/review/planar-pair
.venv/bin/apm compare apm022 apm016f --output .apm/review/planar-finfet-pair
```

## Manual claim boundary

`validation/release_review.toml` is the explicit manual audit record for the
README, changelog, status, third-party policy, and Spectre documentation. It
records the decisions that no real Spectre execution, autonomous visibility
change, or APM foundry/silicon-correlation claim occurred. SHA-256 values bind
that review to the exact public text; editing a reviewed file makes validation
fail until the claims are reviewed again.

Spectre success remains `structurally_checked` with backend status
`experimental_unverified`. It can never satisfy a real-Spectre claim, and real
Spectre validation is not a v1.0 gate.
