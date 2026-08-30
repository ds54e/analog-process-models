# APM v2 Result Contract

This file defines the stable semantic minimum for APM v2 persisted characterization results.

If this file conflicts with `AGENTS.md`, `GOAL.md`, or `DEVICE_FAMILY_MODEL.md`, those files win.

## 1. Principles

1. Persist machine-readable numerical results; plots are derived presentation only.
2. Canonical identity is `technology_id / family_id / device_id`.
3. Bind results to immutable semantic manifests, backend bindings, model/provenance identity, and operating profile.
4. Preserve raw signed terminal quantities separately from canonical positive-magnitude comparison quantities.
5. Preserve enough method metadata to recompute/audit every derived metric.
6. Preserve the raw complex 4x4 terminal Y matrix.
7. Do not invent planar effective width for FinFET results.
8. Keep APM Benchmark variation distinct from upstream/native variation.
9. Do not duplicate every family attribute into every raw row when immutable metadata binding is sufficient; comparison tables may denormalize useful attributes.

## 2. Result-set identity

Every persisted v2 result set must identify at least:

- result schema version;
- `technology_id`;
- `family_id`;
- `device_id`;
- polarity as device metadata or explicit field;
- public APM device name;
- compact-model family/engine;
- model/deck revision or immutable source identifier;
- technology manifest path/hash;
- family manifest path/hash;
- backend binding path/hash;
- relevant provenance path/hash;
- simulator backend/version/build identity;
- operating profile ID and resolved profile data;
- characterization method/type;
- temperature;
- geometry;
- variation origin/mode/profile/sample identity;
- extraction-method metadata.

The same family/device under different Operating Profiles must remain distinguishable.

## 3. Canonical units

Stored canonical numerical fields use explicit SI-derived units:

- voltage: V
- current: A
- conductance/transconductance: S
- capacitance: F
- frequency: Hz
- length: m
- temperature: degC
- gm/Id: 1/V
- gm/gds: dimensionless
- DIBL: V/V
- subthreshold swing: V/decade or explicitly named mV/decade display field
- planar current density: A/m of drawn width
- FinFET normalized current: A/fin

Human-facing outputs may use uA/um, fF/um, mV/dec, etc., but persisted field names/metadata must make units unambiguous.

## 4. Geometry

Planar devices persist:

- `w_m`
- `l_m`
- `l_over_lmin`
- family/device Lmin used for normalization

FinFET devices persist:

- `l_m`
- integer `nfin`
- `l_over_lmin`
- family/device Lmin used for normalization

Do not fabricate `w_m` for FinFET results.

Geometry validity may be N/P/device-specific. Do not infer a technology-wide Lmin when manifests say otherwise.

## 5. Raw and canonical DC semantics

Preserve raw simulator terminal convention.

Canonical effective comparison variables:

- NMOS/NFET: `vctrl_v = VGS`, `vout_v = VDS`, `idmag_a = abs(ID)`
- PMOS/PFET: `vctrl_v = VSG`, `vout_v = VSD`, `idmag_a = abs(ID)`

Do not overwrite raw signed current with `idmag_a`.

Persist enough terminal/bias information to reconstruct the characterized operating point.

## 6. Id-Vg / Id-Vd

Persist sweep coordinates, fixed effective biases, raw signed current, canonical magnitude, geometry, temperature, operating profile, and variation identity.

All family/device sweep generation must use the common manifest-driven characterization engine unless a documented compact-model limitation requires a narrow adapter.

## 7. gm / gds

Canonical values:

- `gm_s = d(IDMAG)/d(VCTRL)`
- `gds_s = d(IDMAG)/d(VOUT)`
- `gm_over_id_per_v = gm_s / IDMAG`
- `gm_over_gds = gm_s / gds_s`

Use central finite differences and more than one perturbation size/convergence check.

Persist perturbation sizes, convergence/error diagnostics, and any native OP oracle separately as e.g. `native_gm_s`/`native_gds_s`.

## 8. Threshold and DIBL

Persist:

- threshold magnitude at low effective drain bias;
- threshold magnitude at high effective drain bias;
- low/high effective drain biases;
- threshold-current criterion and normalization rule;
- DIBL in V/V.

Canonical DIBL remains:

`DIBL = (|Vth_low| - |Vth_high|)/(VOUT_high - VOUT_low)`

Default low drain bias remains 50 mV where legal; high drain bias is normally an operating-profile fraction such as 0.8*reference VDD and must be stored explicitly.

Threshold-current normalization must remain explicit and geometry-aware.

## 9. Ion / Ioff

For the selected Operating Profile, canonical v2 definitions are:

- Ion: `VCTRL = reference_vdd`, `VOUT = reference_vdd`
- Ioff: `VCTRL = 0`, `VOUT = reference_vdd`

