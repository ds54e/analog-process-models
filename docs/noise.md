# Characterize stationary device noise

Work at the repository root after [setup](getting-started.md), including OSDI model
builds for APM130/APM016F. This command runs one useful PSP103 NMOS condition with
ngspice 47's normal Sparse solver and no user `.spiceinit` dependency.

<!-- apm-journey: noise -->
```bash
.venv/bin/apm noise apm130/lv/nmos --output .apm/tutorial-noise
```

Inspect `.apm/tutorial-noise/metadata.json`, `operating_points.csv`,
`noise_spectrum.csv`, `noise_metrics.csv`, `noise_model_snapshot.json` and
`source_breakdown.json`, plus the retained netlists/raw outputs/logs. PSD fields
`s_idrain_terminal_a2_per_hz` and `s_vgate_equivalent_v2_per_hz` use A²/Hz and V²/Hz.
The separately retained `y_dg_real_s`/`y_dg_imag_s` are the actual complex external
gate-to-drain transfer in S. The gate-equivalent PSD uses that transfer rather than
an assumed low-frequency gm or an unqualified backend convenience vector.

The default point is 27 °C, L/Lmin=2, VOUT/VDD=0.5 and resolved gm/Id=15 V⁻¹.
Bias refinement is checked before acquisition. The bounded sweep starts at 1 Hz
through 100 MHz and may repeat through 1, 10 or 100 GHz while seeking a valid white
region. White/flicker fits are secondary and versioned; unavailable regions remain
explicit null/status results. Unreachable gm/Id targets are not clipped into data.

The [method contract](../NOISE_CHARACTERIZATION.md) and preserved
[acquisition/fit details](../NOISE_N1.md) define the 1-ohm CCVS probe, terminal
semantics and fit rules. [Catalog methodology](../NOISE_N2.md) describes comparison
coverage and strict resume. Maintainers run `noise-method-check` and
`noise-catalog-check` separately from a first device study.

Noise results characterize the existing compact-model predictions and their
parameter provenance. Successful execution is not process-noise calibration,
silicon/foundry accuracy, reliability evidence or transient/noise-MC support.
The executed tutorial observations are recorded in the current qualification report.
