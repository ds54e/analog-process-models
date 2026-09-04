# Terminal characterization and comparison

`apm characterize SELECTOR` resolves a technology, family, or device selector
through the v2 catalog. A technology runs every declared family, a family runs
its declared devices, and a device selector restricts the run to that device.
An explicit `--profile` is valid for a family/device selector. Every command
refuses to overwrite a non-empty output directory.

Examples:

```console
apm characterize apm130 --output .apm/results/apm130
apm characterize apm045/thkox --profile common_overlap_1v0 \
  --output .apm/results/apm045-thkox-overlap
apm characterize apm016f/svt/nfet --output .apm/results/apm016f-svt-n
```

Full result directories are reproducible but normally untracked. Compact
milestone evidence belongs under `validation/evidence/`.

## Result identity and files

A family result uses schema `apm.characterization.v2`. `metadata.json`
records technology/family/device identity, compact-model provenance, hashes of
the family and backend manifests, selected Operating Profile, public device
names, simulator/model-build identity, geometry, temperatures, extraction
methods, row counts, checks, and status.

The tabular and raw outputs are:

- `idvg.csv` and `idvd.csv`: effective sweep coordinates, native signed
  ngspice voltage-source current, current entering the drain, and canonical
  `IDMAG`;
- `derived.csv`: terminal finite-difference gm/gds at two step sizes,
  convergence changes, gm/Id, gm/gds, and distinctly named optional native
  compact-model oracle values;
- `dibl.csv`: constant-current threshold magnitudes at low/high drain bias,
  current criterion/normalization, and DIBL;
- `family_metrics.csv`: Ion, Ioff, `log10(Ion/Ioff)`, constant-current
  threshold, and subthreshold swing by identity/temperature/geometry;
- `length_scaling.csv`: normalized-bias and approximately 15 V⁻¹ gm/Id
  summaries across `L/Lmin`;
- `nfin_scaling.csv` for FinFET families: raw and per-fin Id/gm/capacitance
  behavior for NFIN 1, 2, and 4;
- `y_matrix.json`: every real and imaginary entry of each 4×4 terminal
  admittance matrix;
- `capacitance.csv`: Cgg, Cgd, and Cgs derived from the raw Y matrices; and
- `raw/`, `netlists/`, and `logs/`: simulator inputs and outputs needed to
  recalculate or audit every derived metric.

A technology-level orchestration result uses
`apm.technology-characterization.v2` and hash-links each family metadata file.

## Signed and canonical quantities

ngspice reports current through the drain voltage source into that source. APM
retains it as `raw_vd_source_current_a`, records its negative as current
entering the device drain, and records `idmag_a` as a positive magnitude.

Effective coordinates are VGS/VDS for N devices and VSG/VSD for P devices.
Canonical gm and gds differentiate `IDMAG` with respect to those effective
coordinates. Raw signed values and positive-magnitude comparison values remain
distinct fields.

## Finite-difference contract

Canonical gm/gds are terminal central finite differences; internal simulator
OP names are optional validation oracles only. Each result stores both
perturbation sizes, both derivative estimates, and their relative convergence.
The generated netlists explicitly set `gmin=1e-15 S` so off-current behavior
does not depend on a mutable user default.

## Ion, Ioff, and subthreshold swing

Ion is evaluated at `VCTRL=VOUT=reference_vdd`; Ioff at
`VCTRL=0, VOUT=reference_vdd`. Planar values normalize per metre of drawn
width and FinFET values per fin.

The frozen SS method is
`apm.ss.threshold_relative_two_decade_linear_fit`, method version `1.0.0`:

1. use `VOUT=0.05 V`;
2. select the fixed current window 0.003 through 0.3 times the device's
   constant-current threshold criterion;
3. fit `log10(IDMAG/A)` versus effective control voltage by ordinary least
   squares; and
4. require at least five points and R² ≥ 0.995.

The reciprocal fitted slope is reported in V/decade. The window, fit quality,
and validity are persisted, so a later method can coexist without rewriting
historical meaning.

## Terminal Y and capacitance

Terminal order is `d,g,s,b`. Column `j` applies a 1 V small-signal excitation
at terminal `j` while the other ideal terminal sources are at AC ground.
Current is positive entering the device:

`Y[i,j] = terminal current entering i / excitation at j`.

The release flow stores both 100 kHz and 1 MHz matrices at two documented bias
views: equal normalized bias and the available terminal point nearest
gm/Id = 15 V⁻¹. The complex Y data is authoritative. Derived capacitances use:

- `Cii = imag(Yii)/(2*pi*f)`;
- `Cij = -imag(Yij)/(2*pi*f)` for `i != j`.

No reciprocity averaging or internal `cgg/cgd/cgs` field is part of the stable
contract.

## Validation properties

A result is `validated` only after real ngspice analyses complete and every
recorded requirement passes. Checks include row/identity coverage, simulator-log
completion, raw-current sign semantics, conduction-region monotonicity,
finite-difference convergence, native-oracle agreement where available,
positive/sensible DIBL and capacitance, Y-matrix KCL, frequency sensitivity,
SS fit quality, and FinFET per-fin scaling.

Full-range near-off monotonicity is diagnostic only: terminal partition and
leakage can reverse picoamp-level current before channel conduction. From the
documented threshold criterion through conduction, monotonicity is required.

## Comparison views

`apm compare-set TECHNOLOGY SET_ID` runs a manifest-defined set and writes
`comparison.csv` plus schema `apm.comparison.v2` `report.json`.
Threshold-family sets produce both `threshold_equal_bias` and
`threshold_equal_inversion` views. Gate-stack sets produce
`gate_stack_native_profile` plus fresh
`gate_stack_common_overlap` simulations under the named overlap profile.

`apm compare-anchors` characterizes:

`apm350/general → apm130/lv → apm045/vtg → apm022/svt → apm016f/svt`

at normalized coordinates. `apm compare A B` provides the same audited
two-selector machinery for review pairs.

Comparison reports preserve each source result's manifest/model/profile hashes,
normalization basis, and checks. Dimensionless gm/gds, DIBL, and threshold
relations are always allowed. Current/capacitance ratios are reported only for
matching normalization bases; a planar/FinFET relation is explicitly
`not_reported_across_per_width_and_per_fin_bases`.

`apm characterization-check --output DIR` is the release-oriented all-family
flow. It characterizes all 15 families and produces an audited cross-family
summary through the same v2 comparison implementation.

APM045's `mixed_voltage` comparison set uses the separately versioned
`apm.mixed-voltage-comparison.v1` contract. It runs native-profile,
common-bias, equal-physical-length, equal-relative-length, and equal-inversion
views across VTG, io18, and io25 where applicable. Each target retains a
bracketed `validated`, `target_not_reachable`, or `simulation_failed` state;
there is no endpoint substitution. The report also hash-binds source cards,
raw DC/Y data, terminal-order KCL checks, and public-wrapper intrinsic
gate-charge trajectories. These terminal comparisons do not imply foundry,
silicon, reliability, or layout-dependent accuracy.

## Spectre boundary

Spectre artifacts remain `experimental_unverified`. Static structural checks
must never be represented as terminal characterization or a real Spectre
simulation.
