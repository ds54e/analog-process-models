# APM v2.0 Implementation Goal

## 0. Repository identity and release transition

Work on the existing repository:

- repository: `https://github.com/ds54e/analog-process-models`
- project: Analog Process Models
- acronym: **APM = Analog Process Models**

The tagged `v1.0.0` release is the validated historical baseline. Current `main` intentionally begins a breaking v2 redesign. Do not preserve v1 compatibility unless this goal explicitly requires it.

Target release: **APM v2.0.0**.

Do not change repository visibility. Do not declare/tag v2.0.0 until every required release gate is satisfied with current evidence.

## 1. Purpose

APM v2 turns the v1 one-representative-device-per-technology framework into a manifest-driven **multi-electrical-family compact-model framework** while preserving the strongest parts of v1:

- open/self-contained model source distribution;
- ngspice 47 + OSDI validated reference flow;
- terminal-level characterization rather than raw compact-model API unification;
- explicit model provenance/fidelity boundaries;
- deterministic APM benchmark variation;
- technology-neutral benchmark passives;
- machine-readable evidence and fail-closed release validation.

APM is not a manufacturable PDK. v2 still does not provide layout, PCells, DRC/LVS/PEX, signoff, foundry correlation, standard cells, or reliability qualification.

## 2. Domain architecture

Implement `DEVICE_FAMILY_MODEL.md` faithfully.

Canonical hierarchy:

`Technology -> Electrical Family -> Device`

Orthogonal concepts:

- Operating Profile
- Backend Binding
- Variation
- Comparison Set

The architecture must be manifest-driven rather than a collection of technology-specific Python loaders.

Use a small explicit domain model such as:

- `TechnologySpec`
- `FamilySpec`
- `DeviceSpec`
- `OperatingProfile`
- `BiasValidity`
- `BackendBinding`

Names may differ, but responsibilities must remain separated.

## 3. Required technologies and families

Required v2 Electrical Families:

| Technology | Families |
| --- | --- |
| APM350 | `general` |
| APM130 | `lv`, `hv` |
| APM045 | `vtl`, `vtg`, `vth`, `thkox` |
| APM022 | `lvt`, `svt`, `hvt` |
| APM016F | `lvt`, `svt`, `hvt` |

Total required Electrical Families: **13**.

Schema design must remain sparse. Do not assume all families have both polarities or that every technology has the same Vt/gate-stack options.

Cross-process comparison anchor families:

- APM350 `general`
- APM130 `lv`
- APM045 `vtg`
- APM022 `svt`
- APM016F `svt`

## 4. Required repository/catalog shape

Replace v1 one-family `kit.toml` as the canonical SSOT with technology/family/device manifests.

Preferred conceptual layout:

```text
models/<technology>/
  technology.toml
  provenance.toml
  families/<family>/
    family.toml
    ngspice/
      binding.toml
      wrapper.inc
    spectre/
      binding.toml
      model.scs
```

Exact filenames may change if a smaller equivalent design is clearly better, but:

- semantic manifests must be backend-independent where practical;
- simulator-specific model includes/sections/native OP paths belong in Backend Bindings;
- family/device discovery must come from manifests;
- release runtime must not depend on old per-technology hard-coded loader functions as the canonical path.

By v2 release remove obsolete current-main canonical v1 SSOT/compatibility artifacts that conflict with the new design, including `models/*/kit.toml` and unqualified v1 public aliases if they are superseded.

Historical v1 behavior remains available from tag `v1.0.0`; do not build a compatibility layer merely to preserve it.

## 5. Public device interface

Use family-qualified APM-owned names.

Target names:

### APM350

- `apm350_general_nmos`
- `apm350_general_pmos`

### APM130

- `apm130_lv_nmos`
- `apm130_lv_pmos`
- `apm130_hv_nmos`
- `apm130_hv_pmos`

### APM045

