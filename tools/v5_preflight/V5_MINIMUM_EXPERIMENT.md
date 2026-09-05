<!-- SPDX-FileCopyrightText: 2026 APM preflight contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM v5 minimum experiments

## Status and authority

This file defines the exploratory experiments authorized by the current `GOAL.md`
and `V5_PREFLIGHT.md`. It is not a full v5 implementation or release contract.
The source baseline is `b09d104759296e6dd59c6f08e6cd30fa716d6461`.
Always work from current main, not a reset to that baseline. Model bytes remain fixed.

The original standalone packet has been imported as editable exploratory scaffolding.
Python-only checks have been rerun during repository preparation; real ngspice has not
been executed in that preparation environment. The repository report under
`validation/evidence/v5_preflight_preparation.json` records the exact limitations.
Repository instructions, not the earlier ZIP or chat, are authoritative.
The experiment contract takes precedence over shortcomings of the supplied runner.

## Decision to be obtained

Can the frozen APM045 VTG N/P wrappers support a repeatable maximum-gm coordinate
and a well-conditioned two-observable instance mapping, applied to one leaf device
inside a hierarchy without changing its untouched twin?

Do not build a general Monte Carlo framework before this question is answered.
Do not substitute constant-current Vth, endpoint gm, a changed supply, or altered
nominal model cards silently if MG extraction fails.

## Source issue

The 2020 Hart paper Table 1 prints N, L=40nm, 300K A_beta=5.6 percent micrometre.
Literal application to W=.12um, L=.04um gives pair sigma_beta=0.80829. The Figure 8
beta-axis labeling and the current-mismatch curves do not establish a unique coherent
normalization of this number. Runtime adoption remains blocked. Do not treat an
inferred factor-of-ten correction as an author correction.

The first author's 2022 thesis is a targeted follow-up; its full text was not
retrieved during preparation. Its metadata alone does not resolve the coefficient issue.
See `source_audit.toml` for exact references. Primary-paper plots must be visually
inspected, not interpreted only through extracted text.

The software experiments below use artificial deterministic targets, NOT Hart beta
coefficients. Implementing the kernel and resolving the source issue can proceed in
parallel. Passing a synthetic test cannot unblock a source-coefficient release gate.

## Experiment 1: instance application, before any statistics

Use two electrically independent identical VTG devices sharing ideal gate/source/body
bias sources and separate ideal drain sources, behind the same three-level hierarchy:

    Xtop -> Xea -> Xa or Xb -> Mapm045_vtg_core

For N use Vs=Vb=0V, Vd=.05V and Vg sweep 0..1V. For P use Vs=Vb=1V,
Vd=.95V and Vg sweep 1..0V. All primary terminal voltages remain within 1V.
Temperature=300K (26.85C). Default W=1um, L=.12um.

Apply raw DELVTO and MULU0 to A only. Explicitly set B to nominal. Read back W,L,
DELVTO,MULU0 for both. Check both the requested and observed values, and check that
B's current curve remains unchanged. This isolated fixture makes that current check
valid; in a connected mirror the untouched device's bias/current may legitimately move.

Run two deliberate negative controls:

1. A nonexistent hierarchy path: must be rejected, not silently ignored.
2. `reset` after a nonzero perturbation: must fail readback because reset reparses the
   original circuit; it is not a permitted normal execution path.

Do not accept an unrelated extraction or solver failure as a successful negative control.
A fresh ngspice `-n -b` process is used for each deck. No `altermod`, no shared global
model mutation, no reuse of a previous sample's simulator state.

## Experiment 2: extraction repeatability

At zero perturbation repeat the gate sweep with 5mV, 2mV, 1mV steps. Record all raw
signed drain currents and canonical control-voltage magnitudes. The experimental
extractor differentiates a cubic interpolant of terminal current; it does not smooth
measurements or infer the physical BSIM VTH0.

    BETA_MG = gm_max / |VDS|
    VTH_MG  = U_at_max - |ID|/gm_max - |VDS|/2

