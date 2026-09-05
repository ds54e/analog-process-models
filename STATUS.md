<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM status

State: **V6_CANDIDATE_REPAIR**. No v6 tag/release exists.

Starting main: `25140f57c4c3714f6ab4c9c9df44698ad7732662`, fast-forwarded from
`4cd57d98a54ad1cfe8deedf38de39a0b81a22d52`. The intervening commits only add the
selected handoff. V1–v5 source/evidence identities remain immutable.

The starting unflagged maintenance check passed, including 224 current tests,
Ruff, REUSE, provenance and original frozen-copy audits. Baseline output is ignored
under `.apm/v6/baseline/`; compact result bindings will be recorded separately.
The pre-migration inventory reproduces 161 released inputs, 52 v4 artifacts,
30 v5 artifacts and 13 preflight artifacts (overlapping scopes).

The policy transition passed 246 tests and all original frozen-copy checks; see
[transition evidence](validation/evidence/v6_transition.json). Exact source/evidence
exports and offline bundle restoration then passed. After each byte/mode was
verified against the baseline export, 77 classified historical live copies were
retired; [their manifest](releases/retired-v6.json) keeps exact locators. Runtime
models, profiles, source decisions, normative numerical data and notices remain
local and byte-exact. [Helper](releases/helper-migration.json) and
[check](releases/check-migration.json) mappings cover the migration.

Current runtime no longer imports historical release implementations. The latest
development suite passed **236 tests, zero skips**, including synthetic exact-tag
orchestration, incomplete/corrupt evidence, current root discovery and legacy
integrity controls. Current guides have reviewed executable blocks and a
[source-linked editorial review](docs/maintainers/v6-editorial-review.md).
Development model/noise/variation/research/history examples and an actual empty-prefix
compiler/bootstrap run succeeded. These are development observations, not a clean
candidate qualification. Baseline electrical, Benchmark/native and noise regressions
also passed; initial incorrect command names remain recorded as failed attempts.

Same-input baseline/v6 comparison passed: 3,242 physical data files, Benchmark
saved data, 65,536 latent pairs, raw/target parameters and three legacy-realization
replays were exact. Model/method/tool identities and unavailable-state classifications
were preserved. See [development evidence](validation/evidence/v6_development.json),
including retained launcher/postprocessing failures and their verified repairs.

This source freezes candidate identity `6.0.0` and the complete executable acceptance
plan. Its independent GitHub-clone campaign must still run all 57 required checks,
including 90,112 Research SPICE pairs and 12,288 circuit realizations. A later result
summary will identify the exact candidate commit/tree; that summary commit is separate.
The existing EL9/WSL2 tools and ignored historical raw evidence are preserved.
No v6 tag or release has been created; GitHub About remains an unapplied proposal.

The first fresh candidate (`17d9969747059dfba65b5d02c7b783a897aadd66`)
correctly failed its no-skip gate: a model-generator test ignored the configured
verified tool prefix. [The repair](validation/evidence/v6_tool_selection_repair.json)
preserves every scientific assertion, verifies configured-tool execution without
a default prefix, and supplies a byte-verified warm binary for untouched historical
tests. The original 224-test suite now passes without skips. The first candidate's
independent numerical campaign continues; a new exact candidate must be qualified.

Review of candidate `7fc74c117b31de861f7972010e5e32fe31f73201` found a
comparison-launcher failure-path defect: a failed prerequisite could reach dependent
work. [The retained fault injection and repair](validation/evidence/v6_comparison_prerequisite_repair.json)
add checked process exits, observed checkout identity and rejection of matching
failed/partial reports. All six new cases pass; the full current check passes with
236 tests and no skips. Numerical methods, projections and tolerances are unchanged.
Earlier candidate executions remain independent retained evidence; this corrected
source requires its own complete fresh-clone qualification.
