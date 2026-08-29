# Terminal characterization output

`apm characterize <technology>` creates a new result directory and refuses to
overwrite a non-empty directory. Full result directories are reproducible but
normally untracked; compact milestone/release evidence belongs under
`validation/evidence/`.

The current result schema is `apm.characterization.v1` and consists of:

- `metadata.json`: kit/model/simulator identity, geometry, temperatures,
  variation identity, extraction methods, row counts, and property checks;
- `idvg.csv` and `idvd.csv`: effective sweep coordinates plus native signed
  ngspice voltage-source current, device-entering drain current, and `IDMAG`;
- `derived.csv`: terminal finite-difference gm/gds, both perturbation results,
  convergence values, gm/Id, gm/gds, and distinctly named optional native
  compact-model oracle values;
- `dibl.csv`: both constant-current threshold magnitudes, drain biases,
  explicit current coefficient/normalization, and DIBL in V/V;
- `y_matrix.json`: all 16 real and imaginary terminal Y entries in fixed
  `d,g,s,b` order, excitation/current conventions, frequency, and KCL
  diagnostics;
- `capacitance.csv`: Cgg, Cgd, and Cgs derived from raw Y, plus the
  low-frequency sensitivity result;
- `length_scaling.csv`: fixed-normalized-bias and approximately 15 1/V gm/Id
  summaries across `L/Lmin`;
- `raw/`, `netlists/`, and `logs/`: authoritative simulator inputs/outputs
  needed to audit or recalculate the derived tables.

## Signed and canonical quantities

ngspice reports current through the drain voltage source into that source.
APM retains that value as `raw_vd_source_current_a` and separately records its
negative as the current entering the device drain. `idmag_a` is the canonical
positive magnitude.

Effective comparison coordinates are `VGS,VDS` for N devices and `VSG,VSD` for
P devices. Canonical gm and gds differentiate `IDMAG` with respect to these
effective coordinates, so normal PMOS/PFET results are not sign-inverted.

## Y and capacitance convention

For terminal order `d,g,s,b`, column `j` applies a 1 V small-signal excitation
at terminal `j` while the other ideal terminal sources are at AC ground. Each
entry is:

`Y[i,j] = current entering device terminal i / excitation at terminal j`.

The raw complex matrix is authoritative. Reported capacitances use
`Cii=imag(Yii)/(2*pi*f)` and positive transfer coupling
`Cij=-imag(Yij)/(2*pi*f)`. No reciprocity averaging is applied.

## Validation status

An ngspice result is marked `validated` only after the real analyses complete
and its recorded property checks pass. Spectre artifacts remain
`experimental_unverified`; structural inspection must not be represented as a
real Spectre simulation.

DC monotonicity is a required property from the kit's constant-current
threshold criterion through the conduction region. Full-range monotonicity is
also reported as a diagnostic, but is not a pass criterion: a terminal drain
current can legitimately reverse by a few picoamps near zero control voltage
when gate/junction leakage and current partition dominate an otherwise-off
channel. The raw signed curves remain authoritative, and this distinction must
not be used to hide a reversal once channel conduction reaches the documented
threshold criterion.
