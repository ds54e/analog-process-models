# APM022 parameter generation

## Provenance boundary

Every value in `ngspice/apm022_models.inc` was authored for Analog Process
Models. No official PTM22 model card was copied, transcribed, numerically
interpolated, fitted, optimized against, or used as a parameter source. No PTM
file was downloaded or used during APM022 development, and APM does not
redistribute one.

The model uses the native BSIM4 implementation in ngspice. BSIM4 equations,
parameter meanings, and documented defaults are model semantics rather than a
technology parameter source. The release card explicitly overrides the
geometry, oxide, doping, threshold, short-channel, transport, resistance,
output, temperature, capacitance, and feature-selection coefficients on which
the supported behavior depends.

## Public inputs

The primary dimensional and operating reference is Shin et al., “Performance
and Yield Benefits of Quasi-Planar Bulk CMOS Technology for 6-T SRAM at the
22-nm Node,” IEEE Transactions on Electron Devices 58 (2011),
[DOI 10.1109/TED.2011.2139213](https://doi.org/10.1109/TED.2011.2139213).
Its public 22 nm-node bulk study uses a 25 nm physical gate length, 27/28 nm
N/P electrical channel lengths, 0.9 nm EOT, 10 nm source/drain-extension
depth, and 1.0 V device optimization, and projects SRAM operation toward
0.8 V. APM takes those as technology-class dimensional inputs and adopts
0.8 V as its generic lower-voltage comparison point. It does not reproduce the
paper's device, yield model, SRAM design, or fitted electrical curves.

BSIM4 topology and parameter semantics follow the official UC Berkeley
[BSIM4 release page](https://www.bsim.berkeley.edu/models/bsim4/) and the
BSIM4 4.8.2 technical manual distributed there. Berkeley identifies BSIM4 as
a bulk-MOSFET model used through the 22/20 nm generation. APM uses the 4.8.2
card dialect supported by native ngspice 47; no Berkeley BSIM source or binary
is vendored for APM022.

The 2011 ITRS Process Integration, Devices, and Structures roadmap was used as
qualitative context for the severe electrostatic and doping tradeoffs of
continued scaled planar bulk CMOS. It supplied no APM model-card value.

## Authored choices

| Choice | APM022 value | Rationale |
| --- | ---: | --- |
| Supply / physical minimum gate length | 0.8 V / 25 nm | Public class-level geometry and the lower-voltage APM comparison contract. |
| Characterized lengths | 25, 50, 100 nm | Exact `L/Lmin = 1, 2, 4` comparison coordinates and the supported v2 length range. |
| EOT / junction depth | 0.9 nm / 10 nm | Direct dimensional inputs from the primary study. |
| Channel / source-drain doping | 2e18 / 1e20 cm^-3 | Independently selected representative high-doping scales for aggressively scaled bulk and source/drain regions. |
| Baseline threshold coefficients | `VTH0=+0.62/-0.62 V`, N/P | Conventional signed long-channel coefficients; terminal constant-current threshold, not raw `VTH0`, is the public contract. |
| Pocket-length terms | `LPE0=LPEB=0` | Explicitly disables BSIM4's nonzero generic pocket default because APM has no evidenced pocket geometry; avoids an undocumented reverse-short-channel bump. |
| Short-channel terms | explicit `DVT0`, `DVT1`, `DVT2`, `ETA0`, `ETAB`, `DSUB` | Adjusted only against APM's observable threshold-rolloff and DIBL contracts. |
| Low-field mobility | 0.025 / 0.015 m^2/(V s), N/P | Representative electron/hole ordering selected against terminal drive and gm behavior, not another model card. |
| Saturation velocity | 1.2e5 / 1.0e5 m/s, N/P | Representative silicon transport scales selected independently. |
| Series-resistance coefficients | `RDSW=20`, `RDSWMIN=5`, N/P | Modest explicit BSIM coefficients that retain monotonic gm through the supported bias range. |
| Output terms | `PCLM=1.5`; output-DIBL current multipliers off | Produces positive finite gds and deliberately low minimum-length intrinsic gain without negative gm. Threshold DIBL remains controlled by the explicit electrostatic terms. |
| Intrinsic capacitance | `CAPMOD=2`, explicit overlaps and smoothing | Supplies stable terminal Y-derived Cgg/Cgd/Cgs over 100 kHz and 1 MHz. |
| Optional leakage effects | gate current, GIDL, impact-ionization additions off | Keeps v2 focused on stable terminal DC and intrinsic admittance behavior; MOS noise and leakage correlation are outside scope. |

N and P share the physical geometry and capacitance basis, while threshold,
mobility, velocity, and electrostatic coefficients are independently selected
per polarity. The stable interface contains only `w` and `l`; no hidden
multiplicity or finger conversion is involved.

## Observable calibration contract

At 27 degC and 25 nm, the required constant-current threshold magnitude is
0.18–0.34 V, DIBL is 0.14–0.30 V/V, intrinsic gain near gm/Id=15 1/V is
2–9, and on-current at `VCTRL=VOUT=0.8 V` is 1.0–2.5 mA/um N and
0.7–2.0 mA/um P. Threshold and intrinsic gain must rise with length while DIBL
falls. All quantities are enforced from terminal sweeps; internal BSIM4 gm/gds
are validation oracles only.

The validated nominal 27 degC observations are:

| Polarity | `|Vth|` at 25/50/100 nm (V) | DIBL at 25/50/100 nm (V/V) | gm/gds near gm/Id=15 at 25/50/100 nm | 25 nm on-current (mA/um) |
| --- | --- | --- | --- | ---: |
| N | 0.2331 / 0.5200 / 0.5968 | 0.1527 / 0.1024 / 0.0701 | 5.46 / 16.21 / 35.55 | 2.364 |
| P | 0.2541 / 0.5441 / 0.6217 | 0.1571 / 0.1081 / 0.0760 | 6.18 / 17.80 / 38.39 | 1.035 |

At minimum length, APM045's already-validated DIBL is 0.0918/0.1145 V/V N/P
and gain near the same normalized inversion coordinate is 11.49/9.49. Its
1.0 V on-current is 0.979/0.653 mA/um. APM022 therefore has larger DIBL,
lower gain, and higher current at a lower 0.8 V supply for both polarities.
APM016F's validated minimum-length DIBL is 0.0372/0.0382 V/V, establishing the
required improved FinFET electrostatic control relative to APM022.

Full sweeps cover both polarities, four temperatures, three lengths, Id-Vg,
Id-Vd, terminal finite-difference gm/gds, constant-current DIBL, and complete
four-terminal complex Y matrices at 100 kHz and 1 MHz. The benchmark-variation
adapter is separately fitted from nine raw threshold and drive points at
`L=2*Lmin`, `VOUT=0.5*VDD`, and the gate grid point nearest gm/Id=15 1/V.

These are generic educational and comparison behaviors. They do not confer
process-design-kit accuracy, foundry correlation, yield prediction, or a
guarantee beyond the documented geometry, bias, and temperature ranges.
