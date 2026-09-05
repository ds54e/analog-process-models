<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM status

State: **V6_IMPLEMENTING**. No candidate is qualified and no v6 tag/release exists.

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
development suite passed **216 tests, zero skips**, including synthetic exact-tag
orchestration, incomplete/corrupt evidence, current root discovery and legacy
integrity controls. Current guides have reviewed executable blocks and a
[source-linked editorial review](docs/maintainers/v6-editorial-review.md).
Development model/noise/variation/research/history examples and an actual empty-prefix
compiler/bootstrap run succeeded. These are development observations, not a clean
candidate qualification. Baseline electrical, Benchmark/native and noise regressions
also passed; initial incorrect command names remain recorded as failed attempts.

The full current campaign, same-input old/new comparison and 90,112-pair Research
confirmation are being qualified under [predeclared acceptance](validation/acceptance.toml).
No numerical source/algorithm change or scientific blocker has been established.
The existing EL9/WSL2 tools and ignored historical raw evidence are preserved.
No v6 tag or release has been created; GitHub About remains an unapplied proposal.
