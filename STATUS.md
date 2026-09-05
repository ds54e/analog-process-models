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

The policy/identity transition passed unflagged validation with **246 tests, zero
skips**, Ruff, REUSE and all original frozen-copy checks; see
[transition evidence](validation/evidence/v6_transition.json).

Implementation follows [the selected plan](docs/maintainers/v6-plan.md) and
[predeclared acceptance](validation/acceptance.toml). Scientific assets, source
coefficients and numerical algorithms are unchanged. All historical copies remain
local until exact history/export/bundle and dependency verification passes.

The existing EL9/WSL2 toolchain and ignored v5 evidence are preserved. Baseline
real-tool runs are isolated from current source; command-name mistakes are retained
as failed attempts and are being corrected with the documented CLI names. No
scientific or infrastructure blocker has been established.
