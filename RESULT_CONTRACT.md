# APM v1 Result Contract

This file defines the stable semantic minimum for v1 characterization results. It exists to prevent different model-kit adapters from producing incompatible or ambiguous outputs.

The exact internal Python classes and file layout may evolve during implementation, but the information below must remain recoverable from persisted results.

If this file conflicts with `GOAL.md` or `AGENTS.md`, those files win.

## General principles

1. Persist machine-readable numerical results; plots are derived presentation, never the only output.
2. Preserve raw signed terminal quantities separately from canonical positive-magnitude comparison quantities.
3. Preserve enough method metadata to recompute or audit every derived quantity.
4. Preserve model/simulator/provenance identity with every result set.
5. Do not invent a planar effective width for FinFET results.
6. Preserve the raw complex terminal Y matrix rather than only derived capacitance labels.
7. Distinguish APM benchmark variation from PDK-native variation in every result set.

## Required result identity

Every persisted characterization result set must identify at least:

- result schema version;
- APM kit ID (`apm350`, `apm130`, `apm045`, `apm022`, or `apm016f`);
- APM public device name;
- polarity (`n` or `p`);
- compact-model family;
- model/deck revision or immutable source identifier where available;
- simulator backend;
- simulator version/build identity;
- characterization type/method;
- temperature;
- nominal kit VDD used by the characterization;
- geometry;
- variation origin/mode;
- relevant extraction-method metadata.

## Canonical units

Persist canonical numeric fields in explicit SI-derived units:

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

Human-facing tables/plots may rescale units (mV, uA, fF, nm, etc.), but stored machine-readable fields must identify the actual unit and must not rely on display labels for interpretation.

## Geometry

For planar devices persist:

- `w_m`
- `l_m`
- `l_over_lmin`

For APM016F persist:

- `l_m`
- `nfin`
- `l_over_lmin`

Do not fabricate or require `w_m` for FinFET comparison.

Record the kit's `model_lmin`/reference Lmin used to compute normalized length.

## Raw DC quantities

Raw device data must retain the simulator's signed terminal convention.

Where applicable persist terminal voltages/currents or enough equivalent data to reconstruct the characterized bias point.

Canonical comparison coordinates are separate fields:

- NMOS/NFET: `vctrl_v = VGS`, `vout_v = VDS`, `idmag_a = abs(ID)`
- PMOS/PFET: `vctrl_v = VSG`, `vout_v = VSD`, `idmag_a = abs(ID)`

Do not overwrite the raw signed current with `idmag_a`.

## Id-Vg and Id-Vd

Persist the sweep coordinates and current values in machine-readable form, including:

- effective sweep voltage;
- fixed effective bias voltage(s);
- raw signed drain current where available;
- canonical current magnitude;
- geometry;
- temperature;
- variation identity.

The exact CSV/table organization may be chosen during implementation as long as these semantics are explicit.

## gm and gds

Canonical derived values are:

- `gm_s = d(IDMAG)/d(VCTRL)`
- `gds_s = d(IDMAG)/d(VOUT)`
- `gm_over_id_per_v = gm_s / IDMAG`
- `gm_over_gds = gm_s / gds_s`

Persist finite-difference method metadata, including the perturbation sizes actually used and the convergence/error criterion/result.

If a native compact-model OP value is also saved for validation, name it distinctly (for example `native_gm_s`) and never substitute it silently for the canonical finite-difference quantity.

## Threshold and DIBL

Persist at least:

- extracted threshold magnitude at low effective drain bias;
- extracted threshold magnitude at high effective drain bias;
- effective low/high drain biases;
- normalized constant-current criterion and its units/normalization rule;
- resulting DIBL in V/V.

The constant-current extraction coefficient must be explicit metadata because it is not to be inferred from model family or technology name.

## Terminal Y matrix

Use fixed terminal order:

`d, g, s, b`

Define:

`Y[i,j] = terminal current entering terminal i / small-signal voltage excitation applied to terminal j`

with the other terminal voltage sources at AC ground according to the measurement harness.

Persist for each Y extraction:

- DC bias point;
- frequency in Hz;
- terminal order;
- current-direction convention;
- real and imaginary parts of all 16 Y entries, in S;
- any numerical/KCL consistency diagnostics.

Do not store only a reduced capacitance table and discard Y.

## Derived capacitances

With the above Y convention and angular frequency `omega = 2*pi*f`, the default reported capacitance convention is:

- self: `Cii = imag(Yii)/omega`
- transfer coupling magnitude: `Cij = -imag(Yij)/omega`, `i != j`

At minimum expose:

- `cgg_f` from the gate self term;
- `cgd_f` from gate-current response to drain excitation (`Y[g,d]`);
- `cgs_f` from gate-current response to source excitation (`Y[g,s]`).

If a model is measurably non-reciprocal in small signal, do not silently average `Y[g,d]` with `Y[d,g]`. Preserve the raw matrix and document any alternate derived definition.

Record the chosen characterization frequency and the low-frequency sensitivity check used to justify it.

## Variation identity

Every result must include:

- `variation_origin`: `none`, `benchmark`, or `native`;
- `variation_mode`: appropriate value such as `nominal`, `corner`, `process`, `mismatch`, or `all`;
- corner/profile name if applicable.

For APM benchmark variation also include where applicable:

- benchmark specification/schema version;
- RNG algorithm/seed for generated samples;
- resolved sample identifier/path/hash;
- global process perturbations;
- local perturbation identity for the characterized instance.

For PDK-native variation, identify the actual upstream section/profile/model used rather than translating it into an APM benchmark label.

## Provenance and validation status

A result generated by ngspice may be marked validated only when the required real simulation actually ran successfully under the documented reference flow.

Spectre artifacts/results must not be marked validated unless a real Spectre run occurred. Static-model inspection is `structurally_checked` or `experimental_unverified` as defined in `validation/evidence/README.md`.

## Storage recommendation

Prefer a simple run/result directory with:

- one machine-readable metadata file (JSON is preferred for runtime records);
- CSV or similarly simple tabular files for sweeps/derived tables;
- a machine-readable raw Y-matrix representation;
- optional plots generated from those data files.

Do not make a proprietary binary container the only persisted representation.

File names/layout are not public API in the initial scaffold; semantic field meanings are more important. Once a v1.0 storage layout is chosen and exposed to users/tests, document and version it deliberately.