- `apm045_vtl_nmos`, `apm045_vtl_pmos`
- `apm045_vtg_nmos`, `apm045_vtg_pmos`
- `apm045_vth_nmos`, `apm045_vth_pmos`
- `apm045_thkox_nmos`, `apm045_thkox_pmos`

### APM022

- `apm022_lvt_nmos`, `apm022_lvt_pmos`
- `apm022_svt_nmos`, `apm022_svt_pmos`
- `apm022_hvt_nmos`, `apm022_hvt_pmos`

### APM016F

- `apm016f_lvt_nfet`, `apm016f_lvt_pfet`
- `apm016f_svt_nfet`, `apm016f_svt_pfet`
- `apm016f_hvt_nfet`, `apm016f_hvt_pfet`

If authoritative reality requires a sparse exception, record and preserve the sparse reality instead of manufacturing a complementary device merely for naming symmetry.

Common terminals: `d g s b`.

Planar public parameters: `w`, `l`.

FinFET public parameters: `l`, `nfin`.

Do not expose common `m`, `nf`, `ng`, fingers, DNWELL, RF/layout, or fabricated effective-width semantics.

## 6. APM130 v2: IHP LV + HV

Preserve the already validated IHP SG13G2 revision `331c00484213b13414777eec1336ef5c29b969bd` if the required HV assets at that revision pass the exact-file licensing/provenance audit. Do not upgrade the upstream revision merely because v2 exists.

Required families:

### `apm130/lv`

Retain the existing 1.2 V thin-gate-oxide PSP-based family as the anchor.

### `apm130/hv`

Add the pinned IHP thick-gate-oxide/high-voltage MOS family.

Known baseline evidence to re-check during implementation:

- PSP 103.6 model cards;
- 3.3 V supply class / maximum drain-source statement in the upstream HV corner model;
- NMOS valid L range approximately 0.45–10 um;
- PMOS valid L range approximately 0.40–10 um;
- W range approximately 0.30–10 um;
- TT/SS/FF/SF/FS profiles;
- TT statistical and mismatch profiles.

Use exact current upstream/pinned file evidence rather than copying these values blindly from this goal.

Validate nominal terminal characterization and selected upstream/native corner/statistical/mismatch behavior for both LV and HV families. Do not invent cross-family native correlation or a native combined All mode if upstream does not define it.

Family-specific N/P geometry bounds must be supported; do not force one technology-wide Lmin.

## 7. APM045 v2: FreePDK45 VTL/VTG/VTH/THKOX

Retain the existing v1 open-source-clean FreePDK45 revision if VTL/VTH/THKOX assets at that revision pass exact-file licensing/provenance audit. Avoid unnecessary source churn.

Required families:

- `vtl`
- `vtg` — existing v1 anchor
- `vth`
- `thkox`

Characterize all four with the generic v2 path.

Define a threshold-sibling comparison set:

- members `vtl`, `vtg`, `vth`
- anchor `vtg`

Define a gate-stack comparison set:

- members `vtg`, `thkox`

Do not assume a THKOX reference VDD from secondary convention alone. Research the pinned model/docs. If no authoritative nominal VDD exists, choose and document an APM reference operating profile with explicit `apm_selected` origin and evidence that the selected bias is sensible for the model.

Use native VTL/VTG/VTH characterization to help freeze the v2 subthreshold-swing extraction method and to provide empirical context for generic APM022/APM016F multi-Vt target spacing.

## 8. APM350 v2

APM350 remains one `general` Electrical Family.

Do not fabricate LVT/HVT/HV families simply to make the family matrix symmetric.

Keep the independently authored generic BSIM3 provenance/fidelity boundary established in v1 unless new evidence requires a change.

## 9. APM022 v2 generic multi-Vt

APM022 remains independently APM-authored and non-PTM-derived.

Required families:

- `svt` — v1 baseline deck evolved into the v2 baseline family;
- `lvt` — APM-derived generic low-threshold family;
- `hvt` — APM-derived generic high-threshold family.

For LVT/HVT record:

- `origin = apm_derived_variant`
- `base_family = svt`
- `variant_method = threshold_isolated`

Develop target spacing only after characterizing native/open multi-Vt examples. Use public literature/model semantics/trends, not official PTM numeric cards.

Hard nominal family-ordering requirements across the supported reference envelope:

- `|Vth_LVT| < |Vth_SVT| < |Vth_HVT|`
- `Ion_LVT > Ion_SVT > Ion_HVT`
- `Ioff_LVT > Ioff_SVT > Ioff_HVT`

Do not force monotonic DIBL, gm/gds, SS, or capacitance ordering unless characterization/evidence justifies it.

Keep shared physical/gate-stack/basic transport basis when possible; secondary parameter changes require explicit rationale and terminal evidence.

## 10. APM016F v2 generic multi-Vt

Keep the pinned BSIM-CMG 112.1.0 engine/provenance boundary unless a required compatibility/security issue justifies a change.

Required families:

- `svt` — v1 baseline deck evolved into v2 baseline;
- `lvt`;
- `hvt`.

For LVT/HVT record:

- `origin = apm_derived_variant`
- `base_family = svt`
- `variant_method = workfunction_dominant`

Start family creation by adjusting BSIM-CMG gate workfunction (`PHIG`) to meet observable threshold-class targets.

Only if PHIG-only variants produce demonstrably poor/unrepresentative terminal Ion/Ioff/SS/DIBL/numerical behavior may minimal secondary parameters be adjusted. Every secondary adjustment must be documented with rationale/evidence.

ASAP7/open multi-Vt examples may be used to understand qualitative parameter structure/trends only. Do not copy their numerical model parameters into APM016F.

Maintain genuine BSIM-CMG/NFIN behavior and self-heating-off v2 baseline unless evidence requires otherwise.

APM016F thick-oxide/high-voltage I/O is explicitly deferred beyond v2.

## 11. Operating profiles and validity

Implement the distinction defined in `DEVICE_FAMILY_MODEL.md`:

1. model/device validity evidence;
2. APM Operating Profile;
3. reliability/breakdown qualification.

Only 1 and 2 are in normal v2 scope. Do not claim 3.

Each family must have at least one release-ready characterization operating profile with explicit origin.

Known geometry/terminal-bias validity metadata should be captured when authoritative evidence exists. Unknown fields remain unknown rather than being inferred.

Gate-stack comparison may define a common-overlap-bias profile only after both families' model behavior/validity supports it. Do not silently use `min(VDD)` as the comparison method.

## 12. Characterization v2

Preserve all v1 terminal characterization requirements:

- Id-Vg
- Id-Vd
- finite-difference gm/gds
- gm/Id
- gm/gds
- length scaling
- DIBL
- raw 4x4 terminal complex Y matrix
- Cgg/Cgd/Cgs derived from Y
- -40, 27, 85, 125 degC
- raw signed and canonical positive N/P semantics
- finite-difference convergence checks
- low-frequency Y/capacitance consistency checks

Add required v2 family-oriented metrics:

- Ion
- Ioff
- `log10(Ion/Ioff)`
- subthreshold swing

Canonical Ion/Ioff definitions use the selected operating profile:

- Ion: `VCTRL = reference_vdd`, `VOUT = reference_vdd`
- Ioff: `VCTRL = 0`, `VOUT = reference_vdd`

Persist current density basis explicitly: planar per width, FinFET per fin. Keep raw current too.

Subthreshold swing extraction convention is deliberately not frozen by this initial specification. Before release, evaluate candidate methods on native APM130/APM045 family data, freeze one robust documented method, and persist extraction window/bias/fit diagnostics.

Gate leakage is optional, not a common required v2 metric.

## 13. Comparison v2

Implement explicit Comparison Sets and distinct comparison modes.

### Cross-technology anchors

Compare only the anchor family sequence for golden process scaling:

`apm350/general -> apm130/lv -> apm045/vtg -> apm022/svt -> apm016f/svt`

