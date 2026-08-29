# AGENTS.md

This file is mandatory repository policy for implementation agents.

## Repository identity

This repository is:

- **Name:** `analog-process-models`
- **GitHub:** `https://github.com/ds54e/analog-process-models`
- **Project acronym:** **APM = Analog Process Models**

Within this repository, **APM always means this project, Analog Process Models**. It is a project-local acronym, not an external product, Microsoft technology, application-performance-monitoring product, package, or third-party framework.

Do **not** web-search for a pre-existing software product named "APM" in order to implement this repository. When external research is needed, search for the specific compact model, process model, simulator, or upstream source named in `GOAL.md` (for example IHP SG13G2, FreePDK45, BSIM4, BSIM-CMG, ngspice, OpenVAF, Spectre).

The repository itself and `GOAL.md` are authoritative for the meaning and scope of APM.

Work in this existing repository. Do not create, migrate to, or substitute another repository or fork as the project authority. Do not change repository visibility. Tag/release v1.0.0 only after the `GOAL.md` release gates are actually satisfied.

## Mission

Implement `GOAL.md` faithfully and finish APM v1.0.0. Optimize for correctness, reproducibility, licensing clarity, and a small maintainable architecture.

## Unattended execution

Assume normal implementation may run for a long time without human supervision.

Before substantive work, read all of:

1. `GOAL.md`
2. `AGENTS.md`
3. `UNATTENDED_EXECUTION.md`
4. `README.md`
5. `validation/release_gates.toml`
6. `STATUS.md`

Follow `UNATTENDED_EXECUTION.md` as the required long-running execution procedure.

Keep `STATUS.md` current at milestone boundaries so work can be safely resumed after interruption. `STATUS.md` is only a progress index; it never substitutes for actual validation evidence.

Write compact auditable validation summaries under `validation/evidence/` as milestones and release gates are completed. Do not mark missing, skipped, static-only, or unavailable real-tool checks as validated.

The machine-readable v1.0 release-gate contract is `validation/release_gates.toml`. Implementation may extend the validator around this file, but must not weaken or silently omit required gates.

Design the final validation flow so a single release-oriented command, preferably `apm validate --release`, exits non-zero whenever any automatically checkable required gate fails or remains unimplemented.

Do not declare or tag v1.0.0 merely because the agent has reached the end of its run. Completion is evidence-based.

## Scope discipline

Do not expand v1.0 scope beyond `GOAL.md` unless a required item cannot be implemented correctly without a narrowly-scoped change.

In particular, do not add layout, PCells, DRC, LVS, PEX, standard cells, MOS noise, RF devices, AMS, native Windows/macOS support, or Virtuoso automation.

## Platform

The validated reference environment is WSL2 + RHEL-compatible EL9 Linux, x86_64.

Keep project/build/run data on the Linux filesystem, not `/mnt/c`.

Automated tests and characterization must be headless.

Do not depend on xschem GUI state, `~/.spiceinit`, or other mutable user-global configuration.

A container or CI job running EL9 may supplement testing, but it does **not** replace the v1.0 clean-clone validation on the designated WSL2 + EL9 environment.

## Simulator architecture

ngspice is the validated v1.0 reference simulator.

Use native compact models where appropriate and OSDI for Verilog-A compact models where required.

Do not create unnecessary simulator abstraction layers before a second concrete backend requires them.

Spectre support is model-only, experimental, and unverified. Never state or imply that Spectre output has been validated unless it actually has been tested in a real Spectre environment.

Virtuoso integration is user-managed. Do not implement SKILL, CDFs, symbols, OA libraries, ADE/Maestro setup, or OCEAN.

## Model boundaries

Do not force BSIM3, PSP103, BSIM4, and BSIM-CMG into one fake common compact-model API.

The stable cross-technology contract is terminal-level characterization and result semantics, not raw compact-model parameters.

Do not expose multiplicity/finger semantics (`m`, `nf`, `ng`) in the common v1.0 public device interface.

Planar public sizing: `w`, `l`.

FinFET public sizing: `l`, `nfin`.

