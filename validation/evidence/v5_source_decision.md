<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# V5 source decision: independent companion reanalysis

The original Hart/ST40 LVT N/P beta values remain **BLOCKED_NORMALIZATION_CONFLICT**.
Neither their values nor their threshold coefficients enter the new profile.
The thesis remains context, not a correction; its process distinction and hashes
are preserved in the frozen preflight audit.

Adopt `hart-tsmc40-300k-v1` as an explicitly named **source-transfer hypothesis**
from the independent [companion article](https://doi.org/10.1109/JEDS.2020.2988730).
This approves a quantitative input model for numerical qualification. It does not
establish APM/silicon correlation or eliminate source and transfer uncertainty.
The [EPFL PDF](https://infoscience.epfl.ch/server/api/core/bitstreams/9cb2e29b-35ca-4052-ba6b-93ccbbde82e9/content)
has SHA-256 `0f1a691225d51db40440d5e71081bda819a34fda8bda4b08099f5830418e7f5a`.

The adaptation and runtime coefficients are under `variation/research/apm045/derived/`.
`tools/v5/source_reanalysis.py` extracts the pinned PDF's vector paths, error-bar
junctions and separately plotted current curves. Full PDFs, renderings and vector
intermediates remain ignored under `.apm/v5/sources/`. The derived dataset retains
CC-BY-4.0 credit and an adaptation notice; the article's first page expressly gives
that license. Neither the thesis nor the extraction review is redistributed.

## Geometry decision and normalization

The source is standard-Vt, nominally 1.1 V, TSMC40 by the thesis attribution.
Use its 300 K, 50 mV triode data with body tied to source, drawn W/L and 72 pairs
(three dies). The minimum PMOS leakage exclusion concerns subthreshold analysis;
it does not justify deleting its strong-inversion points. APM VTG stays within 1 V.

**The long-L legend is erroneous; the 400 nm assignment is an explicit APM
reanalysis inference, not an author-issued correction.** Fig. 2 contains no
L=1.2 um geometry. Figs. 5, 7 and 12 identify the large device as W=1.2 um,
L=400 nm, and pp.802–803 identify the long-length coefficient trend as 400 nm.
Thus the conflicting legend copied the large-device width into the L label.
The three reported length groups can be associated with 40/120/400 nm without
inventing an unlisted 1.2 um length. The inconsistency remains visible in the data
record. A contradictory primary inventory would invalidate this adoption.

The companion's p.800 overline denotes an ensemble average over matched pairs
of a geometry. Its beta axes are percent, unlike the unresolved original-ST
representation. We interpret sigma(delta beta / population beta) as a pair
statistic. Independent individual-device sigma divides that coefficient by
sqrt(2 W L). The actual pair-average ratio 2(beta1-beta2)/(beta1+beta2) is a separate
nonlinear diagnostic; it is not silently substituted for population normalization.

| Polarity | L nm | A_VT mV um | A_beta percent um |
| --- | ---: | ---: | ---: |
| N | 40 | 3.161 | 0.583 |
| N | 120 | 3.322 | 0.731 |
| N | 400 | 6.703 | 0.990 |
| P | 40 | 2.911 | 0.654 |
| P | 120 | 3.528 | 0.835 |
| P | 400 | 4.598 | 0.803 |

These are derived estimates, not a transcription of an author coefficient table.
Conversions are explicit: mV um × 1e-9 -> V m; percent um × 1e-8 -> fractional m.
The adaptation records source 95% intervals and a conservative 0.5 PDF-point
coordinate bound separately. Interpolate A in log L; use the observed area-law
form for W. The numerical rectangle W=1–4 um, L=.12–.40 um is a transfer hypothesis,
not a measured APM domain. Interpolation and between-process uncertainty are
unquantified epistemic limitations and are never sampled independently per MOS.
Zero Vth/beta correlation is the named independent-Croon approximation in Eq.7,
not a measured covariance or a universal process law.

## Extraction transfer

The full [2002 review](https://doi.org/10.1016/S0026-2714(02)00027-6), Sec.2.2 p.585,
was inspected through a public PDF reader after the publisher endpoint failed.
It specifies the maximum-ID-slope tangent and prints an additive D/2 correction.
The authors' [2013 lecture](https://www-elec.inaoep.mx/seminario2013/ortiz_SNDA13.pdf),
slide 9, describes subtraction. The publisher PDF download was unavailable; no
file hash is asserted for the reader-only 2002 copy. The downloaded lecture is
preserved in the ignored source manifest.

APM explicitly keeps its own versioned cubic-spline, unsmoothed MG extractor,
with subtraction. Under the same tangent, the two conventions differ by D;
at fixed 50 mV that deterministic offset cancels in equal-bias Vth differences.
The reference comparison checks this on identical curves. Beta is gm_max/D;
constant geometry or factor-of-two drive conventions cancel in a same-geometry
fractional beta statistic. This does not establish identical author smoothing or
numerical code. No author raw extraction software was supplied. These limitations
are retained as method-transfer uncertainty, not concealed as exact code identity.

## Independent source checks and limits

Vector slopes in Figs.8/9 support the 40 nm coefficient units; the temperature
plots in Figs.10/11 supply the separate length records. Fig.5 ID-VG traces provide
gm/Id directly from the source curves, without using APM. Applying the extracted
coefficients in the source's Croon equation is then compared with the **measured**
Fig.12 triode curves, not its fitted/model overlays. Two finite gate windows assess
slope sensitivity. The source renderer contains 49 traces of each polarity per
geometry although the caption describes 48 devices; one trace may be an aggregate.
We use their mean slope as a figure-level estimate and do not label these paths
as 49 independent measurements.

Central prediction/observation ratios are not uniformly one: the development
points span about 0.83–1.27 (N) and 0.96–1.55 (P). All investigated intervals
are compatible after separately propagating coefficient intervals, a 72-pair
normal-sigma interval and the declared display bound. The smallest long-device
currents have poor relative figure resolution. Additional bias cross-checks at
N VG=.8/.95 V and P VG=.15/.3 V also agree within those bounds. This supports
normalization and order of magnitude, not a precise fit at each geometry.
The plotted point uncertainty and geometry fit scatter preclude tighter claims.
All these are source-audit development observations made before the numerical
confirmation plan, not independent silicon validation of the implementation.

The source decision can pass while implementation, tails, statistical recovery,
circuits and release qualification still fail. No nominal APM parameter was fitted
to any source figure. No author contact, paid access or external message occurred.
