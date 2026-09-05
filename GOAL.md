<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM post-v5 maintenance

Status: v5.0.0 RELEASED; current main uses `5.0.0+main`.

Maintain the released APM v5.0.0 baseline and its public research/characterization
flows. The completed v5 implementation goal remains in Git at
`381517fda5107fabf98af7801d5a5103f38e230c:GOAL.md`; it is not a new implementation
or release instruction. The qualified candidate first reached V5_RELEASE_READY
with 16/16 gates. The separately approved exact tag then passed 17/17 before
GitHub publication. See `validation/evidence/v5_post_release_requalification.json`.

## Immutable release and evidence

- Annotated `v5.0.0`: `b1a4246b9189fe33915d457e9d7f2938869b8fdf`.
- Peeled approved commit: `381517fda5107fabf98af7801d5a5103f38e230c`.
- Frozen v5 evidence authority: `150084368815f6a57eae9f3e707f685149e920d3`.
- v1–v4 tags, released model bytes and their historical records remain immutable.

Do not modify Benchmark v2 distributions, native variation semantics, nominal
model cards/wrappers/manifests, or frozen v1-v5 records. Keep candidate/exact-tag
reports, source decisions, approved profiles, confirmation plan, release notes
and phase-specific release procedures exact. Their earlier approval flags and
future-tense wording record the state at that time; they are not current blockers
or permission to repeat a publication action.

## Maintenance boundaries

Preserve the manifest-driven Technology -> Electrical Family -> Device model,
native planar W/L and FinFET L/NFIN, released electrical/noise/research schemas,
terminal finite-difference gm/gds, full complex terminal-Y semantics, and the
normal Sparse/no-KLU stationary-noise path. The catalog remains 15 families /
30 public MOS devices. New source coefficients, nominal models, calibration or
versioned capabilities require separate explicit user authorization.

Research Local Mismatch remains optional VTG N/P within the qualified domain.
Hart/TSMC40 companion data is a source-transfer hypothesis, not foundry
correlation, yield or reliability evidence. Original Hart/ST40 beta remains
BLOCKED_NORMALIZATION_CONFLICT. IO18/25 transfer remains UNRESOLVED_WITH_EVIDENCE
with no default mismatch profile. Research Global/All, statistical passives,
spatial effects and noise MC remain unsupported. Spectre remains experimental,
model-only and unverified.

Retain actual observed compiler provenance at the unchanged required OpenVAF pin.
Use the documented EL9 x86_64 / ngspice 47 reference environment; unknown or
mismatched tool/source identities cannot pass. Never substitute an expected pin
for an observed build or reinterpret a source uncertainty as device randomness.

## Validation and Git

Unflagged `apm validate` is the current maintenance path. It checks current
version/guidance, package metadata, preserved release inputs and frozen evidence,
regressions, provenance, distribution hygiene, Ruff and REUSE. Historical v3/v4/v5
qualification procedures remain separate; do not edit them to accept live main.
Missing, skipped, stale, failed and unavailable checks are not passes.

Keep raw runs ignored and summaries hash-linked. Record the exact Git commit and
worktree/input hashes; `5.0.0+main` alone does not identify a source snapshot.
Normal in-scope maintenance, tests, coherent commits and fast-forward pushes are
authorized. Future version/release operations require separate explicit user
authorization. Never force-push, move/recreate released tags, rewrite published
history or alter repository visibility/security settings through routine work.
