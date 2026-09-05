<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# V5 candidate qualification

`apm validate --release-v5 candidate` evaluates the 16 required candidate gates in
`validation/release_gates_v5.toml`. Its only successful finish is
`V5_RELEASE_READY`. It has no tag creation or release publication operation. The
seventeenth, post-tag gate requires separate user authorization and is not a
candidate dependency. The frozen v3/v4 validators and records remain unchanged.

Use `5.0.0.dev0` during development. Freeze code, profiles, source decisions and
the numerical plan together, set project/runtime version to plain `5.0.0`, run
current repository validation, and commit/push the candidate by normal
fast-forward history. Qualification must use that exact clean commit from a
new GitHub clone, not an edited working tree or a copied local checkout.

From a configured development checkout, create the clone before generated state:

```sh
python tools/attest_clean_clone_v5.py \
  --commit EXACT_40_CHARACTER_CANDIDATE_COMMIT \
  --destination .apm/v5/fresh-candidate
```

The destination must not exist. The helper clones the authoritative GitHub remote
with `--no-local`, checks out the exact commit detached, verifies clean state and
absence of `.apm`/`.venv`, and seals an attestation in the clone's ignored storage.
It records the remote, commit/tree, Git directory, creator implementation and
absence of local object alternates. The evaluator checks these again.

In that clone, create a fresh Python environment and install `.[dev,research-audit]`.
Use the reference EL9 x86_64 environment, ngspice 47 and the actual controlled
OpenVAF build described in `ENVIRONMENT.md`. A read-only shared compiler/source
receipt and primary PDF are allowed; copied numerical caches, copied environments
and existing result directories are not. Configure `APM_REPO_ROOT` to the clone,
`APM_STATE_DIR` below its ignored `.apm/v5/`, and `APM_TOOLCHAIN_DIR` to the verified
toolchain. Retain a local `.apm/toolchain/ngspice-47/bin/ngspice` alias to that
executable for the required model-generation regression test; its absence can
cause a skip, which fails candidate qualification.

Provide the legitimate primary companion PDF with `APM_V5_SOURCE_PDF`; the source
reanalysis verifies its pinned hash and uses PyMuPDF 1.26.4. Runtime sampling does
not fetch sources. Keep dependency/tool receipts, the acquisition source URL and
PDF hash with ignored qualification inputs. No full paper is added to the package.

```sh
apm validate --release-v5 candidate --output .apm/v5/candidate
```

The evaluator runs repository pytest/Ruff/REUSE/provenance/distribution checks,
the separate frozen preflight tests, legacy Benchmark/native/electrical/noise
checks, source reanalysis, observed compiler/OSDI checks, all six numerical
suites, explicit model-charge conservation and the public example CLI flow.
It continues independent components after a failure. Missing, skipped, unknown,
failed, duplicate, empty, stale or hash-mismatched required evidence cannot pass.
Successful raw-run inventories and every requested cohort index are checked.
Each uncached statistical run is a separate simulator process; the committed
plan fixes one simulator thread and independent physical-device draws.

The charge check uses the same saved representative replay realizations at all
four temperatures. It records native qg/qd/qs/qb through DC and transient, requires
finite nonconstant charge, verifies their conserved sum to relative 1e-12 and
repeats raw-parameter readback. AC/transient terminal-current agreement is checked
separately. These are compact-model consistency tests, not silicon measurements.

Retain all failed confirmation runs and report their denominator. Revisions need
an explicit development rationale and a committed plan before fresh confirmation;
never tune seeds, delete failures or weaken scope after observing a result.

The raw `report.json` binds the exact candidate commit and component hashes.
A later compact result-only report under `validation/evidence/` may reference
that result without certifying the later evidence commit. Preserve that distinction
in `STATUS.md` and in the final release-readiness statement. Neither plain `5.0.0`
nor a readiness report creates a release or authorizes a tag.

The subsequently approved exact-tag procedure is documented separately in
[release-publication-v5.md](release-publication-v5.md). It runs the unchanged
candidate validator in a new detached tag clone and adds explicit tag/identity
checks as the seventeenth gate; it does not change the qualified candidate.
