# Maintain APM

Read [AGENTS](../../AGENTS.md), [GOAL](../../GOAL.md) and the selected
[v6 plan](v6-plan.md) before substantive changes. [STATUS](../../STATUS.md) reports
executed evidence. Scientific contracts and sources remain in the
[guide index](../index.md); [environment guidance](../../ENVIRONMENT.md) distinguishes
cold bootstrap, verified reuse and actual source/build provenance.

From a configured repository root, `apm validate` runs current package/catalog,
scientific-asset, history, provenance/distribution, test, Ruff and REUSE checks.
Its requested scope and unavailable checks are explicit. `--scope product` checks
a bounded local source distribution without claiming history or release coverage.
[Returning-user commands](../getting-started.md#returning-to-an-existing-checkout)
execute the current check with reconciled editable metadata.

Real-tool regressions remain separate concrete commands: `characterization-check`,
`benchmark-check`, `apm130-native-check`, `noise-method-check`, `noise-catalog-check`
and `research check`. Required missing, skipped, stale or failed evidence never
passes. Tests exercise coordinator fixtures; they must not call the full release
campaign recursively. Use `set num_threads=1` in research SPICE and bounded worker
parallelism, with separate writable outputs and retained failures.

[History and migration](../history.md) replaces old live-tree release workflows.
It records exact source/evidence identities, export/bundle reconstruction and
check/helper dispositions. Source decisions and real scientific input dependencies
remain locally available and hash-checked. New documentation is current guidance;
do not freeze mutable README paragraphs as permanent release policy again.

## Current candidate lifecycle

The [single acceptance manifest](../../validation/acceptance.toml) defines ten
required groups and 57 subordinate candidate checks. Implementation uses
`6.0.0.dev0`; the frozen candidate uses `6.0.0`. The source contains both candidate
and exact-tag orchestration. Candidate qualification starts from a clean commit in
a fresh authoritative GitHub clone and executes the full declared campaign,
including 90,112 Research SPICE pairs and 12,288 circuit realizations.

Evidence names the tested commit **and tree**. A later evidence-summary commit is
not thereby qualified. `V6_RELEASE_READY` requires all candidate checks. Creating
an immutable annotated tag at that exact approved commit, fresh exact-tag
requalification and publication are separate, explicitly approved operations.
No real tag creation/publication is part of the autonomous v6 implementation.
`6.0.0+main` is reserved for maintenance after actual publication.

From the configured source root, create the independent checkout with
`.venv/bin/python tools/create_candidate_clone.py --commit <full-commit> --destination <absent-directory>`.
Inside that clone run `tools/setup-python.sh` with the preserved dependency
constraints, select a verified local compiler prefix using the environment guide,
then `.venv/bin/apm validate --qualify candidate --output .apm/qualification/campaign`.
The coordinator itself executes the published cold setup in another empty prefix,
the warm/current checks, all scientific and archive checks, and emits its typed
results under that new output directory. Existing raw outputs are not candidate
inputs. A failed attempt stays intact; fixes need a new candidate/run where relevant.

After separate approval and real annotated tag creation, use another newly attested
clone of the approved commit and `validate --qualify exact-tag --approval-file <file>`.
The external JSON record uses schema `apm.exact-tag-approval.v1`, exact `commit`,
`tree`, `tag_object`, and the previous `candidate_report` path and its
`candidate_report_sha256`. That report and its evidence must still verify. The
tag must already exist when the clone is made. The coordinator reruns all 57 checks
and adds three tag/approval/freshness checks; it never creates or publishes a tag.

## Reviews and contributions

Keep the implementation explicit and small. Preserve model semantics, file-level
licenses, source decisions, numerators/denominators and confidence limits. Scientific
defects require a minimal reproducer and a candidate blocker; this task does not
silently fix physics or retune sources. See [CONTRIBUTING](../../CONTRIBUTING.md),
[THIRD_PARTY](../../THIRD_PARTY.md) and [SECURITY](../../SECURITY.md).

The package description proposal is: “Open compact models and ngspice tools for
analog device, noise, and mismatch studies.” It is applied to local package metadata.
The GitHub About change remains unapplied because that specific external write is
not authorized.
