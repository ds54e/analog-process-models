# AGENTS.md

This file is mandatory repository policy for implementation agents.

## Repository identity

This repository is **Analog Process Models (APM)**:

- repository: `https://github.com/ds54e/analog-process-models`
- acronym: **APM = Analog Process Models**

Within this repository, APM always means this project. Do not reinterpret it as an unrelated product, package, Microsoft technology, or application-performance-monitoring system.

Work in this existing repository. Do not create or substitute another authoritative repository. Do not change repository visibility. Do not force-push or rewrite published history.

The tagged `v1.0.0` release is the validated historical baseline. Current `main` is the breaking APM v2 development line. The v1 tag is immutable history, not a compatibility requirement for v2.

## Mission

Implement the current `GOAL.md` faithfully and deliver **APM v2.0.0**.

Optimize for:

- physically and semantically honest device-family modeling;
- reproducible real-tool validation;
- explicit provenance and licensing boundaries;
- machine-readable result semantics;
- a small manifest-driven architecture that can grow without technology-specific Python branches.

Completion is evidence-based. Do not tag or declare v2.0.0 complete unless every required gate in `validation/release_gates.toml` has actually passed with the required evidence.

## Required reading before substantive work

Read completely, in this order:

1. `AGENTS.md`
2. `GOAL.md`
3. `DEVICE_FAMILY_MODEL.md`
4. `RESULT_CONTRACT.md`
5. `PROJECT_CONTEXT.md`
6. `ENVIRONMENT.md`
7. `RESEARCH_BASELINE.md`
8. `UNATTENDED_EXECUTION.md`
9. `README.md`
10. `validation/release_gates.toml`
11. `STATUS.md`

Authority on conflict:

1. applicable safety/security requirements and explicit user instructions
2. `AGENTS.md`
3. `GOAL.md`
4. `DEVICE_FAMILY_MODEL.md`
5. `UNATTENDED_EXECUTION.md`
6. `RESULT_CONTRACT.md`
7. `PROJECT_CONTEXT.md`
8. `ENVIRONMENT.md`
9. `RESEARCH_BASELINE.md`
10. `README.md`

Do not resolve a material conflict by silently dropping the harder requirement. Record material departures and evidence in `STATUS.md`.

## v1 baseline reuse versus v2 validation

The v1.0.0 implementation established a useful validated development baseline: WSL2 + AlmaLinux/RHEL-compatible EL9 x86_64, ngspice 47 with OSDI, project-local OpenVAF-ReLoaded, PSP103 OSDI, BSIM-CMG OSDI, and a working Python environment.

During v2 development, reuse the existing project-local `.apm` toolchain, generated OSDI artifacts, caches, and `.venv` when they are present and still match the recorded versions/hashes. Do not gratuitously rebuild ngspice/OpenVAF or rediscover solved bootstrap work.

However:

- v1 validation evidence does **not** satisfy v2 release gates;
- changed v2 model/family paths must be re-exercised with real tools;
- the final v2 release still requires a genuinely fresh clone and documented clean-clone validation from source;
- if the existing local toolchain is missing, corrupted, or incompatible with v2 changes, repair or rebuild it reproducibly rather than pretending it is valid.

## Breaking redesign policy

APM v2 is intentionally allowed to break v1 interfaces because v1 has not been publicly adopted as a compatibility contract.

Do not preserve obsolete v1 structures merely for compatibility. By v2 release, remove superseded canonical sources of truth, including where applicable:

- one-family-per-technology `kit.toml` manifests;
- technology-specific characterization loaders/branches that the v2 catalog makes unnecessary;
- v1 public aliases such as unqualified `apm045_nmos` when a family-qualified v2 name replaces them;
- v1 result schemas as the current runtime output contract;
- v1 benchmark adapter/config schemas as the current benchmark contract.

Historical v1 source and evidence remain available from the `v1.0.0` tag. Do not maintain a dual-schema compatibility layer unless `GOAL.md` explicitly requires one.

