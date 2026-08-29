# Unattended Execution Protocol

This document defines how a long-running autonomous implementation agent should execute `GOAL.md` when no human will supervise intermediate decisions.

It is process guidance, not a replacement for `GOAL.md` or `AGENTS.md`.

## Authority and conflict handling

Use this order when repository instructions appear to conflict:

1. applicable safety/security requirements and explicit user instructions
2. `AGENTS.md` — mandatory repository policy and guardrails
3. `GOAL.md` — authoritative v1.0 scope, requirements, and Definition of Done
4. this file — unattended execution procedure
5. `PROJECT_CONTEXT.md` — informative design history and rationale
6. `ENVIRONMENT.md` — reported initial environment and M0 bootstrap expectations
7. `RESEARCH_BASELINE.md` — dated external-research baseline
8. `README.md` — public-facing project description

`PROJECT_CONTEXT.md`, `ENVIRONMENT.md`, and `RESEARCH_BASELINE.md` provide context and starting assumptions, but they are not allowed to override the normative contract above them. Current authoritative upstream evidence or actual tool behavior may supersede a dated research baseline; record material changes in `STATUS.md` and provenance/evidence.

Do not silently resolve a material conflict by dropping a harder requirement. Prefer the stricter interpretation and record the decision in `STATUS.md`.

## Expected initial execution environment

The first unattended implementation run is expected to start with Codex CLI running directly inside WSL2 on AlmaLinux, with ngspice/OpenVAF not yet installed. Treat that as reported input, not validation.

Missing initial simulator/compiler tooling is expected M0 bootstrap work, not a blocker by itself.

Do not create a nested container or alternate Linux VM merely to claim that the WSL2/EL9 release gate was satisfied. Containers may be useful supplementary checks, but the direct WSL2 + AlmaLinux environment is the primary reference environment and final clean-clone target.

## Startup sequence

Before implementation work:

1. Confirm the working repository origin is `https://github.com/ds54e/analog-process-models`.
2. Read `AGENTS.md`, `GOAL.md`, `PROJECT_CONTEXT.md`, `ENVIRONMENT.md`, `RESEARCH_BASELINE.md`, `UNATTENDED_EXECUTION.md`, and `README.md` completely.
3. Read `validation/release_gates.toml` and `STATUS.md` before deciding what is already complete.
4. Inspect `git status` before changing anything.
5. Preserve any pre-existing user changes. Never use destructive `git reset --hard`, `git clean -fdx`, force-push, or history rewriting to obtain a clean tree.
6. Verify the actual WSL2/EL9 environment locally rather than trusting the reported initial state. Record the result in `STATUS.md` and validation evidence.
7. Inventory installed simulator/compiler/tool versions before installing or upgrading anything.
8. Bootstrap the required M0 toolchain when absent. For the initial target, this means Python >=3.9, ngspice 47 with OSDI, and OpenVAF-ReLoaded where Verilog-A-to-OSDI compilation is required.
9. Begin actual model qualification with M0 from `GOAL.md`; do not start by inventing a generic framework.

Use `PROJECT_CONTEXT.md` to understand settled rationale before reopening architecture questions. Use `RESEARCH_BASELINE.md` to avoid repeating already-completed discovery, but re-check authoritative upstream sources before pinning a revision or making a release claim. A different implementation is acceptable when new authoritative evidence or actual tool behavior requires it, but record material departures and their evidence in `STATUS.md` rather than silently replacing the original design intent.

## M0 toolchain bootstrap discipline

On the reported bare AlmaLinux environment, source-building required tools is an acceptable and expected path.

For ngspice:

- target ngspice 47 with the OSDI/predictor support required by the project;
- use authoritative source;
- prefer a reproducible user-local/project-controlled install prefix when practical;
- do not destructively replace unrelated system software solely for APM;
- document dependencies, source version/hash, configure flags, compiler, prefix, and version output;
- prove OSDI with actual loaded-model simulation.

For OpenVAF-ReLoaded:

- use authoritative upstream binaries or source;
- pin the actual revision/version used;
- record the toolchain if building from source;
- prove the selected tool by compiling the actual PSP103 and BSIM-CMG paths required by APM, not just a trivial example.