Use normalized coordinates including `L/Lmin`, `VOUT/VDD`, and documented gm/Id inversion level where appropriate.

Planar quantities remain per width; FinFET quantities remain per fin. Do not invent cross-basis current/capacitance ratios.

### Threshold-family comparison

For VTL/VTG/VTH and generic LVT/SVT/HVT provide:

- equal-bias view;
- equal-inversion view.

Report threshold, Ion/Ioff/log ratio, SS, gm/Id, gm/gds, DIBL, and capacitance metrics with clear basis.

### Gate-stack comparison

For APM130 LV/HV and APM045 VTG/THKOX provide:

- native-profile view;
- common-overlap-bias view when validated/legal.

Do not present gate-stack differences as merely Vt differences.

## 14. Result contract v2

Implement `RESULT_CONTRACT.md`.

Canonical result identity becomes:

- `technology_id`
- `family_id`
- `device_id`

Result metadata must bind the relevant technology/family/device semantic manifest and backend binding hashes/snapshots, operating profile, simulator/toolchain identity, model provenance, extraction methods, geometry, and variation identity.

Do not require full family metadata duplicated into every raw CSV row; semantic identity plus immutable metadata binding is preferred. Comparison outputs may denormalize family attributes for usability.

Current runtime output must use v2 schemas by release. v1 result schemas are historical and must not remain the current canonical runtime contract.

## 15. Benchmark Variation v2

Rename the APM synthetic modes:

- Benchmark Global
- Benchmark Local
- Benchmark All

Keep deterministic benchmark corners (`bench_tt`, `bench_ff`, `bench_ss`, `bench_fs`, `bench_sf`) as explicit fixed benchmark Global vectors.

Canonical MOS observable intents remain:

- `vth_shift`
- `drive_shift`

### Global semantics

Draw technology/polarity observable latent variables and share them across that technology's electrical families. Each family/device maps the common observable stress through its own real-tool-calibrated raw adapter.

This is a synthetic common comparison stress, not a claim that real family process variations are fully correlated.

Do not invent numeric partial-correlation coefficients.

Persist latent names/values so future family-specific residual latent variables can be added without redesigning the resolved sample concept.

### Local semantics

Keep explicit per-instance local mismatch. Preserve the synthetic v1 matching-size laws unless v2 evidence justifies a deliberate change:

Planar:

`match_size = (W*L)/(Wref*Lref)`

FinFET:

`match_size = (NFIN*L)/(NFINref*Lref)`

`σ_local = σ_ref/sqrt(match_size)`

### RNG/replay

Continue Python NumPy Generator + explicit PCG64 baseline for ngspice benchmark sampling unless evidence requires a documented migration.

Persist seeds, latents, resolved values, instance-local values, hashes, and deterministic replay identity.

### Calibration

Every required family/device must have a validated adapter or a documented family-shared adapter only when real-tool evidence proves sharing is semantically valid.

Do not assume raw knob signs/scales match across families.

The v1 frozen sigma/severity values are a starting prior, not an automatic v2 release decision. Re-evaluate them after multi-family adapters exist; preserve them only if evidence shows they remain sensible for the v2 comparison contract.

## 16. Upstream/native variation

Upstream/native variation remains separate from APM Benchmark Variation.

For APM130 validate available LV and HV native:

- corners;
- statistical/process profile(s);
- mismatch profile(s).

Retain upstream names and semantics. Do not invent family-to-family native correlation or an upstream `all` mode.

FreePDK45 Vt/THKOX families are nominal electrical families, not native statistical modes.

## 17. Benchmark passives

Keep technology-neutral `Rbench(value, tc1, match_size)` and `Cbench(value, tc1, match_size)` as the common cross-technology passive basis.

Rename synthetic variation terminology consistently to Benchmark Global/Local/All.

`match_size` remains dimensionless synthetic matching size. Preserve ordinary simulator resistor/capacitor primitives and resistor Johnson-noise behavior.