## Device-family architecture

Follow `DEVICE_FAMILY_MODEL.md`.

The core domain model is:

`Technology -> Electrical Family -> Device`

with these orthogonal concepts:

- Operating Profile
- Backend Binding
- Variation
- Comparison Set

Do not collapse these concepts into one device-type string.

Important boundaries:

- Electrical Family means a distinct nominal electrical model/parameterization identity.
- Family IDs are technology-local; cross-technology semantics come from explicit metadata.
- `core`, `io`, `analog`, `rf`, `standard-cell`, and similar usage labels are not primary electrical-family identities.
- gate-stack class, threshold class, operating voltage/profile, and isolation/layout view are distinct concepts.
- do not require every family to contain both N and P devices;
- do not treat an RF/layout/isolation view as a new electrical family without electrical-model evidence;
- do not infer undocumented voltage limits, reliability/breakdown guarantees, or family-to-family statistical correlation.

The v2 implementation must be manifest-driven. Adding a normal new technology/family/device should not require a new technology-specific loader or large `if/elif` branch in characterization/benchmark code.

Avoid speculative plugin systems. The manifest-driven abstraction is justified by the concrete v2 family set; keep the implementation straightforward.

## Public model boundaries

Do not force BSIM3, PSP103, BSIM4, and BSIM-CMG raw parameter APIs into a fake universal compact-model API.

Commonize terminal characterization and result semantics, not compact-model knobs.

Public sizing remains geometry-native:

- planar devices: `w`, `l`
- FinFET devices: `l`, `nfin`

Do not invent a universal effective width for FinFETs. Do not expose common `m`, `nf`, `ng`, or finger/layout semantics in the v2 common interface.

Use APM-owned, family-qualified public wrapper names.

## APM-authored family independence

APM022 and APM016F remain independently authored generic models.

Official PTM/PTM-MG parameter cards must not be copied, transcribed, interpolated, optimized against as a numeric fitting target, or used as numeric source material for APM-authored decks/variants. They may be local, non-redistributed sanity oracles only.

For generic multi-Vt families:

- APM022 `lvt`/`hvt` are controlled APM-derived variants around the `svt` basis and must be documented as threshold-isolated generic variants, not foundry options.
- APM016F `lvt`/`hvt` are workfunction-dominant generic variants around the `svt` basis. Start with gate-workfunction adjustment and permit only evidence-backed minimal secondary parameter changes when terminal behavior requires them.

Write behavioral targets before tuning parameters. Keep published facts separate from APM engineering choices. Never claim foundry or silicon correlation for APM-authored families.

## Characterization policy

Canonical gm/gds come from terminal finite differences. Internal simulator OP quantities are validation oracles only.

Canonical capacitance comes from the terminal AC Y matrix. Preserve all 16 complex entries and the measurement convention.

Preserve raw signed simulator quantities separately from canonical positive-magnitude N/P comparison quantities.

Required v2 characterization extends v1 with family-oriented metrics including Ion, Ioff, log10(Ion/Ioff), and subthreshold swing. Do not freeze a dubious SS extraction window merely to satisfy implementation progress; use native-family data to select and document a robust method before release.

Use comparison modes appropriate to the question:

- cross-technology anchor comparison;
- equal-bias threshold-family comparison;
- equal-inversion comparison, typically around documented gm/Id;
- native-profile gate-stack comparison;
- explicitly documented common-overlap-bias gate-stack comparison.

Do not compare unrelated voltage/gate-stack families as though a normalized VDD view alone removes all physical differences.

## Variation policy

Keep APM synthetic benchmark variation and upstream/native variation distinct in code, metadata, plots, and documentation.

APM v2 benchmark terminology is:

- **Benchmark Global** — synthetic die-wide/common observable stress;
- **Benchmark Local** — synthetic instance-local mismatch stress;
- **Benchmark All** — Global + Local.

