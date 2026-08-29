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

## Mission

Implement `GOAL.md` faithfully and finish APM v1.0.0. Optimize for correctness, reproducibility, licensing clarity, and a small maintainable architecture.

## Scope discipline

Do not expand v1.0 scope beyond `GOAL.md` unless a required item cannot be implemented correctly without a narrowly-scoped change.

In particular, do not add layout, PCells, DRC, LVS, PEX, standard cells, MOS noise, RF devices, AMS, native Windows/macOS support, or Virtuoso automation.

## Platform

The validated reference environment is WSL2 + RHEL-compatible EL9 Linux, x86_64.

Keep project/build/run data on the Linux filesystem, not `/mnt/c`.

Automated tests and characterization must be headless.

Do not depend on xschem GUI state, `~/.spiceinit`, or other mutable user-global configuration.

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

## Variation

Keep APM benchmark variation and PDK-native variation distinct in code, metadata, plots, and documentation.

APM benchmark variation must use observable intents (`vth_shift`, `drive_shift`) rather than pretending raw compact-model knobs are universal physical quantities.

For ngspice benchmark MC, generate random samples in Python and run deterministic simulations. Persist seeds and resolved samples.

Do not make Verilog-A random functions a dependency of benchmark MC.

Do not finalize benchmark sigma values without empirical characterization of representative kits.

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

High autonomy is authorized for ordinary in-scope work: research, local dependency installation inside the designated WSL environment, implementation, testing, refactoring, debugging, documentation, and commits.

Stop/escalate only for a genuine blocker such as unresolved redistribution rights, unavailable required credentials, or an action that would modify unrelated user data.

## Completion

Do not declare v1.0 complete before every `GOAL.md` release gate is actually satisfied.
