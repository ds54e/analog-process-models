# APM v2.0 Implementation Status

This file is the compact persistent progress index for the current v2 development line. It is not evidence by itself.

## Overall state

- Project: Analog Process Models (APM)
- Repository: `https://github.com/ds54e/analog-process-models`
- Stable historical release: `v1.0.0`
- v1 baseline commit: `e7bba6aaba1487a1116459a6b7b2c3c5add93318`
- Current target: `v2.0.0`
- Current state: `V2_NOT_STARTED`
- Current milestone: `V2-M0 Domain/catalog migration foundation`
- Release eligible: `NO`

The v2 specification intentionally breaks the v1 one-family-per-technology architecture. Current implementation code is still the v1 baseline until Codex performs the v2 migration.

Existing v1 release evidence is historical baseline only and does not satisfy v2 release gates.

## v1 validated toolchain baseline available for reuse

The v1.0 implementation validated:

- WSL2 kernel `6.18.33.2-microsoft-standard-WSL2`
- AlmaLinux 9.7, x86_64
- repository/build work on Linux ext4, not `/mnt/c`
- Python 3.9.25
- ngspice 47 built with `--enable-predictor --enable-osdi --with-x=no`
- project-local OpenVAF-ReLoaded tag `v24.0.2mob`, commit `fdf2522b70f42793f64b1c72f0195c96dea0cc19`
- AlmaLinux LLVM 20.1.8 source-build path for OpenVAF
- PSP103 OSDI real-device simulation
- BSIM-CMG 112.1.0 OSDI real-device simulation
- native BSIM3/BSIM4 real-device simulation

During v2 development the existing `.apm` toolchain, OSDI artifacts, caches, and `.venv` should be reused when present and verified. Do not rebuild solved infrastructure without reason.

Final v2 release still requires its own clean-clone/bootstrap/release validation.

## v2 required family target

| Technology | Required families | Current v2 status |
| --- | --- | --- |
| APM350 | `general` | NOT_STARTED migration from v1 |
| APM130 | `lv`, `hv` | NOT_STARTED; LV exists in v1, HV to add |
| APM045 | `vtl`, `vtg`, `vth`, `thkox` | NOT_STARTED; VTG exists in v1 |
| APM022 | `lvt`, `svt`, `hvt` | NOT_STARTED; v1 deck becomes SVT baseline |
| APM016F | `lvt`, `svt`, `hvt` | NOT_STARTED; v1 deck becomes SVT baseline |

Total target: 13 Electrical Families.

## v2 milestones

| Milestone | Status | Purpose |
| --- | --- | --- |
| V2-M0 Domain/catalog migration | NOT_STARTED | Manifest-driven Technology/Family/Device/OperatingProfile/BackendBinding architecture; migrate existing v1 representative families first. |
| V2-M1 APM130 LV/HV | NOT_STARTED | Add/audit IHP HV family, N/P-specific bounds, native LV/HV variation, gate-stack profile semantics. |
| V2-M2 APM045 VTL/VTG/VTH/THKOX | NOT_STARTED | Add/audit all FreePDK45 families, collect native multi-Vt/gate-stack characterization, freeze THKOX profile research. |
| V2-M3 Characterization/result/comparison v2 | NOT_STARTED | v2 identity/schema; Ion/Ioff/log ratio/SS; comparison sets and views. |
| V2-M4 Benchmark Global/Local/All | NOT_STARTED | Multi-family latent stress, family adapters, deterministic replay, severity review. |
| V2-M5 APM022 multi-Vt | NOT_STARTED | Threshold-isolated generic LVT/SVT/HVT families. |
| V2-M6 APM016F multi-Vt | NOT_STARTED | Workfunction-dominant generic LVT/SVT/HVT FinFET families. |
| V2-M7 Integrated all-family validation | NOT_STARTED | All five technologies/13 families, comparisons, variation, removal of v1 runtime SSOT dependency. |
| V2-M8 Spectre/provenance/docs | NOT_STARTED | v2 model-only Spectre structure, exact-file audits, claims/docs, remove obsolete v1 canonical artifacts. |
| V2-M9 Release validation | NOT_STARTED | 2.0.0 metadata, fail-closed validator, fresh clone, all gates, tag. |

Allowed status values: `NOT_STARTED`, `IN_PROGRESS`, `VALIDATED`, `BLOCKED`.

## Authoritative v2 design decisions already settled

- v2 is an intentional breaking redesign; no backward-compatibility layer is required.
- canonical hierarchy is `Technology -> Electrical Family -> Device`.
- Operating Profile, Backend Binding, Variation, and Comparison Set are orthogonal concepts.
- Family means nominal electrical parameterization, not primarily `core/io/RF` usage.
- Family IDs are technology-local; cross-technology semantics come from metadata/comparison sets.
- schema must allow sparse/asymmetric devices; do not require N/P pairs globally.
- model validity, APM Operating Profile, and reliability/rating claims are distinct.
- runtime must be manifest-driven by v2 release; normal family addition must not require a technology-specific loader branch.
- APM130 should preserve the pinned v1 IHP revision if its HV assets pass exact-file audit.
- APM045 should preserve the pinned v1 clean FreePDK45 revision if VTL/VTH/THKOX assets pass audit.
- APM022 LVT/HVT are `threshold_isolated` generic variants around SVT.
- APM016F LVT/HVT are `workfunction_dominant` generic variants around SVT.
- APM016F thick-oxide/high-voltage I/O is deferred beyond v2.
- v2 adds Ion, Ioff, `log10(Ion/Ioff)`, and subthreshold swing.
- threshold-family comparison requires equal-bias and equal-inversion views.
- gate-stack comparison requires native-profile and validated common-overlap-bias views.
- APM synthetic variation terminology becomes Benchmark Global / Benchmark Local / Benchmark All.
- Benchmark Global is common synthetic observable stress across a technology/polarity's families, not a real foundry family-correlation claim.
- upstream/native family-to-family statistical correlation is not invented.
- Spectre remains model-only experimental/unverified unless real execution occurs.

## Deliberately unresolved v2 research values

These are not blockers at V2-M0 but must be frozen with evidence before release:

- FreePDK45 THKOX reference Operating Profile/VDD;
- common-overlap LV/HV and VTG/THKOX comparison biases;
- final subthreshold-swing extraction convention/window;
- APM022 generic LVT/SVT/HVT target spacing/secondary adjustments;
- APM016F generic LVT/SVT/HVT target spacing/secondary adjustments;
- whether v1 benchmark sigma/corner severity remains appropriate for v2;
- all new family-specific benchmark adapter coefficients.

Do not replace these with arbitrary convenient values.

## v1 historical evidence

The existing `validation/evidence/m0-runtime.md` through `m10-release.md` remain useful historical evidence for v1 and for unchanged tool/model baseline facts.

They do not mark any V2-M* milestone VALIDATED.

New v2 evidence should use clearly v2-labeled filenames/metadata and bind claims to current v2 commits/results.

## Expected state immediately after this specification commit

It is expected that:

- package/runtime implementation may still report 1.0.0;
- current `kit.toml` and v1 loaders/configs still exist temporarily;
- v1 release-validator tests may fail because `validation/release_gates.toml` now describes v2;
- current public wrappers/results are still v1 until V2-M0+ migration.

This is intentional development state, not a release failure to be hidden. Codex should implement `GOAL.md`, not weaken v2 policy to make old v1 validation green.

## Current blockers

None recorded.

## Release gate summary

The authoritative gate contract is `validation/release_gates.toml`.

Current validated v2 gates: **none**.

`v1.0.0` remains the only validated release until all v2 gates pass.