Persist:

- raw signed current;
- `ion_a` / `ioff_a` magnitudes;
- normalized current basis;
- planar normalized values in A/m of drawn width or clearly equivalent persisted field;
- FinFET normalized values in A/fin;
- `log10_ion_over_ioff` when both magnitudes are finite/positive;
- any underflow/floor/measurement diagnostics.

A linear Ion/Ioff ratio may be a derived display value but must not be the only persisted representation.

Upstream published Ion/Ioff metrics at different biases are separate native/spec observations and must not silently replace the APM canonical definitions.

## 10. Subthreshold swing

Subthreshold swing is required in v2.

The exact extraction convention is research-dependent until native family data are reviewed, but before release it must be frozen and versioned.

Persist at least:

- extraction method ID/version;
- drain/output bias;
- current window or gate-voltage window;
- normalization basis;
- fit/derivative method;
- fitted slope and SS;
- number of points;
- fit quality/residual diagnostic;
- failure/insufficient-range status when extraction is not valid.

Do not hide a failed SS extraction by clipping or silently moving the window without recording the resolved method.

## 11. Terminal Y matrix

Fixed terminal order:

`d, g, s, b`

Definition:

`Y[i,j] = terminal current entering terminal i / AC voltage excitation applied to terminal j`

with other terminal voltage sources AC grounded according to the measurement harness.

Persist for every Y extraction:

- DC bias;
- frequency;
- terminal order;
- current convention;
- real/imaginary parts of all 16 entries in S;
- KCL/numerical consistency diagnostics.

Raw Y is authoritative.

## 12. Derived capacitances

Default convention:

- `Cii = imag(Yii)/omega`
- `Cij = -imag(Yij)/omega`, `i != j`

At minimum persist/expose Cgg, Cgd, Cgs with exact source entries.

Do not silently symmetrize non-reciprocal terms.

Record selected quasi-static frequencies and frequency-insensitivity diagnostics.

## 13. Comparison identity

Comparison outputs must identify the comparison kind and its resolved coordinate/profile.

Supported v2 comparison kinds include:

- `cross_process_anchor`
- `threshold_equal_bias`
- `threshold_equal_inversion`
- `gate_stack_native_profile`
- `gate_stack_common_overlap`

Comparison tables may denormalize:

- technology/family/device IDs;
- threshold class;
- gate-stack class;
- origin;
- operating-profile reference VDD;
- current-density basis.

Do not report current/capacitance ratios across planar-per-width and FinFET-per-fin bases unless a future explicit physical conversion model is introduced. The v2 electrical contract, including v3 package outputs that preserve it, must leave such cross-basis ratios absent/null.

## 14. Variation identity

Every result must include:

- `variation_origin`: at least `none`, `benchmark`, or `upstream`;
- variation mode;
- profile/corner/sample ID where applicable.

### Benchmark modes

Canonical v2 benchmark mode names:

- `global`
- `local`
- `all`
- `corner` for deterministic benchmark corners

Persist where applicable:

- benchmark spec/schema version/hash;
- RNG algorithm;
- seed;
- latent variable names/values;
- resolved sample ID/path/hash;
- family/device raw adapter identity/hash;
- global resolved perturbations;
- local instance perturbations;
- replay identity.

The v2 sample schema should support technology/polarity latent variables now and future family residual latents later without redefining Family identity.

### Upstream/native modes

Retain actual upstream section/profile names and semantics such as corner/statistical/process/mismatch. Do not translate them into benchmark labels.

If cross-family upstream correlation is unknown, metadata must not imply it is known.

## 15. Family-origin/fidelity binding

Result metadata must preserve enough immutable binding to determine whether a family is:

- `upstream_model`;
- `apm_authored`;
- `apm_derived_variant`.

For derived variants, metadata must make base-family and variant-generation identity auditable.

A result from an APM-authored/derived generic family must not be presented as foundry/silicon-correlated merely because the simulator run validated numerically.

## 16. Validation status

`validated` means the required real backend/tool actually executed and the result contract/checks passed.

Spectre remains `structurally_checked` / `experimental_unverified` unless real Spectre execution occurs.

Missing, skipped, stale-v1-only, or structurally inspected evidence is not a v2 real-tool pass.

## 17. Storage recommendation

Prefer per-run directories containing:

- metadata JSON;
- simple CSV tables for sweeps/derived metrics;
- machine-readable raw Y JSON or equivalent;
- resolved benchmark sample JSON where applicable;
- optional plots derived from persisted numeric data.

Persist manifest/binding/provenance hashes in metadata. Avoid proprietary-only binary containers.

By v2 release, current runtime outputs must use v2 result schemas. Historical v1 result schemas remain available only through v1 history/tag and must not remain the canonical current output contract.
