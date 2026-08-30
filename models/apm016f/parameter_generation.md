# APM016F parameter generation

## Provenance boundary

The APM016F parameter cards are independently authored for this project. No
official PTM-MG model card was copied, transcribed, numerically interpolated,
optimized against, or used as a parameter source. PTM-MG is not distributed by
APM. This boundary applies to both polarities and every value in
`ngspice/apm016f_models.inc`.

The compact-model equations and parameter semantics come from the pinned,
redistributable UC Berkeley BSIM-CMG 112.1.0 implementation. Model defaults are
part of that documented engine; the release card explicitly overrides the
parameters that define its structural, threshold, transport, short-channel,
output-conductance, and feature-selection behavior.

## Public inputs

The dimensional starting point is the open-access experimental/calibration
study “Analysis of electrical characteristics of bulk FinFET according to
spacer length” (Nanoscale Research Letters 10, 2015,
[DOI 10.1186/s11671-015-0739-0](https://doi.org/10.1186/s11671-015-0739-0)). Its
16 nm bulk high-k/metal-gate reference device reports an 8 nm rectangular fin,
32 nm fin height, 1 nm EOT, source/drain concentration of 1e20 cm^-3, channel
concentration of 1.5e18 cm^-3, and an effective work-function range of 4.4 to
4.5 eV used to obtain approximately 0.25 V threshold behavior.

The operating-voltage and electrostatic sanity basis is the primary IEDM 2014
paper “An Enhanced 16nm CMOS Technology Featuring 2nd Generation FinFET
Transistors and Advanced Cu/low-k Interconnect for Low Power and High
Performance Applications”
([DOI 10.1109/IEDM.2014.7046970](https://doi.org/10.1109/IEDM.2014.7046970)).
It reports 0.8 V device measurements, a 48 nm fin pitch, DIBL below 40 mV/V,
and subthreshold swing below 70 mV/dec for that foundry technology. APM uses
these only as representative public class-level inputs, not as a claim of
foundry matching.

BSIM-CMG topology, geometry, and extraction semantics follow the official
[BSIM-CMG technical manual](https://bsim.gitbooks.io/bsimcmg/content/) and
[Berkeley BSIM-CMG release page](https://www.bsim.berkeley.edu/models/bsimcmg/).
In particular, `GEOMOD=1` selects a triple-gate fin, internal current and charge
scale with `NFIN`, and `SHMOD=0` disables self-heating.

## Authored choices

| Choice | APM016F value | Rationale |
| --- | ---: | --- |
| Supply / minimum gate length | 0.8 V / 16 nm | Public 16 nm-class operating point and device gate length. |
| Topology | bulk triple-gate (`BULKMOD=1`, `GEOMOD=1`) | Matches the public bulk FinFET structure and exercises genuine multi-gate equations. |
| Fin geometry | 32 nm high, 8 nm thick, 48 nm pitch | Direct public dimensional inputs listed above. |
| EOT | 1 nm | Direct public dimensional input. |
| Channel / S-D concentration | 1.5e24 / 1.0e26 m^-3 | SI conversion of the public 1.5e18 / 1e20 cm^-3 values. |
| N gate work function | 4.45 eV | Midpoint of the published 4.4–4.5 eV calibration interval. |
| P gate work function | 4.75 eV | Independently selected complementary metal-gate value to meet APM's symmetric threshold-magnitude behavior target; not taken from a model card. |
| Low-field mobility | 0.030 / 0.014 m^2/(V s), N/P | Representative silicon electron/hole ordering, selected against APM's observable current and transconductance requirements. |
| Saturation velocity | 1.0e5 / 0.8e5 m/s, N/P | Representative silicon transport scale, selected independently. |
| Short-channel terms | explicit `CDSC`, `DVT0`, `DVT1`, `ETA0`, `DSUB` | Adjusted only against the documented APM threshold-rolloff and DIBL ranges. |
| Output terms | explicit `PCLM`, `PDIBL1`, `PDIBL2` | Adjusted only against positive finite output conductance and sensible intrinsic gain. |
| Parasitic and leakage selectors | intrinsic CV; optional gate/GIDL/II effects off | Keeps v2 focused on stable terminal DC and intrinsic admittance behavior. |
| Self-heating | off (`SHMOD=0`) | Required APM v2 boundary. |

The N and P cards share physical geometry and electrostatic coefficients, but
their work function, mobility, and velocity are separately authored. No hidden
effective-width conversion is used by the public interface or stored results.

## Observable calibration contract

At 27 °C and minimum length, the constant-current threshold magnitude target is
0.20–0.35 V and DIBL target is positive and no greater than 0.08 V/V. The APM
constant-current convention is 100 nA per fin, stored explicitly as
`criterion = 100 nA * NFIN`; it is a project measurement convention rather than
a compact-model parameter.

At common legal bias and length for `NFIN = 1, 2, 4`, normalized Id and gm must
remain within 2%, each reported capacitance per fin within 2%, gm/Id within 2%,
and gm/gds within 5%. Full terminal sweeps, finite-difference gm/gds, raw signed
currents, complete complex Y matrices, derived capacitances, temperature
behavior, threshold rolloff, and DIBL are retained as real-tool evidence. A
later cross-kit gate compares APM016F electrostatic control with the
independently authored APM022 deck.

These targets define a generic educational/benchmark model. They do not confer
process-design-kit accuracy or predict any commercial 16 nm process.
