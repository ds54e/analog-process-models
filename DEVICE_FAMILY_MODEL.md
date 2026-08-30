# Device Family Domain Model

This file defined the APM v2 domain model and remains the preserved electrical
taxonomy in released v3.0.0 unless current `AGENTS.md` or a later explicit goal
introduces a versioned change.

Its purpose is to prevent device taxonomy, operating conditions, simulator bindings, and variation semantics from becoming entangled as APM expands beyond one representative MOS pair per technology.

## 1. Core hierarchy

The canonical domain hierarchy is:

`Technology -> Electrical Family -> Device`

The following are orthogonal concepts, not additional hierarchy levels that may be silently collapsed into Family identity:

- Operating Profile
- Backend Binding
- Variation
- Comparison Set

Future electrical modes/views may be added only when real use cases require them. Layout/RF/isolation presentation variants are not v2 Electrical Families by default.

## 2. Technology

A Technology identifies the process/node class and the top-level APM technology namespace.

Required v2 technologies:

- `apm350`
- `apm130`
- `apm045`
- `apm022`
- `apm016f`

Technology-level metadata may include technology class, broad architecture lineage, provenance summary, family list, cross-process comparison anchor, and explicit comparison sets.

Do not place family-specific VDD, Lmin, compact-model flavor, N/P symmetry, or geometry bounds at Technology level when they differ among families/devices.

Family IDs are technology-local. `apm045/vtg` and `apm016f/svt` may both represent a standard/regular threshold intent without being required to share a literal family ID.

## 3. Electrical Family

An Electrical Family is a distinct nominal electrical model or parameterization identity that APM intends to characterize separately.

A Family is **not** primarily a usage category.

Examples of v2 Families:

- `apm130/lv`
- `apm130/hv`
- `apm045/vtl`
- `apm045/vtg`
- `apm045/vth`
- `apm045/thkox`
- `apm022/lvt`
- `apm022/svt`
- `apm022/hvt`
- `apm016f/lvt`
- `apm016f/svt`
- `apm016f/hvt`

Typical-use words such as `core`, `io`, `analog`, `rf`, `standard_cell`, or `high_voltage_analog` may appear as descriptive metadata but must not substitute for electrical identity.

A Family should carry explicit searchable metadata where evidence supports it, for example:

- `architecture`
- `compact_model`
- `gate_stack_id` — technology-local gate-stack identifier
- `gate_stack_class` — coarse cross-technology class such as `thin`, `thick`, `legacy_single`, or `unknown`
- `threshold_class` — e.g. `low`, `standard`, `high`, `native`, `general`, or `unspecified`
- `origin` — `upstream_model`, `apm_authored`, or `apm_derived_variant`
- `upstream_flavor` where applicable
- `base_family` and `variant_method` for derived generic variants
- `typical_uses` as non-normative descriptive metadata

Do not invent metadata merely to fill a field. Unknown/undisclosed is preferable to false precision.

## 4. Required v2 family matrix

The v2 release target is:

| Technology | Required electrical families | Basis |
| --- | --- | --- |
| APM350 | `general` | existing APM-authored generic BSIM3 |
| APM130 | `lv`, `hv` | IHP SG13G2 thin-oxide and thick-oxide PSP families |
| APM045 | `vtl`, `vtg`, `vth`, `thkox` | FreePDK45 native model flavors |
| APM022 | `lvt`, `svt`, `hvt` | APM generic threshold-class families |
| APM016F | `lvt`, `svt`, `hvt` | APM generic workfunction-dominant FinFET families |

This is 13 required Electrical Families.

The schema itself must remain sparse and must not encode assumptions that every technology has these same family types.

APM016F thick-oxide/high-voltage I/O is not a v2 requirement.

## 5. Device

A Device is the APM simulation entity within an Electrical Family.

Device metadata includes:

- device ID local to the family, e.g. `nmos`, `pmos`, `nfet`, `pfet`;
- polarity;
- public APM wrapper name;
- terminal list;
- geometry kind;
- known geometry validity/characterization bounds;
- threshold-current normalization inputs where applicable;
- backend binding references.

Do not require N/P symmetry. A Family may legally contain only one polarity/device when that is what the model set supports.

Canonical result identity is:

`technology_id / family_id / device_id`

Polarity is device metadata and may also be denormalized into result tables where useful.

### Public v2 names

Use family-qualified APM-owned names. Required families should converge on names of this form:

- `apm350_general_nmos`, `apm350_general_pmos`
- `apm130_lv_nmos`, `apm130_lv_pmos`
- `apm130_hv_nmos`, `apm130_hv_pmos`
- `apm045_vtl_nmos`, `apm045_vtl_pmos`
- `apm045_vtg_nmos`, `apm045_vtg_pmos`
- `apm045_vth_nmos`, `apm045_vth_pmos`
- `apm045_thkox_nmos`, `apm045_thkox_pmos`
- `apm022_lvt_nmos`, `apm022_lvt_pmos`
- `apm022_svt_nmos`, `apm022_svt_pmos`
- `apm022_hvt_nmos`, `apm022_hvt_pmos`
- `apm016f_lvt_nfet`, `apm016f_lvt_pfet`
- `apm016f_svt_nfet`, `apm016f_svt_pfet`
- `apm016f_hvt_nfet`, `apm016f_hvt_pfet`

