# AGENTS.md

This file is mandatory repository policy for implementation agents.

## Repository identity

This repository is **Analog Process Models (APM)**:

- repository: `https://github.com/ds54e/analog-process-models`
- acronym: **APM = Analog Process Models**

Within this repository, APM always means this project. Work in this existing repository. Do not create or substitute another authoritative repository. Do not change repository visibility. Do not force-push or rewrite published history.

## Released baseline and current development line

APM v2.0.0 is released and immutable.

- released tag: `v2.0.0`
- released commit: `3cc6cfea4932cc40f2d693784d0a569926cdf399`
- post-release exact-tag requalification is recorded on `main` under `validation/evidence/v2_post_release_requalification.json`

Do not modify the v2 tag or reinterpret current v3 work as evidence that the v2 release was incomplete.

Current `main` is the post-v2 development line. The current goal is defined by `GOAL.md` and presently begins the v3 stationary small-signal MOS-noise characterization work.

## Mission

Implement the current `GOAL.md` faithfully.

For the current v3 phase, optimize for:

- physically and semantically honest noise-model claims;
- reproducible real-tool validation;
- explicit parameter-level noise provenance;
- machine-readable result semantics;
- reuse of the validated v2 manifest-driven family/device architecture;
- minimal disruption to the released v2 DC/Y/capacitance framework.

The current goal is an evidence-producing noise foundation/spike, not permission to tag v3.0.0. Do not change package/release version or create a v3 tag unless a later repository goal explicitly requires it.

## Required reading before substantive work

Read completely, in this order:

1. `AGENTS.md`
2. `GOAL.md`
3. `NOISE_CHARACTERIZATION.md`
4. `DEVICE_FAMILY_MODEL.md`
5. `RESULT_CONTRACT.md`
6. `PROJECT_CONTEXT.md`
7. `ENVIRONMENT.md`
8. `RESEARCH_BASELINE.md`
9. `UNATTENDED_EXECUTION.md`
10. `README.md`
11. `validation/release_gates.toml`
12. `STATUS.md`

Authority on conflict:

1. applicable safety/security requirements and explicit user instructions;
2. `AGENTS.md`;
3. `GOAL.md`;
4. `NOISE_CHARACTERIZATION.md` for noise work;
5. `DEVICE_FAMILY_MODEL.md`;
6. `UNATTENDED_EXECUTION.md`;
7. `RESULT_CONTRACT.md` for the existing v2 result domain;
8. `PROJECT_CONTEXT.md`;
9. `ENVIRONMENT.md`;
10. `RESEARCH_BASELINE.md`;
11. `README.md`.

Do not resolve a material conflict by silently dropping the harder requirement. Record material departures and evidence in `STATUS.md`.

## Reference environment and baseline reuse

Reuse the existing validated local development environment when present and valid:

- WSL2;
- AlmaLinux/RHEL-compatible EL9 x86_64;
- Python 3.9 baseline;
- ngspice 47 with OSDI/predictor support;
- project-local OpenVAF-ReLoaded;
- native BSIM3 and BSIM4;
- PSP103 OSDI;
- BSIM-CMG 112.1.0 OSDI.

Do not gratuitously rebuild ngspice/OpenVAF or rediscover solved bootstrap work. If the toolchain is missing, corrupted, or incompatible with the current work, repair/rebuild it reproducibly.

For required noise `.noise` validation, use the normal Sparse solver path; do not use KLU as the required reference noise solver.

The v2 release evidence remains historical release evidence. New v3 noise claims require new current evidence.

## Stable v2 architecture boundary

Preserve the released manifest-driven domain model:

`Technology -> Electrical Family -> Device`

with orthogonal:

- Operating Profile;
- Backend Binding;
- Variation;
- Comparison Set.

Do not reintroduce technology-specific normal-family loaders or collapse electrical family, voltage profile, gate stack, threshold class, backend, and usage labels into one type string.

Public geometry remains native:

- planar devices: `w`, `l`;
- FinFET devices: `l`, `nfin`.

Do not invent a common effective width for FinFETs. Do not expose a fake universal compact-model parameter API.

The existing v2 characterization/result domain remains valid. Prefer a separate noise schema/domain, e.g. `apm.noise-characterization.v1`, instead of unnecessarily rewriting `apm.characterization.v2`.

## Noise characterization policy

Follow `NOISE_CHARACTERIZATION.md`.

Core rules:

- simulator execution is not a calibration claim;
- distinguish backend capability from model/noise-parameter fidelity;
- preserve parameter-level effective-value provenance;
- distinguish explicit model-card values from compact-model/backend defaults;
- canonical cross-engine comparison uses external-terminal observables, not raw compact-model internal source names;
- do not call APM-authored default-noise behavior silicon-correlated or process-calibrated;
- do not tune APM350/APM022/APM016F process-noise coefficients merely to make spectra look plausible or to pass the initial spike;
- preserve raw source breakdown as backend evidence without forcing false cross-engine source equivalence;
- fail closed when a bias target, fit, parameter snapshot, or backend capability cannot be established.

