<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Codex: APM v5 full implementation

Work in `ds54e/analog-process-models` on current `main`. Synchronize safely without
resetting unrelated work. The repository is the complete handoff; no attachment
or old chat transcript is needed.

Read `AGENTS.md`, `GOAL.md`, `V5_RESEARCH_VARIATION.md`,
`validation/release_gates_v5.toml`, `variation/research/apm045/sources.toml`,
`APM045_POSITIONING.md`, `ENVIRONMENT.md`, `STATUS.md`, and the completed
`validation/evidence/v5_preflight_findings.json` and source audit.

This is now full v5 implementation and release-readiness work, not another bounded
preflight. The preflight-only ban on production src/API/schema/version work has
been superseded by the current goal. Preserve its completed reports/tool snapshot
and all released models, Benchmark/native semantics, frozen v4 artifacts and tags.

First bootstrap the current mission/version validators and mutable guidance
coherently for v5. The handoff still has 4.0.0+main software; migrate to 5.0.0.dev0
without dropping legacy integrity or numerical checks. Treat historical release
validators as historical, not a reason to rewrite released evidence.

Implement the smallest usable research-local flow: source-aware profiles, versioned
MG extraction and verified N/P mapping, persistent UID-keyed realizations,
hierarchical application/readback, sample/run/replay, explicit support tiers,
statistical/circuit qualification and narrow compiler-provenance repair.
Use real ngspice 47 and actual observed tool identities.

Investigate the companion Hart data as an independent process source. Keep the
original ambiguous beta values blocked. Resolve units, geometry, normalization,
extraction and reanalysis uncertainty; do not assume MG and ELR are equivalent or
different solely from names. Do not splice ST Vth with TSMC beta or invent a factor
correction. Continue independent implementation with clearly artificial fixtures
while source approval is pending; artificial results cannot qualify the default.
No author contact, external messages or paid data purchase.

Fix actual OpenVAF provenance: expected pins are not observations. Bind a controlled
pinned build or verifiable receipt to the actual compiler binary and OSDI outputs.
Do not change the pin to match the installed host or rewrite historical reports.

Do not clip/redraw/drop invalid samples, refit a realization when temperature or
bias changes, silently narrow the required domain, adopt unmeasured IO beta, or
weaken gates after seeing failures. Predeclare confirmation plans and report
negative findings. Complete independent tasks before declaring a genuine blocker.

Run the repository and v5 validation, keep compact hash-bound evidence, and update
STATUS.md only from work actually executed. Preserve unrelated work and push
coherent commits with normal fast-forward history.

Continue through all candidate-required gates to V5_RELEASE_READY, or report a
specific evidenced blocker after completing independent work. Do not stop merely
at a successful intermediate milestone. Do not create v5.0.0 or publish a GitHub
Release: candidate approval and publication are separate user-authorized steps.
Finish with the candidate commit or blocker, exact checks, source-profile decisions,
remaining limitations, and evidence paths.