These names deliberately avoid claiming that Benchmark Global represents a physically correct foundry process-correlation model.

Canonical MOS benchmark intents remain observable `vth_shift` and `drive_shift`, not universal raw compact-model parameters.

For v2 multi-family technologies, a technology/polarity benchmark Global latent stress is shared across its electrical families and each family uses its own calibrated raw adapter. This is a common comparison stress, not a claim of real full family-to-family correlation.

Do not invent numeric partial-correlation coefficients. Preserve a latent-variable namespace that can be extended later if evidence supports residual family-specific terms.

Benchmark Local remains per-instance with the explicit synthetic matching law. Upstream/native family-to-family correlation must not be invented when upstream does not provide it.

Generate ngspice benchmark randomness in Python, persist seeds/latents/resolved samples, and keep replay deterministic.

## Licensing and provenance

License correctness is a release gate.

Before vendoring any new third-party family/model file:

1. identify authoritative upstream source;
2. pin exact revision;
3. inspect exact file-level header and applicable license/redistribution terms;
4. record source URL/revision/path/hash/modifications;
5. preserve notices and license text;
6. only then ship the asset.

Do not infer file rights from a repository root license when model-specific terms may differ. Do not relicense third-party assets. If rights remain ambiguous, do not ship the file.

Prefer preserving the already validated v1 upstream revisions when the required v2 family assets exist in the same pinned snapshots; avoid revision churn without a technical or licensing reason.

Never commit proprietary PDK content, credentials, tokens, passwords, or user secrets.

## Spectre boundary

ngspice remains the validated reference backend.

Spectre support remains model-only **experimental/unverified** unless a real Spectre environment actually validates it. Do not claim real Spectre parsing or numerical validation from static inspection.

Virtuoso integration remains user-managed. Do not add SKILL, CDF, symbols, OA libraries, ADE/Maestro state, OCEAN, or Virtuoso automation in v2.

## Scope exclusions

Unless `GOAL.md` explicitly changes them, v2 still excludes:

- layout/PCells/DRC/LVS/PEX;
- standard cells;
- RF-specific model/view support;
- MOS noise as a required cross-family characterization metric;
- APM016F thick-oxide/high-voltage I/O family;
- native Windows/macOS reference support;
- Virtuoso automation.

Do not expand scope because an upstream PDK happens to contain additional devices.

## Tests and evidence

Prefer property/regression tests over fragile exact snapshots.

Do not weaken legitimate tests to match broken behavior.

Every validated milestone/gate must have compact auditable evidence under `validation/evidence/` or another explicitly documented v2 evidence path. Missing evidence is not pass.

A release-oriented command, preferably `apm validate --release`, must fail closed if any required v2 automatic gate is failed, skipped, unimplemented, or evidence-free.

The existing v1 release validator may intentionally fail immediately after the v2 specification commit; that is expected until Codex migrates it. Do not weaken v2 gates merely to restore old v1 green status.

## Git and autonomy

High autonomy is authorized for in-scope research, local dependency installation/repair, implementation, refactoring, simulations, tests, documentation, commits, and pushes.

Keep coherent milestone commits. Do not force-push. Do not alter repository visibility/security settings.

Stop/escalate only for a genuine blocker such as unresolved redistribution rights, unavailable required credentials, or a real contradiction in the normative v2 contract.

## Completion

Do not tag v2.0.0 until:

- all v2 release gates pass with current evidence;
- obsolete v1 canonical SSOT/compatibility artifacts forbidden by the v2 contract are removed from current main;
- all release-critical research-dependent values are frozen with evidence or the corresponding feature is legitimately removed from scope;
- package/runtime/release metadata consistently identify 2.0.0;
- a fresh clone on the required WSL2/EL9 reference environment builds/validates from source;
- README/release claims match evidence;
- Spectre remains correctly bounded as experimental/unverified unless genuinely validated.
