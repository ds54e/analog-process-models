<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# V5 approved tag and publication procedure

The user explicitly approved only candidate
`381517fda5107fabf98af7801d5a5103f38e230c`. The authorization and pre-operation
legacy tag/release observations are in
`validation/evidence/v5_release_authorization.json`. Approval does not permit
tagging a later `main` commit, moving a tag or publishing after a failed check.
The frozen candidate and its original gate contract remain unchanged.

Before tagging, fetch authoritative `main` without rewriting local work. Verify
the approved commit is its ancestor; local and remote `v5.0.0` and the GitHub
Release are absent; v1–v4 annotated objects/commits match frozen evidence; and
existing GitHub releases retain their recorded identity. Retain a complete
before-operation snapshot. Existing v1/v2 tags have no GitHub Release at this
approval boundary; do not create substitute historical releases.

Create exactly one annotated tag, with no force or replacement option:

```sh
git tag -a v5.0.0 381517fda5107fabf98af7801d5a5103f38e230c \
  -m 'Analog Process Models v5.0.0'
git push origin refs/tags/v5.0.0:refs/tags/v5.0.0
```

The candidate CLI intentionally remains `apm validate --release-v5 candidate`.
The separate `tools/requalify_v5_tag.py` on `main` supplies the post-tag procedure:

```sh
.venv/bin/python tools/requalify_v5_tag.py \
  --destination .apm/v5/fresh-exact-tag-1 \
  --source-pdf .apm/v5/sources/companion.pdf \
  --toolchain .apm/toolchain \
  --constraints .apm/v5/evaluator-development/candidate-constraints.txt
```

The helper checks local/authoritative annotated objects and peeled commits, then
uses the unchanged candidate clone creator to clone GitHub with `--no-local`
and attest empty generated state at the approved commit. It explicitly selects
`v5.0.0` detached and proves the commit/tree did not change. A new venv is created
and installed; no environment, mapping cache or numerical result is copied.
Only hash-pinned dependency constraints, primary PDF and verified compiler/source
receipts are shared. Each fresh clone builds its own OSDI and numerical state.

The helper launches the installed fresh-clone `apm` executable to rerun the full
16-gate validator. It requires a successful command, the complete unique gate
inventory, matching source/contract/tool/dependency identities and valid report
hashes located within that new rerun directory. It then rechecks the unchanged
annotated tag, remote object, approved commit/tree, detached HEAD, clean worktree
and helper implementation hash. This combination is the seventeenth
`release.exact_tag_requalification` gate, with status PASS only at 17/17.

The sealed `.apm/v5/exact-tag/report.json` inside the new clone binds the helper
commit/hash, authorization, tag identities, fresh-clone attestation, setup/run
commands and logs, inputs, all candidate report hashes and before/after checks.
A failure retains the raw report and forbids publication. Never move, delete or
recreate the tag to repair failed requalification.

Only after a fresh 17/17 PASS, recheck legacy tags/releases and publish the
existing tag using `gh release create v5.0.0 --verify-tag` with title
`Analog Process Models v5.0.0` and `--notes-file RELEASE_V5.md`. Do not use a
command that implicitly creates a different tag or selects current `main`.
Verify the published tag, notes hash and publication time after requalification.
Record concise hash-linked results on later `main`, then move mutable metadata
to `5.0.0+main`. Preserve the exact released candidate and frozen evidence.