Native process passives remain optional/out of common v2 scope.

## 18. Spectre v2 model-only layer

Provide model-only Spectre-compatible artifacts for all required v2 families/devices, benchmark passives, benchmark corners, and Benchmark Global/Local/All semantics.

Status remains prominently:

**EXPERIMENTAL / UNVERIFIED**

unless real Spectre execution actually occurs.

Do not add Spectre testbenches, SKILL, CDF, symbols, OA libraries, ADE/Maestro states, OCEAN, or Virtuoso automation.

IHP-native Spectre family MC is not a v2 requirement.

## 19. Licensing/provenance

Maintain exact-file provenance for every shipped third-party family/model asset.

Prefer existing v1-pinned source revisions where required family assets exist and are legally redistributable. Any new file requires fresh exact-file audit even when it comes from an already pinned upstream repository.

APM-authored family decks/variant-generation records must clearly separate public inputs, APM choices, base family, generation/calibration method, and validation boundary.

No official PTM/PTM-MG model card redistribution or numeric derivation of APM022/APM016F is permitted.

Run REUSE/SPDX and self-contained-distribution audits.

## 20. Platform and toolchain

The validated v1 development baseline is reusable during v2 implementation:

- WSL2
- AlmaLinux/RHEL-compatible EL9 x86_64
- ngspice 47 with OSDI/predictor
- project-local OpenVAF-ReLoaded `v24.0.2mob`/recorded commit unless deliberately changed
- PSP103 and BSIM-CMG OSDI paths
- Python >=3.9

At v2 startup, inventory and reuse the existing `.apm`/`.venv` toolchain when valid. Do not rebuild solved infrastructure without reason.

This reuse does not waive final v2 clean-clone validation. Final release must prove source bootstrap/build/run from a new clone on the required WSL2/EL9 environment.

Spectre remains non-required as a real-tool release dependency.

## 21. CLI direction

Provide a family-aware CLI with equivalent capabilities to:

```text
apm list technologies
apm list families apm045
apm describe apm045/vtg
apm characterize apm045/vtg
apm characterize apm045/vtg/nmos
apm characterize apm045
apm compare apm045/vtl apm045/vth
apm compare-set apm045 threshold
apm compare-set apm130 gate_stack
apm compare-anchors
```

Exact command spelling may improve during implementation, but canonical selectors must clearly support technology/family/device identity and must not rely on ambiguous one-family kit names.

## 22. Manifest-driven implementation requirement

This is a release-critical architectural requirement.

The final runtime must discover technologies/families/devices from manifests. Normal family addition must not require adding a new technology-specific production loader/branch.

Tests must prove generic catalog discovery and generic characterization/benchmark dispatch using fixture manifests or equivalent.

Do not replace straightforward manifest-driven Python with a speculative plugin ecosystem.

## 23. Deliberately unfrozen values

Do not invent these before evidence exists:

- FreePDK45 THKOX final reference operating VDD/profile;
- final common-overlap gate-stack comparison biases;
- v2 SS extraction window/method details;
- APM022 LVT/SVT/HVT target spacing and any secondary adjustments;
- APM016F LVT/SVT/HVT target spacing and any secondary parameter adjustments beyond workfunction-dominant baseline;
- whether v1 benchmark Global/Local sigma magnitudes remain unchanged for v2;
- family-specific benchmark adapter coefficients before real characterization.

These are research/characterization tasks, not permanent release TBDs. Every release-critical value must be frozen with evidence before v2.0.0.

## 24. Milestones

### V2-M0 — Domain/catalog migration foundation

- implement Technology/Family/Device/OperatingProfile/Validity/BackendBinding manifests and loader;
- migrate the existing five v1 representative families into the new architecture first;
- prove generic manifest-driven discovery/dispatch;
- reuse and smoke the existing validated local toolchain;
- do not yet claim all 13 families.

### V2-M1 — APM130 LV/HV

