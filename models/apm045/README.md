# APM045

APM045 is APM's 45 nm planar predictive/open reference and is best interpreted
for subsequent research as a **generic 40/45 nm-class planar bulk CMOS
research environment**. It exposes four FreePDK45-derived BSIM4 electrical
families plus two independently APM-authored generic mixed-voltage families.
The upstream cards disclose customized PTM ancestry and representative
published bulk-Si tuning; they are not a silicon-correlated PDK and are not
numeric source material for the APM-authored families.

This positioning is generation-level only. APM045 is not a TSMC40/45 model,
a TSMC55 proxy, or a foundry-correlated PDK. The released `v4.0.0` tag and
qualification evidence remain unchanged. See
[`APM045_POSITIONING.md`](../../APM045_POSITIONING.md) for the post-release
rationale and transfer boundary. Completed v4 contracts and release evidence
remain frozen historical records.

The `apm045` identifier remains the technical 45 nm FreePDK45-based technology
namespace. For post-release positioning, public TSMC 40/45 nm information is
used only as a generation-level taxonomy sanity check: TSMC 45 nm publicly
described multiple-Vt core devices, a low-power triple-gate-oxide option, and
1.8 V/2.5 V/3.3 V I/O options; TSMC 40 nm was described as a direct linear
shrink from 45 nm and retained multiple-Vt core, mixed-signal/RF,
triple-gate-oxide, and 1.8 V/2.5 V I/O options. It was not a numerical input,
fitting target, or calibration reference for the released `io18`/`io25`
model-generation flow. No TSMC numerical model parameter, geometry rule,
reliability value, or electrical curve is used by APM045.

## Electrical families

| Family | Public devices | Threshold/gate stack | Default profile |
| --- | --- | --- | ---: |
| `vtl` | `apm045_vtl_nmos`, `apm045_vtl_pmos` | low-VT, thin | 1.0 V |
| `vtg` | `apm045_vtg_nmos`, `apm045_vtg_pmos` | general-VT, thin | 1.0 V |
| `vth` | `apm045_vth_nmos`, `apm045_vth_pmos` | high-VT, thin | 1.0 V |
| `thkox` | `apm045_thkox_nmos`, `apm045_thkox_pmos` | general-VT, thick | 2.0 V APM-selected |
| `io18` | `apm045_io18_nmos`, `apm045_io18_pmos` | APM-authored generic 1.8 V class | 1.8 V |
| `io25` | `apm045_io25_nmos`, `apm045_io25_pmos` | APM-authored generic 2.5 V class | 2.5 V |

The recommended 40/45 nm-generation interpretation is:

```text
VTL / VTG / VTH   multiple-Vt ~1 V-class core study
io18              generic 1.8 V-class mixed-voltage MOS
io25              generic 2.5 V-class mixed-voltage MOS
THKOX             legacy FreePDK45 thick/high-Vt anchor
```

This is a comparison/research palette, not a claim that these APM families map
to specific primitives or coexist exactly in any one foundry process option.

Each planar device uses `d g s b` and only `w,l`. The upstream-documented
drawn range for the four FreePDK45 families is L = 0.05–1 µm and W =
0.09–16 µm. The qualified APM-supported model ranges are L = 0.08–2 µm
and W = 0.25–16 µm for `io18`, and L = 0.18–2 µm and W = 0.25–16 µm for
`io25`. Those bounds describe tested model behavior, not foundry design-rule
minima.

THKOX's 2.0 V profile is an APM-selected behavior profile, not an upstream
reliability rating. VTG/THKOX common-overlap comparison is separately simulated
at 1.0 V. The io18/io25 families expose `common_overlap_1v0` profiles, and
`io25` also exposes `common_overlap_1v8`, for explicitly labeled common-bias
comparisons.
Operating-profile voltage is a characterization choice, not a safe-operating,
breakdown, lifetime, or reliability rating.

## ngspice

Each family binding selects its exact upstream N/P cards. For VTG:

```spice
.include "models/apm045/vendor/freepdk45/NMOS_VTG.inc"
.include "models/apm045/vendor/freepdk45/PMOS_VTG.inc"
.include "models/apm045/families/vtg/ngspice/wrapper.inc"

Xn d g s b apm045_vtg_nmos w=1u l=0.05u
```

Native BSIM4 needs no OSDI artifact. Exact FreePDK45 revision, retained
README/license/manual, imported paths, and SHA-256 hashes are in
`provenance.toml`.

```console
apm characterize apm045 --output .apm/results/apm045
apm compare-set apm045 threshold --output .apm/results/apm045-threshold
apm compare-set apm045 gate_stack --output .apm/results/apm045-gate-stack
apm compare-set apm045 mixed_voltage --output .apm/results/apm045-mixed-voltage
```

The threshold set reports equal-bias/equal-inversion VTL/VTG/VTH views. The
gate-stack set reports native-profile and 1.0 V common-overlap VTG/THKOX views.
The versioned mixed-voltage set reports native, common-1.0 V, common-1.8 V,
equal-physical-length, equal-relative-length, and equal-inversion terminal
views for VTG/io18/io25 as applicable. It preserves exact source identities,
raw signed currents, complete Y matrices, explicit target-solver states, and
intrinsic public-wrapper gate-charge trajectories.

The released io18/io25 cards are deterministic outputs of the completed
offline model-generation flow under `tools/modelgen/apm045_mixed_voltage/`.
Public source facts and their allowed/forbidden uses are recorded in
`mixed_voltage_evidence.toml`; exact generation lineage is recorded in
`provenance.toml`. The retained candidate ensemble represents
model-construction uncertainty and is not process, mismatch, yield, or foundry
variation.

The `io18` and `io25` families are generic research models. They are not
correlated to TSMC, UMC, or other foundry silicon; do not establish calibrated
leakage or process-noise accuracy; include no layout-dependent parasitics; and
provide no manufacturability or reliability qualification. A standalone 3.3 V
family is outside the released portfolio and current maintenance scope.

For later LDO or mixed-voltage research, transfer normalized mechanisms and
tradeoffs rather than absolute foundry quantities. gm/Id, gds/Id, normalized
headroom, length elasticity, relative current-density/width tradeoffs,
intrinsic capacitance/charge, pass-device versus gate-drive burden, loop
behavior, and transient charge balance are appropriate research outputs.
Absolute W, Id/W, mismatch, leakage, layout parasitics, and reliability must be
re-established in the actual target PDK.

Each family has `families/<id>/spectre/model.scs`, model-only
**experimental/unverified** and not parsed or simulated by Spectre.
