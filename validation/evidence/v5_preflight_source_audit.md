<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM v5 preflight source audit

Audit date: 2026-09-05 UTC. **Beta normalization: UNRESOLVED for N and P.**
The 2022 thesis was retrieved and visually inspected. It repeats the disputed
table and plot; it does not establish a correction. All Hart beta coefficients
remain blocked from runtime adoption. No coefficient was rescaled, fitted to APM,
or used by the independent artificial numerical experiments.

## Exact sources and inspection

| Primary source | Downloaded version and SHA-256 | Inspected references |
| --- | --- | --- |
| [Hart et al., JEDS 2020, pp.263–273](https://pure.tudelft.nl/ws/portalfiles/portal/71537207/09015956.pdf), DOI `10.1109/JEDS.2020.2976546` | Final published version, current version 2020-03-10; `de6e2c0a83a900d563369b34ca10de30b4ae79290f12deefd9c9dfff2e74a31b` | Visual: PDF indices 2–5 / printed pp.264–267, geometry, extraction, Eqs.1–4, Figures 8–10, Table 1. |
| [P.A. 't Hart, 2022 thesis](https://repository.tudelft.nl/file/File_44cb70b1-3c6f-47fb-b6b2-98de516f7514), DOI `10.4233/uuid:0ab4ca6c-dc69-4207-970f-d3b9f0d9c5b4` | Final published version, 143 PDF pages; `71b760b1de42a0b5f86cfd611bc9d8ca6abe3a64ce2761bf9ddda816f4d4158c` | Chapter 3: printed pp.46–55, especially p.52 Figure 6 and p.53 Tables 1/2; pp.57–58, p.67. Printed page = PDF index minus 10. |
| [Hart et al., JEDS 2020, pp.797–806](https://infoscience.epfl.ch/server/api/core/bitstreams/9cb2e29b-35ca-4052-ba6b-93ccbbde82e9/content), DOI `10.1109/JEDS.2020.2988730` | Final published version, current version 2020-08-07; `0f1a691225d51db40440d5e71081bda819a34fda8bda4b08099f5830418e7f5a` | Visual: PDF index 2 / printed p.799; index 5 / p.802, Figures 8–11. Text: setup, extraction and Eqs.7/8. |

Original-paper source facts: LVT 1.1-V core MOS, 300 K comparison, source tied
to body, and linear extraction at `|VDS|=50 mV`. Maximum-gm extraction uses
terminal `ID–VG`; it is not a physical BSIM threshold parameter. Statistics use
99 pairs, or 351 with array devices for selected geometries, with 95% intervals.
Equation 1 normalizes current difference by the pair average. Equation 4 gives
`sigma(Delta beta / beta_bar) = A_beta / sqrt(WL)` using active dimensions.
The beta term in Eq.2 is a pair statistic, not an individual-device sigma.
[Original paper, pp.264–266](https://pure.tudelft.nl/ws/portalfiles/portal/71537207/09015956.pdf).

## Literal coefficient check and visual contradiction

At `W=0.12 µm, L=0.04 µm`, `sqrt(WL)=0.0692820323 µm`.
The following is arithmetic on the printed table, **not an adopted profile**:

| Polarity, 300 K | Printed `A_beta` (`% µm`) | Literal pair sigma | Propagated printed 95% interval |
| --- | --- | --- | --- |
| N | 5.6 ± 0.2 | 80.8290% | 77.9423–83.7158% |
| P | 5.3 ± 0.3 | 76.4989% | 72.1688–80.8290% |

Figure 8b/d labels beta mismatch in percent but uses ticks 0, 0.05, 0.10,
0.15. At the minimum-area point, plotted values are about 0.08 on that axis.
Figures 9a/10a show the 300 K current mismatch below 20% near `|VGS|=1.1 V`.
These are deliberately coarse visual observations, not curve digitization.
[Original paper, p.267](https://pure.tudelft.nl/ws/portalfiles/portal/71537207/09015956.pdf).

Our consistency inference is decisive about rejection, but not correction:
the published additive, nonnegative variance equation requires current-mismatch
sigma to be at least beta-mismatch sigma. The literal N and P table predictions
violate the plotted current-mismatch bound. A percent/fraction interpretation of
Figure 8 and a factor-of-ten table change might appear compatible, but that
requires two unverified editorial assumptions. Pair-to-individual `sqrt(2)`
conversion cannot repair either inconsistency. A common multiplicative
definition of beta cancels from relative mismatch of equal-geometry devices.

The thesis preserves the beta-axis labels in Figure 6 and the same numbers and
units in Table 2. Its later date therefore provides corroboration of the
unresolved print conflict, not independent numerical validation.
[Thesis, pp.52–53](https://repository.tudelft.nl/file/File_44cb70b1-3c6f-47fb-b6b2-98de516f7514).

## Distinct-process follow-up

The thesis identifies the original experiment as **STMicroelectronics 40-nm LVT**
(pp.45–46). The later study uses **TSMC 40-nm standard-Vt** devices (p.57), and
p.58 explicitly distinguishes the fabrication process and redesigned test
structures. These identities describe the measured sources; APM045 remains
generic 40/45 nm-class and gains no foundry correlation.
[Thesis, pp.45–58](https://repository.tudelft.nl/file/File_44cb70b1-3c6f-47fb-b6b2-98de516f7514).

The companion article independently confirms the different process on p.799.
Its p.802 beta-mismatch plots have percent ticks up to 20, while coefficient
plots have `% µm` ticks up to 5. This is a separate, potentially useful source
lead, not a correction to the first table. It uses ELR extraction and 72 pairs
per geometry; minimum-size PMOS subthreshold data are excluded for leakage.
Its larger-length plot legends also need reconciliation with the geometry
inventory before any new profile. No coefficients were digitized or adopted.
[Companion article, pp.799–802](https://infoscience.epfl.ch/server/api/core/bitstreams/9cb2e29b-35ca-4052-ba6b-93ccbbde82e9/content).

## Evidence, limitations and next decision

Raw downloads, full text, rendered pages, arithmetic and access/search notes are
under ignored `.apm/v5-preflight/source-audit/`. The file inventory and the exact
subset visually inspected are in `manifest.json`, SHA-256
`ad0092b950df15ffec82e65fd69f54e1280296910fae1193a63f0d8e8c37ef44`.
Rendering used isolated PyMuPDF 1.26.4 at matrix `(1.7,1.7)`; downloaded-PDF
hashes above are the source authority. Exact URLs and retrieval times are also
in [`source_audit.toml`](../../tools/v5_preflight/source_audit.toml).

Targeted title/DOI searches did not locate an author correction or raw pair
dataset. The downloaded [Crossref record](https://api.crossref.org/works/10.1109/JEDS.2020.2976546)
has no update relation, which does not prove none exists. IEEE's article page
required JavaScript verification; no access bypass was attempted. The 2018
precursor's primary metadata was inspected, but its full text was not obtained.
No author contact occurred. Author extraction code, measurement grid and raw
pair values were not obtained. The thesis file record has no clear open
redistribution license, so papers, text and screenshots remain local; only our
findings and hashes are committed.

The smallest justified source clause for a future v5 contract is an explicit
coefficient gate: pin the source and process; resolve units and pair versus
device normalization; bind geometry, temperature and extraction; quantify
source/reanalysis uncertainty; and independently check predicted total current
mismatch. Keep Hart's original N/P beta values blocked until that gate passes.
An alternative source needs its own auditable profile decision. Successful
artificial mappings cannot supply missing measured coefficients. Vth transfer
qualification remains separate. This preflight creates no statistical profile
or full-v5 authorization.