If authoritative upstream reality requires a sparse exception, preserve the sparse reality rather than fabricating a complementary device.

### Geometry kinds

Planar:

- parameters `w`, `l`
- result geometry uses `w_m`, `l_m`

FinFET:

- parameters `l`, `nfin`
- result geometry uses `l_m`, integer `nfin`
- no fake continuous planar effective width

Do not expose common `m`, `nf`, `ng`, finger/layout, DNWELL, or RF-layout semantics as v2 common device parameters.

## 6. Validity metadata

Known model validity and APM characterization envelope are not the same thing.

A Device/Family may record evidence-backed validity fields such as:

- `lmin_m`, `lmax_m`
- `wmin_m`, `wmax_m`
- supported integer NFIN values/range
- `vds_min_v`, `vds_max_v`
- `vgs_min_v`, `vgs_max_v`
- `vbs_min_v`, `vbs_max_v`

These fields are optional unless authoritative upstream/model evidence supports them. Missing information means not established, not unlimited.

Do not convert model-validity metadata into oxide-lifetime, breakdown, safe-operating-area, or reliability guarantees unless the project has explicit authoritative evidence and scope for that claim. v2 does not claim reliability qualification.

## 7. Operating Profile

An Operating Profile is an APM characterization/use profile attached to a Family, not the Family identity itself.

A profile may define:

- reference VDD used for characterization;
- reference bias conventions;
- temperature set;
- geometry sampling policy;
- profile provenance (`upstream`, `apm_selected`, etc.);
- purpose such as nominal characterization or common-overlap comparison.

A Family may eventually have multiple operating profiles. Do not assume one nominal voltage uniquely defines one electrical model family.

Three distinct concepts must remain separate:

1. model validity — what the source/model says is valid;
2. operating profile — the representative APM characterization condition;
3. reliability/rating — lifetime/breakdown claims, generally out of v2 scope.

For values not currently established by primary evidence, such as the final FreePDK45 THKOX reference VDD, research and characterize before freezing a release value. Record whether the value is upstream-specified or APM-selected.

## 8. Backend Binding

Simulator-specific mechanics belong in Backend Bindings rather than semantic family manifests.

A backend binding may contain:

- simulator name/backend ID;
- include/library files and sections;
- compact-model native name;
- OSDI artifact requirements;
- wrapper path;
- native OP-path templates used only as validation oracles;
- simulator-specific parameter handles used by variation adapters.

Preferred repository shape is conceptually:

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

Exact filenames may evolve, but semantic manifests must not become dumps of simulator-specific hard-coded paths when a binding file is clearer.

The Python runtime should discover normal Technologies/Families/Devices from manifests rather than from technology-specific loader functions.

## 9. Comparison Sets

Comparison relationships should be explicit rather than inferred only from labels.

Technology manifests may define named sets, for example:

### APM045

- `threshold`: members `vtl`, `vtg`, `vth`, anchor `vtg`
- `gate_stack`: members `vtg`, `thkox`

### APM130

- `gate_stack`: members `lv`, `hv`

### APM022

- `threshold`: members `lvt`, `svt`, `hvt`, anchor `svt`

### APM016F

- `threshold`: members `lvt`, `svt`, `hvt`, anchor `svt`

Cross-process technology anchors are:

- APM350: `general`
- APM130: `lv`
- APM045: `vtg`
- APM022: `svt`
- APM016F: `svt`

The anchor path preserves the original scaling question without mixing thick-oxide/high-voltage or alternate-Vt families into the golden cross-process sequence.

## 10. Characterization views by comparison type

### Threshold-sibling comparison

Use both:

1. **equal-bias view** — documented equal normalized or absolute legal bias suitable for siblings;
2. **equal-inversion view** — common inversion level, normally a documented gm/Id target.

Required family-oriented observables include:

- threshold magnitude;
- Ion density;
- Ioff density;
- `log10(Ion/Ioff)`;
- subthreshold swing;
- gm/Id;
- gm/gds;
- DIBL;
- Cgg/Cgd/Cgs;
- temperature behavior.

Do not require simple monotonic ordering for every secondary metric. For generic LVT/SVT/HVT families, the hard ordering contract should focus on threshold and drive/leakage direction unless evidence justifies more.

### Gate-stack / voltage-family comparison

Provide two explicitly distinct views where legal/evidenced:

1. **native-profile view** — each family at its own operating profile;
2. **common-overlap-bias view** — both families at a deliberately selected common legal bias.