These are versioned extraction coordinates, not a claim of exact author-code replication.
The preliminary engineering checks in the runner are 50uV Vth range and 0.1% beta range
across step sizes. They are preflight choices, not source confidence intervals or final
release tolerances. Preserve failures and refine the numerical method from evidence.

Endpoint maximum, nearly competing peaks and unstable results require an explicit
finding. Flat gm may permit stable extracted coordinates, but that needs a documented
extractor extension; this initial implementation rejects endpoint maxima.

Only after the initial N/P point works, expand to W=1/2/4um and L=.12/.24/.40um.
An expansion failure cannot erase the mandatory initial failures or automatically shrink
an approved release domain.

## Experiment 3: two-observable mapping

Use raw coordinates x=(DELVTO, ln(MULU0)). Measure the Jacobian with finite raw increments
(1mV and .01 in log multiplier initially), not machine-epsilon-sized changes.
Use output scales (10mV, .02) only to nondimensionalize this artificial numerical test.
A dimensional/unscaled condition number is not an acceptance criterion.

Test all four combinations of Delta VTH_MG=+/-10mV and Delta beta/beta0=+/-2%.
Solve with fixed, bounded raw coordinates, and independently remeasure with a 0.5mV
gate step. Check the full residual vector and cross coupling, not only its aggregate
variance. The runner has exploratory bounds DELVTO in [-.1,.1]V and MULU0 in [.5,1.5].
They are NOT a statistical support range, and NOT device reliability bounds.

Passing this test does not qualify +/-6 sigma or any Monte Carlo tail. That is a later
v5 task using an approved coefficient profile and a specified circuit/sample count.

## Offline checks supplied

`numerical_core.py` plus tests exercise: analytic MG extraction/refinement/failures,
two-dimensional synthetic mapping/inversion, explicit pair-to-device sqrt(2), unequal
areas, A(L) versus area scaling, pair-average normalization, covariance, stable keyed
draws, ordering/insertion/thread-worker invariance, tail probabilities, deck construction,
readback parsing and bad input rejection. Population tests use artificial coefficients.

No offline test counts as ngspice, model-to-silicon, or v5 release evidence.

## How to run on the existing reference host

Use the user's existing WSL2/EL9 ngspice 47 environment. Do not rebuild OpenVAF or rerun
an old release qualification just for this native-BSIM4 spike.

From the repository root, using the existing APM Python environment:

```sh
PYTHONPATH=tools/v5_preflight .venv/bin/python -m pytest -q tools/v5_preflight/tests
.venv/bin/python tools/v5_preflight/run_spike.py \
  --repo "$PWD" \
  --ngspice /absolute/path/to/the/existing/ngspice \
  --output "$PWD/.apm/v5-preflight/run-001"
```

The output directory must not already exist. Locate the existing simulator through
repository toolchain records/doctor; do not assume the example path exists. The runner
verifies all three VTG input files against their known Git blob IDs. Only native BSIM4
is required for these probes. It leaves repository files unchanged.

Then repeat with `--l-um .24`, `.40` and `--w-um 2`, `4` as appropriate. Keep raw decks,
logs, readback and extraction records. An overall preflight success is NOT a v5 release.

## Required report from Codex

Report exact repository/tool identities, actually executed cases, extraction grid errors,
normalized Jacobian/condition numbers, target/recovered residuals, neighbor isolation,
negative-control classification, run count, wall time, failed cases, and whether the
existing unmodified cards can support the proposed coordinate system.

Keep these as distinct states:

- NUMERICAL_KERNEL_TESTED
- NGSPICE_INSTANCE_APPLICATION_PROVEN or UNRESOLVED
- MG_EXTRACTION_PROVEN or UNRESOLVED
- TWO_OBSERVABLE_MAPPING_PROVEN or UNRESOLVED
- SOURCE_BETA_NORMALIZATION_RESOLVED or UNRESOLVED
- V5_RELEASE_READY (not reachable from this packet alone)

Do not move tags, alter cards, weaken released tests, create a release, or extend the
current GOAL merely to claim these experiments passed. Full v5 activation needs its
explicit repository goal/contract commit after this preflight and source decisions.
