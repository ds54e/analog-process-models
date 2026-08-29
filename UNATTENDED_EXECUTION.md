# Unattended Execution Protocol for APM v2

This document defines how a long-running autonomous implementation agent should execute the current v2 `GOAL.md` after the v1.0.0 baseline has already been completed.

It is process guidance, subordinate to `AGENTS.md`, `GOAL.md`, and `DEVICE_FAMILY_MODEL.md`.

## 1. Authority

Use this order on conflict:

1. safety/security requirements and explicit user instructions
2. `AGENTS.md`
3. `GOAL.md`
4. `DEVICE_FAMILY_MODEL.md`
5. this file
6. `RESULT_CONTRACT.md`
7. `PROJECT_CONTEXT.md`
8. `ENVIRONMENT.md`
9. `RESEARCH_BASELINE.md`
10. `README.md`

Do not silently weaken a requirement. Record material departures and evidence in `STATUS.md`.

## 2. Continuation context: do not throw away solved v1 work

v2 is expected to begin in the same WSL2/AlmaLinux working environment that successfully completed v1.0.0.

The implementation agent may have a compacted continuation of the v1 Codex session. Treat repository files as the authoritative contract, while retaining useful operational knowledge from the v1 run.

Before rebuilding anything, inventory the existing local project state:

- `.apm/toolchain`;
- generated OSDI artifacts;
- `.venv`;
- ngspice/OpenVAF/LLVM/Rust versions;
- current `apm doctor` behavior;
- current git status/origin/HEAD.

If the existing toolchain matches the validated v1 baseline and works, reuse it for v2 development. Do not rebuild ngspice 47/OpenVAF merely to reenact M0.

The final v2 release must still rebuild/validate from a genuinely fresh clone. Development reuse and release reproducibility are separate questions.

## 3. Startup sequence after v2 specification pull

1. Confirm repository origin is `https://github.com/ds54e/analog-process-models`.
2. Inspect `git status`; preserve user changes.
3. Read all required files listed in `AGENTS.md` completely.
4. Confirm `STATUS.md` says v2 is not yet release-eligible and that v1 evidence is historical baseline only.
5. Inventory/reuse the existing validated local toolchain.
6. Run a lightweight baseline smoke such as current `apm doctor` if practical before large migration; record failures as v2 migration work rather than rebuilding blindly.
7. Inspect current v1 code architecture and identify obsolete canonical SSOT that v2 will replace.
8. Start V2-M0. Do not stop at a migration plan.

The specification commit intentionally makes current `main` a v2-development branch while implementation still reflects v1. Existing v1 tests/release validation may fail until migrated. This is expected and must not be “fixed” by weakening v2 requirements.

## 4. v1 evidence handling

Historical v1 evidence remains useful for:

- toolchain versions/build methods;
- known simulator quirks;
- v1 model/provenance hashes;
- current family baseline terminal behavior;
- reproducible bootstrap knowledge.

It does **not** automatically validate:

- v2 manifests/domain architecture;
- new LV/HV/Vt/THKOX families;
- v2 Ion/Ioff/SS methodology;
- v2 Benchmark Global/Local/All semantics;
- v2 family-specific adapters;
- v2 public device names/result schemas;
- v2 clean-clone release.

When reusing a v1 asset unchanged, explicitly bind v2 evidence to its unchanged hash/revision plus current v2 integration test rather than rerunning irrelevant research.

## 5. Milestone loop

For each V2-M0 through V2-M9 milestone:

1. re-read the relevant `GOAL.md` section and `DEVICE_FAMILY_MODEL.md` boundary;
2. re-check any dated upstream fact that becomes a new vendored file, frozen profile, generic target, or release claim;
3. implement the smallest complete milestone design;
4. run real simulator/tool checks as soon as meaningful;
5. investigate failures rather than weakening properties;
6. record compact evidence under `validation/evidence/` using clearly v2-labeled filenames;
7. update `STATUS.md` with current milestone, evidence, blockers, and material decisions;
8. commit a coherent checkpoint;
9. continue unless there is a genuine blocker.

Do not create a large narrative work log. `STATUS.md` is an index; evidence files hold reproducible claims.

## 6. V2-M0 migration discipline

Migrate architecture before multiplying family-specific code.

The target is a straightforward manifest-driven catalog, not a plugin framework.

V2-M0 should:

- introduce semantic Technology/Family/Device/OperatingProfile/Validity structures;
- introduce simulator Backend Binding data;
- migrate the existing five representative v1 families first;
- prove generic discovery and generic characterize dispatch;
- preserve current numerical behavior sufficiently to detect migration regressions;
- add fixture-based tests proving a normal new family does not require a new production technology loader.

Do not immediately add 13 special-case loaders and plan to “generalize later”.

During migration, old and new structures may coexist temporarily. By v2 release, obsolete v1 canonical SSOT/aliases required to be removed by `GOAL.md` must be gone from current runtime.

## 7. Native-family implementation discipline

Implement APM130 LV/HV before generic multi-Vt variants because it stresses real architecture differences:

- distinct gate-stack/operating profiles;
- N/P-specific Lmin for HV;
- upstream corners/statistical/mismatch;
- same pinned IHP source lineage.

Then implement APM045 VTL/VTG/VTH/THKOX to establish real multi-Vt/gate-stack characterization.

Do not decide generic APM022/APM016F Vt spacing before these native/open data exist.

## 8. Upstream acquisition/licensing

Before adding a third-party family/model file:

1. identify authoritative upstream source;
2. prefer the already pinned v1 revision if the file exists there;
3. inspect exact pinned file header/terms;
4. hash the file;
5. record provenance/license/notice requirements;
6. vendor only if redistribution is clear.