The initial v3 spike must validate the harness before trusting MOS spectra, including analytic resistor noise, transparent current probing, OSDI white/flicker sources, and an analytic correlated-noise network.

## APM-authored family independence

APM022 and APM016F remain independently authored generic models.

Official PTM/PTM-MG parameter cards must not be copied, transcribed, interpolated, optimized against as a numeric fitting target, or used as numeric source material for APM-authored decks/variants. Public literature/open models may be used to understand qualitative behavior or later generic behavior envelopes, subject to licensing/provenance rules.

APM022 LVT/HVT remain threshold-isolated variants around SVT. APM016F LVT/HVT remain documented PHIG/workfunction-dominant variants around SVT.

Noise characterization of those variants must not be generalized into a claim that real foundry Vt options share the same noise coefficients.

## Characterization and bias policy

Existing canonical gm/gds remain terminal finite differences. Internal simulator OP quantities remain oracles unless an explicit contract says otherwise.

For noise equal-inversion points, do not merely take the nearest old DC sweep row. Resolve the requested gm/Id target using existing DC data as a bracket, re-run/recompute the operating point and finite-difference gm/gds, and persist the achieved target/error diagnostics.

Preserve raw signed terminal quantities separately from canonical magnitude/comparison quantities.

For noise, preserve the actual complex gate-to-drain small-signal transfer used for input-referred results. Do not assume `gm` alone is the full transfer at high frequency.

## Variation boundary

Keep APM Benchmark Global/Local/All and upstream/native variation distinct.

The initial v3 noise phase does not add noise-coefficient variation, noise mismatch, or benchmark noise-correlation models. Do not invent them from the existing v2 Vth/drive benchmark variation.

## Licensing and provenance

License correctness remains mandatory.

Before vendoring any new third-party asset:

1. identify the authoritative upstream source;
2. pin the exact revision;
3. inspect exact file-level licensing/redistribution terms;
4. record source URL/revision/path/hash/modifications;
5. preserve notices/license text;
6. only then ship the asset.

Do not infer file rights from a repository root license when model-specific terms may differ. Do not relicense third-party assets. If rights remain ambiguous, do not ship the file.

Never commit proprietary PDK content, credentials, tokens, passwords, or user secrets.

The current noise spike should not require new third-party model assets; prefer the already vendored/pinned v2 engines and cards.

## Spectre boundary

ngspice remains the validated reference backend.

Spectre remains model-only **experimental/unverified** unless a real Spectre environment actually validates it. The v3 noise spike does not promote Spectre to a validated noise backend.

Do not add SKILL, CDF, symbols, OA libraries, ADE/Maestro state, OCEAN, or Virtuoso automation unless a later explicit goal requires them.

## Scope exclusions for the current v3 phase

Unless `GOAL.md` explicitly expands them, the current phase excludes:

- layout/PCells/DRC/LVS/PEX;
- standard cells;
- new RF/layout/isolation device families;
- transient noise and RTS;
- PSS/PNoise and oscillator phase noise;
- RF noise figure/NFmin as a required metric;
- a canonical full four-terminal noise-correlation matrix;
- noise variation/mismatch/correlation models;
- APM016F thick-oxide/high-voltage I/O;
- native Windows/macOS reference support;
- real Spectre validation;
- Virtuoso automation.

Do not expand scope because an upstream PDK/model happens to support additional effects.

## Tests and evidence

Prefer property/regression/analytic-reference tests over fragile exact snapshots.

Do not weaken legitimate tests to match broken behavior.

Every validated v3 noise spike claim must have compact auditable evidence under `validation/evidence/` or another explicitly documented current evidence path. Missing evidence is not pass.

Audit simulator logs for critical diagnostics, unsupported parameters/features, convergence failures, or silent fallback behavior.

Do not replace failed fit/bias/capability results with clipped or fabricated values. Persist explicit failure status.

The existing `validation/release_gates.toml` defines the already released v2 gate contract. Do not rewrite history by making those old v2 gates pretend to be v3 gates. Introduce new v3/spike validation structures only when implementation requires them.

## Git and autonomy

High autonomy is authorized for in-scope research, local dependency installation/repair, implementation, refactoring, simulations, tests, documentation, coherent commits, and pushes.

Do not force-push. Do not change repository visibility/security settings. Do not move or rewrite released tags.

Stop/escalate only for a genuine blocker such as unresolved redistribution rights, unavailable required credentials, or a real contradiction in the normative current contract.

## Completion for the current goal

The current goal is complete only when:

- every required item in `GOAL.md` and the initial-spike acceptance criteria in `NOISE_CHARACTERIZATION.md` has real-tool evidence;
- the harness itself is analytically validated before MOS results are accepted;
- all four required compact-model engine paths execute the provisional noise experiment;
- effective noise parameters/provenance are captured without overstating calibration;
- unresolved frequency/fit/correlation decisions are explicitly reported rather than guessed;
- v2 release/tag/evidence remain untouched;
- no v3 release/tag is created from the spike alone.
