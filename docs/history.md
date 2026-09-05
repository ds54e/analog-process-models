# History and v6 migration

V6 separates current use and maintenance from reproduction of earlier releases.
Public model paths, scientific inputs, coefficients, model names, schemas and saved
realization meanings remain unchanged. The major-version boundary is the deliberate
migration of maintainer workflows and historical live-file locations.

Work at the root of a full configured Git clone. History commands read pinned
objects; they neither execute old code, change the checkout, fetch automatically
nor create tags. Listing locators alone is not verification.

<!-- apm-journey: history -->
```bash
.venv/bin/apm history list
.venv/bin/apm history verify --output .apm/tutorial-history.json
.venv/bin/apm history export v5.0.0 source --output .apm/tutorial-history-source
.venv/bin/apm history export v5.0.0 evidence --output .apm/tutorial-history-evidence
```

Inspect `tutorial-history.json` for exact tag objects, source/evidence tree
inventories and all successful checks. The source export has original `5.0.0`
package metadata. Its later evidence authority additionally contains the final
candidate, approval and exact-tag summaries. Exports preserve complete trees,
relative documentation/license context, byte contents, symlinks and executable bits.
Destination collisions and unsafe archive paths are rejected before writing.

The [index](../releases/index.toml) lists all five released annotated tags, their
peeled commits/trees, and separate evidence commits. Supplementary source snapshots
include `v3-publication`, `v5-preflight` and `v6-baseline`; export those with kind
`source`. The preflight snapshot is the complete exploratory source, not a relabeled
current implementation. The later v3 publication record remains distinct from its
earlier exact-tag qualification.

## Changed locations and commands

| Before v6 on main | V6 workflow |
| --- | --- |
| `apm validate --release`, `--release-v4`, `--release-v5` | Nonzero migration diagnostic; use the exact historical source/procedure |
| Historical release validators and clone helpers in `src/apm` | Exact source export/checkout; current coordinator has separate ownership |
| Completed release documents, prompts and most milestone summaries at live paths | Exact inventory locator and full source/evidence export |
| `apm validate` calling older release implementations | Current checks, explicit history integrity and separate real-tool campaigns |
| Checkout recognized by a v3 gate file | Project identity plus current model/variation resources |

The complete [77-file retirement inventory](../releases/retired-v6.json) and
[old-to-new test mapping](../releases/check-migration.json) make each disposition
reviewable. The [pre-migration inventory](../releases/migration-v6.json) records
original blobs/modes/hashes and inbound references. Retained scientific/normative
exceptions include source decisions, the source-audit locator, Benchmark/native
provenance evidence, IO generation evidence/generators, comparison data and the
preserved Research numerical plan. The v4 gate TOML is retained as an actual
mixed-voltage numerical input; current runtime does not import the old validator.

For strict old qualification, use a separate full clone detached at the index's
exact source commit and follow that source's original procedure. An export has no
`.git`, so it cannot alone satisfy a historical clean-clone/release requirement.
An isolated representative execution is not a full 16/17-gate requalification.
Current main never runs an old release flag against new code and labels it old.

## Offline and incomplete history

`tools/verify_history_migration.py --output <new-ignored-directory>` explicitly
exports every authority, creates a self-contained Git bundle including source and
post-tag authority ancestry, verifies it, and restores a new repository offline.
Its report binds the bundle and reconstructed inventories. It does not execute
historical code. The bundle belongs in ignored storage, not in the repository.

A full clone can verify/export without network access. A shallow clone must explicitly
fetch the missing ancestry and tags (for example, `git fetch --unshallow --tags origin`);
a source snapshot needs a full clone or a separately provided bundle. Missing objects,
wrong tags, grafts or shallow state produce a non-PASS result and nonzero exit status.
Replace-object behavior is disabled during exact-object audits.

A Git bundle preserves committed trees/evidence, not ignored raw runs, Python
environments, compilers, downloaded papers or external services. Old hash-only raw
references remain hash-only when those files are unavailable. Verification does
not prove old numerical results correct; newly executed evidence is a separate claim.

[Maintainer checks](maintainers/index.md) and [source-snapshot use](source-snapshot.md)
explain the current alternatives. No v6.0.0 tag or GitHub Release is created by these
workflows; both require separate approval.
