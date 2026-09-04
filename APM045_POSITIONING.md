<!-- SPDX-FileCopyrightText: APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM045 positioning after v4.0.0

## Current interpretation

APM045 should be interpreted as a **generic 40/45 nm-class planar bulk CMOS
research environment**, not as a TSMC40/45 model, a TSMC55 proxy, or a
foundry-correlated PDK.

This positioning does not change any released model card, electrical result,
qualification gate, tag, or release artifact. The immutable `v4.0.0` release
continues to mean exactly what its frozen technical and release contracts say.
This document refines only the recommended process-generation interpretation
for subsequent research on `main`.

## Why 40/45 nm-class is the best fit

The physical/model anchor of APM045 is FreePDK45: an open generic 45 nm planar
bulk BSIM4 reference with VTL/VTG/VTH and legacy THKOX model flavors. APM v4
preserves those upstream-derived families and adds independently APM-authored
`io18` and `io25` mixed-voltage families.

Public TSMC technology information provides a useful generation-level sanity
check without supplying any APM model parameter:

- TSMC's 45 nm logic family publicly described multiple-Vt core devices, a
  low-power triple-gate-oxide option, and 1.8 V, 2.5 V, and 3.3 V I/O options.
  Source: https://pr.tsmc.com/english/news/1429
- TSMC's 40 nm process was publicly described as a direct linear shrink from
  its 45 nm counterpart. The 40 nm GP/LP families also included mixed-signal
  and RF options, low-power triple-gate-oxide support, multiple-Vt core
  devices, and 1.8 V/2.5 V I/O options.
  Source: https://pr.tsmc.com/schinese/news/1490
- TSMC continues to list 40 nm as a production logic/ULP platform, including
  specialty RF, embedded-flash, BCD, SOI, and enhanced analog use cases.
  Sources:
  https://www.tsmc.com/english/dedicatedFoundry/technology/logic/l_40nm
  https://www.tsmc.com/english/dedicatedFoundry/technology/platform_IoT

The resulting APM045 palette therefore has a useful generation-level analogy:

```text
APM045 research family     40/45 nm-generation interpretation
------------------------   ------------------------------------
VTL / VTG / VTH            multiple-Vt ~1 V-class core study
io18                       generic 1.8 V-class mixed-voltage MOS
io25                       generic 2.5 V-class mixed-voltage MOS
THKOX                      legacy FreePDK45 thick/high-Vt anchor
```

This is an analogy of device classes and design use, not a mapping to any
specific TSMC device primitive or process option.

## Why not 55 nm-class as the primary interpretation

55 nm remains a nearby planar bulk generation, and mixed-voltage lessons may
transfer qualitatively. However, the APM045 upstream anchor is explicitly a
45 nm predictive/open reference, while public TSMC information describes 40 nm
as a direct shrink of 45 nm. That relationship is more direct than using a
55 nm generation label.

Consequently, subsequent APM documentation and circuit-research work should
prefer **generic 40/45 nm-class** when describing APM045 as a whole. Historical
v4.0.0 wording that says `45/55 nm-class` remains part of the immutable release
record and should not be rewritten retroactively.

## Claim boundary

The 40/45 nm-class positioning does **not** authorize any of the following:

- calling APM045 a TSMC40 or TSMC45 model;
- claiming correlation to TSMC, UMC, Fujitsu, or another foundry process;
- inferring foundry design-rule minima from APM-supported geometry floors;
- treating APM operating-profile voltages as reliability or safe-voltage
  ratings;
- copying public physical oxide thicknesses into BSIM `TOXE`;
- treating APM current density, capacitance, gm/gds, mismatch, noise, leakage,
  or geometry as production-process values;
- using the APM-authored epistemic ensemble as process variation.

FreePDK45-derived families retain their exact upstream provenance. The v4
`io18`/`io25` families remain independently APM-authored behavior-constrained
research models.

## Circuit-research implication

For later LDO and mixed-voltage research, the most defensible transfer target is
not an absolute transistor size or current density. Prefer conclusions in
coordinates such as:

- gm/Id and gds/Id;
- intrinsic gain and its length elasticity;
- normalized voltage headroom;
- required control-voltage range;
- relative current-density and width tradeoffs between voltage classes;
- intrinsic capacitance/charge tradeoffs;
- pass-device conduction versus gate-drive burden;
- loop, charge-deficit, transient, and PSRR mechanisms.

Absolute W, absolute Id/W, layout parasitics, reliability, mismatch, leakage,
and foundry-specific corner conclusions must be re-established in the actual
PDK before product use.

## Status

Positioning: **GENERIC 40/45 NM-CLASS**

Model/release changes required: **NONE**

`v4.0.0` tag and GitHub Release: **UNCHANGED / IMMUTABLE**
