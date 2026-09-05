<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# V5 independent candidate qualification

**V5_RELEASE_READY: 16/16 candidate-required gates passed** at exact commit `381517fda5107fabf98af7801d5a5103f38e230c`.
The source was cloned independently from GitHub, installed in a new environment,
and stayed clean throughout qualification. Plain `5.0.0` is an untagged candidate.
No v5 tag or release was created; publication requires separate user approval.

The [machine-readable summary](v5_release_candidate.json) binds raw reports,
cohort summaries, source decisions, tool receipts and the fresh-clone attestation.
Raw acquisition and logs remain ignored under `.apm/v5/fresh-candidate-1/.apm/v5/`.
This evidence qualifies the candidate above, not a later result-only commit.

## Instance application, MG extraction and two-observable mapping

| Polarity | Mechanism controls | Mapping geometry/targets | Maximum extraction error / sigma | Maximum mapping error / sigma | Scaled condition range |
| --- | --- | --- | --- | --- | --- |
| N | 9/9 PASS | 11 / 286 PASS | 5.83e-07 | 0.00017 | 3.784–6.550 |
| P | 9/9 PASS | 11 / 286 PASS | 5.65e-07 | 8.12e-05 | 3.777–5.558 |

Each polarity passed hierarchy/model/geometry/readback checks and untouched-twin
isolation. Negative controls demonstrate their intended bad-path, wrong-model,
wrong-geometry, reset-loss, duplicate, corrupt-record/cache and timeout mechanisms.
The cubic maximum-gm tangent is a versioned research coordinate; released canonical
gm/gds and VTH_CC remain unchanged. Full cross-term inverses passed all nine
anchors, two geometry holdouts and joint six-sigma target tests per polarity.
The additional 2 mV versus 1 mV nominal-grid audit passed all 22 cases; its maximum error was 4.91e-06 sigma, below 0.005.
The mapping held-out re-extraction used a separate 0.5 mV grid.

## Statistics and circuits

The pure artificial sampler passed 65,536 pairs. All 90,112 source-profile SPICE
pairs executed, with zero failed pairs: 4,096 pairs at every anchor/holdout and
polarity. Simultaneous chi-square sigma intervals for the approximately normal
Vth and population-normalized beta differences had to fit wholly inside 0.90–1.10.
Actual pair-average beta ratios used a separately reported deterministic bootstrap.

| Polarity | Pairs / failures | Overall sigma-CI range | Current sensitivity ratio range | Simplified Croon ratio range |
| --- | --- | --- | --- | --- |
| N | 45,056 / 0 | 0.9480–1.0541 | 0.9836–1.0183 | 0.9667–1.0177 |
| P | 45,056 / 0 | 0.9515–1.0565 | 0.9829–1.0243 | 0.9507–1.0237 |

All tested nominal gm/Id=5/10/15 levels at |VDS|=0.05/0.5 V were reachable.
Gate bias stayed fixed across samples. Simulator-sensitivity and simplified-Croon
predictions are reported separately; no source coefficient was refitted.
This demonstrates configured APM statistics, not silicon calibration.

All 12 circuit families passed 1,024 realizations each, with zero failed runs.
The 1:4 mirror uses individually mapped unequal widths; banks use distinct physical
units and UIDs. Ideal supplies, output clamps and reference/tail currents are excluded.
Nominal systematic mirror error is separated from the random variation. Differential
offset balancing is a measurement, not per-device bias retuning.

| Circuit | N observed sigma | P observed sigma | Meaning |
| --- | --- | --- | --- |
| mirror1 | 10.8039 | 8.8191 | % normalized current mismatch |
| mirror4 | 8.2953 | 7.0709 | % normalized current mismatch |
| diffpair | 11.1309 | 8.2132 | mV input offset |
| bank1 | 10.7021 | 8.7601 | % normalized current mismatch |
| bank4 | 5.1959 | 4.2594 | % normalized current mismatch |
| bank16 | 2.6714 | 2.1390 | % normalized current mismatch |