Do not modify user shell startup files as the required installation mechanism. Use explicit/project-managed paths or reproducible setup scripts/configuration.

## Milestone execution loop

Treat M0–M10 in `GOAL.md` as durable checkpoints.

For each milestone:

1. Re-read the relevant `GOAL.md` requirements and relevant rationale in `PROJECT_CONTEXT.md`.
2. Re-check any dated upstream fact from `RESEARCH_BASELINE.md` that will become a pinned dependency, vendored asset, or release claim.
3. Implement the smallest complete design that satisfies the milestone and preserves the public contract.
4. Run milestone-level tests using the actual tools whenever available.
5. Investigate failures rather than weakening assertions or changing requirements to match broken behavior.
6. Record compact validation evidence under `validation/evidence/`.
7. Update `STATUS.md` with the milestone result, exact evidence paths, blockers, and material decisions.
8. Commit a coherent checkpoint before moving to the next milestone.

Parallel research is acceptable when it cannot create conflicting implementations, but dependent implementation milestones should preserve the order in `GOAL.md` unless evidence justifies a deviation.

Do not create large append-only work logs. `STATUS.md` should remain a compact current-state summary, and validation evidence should contain only information needed to reproduce or audit a result.

## Evidence standard

A requirement is not "validated" merely because code exists or a file parses visually.

For each validation claim, record enough information to audit it later. Small committed evidence summaries should include, where applicable:

- gate or milestone identifier
- date/time
- git commit SHA or working-tree state
- OS/distribution and architecture
- relevant tool versions
- exact command(s)
- exit status
- concise observed result
- paths/hashes of important generated artifacts when useful
- whether the result is `validated`, `structurally_checked`, `experimental_unverified`, or `blocked`

Raw simulation outputs, compiler products, downloaded archives, OSDI binaries, and large logs should normally remain untracked. Store only compact summaries needed for auditability.

Never promote `structurally_checked` or `experimental_unverified` to `validated` without running the required real backend.

## Source acquisition and licensing

Third-party model acquisition is a gated operation.

Before copying a third-party model file into the repository:

1. identify the authoritative upstream project/source;
2. pin an exact revision, release, or commit whenever possible;
3. inspect the exact file-level header and applicable upstream license/redistribution terms;
4. record source URL, exact revision, imported path(s), license, modifications, and checksum(s) in provenance metadata;
5. preserve required notices and license text;
6. only then vendor the file.

Search-engine snippets, mirrors with unclear provenance, blog posts, generated license summaries, or assumptions based only on a repository root license are not sufficient evidence for redistribution rights.

If redistribution remains ambiguous after reasonable investigation, do not vendor the asset. Continue using a clearly redistributable alternative or an independently authored APM model as permitted by `GOAL.md`.

Do not publish PTM/PTM-MG model cards or use their numerical parameter decks as source material for APM022/APM016F.

## APM-authored model discipline

For APM022 and the APM016F parameter deck:

- write down the behavioral targets before tuning compact-model parameters;
- keep public literature/model-specification inputs auditable;
- distinguish published facts from engineering choices made by APM;
- avoid unexplained parameter fitting;
- retain model-generation notes/scripts needed to reproduce the committed parameter deck;
- never claim foundry or silicon correlation.

Do not tune an APM-authored deck merely until a test stops failing. Tests and model targets must represent the documented intended behavior.

## Benchmark variation discipline

The numerical benchmark-variation severities currently marked `TBD` are deliberately unfrozen.

Do not replace them with arbitrary convenient values.

Freeze them only after representative model families are operational and the effect of proposed values has been characterized. Record the rationale and observed impact when freezing a value.

Keep process/global, mismatch/local, N/P, and R/C correlation semantics explicit. Do not introduce undocumented correlation.

Development-time TBDs must not survive into release-critical model provenance, benchmark variation/passive configuration, or release metadata. The final release validator must treat unresolved release-critical placeholders as failure.

## Environment and dependency changes

Local installation of required development dependencies inside the designated WSL/EL9 environment is permitted.

Prefer reproducible, documented setup over ad-hoc machine modification.

Do not:

- modify unrelated host Windows settings;
- overwrite user-global simulator configuration;
- replace the user's shell configuration as an installation mechanism;
- require `/mnt/c` for source/build/run data;
- assume a tool feature exists without checking the installed version or authoritative documentation.

Use the distro package manager for ordinary build prerequisites when appropriate, but avoid replacing or removing unrelated user software. Prefer user-local prefixes for source-built simulator/compiler tooling when practical.

Pin model-engine/upstream revisions where reproducibility requires it. Record actual validated tool versions rather than claiming compatibility with untested versions.

## Blocker handling

A blocker is not a reason to stop all useful work.

When blocked:

1. determine whether the blocker is local, upstream, licensing-related, environment-related, or a real contradiction in the goal;
2. research authoritative alternatives;
3. continue independent milestones that do not depend on the blocker;
4. record the blocker clearly in `STATUS.md`;
5. do not fake or downgrade the blocked requirement.

Examples of genuine hard blockers include:

- required credentials unavailable to the execution environment;
- unresolved redistribution rights where no compliant alternative can be found;
- required real-tool validation impossible because the required tool/environment is unavailable and the Definition of Done explicitly requires it.

For Spectre, real validation is explicitly not a v1.0 release gate. If Spectre is unavailable, perform useful structural/static checks but keep the status `experimental_unverified` exactly as required by `GOAL.md`.

If a mandatory ngspice/WSL2 release gate cannot be validated, continue all other work but do **not** tag or declare v1.0.0 complete.

## Git discipline

Work in the existing repository and preserve reviewability.

- Make coherent milestone commits.
- Do not force-push or rewrite published history.
- Do not delete unrelated files or user work.
- Do not change repository visibility or security/account settings.
- Do not create a replacement repository because setup is inconvenient.
- Keep generated binaries, caches, downloaded archives, raw runs, and temporary fitting data out of git unless a small source artifact is intentionally part of the distribution.

A successful command is not sufficient reason to commit an artifact; commit only source, configuration, documentation, compact audit evidence, and legally redistributable model assets that belong in the distribution.

## Release-gate behavior

The stable machine-readable gate definition is `validation/release_gates.toml`.

During implementation, build the validation tooling so that a single release-oriented command, preferably:

```text
apm validate --release
```

can evaluate all automatically checkable mandatory gates and exits non-zero when any required automatically checkable gate fails.

Do not let that command report success merely because an unimplemented check was skipped. Required-but-manual gates must be represented separately and remain visibly incomplete until evidence exists.

The release-oriented validator must also reject at least:

- unresolved release-critical `TBD`, placeholder, or candidate-only provenance state;
- package/release metadata that does not identify the target as v1.0.0;
- missing required license/provenance evidence;
- a required gate with no evidence or an explicitly blocked status;
- Spectre claims stronger than the available evidence allows.

`STATUS.md` is a progress index, not proof. Evidence and actual test execution are proof.

## Final clean-clone protocol

Before v1.0.0 can be declared complete:

1. ensure the working repository has no unintended local-only dependencies;
2. create a genuinely fresh clone in a new directory on the WSL Linux filesystem;
3. follow only the documented installation/build instructions;
4. build required OSDI/model artifacts from source;
5. run `apm doctor`;
6. run the full automated validation suite;
7. run `apm validate --release` or the final equivalent;
8. run representative characterization/comparison commands for all five kits;
9. verify the provenance/license audit from the clean clone;
10. confirm no release-critical `TBD` or placeholder values remain;
11. confirm package/release metadata and release notes identify v1.0.0 consistently;
12. confirm README claims match actual evidence;
13. confirm Spectre remains labeled experimental/unverified unless separately validated;
14. confirm every mandatory `GOAL.md` gate has evidence;
15. only then prepare/tag v1.0.0.

If any mandatory gate fails, fix it and repeat the relevant clean-clone steps. Do not waive a gate solely because the run has already consumed substantial time.

## Completion report

At the end, leave the repository self-explanatory for a reviewer who did not observe development.

`STATUS.md` should summarize:

- final milestone states;
- validated environment/tool versions;
- release-gate result;
- known limitations;
- any explicitly deferred items allowed by `GOAL.md`;
- evidence locations.

The final result should be auditable from the repository without access to the agent's hidden reasoning or conversational history.