- vendor/audit required HV files from the pinned IHP snapshot if valid;
- implement LV/HV family manifests/bindings/public wrappers;
- support N/P-specific geometry limits;
- validate nominal characterization and upstream LV/HV variation subsets;
- establish family/gate-stack operating-profile semantics.

### V2-M2 — APM045 VTL/VTG/VTH/THKOX

- audit/vendor exact required model files;
- implement all four families;
- characterize threshold siblings and THKOX;
- research/freeze THKOX operating profile;
- collect native family evidence for Ion/Ioff/SS and generic multi-Vt target development.

### V2-M3 — Characterization/result/comparison v2

- switch runtime outputs to v2 result identity/schema;
- add Ion/Ioff/log ratio and SS;
- freeze/document SS extraction after native data review;
- implement explicit comparison sets, equal-bias/equal-inversion/native-profile/common-overlap views;
- preserve raw Y/finite-difference contract.

### V2-M4 — Benchmark Global/Local/All v2

- migrate terminology/sample schema;
- implement technology/polarity shared observable latents;
- calibrate family-specific adapters;
- re-evaluate/freeze v2 sigma/corner severity;
- preserve deterministic replay and benchmark passives.

### V2-M5 — APM022 multi-Vt

- implement SVT baseline plus threshold-isolated LVT/HVT generic families;
- freeze evidence-based target spacing;
- validate family ordering and full characterization/benchmark adapters.

### V2-M6 — APM016F multi-Vt

- implement SVT baseline plus workfunction-dominant LVT/HVT generic families;
- validate genuine BSIM-CMG/NFIN behavior for all families;
- freeze evidence-based target spacing and any minimal secondary adjustments.

### V2-M7 — Integrated all-family validation

- regenerate/audit all five technologies, all 13 families, all required devices/temperatures/metrics;
- validate comparison anchors/sets and variation across the manifest-driven path;
- prove no current runtime dependency on v1 `kit.toml`/unqualified aliases.

### V2-M8 — Spectre/provenance/licensing/documentation

- complete all v2 Spectre model-only structural artifacts;
- complete new exact-file provenance/license audits;
- update public docs/claim review;
- remove obsolete v1 canonical SSOT/compatibility artifacts from main.

### V2-M9 — Release validation

- package/runtime/release metadata = 2.0.0;
- fail-closed v2 release validator implements every required gate;
- fresh network clone on WSL2/EL9;
- bootstrap/build from source;
- doctor/tests/real-tool all-family characterization/variation/comparison/provenance audit;
- claim audit;
- only then annotate/tag `v2.0.0`.

## 25. Definition of Done

APM v2.0.0 is complete only when all of the following are true:

- five technologies and 13 required Electrical Families are present and manifest-discoverable;
- required Devices use family-qualified public interfaces and correct geometry semantics;
- APM130 LV/HV and APM045 VTL/VTG/VTH/THKOX use audited upstream assets;
- APM022/016F generic multi-Vt families satisfy documented independent-authorship/variant contracts;
- all required characterization metrics including Ion/Ioff/log ratio/SS complete at all required temperatures;
- cross-process anchors and within-technology comparison sets work with documented views;
- Benchmark Global/Local/All works across all required families with calibrated observable adapters and deterministic replay;
- selected APM130 upstream/native LV/HV corner/stat/mismatch flows are validated without invented cross-family correlation;
- FinFET families genuinely execute BSIM-CMG and preserve NFIN semantics;
- Spectre model-only artifacts cover all required families and remain correctly experimental/unverified;
- exact-file provenance/licensing and self-contained-source audits pass;
- v1 canonical `kit.toml`/result/adapter/public-alias SSOT does not remain required by current runtime;
- package/runtime/changelog/release metadata identify 2.0.0;
- no release-critical research TBD/placeholder remains;
- a fresh clone passes the full fail-closed v2 release validator;
- README/release claims match actual evidence;
- repository visibility has not been changed.