Bank scaling relative to the N=1 result agreed with 1/sqrt(N):
N ratios were 0.9710 (4 units) and 0.9985 (16); P ratios were 0.9725 and 0.9767.
The declared 204,800-scalar-draw campaign has estimated domain-exhaustion probability 0.00040402, below 0.001. Out-of-domain draws are failures, never clipped or redrawn.

## Replay and IO assessment

All eight N/P replays at -40/27/85/125 °C passed DC/AC/transient execution,
unchanged raw-parameter readback, AC/transient agreement and terminal KCL.
Native qg/qd/qs/qb were finite and nonconstant, with conserved sum in DC/transient.
These temperatures are uncalibrated model predictions; no temperature-dependent
statistical coefficients were invented. The public describe/sample/run example
also passed, including replay of its unchanged serialized realization.

| Assessment | Outcome | Tcap proxy range (nm) | Maximum relative length-fit residual |
| --- | --- | --- | --- |
| io18 / N | UNRESOLVED_WITH_EVIDENCE | 2.9196–3.0455 | 1.37e-05 |
| io18 / P | UNRESOLVED_WITH_EVIDENCE | 3.1391–3.2797 | 1.51e-05 |
| io25 / N | UNRESOLVED_WITH_EVIDENCE | 4.4589–4.5973 | 5.52e-06 |
| io25 / P | UNRESOLVED_WITH_EVIDENCE | 4.4649–4.6089 | 5.94e-06 |

Every assessment contains 48 frequency/bias/geometry rows and 12 fits. The
3.9*epsilon0/C slope proxy is not physical TOXE or measured TINV. Source effective
work function/depletion and matched electrostatic transfer remain unavailable;
substituting |VTH_MG|+0.1 is not justified. No IO beta or default statistical profile
is supplied. Assessment execution passed; numerical IO transfer remains unresolved.

## Beta-source normalization and preserved scope

Original Hart/ST40 beta remains **BLOCKED_NORMALIZATION_CONFLICT for N and P**.
The independent Hart/TSMC40 companion profile is an approved **transfer hypothesis**,
with both Vth and beta derived from that same process source. It is not a correction
of the ST values. The [source audit](v5_source_decision.md) records the explicit
400 nm geometry inference, percent/area units, extraction-offset cancellation,
named independent-Croon rho=0 assumption and independent current-mismatch check.
Source confidence and digitization bounds stay separate from random device variation.
Process-transfer and log-L interpolation uncertainties remain unquantified.

Actual OpenVAF source/build provenance is VERIFIED at the unchanged required pin
`fdf2522b70f42793f64b1c72f0195c96dea0cc19`, with binary, tool/library, source/submodule
and OSDI receipt bindings. Native BSIM4 results are distinguished from OSDI execution.
The original system compiler and historical reports were preserved.

Repository validation passed 194 current tests and 39 separate preflight tests,
with no skips, plus Ruff, REUSE and provenance/distribution checks. All legacy
Benchmark/native/electrical/noise gates passed, including noise method 10/10 and
noise catalog 16/16. Released inputs, frozen v4/preflight records and tag identities
remain exact. Spectre remains model-only experimental/unverified.

The supported implementation is optional VTG N/P local Vth/beta variation within
W=1–4 µm, L=.12–.40 µm, referenced to 300 K, |VDS|=.05 V, VBS=0. It adds no
global/spatial/passive/noise-MC variation, foundry/yield claim or new nominal model.
The earlier interrupted confirmation remains recorded as incomplete in
[development evidence](v5_evaluator_development.json); none of its unfinished
cases were promoted to passes. This fresh candidate used the complete frozen plan.
Independent suites and later P cohorts ran concurrently in separate directories;
the main evaluator then revalidated the same source/seed-bound runs and their hashes.
All acquisition schedules and logs are retained with the ignored evidence.

Separate approval is required before tagging this exact candidate, fresh exact-tag
requalification and publication. This report does not authorize those actions.