Do not silently choose `min(VDD)` as the common bias. Store the selected common-bias profile and evidence that it lies within known valid characterization ranges.

## 11. Ion, Ioff, and subthreshold swing

Canonical v2 Ion/Ioff definitions use effective N/P positive bias variables and the selected operating profile:

- Ion: `VCTRL = reference_vdd`, `VOUT = reference_vdd`
- Ioff: `VCTRL = 0`, `VOUT = reference_vdd`

Store raw current and normalized density basis separately:

- planar current density: A/m or clearly documented per-width derived units;
- FinFET current density: A/fin.

Canonical family comparison should store `ion`, `ioff`, and `log10_ion_over_ioff`. A linear Ion/Ioff ratio may be a display-derived value but should not be the only persisted representation because HVT Ioff may become extremely small.

Subthreshold swing is required for v2, but its extraction window must be frozen only after native-family data are evaluated. Persist the exact current window/range, regression/derivative method, drain bias, and fit-quality diagnostics.

Gate leakage is not a required common v2 metric. It may be exposed as an optional upstream/native metric when a trustworthy model supports it.

## 12. Generic APM multi-Vt families

### APM022

- `svt` is the baseline APM-authored family.
- `lvt` and `hvt` are APM-derived generic variants.
- document `base_family = "svt"` and `variant_method = "threshold_isolated"`.
- keep shared geometry/gate-stack/basic transport basis unless evidence supports a necessary secondary change.
- derive target threshold-family spacing from characterized native/open family trends and public literature, not PTM numeric cards.

Hard nominal ordering expectations:

`|Vth_LVT| < |Vth_SVT| < |Vth_HVT|`

`Ion_LVT > Ion_SVT > Ion_HVT`

`Ioff_LVT > Ioff_SVT > Ioff_HVT`

Do not invent guaranteed monotonic ordering for every DIBL/gain/capacitance metric.

### APM016F

- `svt` is the baseline APM-authored family.
- `lvt` and `hvt` are APM-derived generic variants.
- document `base_family = "svt"` and `variant_method = "workfunction_dominant"`.
- begin with BSIM-CMG gate-workfunction (`PHIG`) adjustment to meet observable threshold targets.
- permit only minimal documented secondary parameter adjustment when terminal Ion/Ioff/SS/DIBL or numerical behavior demonstrates that a PHIG-only variant is not a sensible generic family.
- do not copy ASAP7 or PTM-MG parameter values. Public/open examples may inform qualitative structure and target ranges only.

## 13. Variation is orthogonal to Family

LVT/SVT/HVT are nominal Families, not corners and not benchmark variation states.

Each nominal Family can independently be characterized under:

- nominal;
- Benchmark Global;
- Benchmark Local;
- Benchmark All;
- deterministic benchmark corners;
- upstream/native corner/process/mismatch profiles when supported.

### Benchmark Global

For MOS devices, v2 uses technology/polarity observable latent stresses such as:

- `tech.<technology>.n.vth`
- `tech.<technology>.n.drive`
- `tech.<technology>.p.vth`
- `tech.<technology>.p.drive`

The same latent stress is applied to the technology's relevant electrical families, then each family/device uses its own real-tool-calibrated raw adapter.

This means common benchmark comparison stress, **not** a claim that real LVT/SVT/HVT or LV/HV process fluctuations are fully correlated.

Do not invent a numeric correlation matrix without evidence. The latent namespace should permit future family residual variables without breaking the sample schema.

### Benchmark Local

Local perturbations are instance-local and independent by default, with the explicit synthetic APM matching law defined in `GOAL.md`/benchmark configuration.

### Upstream/native variation

Retain upstream profile names and semantics. Do not infer family-to-family native correlation or a combined native `all` mode when upstream does not define/validate it.

## 14. What is not an Electrical Family in v2

Do not create v2 Families solely for:

- RF symbol/layout views sharing the same underlying electrical model;
- DNWELL/isolated placement that does not change the intended nominal electrical model;
- ESD/SAB/layout variants unless APM intentionally adopts their distinct electrical model as an in-scope family;
- standard-cell versus analog usage;
- a different plotting/characterization profile;
- a benchmark corner or Monte Carlo state.

If future evidence shows a mode materially changes terminal behavior and users need it, introduce a separate well-defined Device Mode/View concept rather than overloading Family.

## 15. Manifest-driven release requirement

By v2 release, normal family discovery and characterization must be data-driven.

A release test must prove at least:

- all five technologies and 13 required families are discoverable from manifests;
- Devices and geometry contracts are discovered from manifests;
- the generic characterization path can run all required families;
- adding a normal fixture family to a test catalog does not require a new technology-specific production loader;
- current runtime does not depend on v1 `kit.toml` as canonical SSOT;
- obsolete unqualified v1 public wrapper aliases are not required by the v2 implementation.

Keep the abstraction small. The objective is declarative catalog data plus straightforward Python, not a plugin framework.