Repository-root licensing alone is insufficient when model-file provenance/terms may differ.

Do not upgrade IHP/FreePDK45 revisions merely for freshness. Upgrade only for a documented technical/licensing reason and rerun affected provenance/behavior validation.

## 9. Research-dependent values

The following are deliberate research tasks, not permission to choose convenient constants:

- THKOX operating profile;
- common-overlap gate-stack bias;
- SS extraction method/window;
- generic APM022 Vt spacing;
- generic APM016F Vt spacing/secondary adjustments;
- v2 benchmark severity and adapter coefficients.

For each:

1. gather primary/open evidence;
2. distinguish observed evidence from inference;
3. characterize with current real-tool framework;
4. surface plausible alternative choices;
5. choose a simple documented value/method;
6. freeze it in machine-readable config plus evidence;
7. add tests for the frozen semantic contract.

No release-critical TBD may remain at v2.0.0.

## 10. Generic APM variant discipline

### APM022

Start from SVT. Define observable LVT/HVT targets before changing card parameters. Prefer threshold-isolated changes. Secondary changes require explicit evidence/rationale.

Do not use PTM cards as numeric source/fitting target.

### APM016F

Start from SVT. Use PHIG/workfunction as dominant control. Validate terminal behavior. Make secondary changes only when necessary and justified. Do not copy ASAP7/PTM-MG numeric parameters.

For both technologies, tests should enforce intended nominal ordering for Vth/Ion/Ioff but must not invent universal monotonic ordering of every secondary metric.

## 11. Characterization-method freeze discipline

Ion/Ioff definitions are already specified in `RESULT_CONTRACT.md`.

SS method is not yet frozen. Use APM130/APM045 real family curves to compare candidate methods. A good final method must:

- be deterministic;
- be applicable across the required model families;
- record its extraction window and quality diagnostics;
- fail visibly when insufficient subthreshold range exists;
- avoid device-specific silent window manipulation.

Once chosen, freeze/version it and rerun all families.

## 12. Benchmark v2 discipline

Do not rename modes only cosmetically. Migrate sample/config/result semantics to Global/Local/All.

Global:

- draw technology/polarity observable latents;
- share the latent across the technology’s relevant families;
- resolve through family/device-specific calibrated adapters;
- document that this is synthetic common stress, not real family correlation.

Local:

- instance-local;
- deterministic Python sampling;
- explicit matching-size law.

All:

- Global + Local with documented composition.

Persist latents and resolved sample identity. Never introduce hidden correlation.

Re-evaluate v1 sigma/corner strength only after enough family adapters exist. If retaining v1 values, record evidence that they remain sensible rather than treating history as proof.

## 13. Tests/evidence standard

A v2 requirement is not validated because:

- old v1 evidence passed;
- a manifest exists;
- a model file visually parses;
- a static Spectre check passed;
- the agent says the behavior is plausible.

Evidence should include as applicable:

- milestone/gate ID;
- date/time;
- git commit/working state;
- tool versions;
- exact commands;
- exit status;
- concise measured observations;
- report/artifact hashes;
- evidence status (`validated`, `structurally_checked`, `experimental_unverified`, `blocked`).

Large raw results stay untracked; commit compact summaries and reproducible source/config.

## 14. Blockers

When blocked:

- classify the blocker (licensing/upstream/model/runtime/spec contradiction);
- investigate compliant alternatives;
- continue independent work;
- record exact blocker/evidence in `STATUS.md`;
- never waive a gate because substantial work has already been done.

Spectre real execution remains explicitly non-required; keep it experimental/unverified if unavailable.

## 15. Git discipline

- coherent milestone commits;
- no force push/history rewrite;
- preserve unrelated user work;
- no repository visibility/security changes;
- no generated OSDI/raw/log/cache commits unless intentionally required source evidence;
- do not create a replacement repository.

## 16. Release-validator migration

The authoritative v2 gate file is `validation/release_gates.toml`.

Current v1 release-validator code is expected to become stale immediately after the v2 specification commit. Migrate it deliberately.

The final `apm validate --release` (or documented equivalent) must:

- verify implemented required gate IDs exactly match required contract IDs;
- fail on missing/skipped/unimplemented/evidence-free gates;
- regenerate current real-tool family validation rather than trusting old milestone reports;
- verify current v2 result/manifest schemas;
- reject obsolete v1 canonical SSOT/public alias requirements forbidden by v2;
- audit licensing/provenance/distribution/claims;
- require exact-commit clean-clone attestation.

## 17. Final clean-clone protocol

Before v2.0.0:

1. start from a genuinely fresh network clone on the WSL Linux filesystem;
2. attest clean origin/path/commit/platform before bootstrap state exists;
3. follow only documented setup;
4. build/reconstruct required ngspice/OpenVAF/OSDI artifacts from source/cache rules allowed by release docs;
5. run doctor;
6. run complete tests/lint/REUSE/provenance/distribution audits;
7. run full all-technology/all-family characterization and comparisons;
8. run Benchmark Global/Local/All validations;
9. run APM130 upstream LV/HV variation validation;
10. run Spectre structural checks with explicit unverified boundary;
11. run fail-closed `apm validate --release`;
12. verify package/runtime/changelog version 2.0.0;
13. verify no release-critical TBD/obsolete-v1 SSOT remains;
14. verify README/claim review;
15. only then tag `v2.0.0`.

## 18. Completion report

Leave `STATUS.md` concise and current with:

- v1 baseline reference;
- v2 milestone states;
- validated development/reference toolchain;
- v2 release-gate status;
- known limitations/deferred scope;
- evidence index;
- final release commit/tag state.

The repository must be sufficient for a reviewer without access to conversational or hidden agent reasoning.
