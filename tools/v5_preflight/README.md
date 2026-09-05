<!-- SPDX-FileCopyrightText: 2026 APM preflight contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM v5 preflight tools

Follow [`GOAL.md`](../../GOAL.md), [`V5_PREFLIGHT.md`](../../V5_PREFLIGHT.md) and
[`V5_MINIMUM_EXPERIMENT.md`](V5_MINIMUM_EXPERIMENT.md). These are bounded
exploratory experiments, not a production variation API or release gate.

The executed findings are in
[`v5_preflight_findings.json`](../../validation/evidence/v5_preflight_findings.json),
with a separate [source audit](../../validation/evidence/v5_preflight_source_audit.md).
Both VTG polarities passed application, MG extraction and artificial mapping at
the initial point and all nine specified W/L combinations. This evidence covers
300 K, 50 mV drain bias and the tested deterministic perturbations only. Hart beta
normalization remains unresolved; no statistical profile is approved.

- `numerical_core.py`: exploratory extraction, inversion and artificial sampling helpers.
- `run_spike.py`: isolated native-BSIM4 experiments with independent N/P stage reporting.
- `tests/`: analytic and synthetic regressions; no real-SPICE claim.
- `source_audit.toml`: primary-source decisions and explicitly artificial inputs.
- `CODEX_PROMPT.md`: the original repository handoff launch prompt.

From the repository root, reuse an existing compatible Python environment and
ngspice 47. Inspect the host before setup; the example binary path must be verified.
The default pytest configuration excludes this separate suite:

```sh
PYTHONPATH=tools/v5_preflight .venv/bin/python -m pytest -q tools/v5_preflight/tests
.venv/bin/python tools/v5_preflight/run_spike.py \
  --repo "$PWD" --ngspice /usr/local/bin/ngspice \
  --output "$PWD/.apm/v5-preflight/new-minimum"
```

The output directory must be new and below `.apm/v5-preflight/`. First understand
N/P at W=1 µm, L=0.12 µm. Only then repeat with the specified `--w-um` 1/2/4 and
`--l-um` 0.12/0.24/0.40 combinations. Each output contains a compact stage report
and hash inventory binding every request, deck, signed curve, log, readback and
extraction. Failed stages and individual targets are retained; unavailable mapping
is `BLOCKED`. A report-level `PASSED` covers only the numerical experiments in
that run and is never a source-coefficient or release qualification.

The reviewed runner proves nonzero application and twin isolation before extracting
MG. Bad-path controls require explicit missing-leaf diagnostics and nominal curves.
Reset controls read the nonzero knobs before reset and their loss afterward.
Unrelated solver errors, missing data and timeouts cannot pass either control.
Timeouts retain the request and captured partial logs. Each uncached request uses
a fresh `ngspice -n -b` process; identical requests may reuse their saved result.

The current host's system `spinit` selects eight ngspice threads. `CKTsetup` uses
ngspice's `num_threads` variable, overriding `OMP_NUM_THREADS`. The first parallel
expansion suffered severe contention and was interrupted with its partial evidence
retained. The runner now explicitly sets `num_threads=1` before any analysis.
All required experiments were rerun successfully, without changing numerical
criteria, observables, model bytes or voltage limits.

The cubic-interpolant MG method and finite physical differencing are preserved.
Reports now include every refinement grid, peak/endpoint diagnostics, both raw and
scaled Jacobians, a half-increment sensitivity check, cross terms, all four target
residual vectors and independent 0.5 mV-grid remeasurement with twin checks.
The bounds and tolerances remain preflight engineering choices, not manufacturing
sigmas, qualified Monte Carlo support or device reliability limits.

The original scaffold's 34-test preparation result is preserved in
[`v5_preflight_preparation.json`](../../validation/evidence/v5_preflight_preparation.json).
Its original real minimum run also remains recorded in the findings. The repaired
suite has 39 tests, including stronger negative-control classification, timeout-log
preservation and independent failure reporting. No paper or measured coefficient
is shipped by this tooling.
