<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Analog Process Models v5.0.0

APM v5 adds optional **Research Local Mismatch for APM045 VTG NMOS and PMOS**.
The public `apm research describe/sample/run/check` flow samples independent
physical devices, applies paired threshold/current-factor targets inside
hierarchical circuits, saves the resulting instance parameters, and replays the
same realization across bias, temperature, DC, AC and transient analyses.

The source is the exact approved candidate
`381517fda5107fabf98af7801d5a5103f38e230c`, tree
`8751c3ed03dc31c87f52d3eb3c5c0b4da903ed65`. Later evidence and release-tooling
commits on `main` are not the release source. Publication requires an independent
fresh exact-tag rerun of all 16 candidate gates plus the seventeenth tag gate.

The versioned maximum-gm extraction and full two-observable mapping support
W=1–4 µm and L=0.12–0.40 µm, referenced to 300 K, |VDS|=50 mV and VBS=0.
Qualification covers both polarities, nine anchors and two geometry holdouts,
572 mapping targets, 65,536 pure sampler pairs, 90,112 real-SPICE pairs and
12,288 circuit realizations. Circuit coverage includes 1:1/1:4 mirrors,
differential-pair offset and independent unit banks of 1/4/16 devices. Saved
realizations are checked at −40/27/85/125 °C with parameter readback, terminal
KCL, native charge conservation and AC/transient agreement. Those temperature
responses are uncalibrated model predictions.

APM045 remains a **generic 40/45 nm-class research environment, not a foundry
PDK**. The coherent Hart/TSMC40 companion adaptation is an explicit
**source-transfer hypothesis**. Its geometry inference, extraction convention,
independent-Croon rho=0 assumption and normalization are recorded in the source
audit. Source confidence and digitization bounds remain separate from device
randomness; process-transfer and log-L interpolation uncertainty are unquantified.
Original Hart/ST40 beta remains **BLOCKED_NORMALIZATION_CONFLICT for N and P**;
the companion study is not a correction or a cross-process splice.

Research Global/All remain unsupported. The io18/io25 N/P transfer assessments
remain **UNRESOLVED_WITH_EVIDENCE**, with no default mismatch profile and no
implicit beta=0. No foundry correlation, yield, reliability, statistical-passive,
spatial-variation or noise-Monte-Carlo claim is made. Spectre remains
experimental, model-only and unverified.

The reference is ngspice 47 on EL9 x86_64/WSL2. Actual OpenVAF source/build and
OSDI provenance is verified at the unchanged required pin
`fdf2522b70f42793f64b1c72f0195c96dea0cc19`. Native BSIM4 execution is distinguished
from OSDI-dependent evidence. Released nominal models, the 15-family/30-device
catalog, Benchmark/native semantics, and existing electrical/noise schemas are
preserved, as are immutable v1–v4 tags and historical records.

See `docs/research-local.md` for usage and
`validation/evidence/v5_release_candidate.md` for candidate findings. Exact-tag
and publication evidence are recorded on later `main` under
`validation/evidence/v5_post_release_requalification.json`.