Use explicit public names for model wrappers/devices; do not expose ambiguous upstream names as the APM user contract.

## APM022 and APM016F independence

APM022 and the APM016F parameter deck must be independently authored.

Do not copy, transcribe, numerically interpolate, optimize directly against, or derive parameter values from official PTM/PTM-MG model cards.

PTM/PTM-MG may only be used locally as non-redistributed sanity/comparison oracles.

Use public literature, compact-model specifications, representative published characteristics, and explicit APM behavior contracts as model-development inputs.

Document model-generation inputs and decisions.

## Characterization

Canonical gm/gds are terminal finite-difference quantities. Internal simulator OP names are optional validation oracles only.

Canonical capacitance is derived from terminal AC admittance/Y data. Do not make internal `cgg/cgd/cgs` fields the stable API.

Store enough raw data and metadata that derived metrics can be recalculated later.

Cross-process comparisons should prefer normalized coordinates such as `L/Lmin`, `VDS/VDD`, and `gm/Id` rather than identical absolute geometry/bias.

Preserve raw signed simulator terminal quantities. For cross-technology N/P comparison, use an explicitly documented effective-voltage/current-magnitude convention so PMOS/PFET metrics are not accidentally sign-inverted. Do not silently mix raw signed values with positive-magnitude comparison metrics.

For Y-matrix extraction, document terminal order, excitation convention, current sign convention, reference node, frequency, and conversion from Y to reported capacitances. Raw complex Y data is authoritative.

## Variation

Keep APM benchmark variation and PDK-native variation distinct in code, metadata, plots, and documentation.

APM benchmark variation must use observable intents (`vth_shift`, `drive_shift`) rather than pretending raw compact-model knobs are universal physical quantities.

For ngspice benchmark MC, generate random samples in Python and run deterministic simulations. Persist seeds and resolved samples.

Do not make Verilog-A random functions a dependency of benchmark MC.

Do not finalize benchmark sigma values without empirical characterization of representative kits.

Do not invent undocumented statistical correlation. Benchmark process variables, mismatch variables, and R/C variation must have explicit correlation/independence semantics in the benchmark specification.

Spectre benchmark MC may use Spectre's own random sampling and therefore does not need seed-for-seed identity with the ngspice Python sampler in v1.0. The required contract is matching intended distributions, geometry scaling, and correlation semantics; fixed-sample cross-simulator conformance can be added later.

## Licensing

License correctness is a release gate, not cleanup work.

Before vendoring any third-party model file, verify its exact file-level redistribution terms from authoritative sources.

Never infer that every file inherits a repository root license if model-specific headers or terms may differ.

Do not relicense third-party code/model files.

Preserve upstream notices and use SPDX/REUSE-compatible metadata where practical.

If rights are ambiguous, do not ship the file. Find a clearly redistributable alternative or replace it with an independently authored APM asset.

Never commit proprietary PDK content, credentials, tokens, passwords, or user secrets.

## Tests

Prefer property/regression tests over fragile exact numerical snapshots.

Do not weaken or delete a legitimate test simply to make CI pass.

When a model/upstream revision changes results, investigate and document the cause.

Use exact snapshots only as secondary review signals unless a value is truly part of the public contract.

## Implementation style

Keep the repository small and explicit.

Avoid speculative plugin systems, generic factories, framework layers, and premature abstraction.

When adding a new abstraction, point to at least two concrete use cases that require it.

Prefer straightforward Python, TOML, SPICE/Spectre model files, and small shell helpers.

Generated OSDI binaries and large simulation results should normally remain untracked.

## Autonomy

High autonomy is authorized for ordinary in-scope work: research, local dependency installation inside the designated WSL environment, implementation, testing, refactoring, debugging, documentation, commits, and pushes to this repository.

Stop/escalate only for a genuine blocker such as unresolved redistribution rights, unavailable required credentials, or an action that would modify unrelated user data.

Do not change repository visibility or security-sensitive repository/account settings as part of autonomous implementation.

## Completion

Do not declare v1.0 complete before every `GOAL.md` release gate is actually satisfied and the required release evidence is present.
