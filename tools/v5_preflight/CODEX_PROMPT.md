<!-- SPDX-FileCopyrightText: APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Codex launch prompt

Work in the existing `ds54e/analog-process-models` repository on current `main`.
The repository now contains the complete v5 preflight handoff; no chat attachment
or ZIP is required. Preserve unrelated work and do not reset to an older commit.

Read and follow `AGENTS.md`, `GOAL.md`, `V5_PREFLIGHT.md`,
`APM045_POSITIONING.md`, `ENVIRONMENT.md`,
`tools/v5_preflight/V5_MINIMUM_EXPERIMENT.md`,
`tools/v5_preflight/source_audit.toml`, and `STATUS.md`.

Complete the currently authorized APM v5 preflight, not the full v5 release.
Review the supplied exploratory code, rerun its offline tests, and use the existing
ngspice 47 reference environment to prove hierarchical instance isolation, maximum-gm
extraction convergence, and the two-observable instance mapping for VTG N/P.
Start with the specified minimum point; expand only after it is understood.
Report each experiment and each polarity independently. A failed negative control
counts only when the intended failure mechanism is demonstrated.

In parallel, investigate the unresolved Hart beta normalization using legitimate
primary sources, including the identified thesis. Do not adopt or silently rescale
ambiguous coefficients. Source uncertainty must not prevent the independent
artificial numerical experiments. Do not contact authors or send external messages.

Preserve all released models, wrappers, benchmark/native variation, frozen v4
records, tags, and releases. Keep `4.0.0+main`; do not create a new version, tag,
release, production statistical profile, or broad framework in this task.

Keep raw runs in ignored `.apm/v5-preflight/` storage. Commit concise, hash-linked
findings and source-audit decisions to the paths specified by `V5_PREFLIGHT.md`.
Run the applicable repository validation and update `STATUS.md` from checks actually
executed. Missing, skipped, and failed checks are not passes. Push coherent changes
with normal fast-forward history only.

Continue through every feasible preflight experiment rather than stopping after
Python tests. Finish with the four separate application/extraction/mapping/source
results, evidence locations, unresolved limitations, and the smallest justified
proposal for the full v5 implementation contract. Do not proceed to release work
without a separate explicit authorization.
