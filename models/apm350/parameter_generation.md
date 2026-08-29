# APM350 parameter generation and source audit

## Selected provenance boundary

APM350 is an APM-authored, Apache-2.0 open generic reference. It uses native
BSIM3 in ngspice, but it does not redistribute or numerically transcribe a
third-party process card. The technology label is deliberately
`0.35um-class`, while the actual minimum modeled and supported channel length
is 0.4 um.

The preferred project-definition candidate was audited before implementation:
`silicon-vlsi-org/eda-technology` commit
`70c89ecac61bf3409322355463650775f5b29f5e`, path
`scn4m_subm/models/scn4m_cnrs_bsim3v1.lib`, SHA-256
`7c7ec1d43149b84ac9f7eb859e62cced62fc3f74efc6dfe929558541eb16f19c`.
The repository has an MIT root license, but the exact parameter file has no
author, copyright, original-source, or file-level license statement. Its Git
history begins with the whole card appearing in one 2024 commit and provides
no earlier provenance. That is insufficient under APM's rule against assuming
that a repository root license necessarily covers imported model parameters.
The candidate card was therefore rejected and is neither copied nor shipped.
None of its compact-model parameter values was used to author APM350.

The candidate repository's MIT-licensed
[README at the pinned commit](https://github.com/silicon-vlsi-org/eda-technology/blob/70c89ecac61bf3409322355463650775f5b29f5e/README.md)
is used only for three non-card, class-level statements: the SCN4M_SUBM
description reports Lmin=0.4 um, Wmin=0.6 um, and VDD=5 V. These define the
public operating envelope; they do not imply compatibility with a MOSIS
process or foundry correlation.

## Compact-model semantics

Parameter names, units, equations, and the version dialect follow the official
UC Berkeley [BSIM3 model page](https://www.bsim.berkeley.edu/models/bsim3/)
and its BSIM3v3.3.0 technical manual. APM uses the native ngspice 47 level-49
implementation. No Berkeley model source or binary is vendored for APM350.

## Independently authored choices

| Choice | APM350 value | Rationale |
| --- | ---: | --- |
| Technology class / actual Lmin | 0.35 um / 0.4 um | Preserves the honest distinction required by the APM goal and the open class description. |
| Supply / published Wmin | 5 V / 0.6 um | Class-level statements from the pinned open README; the default characterized width is 1 um. |
| Characterized lengths | 0.4, 0.8, 1.6 um | Exact `L/Lmin=1,2,4` normalized comparison coordinates. |
| Oxide / junction depth / channel doping | 8 nm / 0.15 um / 1.5e17 cm^-3 | Rounded, independently selected mature-planar scales; not values transcribed from the rejected card. |
| Baseline threshold coefficients | `VTH0=+0.55/-0.65 V`, N/P | Independently selected signed mature-CMOS values; terminal constant-current threshold is authoritative. |
| Low-field mobility | 500 / 200 cm^2/(V s), N/P | Rounded electron/hole transport ordering for a generic mature planar comparison. |
| Saturation velocity | 1.0e5 / 0.8e5 m/s, N/P | Rounded silicon transport scales. |
| Short-channel terms | Explicit DVT, ETA, DSUB terms | Selected against observable positive DIBL and strict improvement with length, without using another card. |
| Series resistance | `RDSW=200/300`, N/P | Explicit generic values retaining monotonic Id and gm over the supported envelope. |
| Output terms | Explicit PCLM, PDIBLC, DROUT, PVAG | Produces positive finite gds and mature-node intrinsic gain that rises with length. |
| Intrinsic capacitance | `CAPMOD=2`, explicit overlaps | Provides stable, positive terminal-Y-derived Cgg/Cgd/Cgs at 100 kHz and 1 MHz. |
| Internal diffusion geometry | 0.4 um source/drain extension per side | The public wrapper derives area and perimeter from `w`; this makes junction geometry explicit and eliminates BSIM3's omitted-perimeter warnings without exposing layout parameters. |

The card explicitly selects every major geometry, threshold, short-channel,
transport, resistance, output, temperature, and capacitance coefficient on
which the supported behavior relies. N and P choices are independent except
for the shared physical class. The public interface remains only `w` and `l`;
source/drain area and perimeter are wrapper-internal implementation details.

## Observable behavior contract

At 27 degC and L=0.4 um, the required constant-current threshold magnitude is
0.35–0.90 V, DIBL is 0–0.08 V/V, intrinsic gain near gm/Id=15 1/V is 15–250,
and on-current at `VCTRL=VOUT=5 V` is 0.2–3.0 mA/um N and 0.1–2.0 mA/um P.
Threshold and intrinsic gain must rise strictly with length while DIBL falls.

The validated nominal observations are:

| Polarity | `|Vth|` at 0.4/0.8/1.6 um (V) | DIBL at 0.4/0.8/1.6 um (V/V) | gm/gds near gm/Id=15 at 0.4/0.8/1.6 um | 0.4 um on-current (mA/um) |
| --- | --- | --- | --- | ---: |
| N | 0.4731 / 0.4857 / 0.5057 | 0.02916 / 0.02001 / 0.01167 | 27.13 / 59.72 / 109.10 | 1.100 |
| P | 0.5876 / 0.6172 / 0.6449 | 0.03531 / 0.02137 / 0.01074 | 33.80 / 59.27 / 144.24 | 0.609 |

All values are terminal measurements. Internal BSIM3 gm/gds are validation
oracles only. Full sweeps cover both polarities, four temperatures, all three
lengths, Id-Vg, Id-Vd, terminal finite-difference gm/gds, constant-current
DIBL, and complete four-terminal complex Y matrices.

These results are generic educational and comparison behavior. They are not a
manufacturable PDK, a MOSIS/TSMC/foundry model, a silicon fit, or a yield
prediction, and no accuracy is claimed outside the documented geometry, bias,
and temperature envelope.
