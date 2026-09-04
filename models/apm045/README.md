# APM045

APM045 is APM's 45 nm planar predictive/open reference. It exposes four
FreePDK45-derived BSIM4 electrical families plus two independently APM-authored
generic mixed-voltage families. The upstream cards disclose customized PTM
ancestry and representative published bulk-Si tuning; they are not a
silicon-correlated PDK and are not numeric source material for the APM-authored
families.

## Electrical families

| Family | Public devices | Threshold/gate stack | Default profile |
| --- | --- | --- | ---: |
| `vtl` | `apm045_vtl_nmos`, `apm045_vtl_pmos` | low-VT, thin | 1.0 V |
| `vtg` | `apm045_vtg_nmos`, `apm045_vtg_pmos` | general-VT, thin | 1.0 V |
| `vth` | `apm045_vth_nmos`, `apm045_vth_pmos` | high-VT, thin | 1.0 V |
| `thkox` | `apm045_thkox_nmos`, `apm045_thkox_pmos` | general-VT, thick | 2.0 V APM-selected |
| `io18` | `apm045_io18_nmos`, `apm045_io18_pmos` | APM-authored generic 1.8 V class | 1.8 V |
| `io25` | `apm045_io25_nmos`, `apm045_io25_pmos` | APM-authored generic 2.5 V class | 2.5 V |

Each planar device uses `d g s b` and only `w,l`. The upstream-documented
drawn range for the four FreePDK45 families is L = 0.05–1 µm and W =
0.09–16 µm. The qualified APM-supported model ranges are L = 0.08–2 µm
and W = 0.25–16 µm for `io18`, and L = 0.18–2 µm and W = 0.25–16 µm for
`io25`. Those bounds describe tested model behavior, not foundry design-rule
minima.

THKOX's 2.0 V profile is an APM-selected behavior profile, not an upstream
reliability rating. VTG/THKOX common-overlap comparison is separately simulated
at 1.0 V. The new families add `common_overlap_1v0` profiles, and `io25` also
adds `common_overlap_1v8`, for explicitly labeled common-bias comparisons.
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

The new cards are deterministic outputs of the offline model-generation flow
under `tools/modelgen/apm045_mixed_voltage/`. Public source facts and their
allowed/forbidden uses are recorded in `mixed_voltage_evidence.toml`; exact
generation lineage is recorded in `provenance.toml`. The retained candidate
ensemble represents model-construction uncertainty and is not process,
mismatch, yield, or foundry variation.

The `io18` and `io25` families are generic research models. They are not
correlated to TSMC, UMC, or other foundry silicon; do not establish calibrated
leakage or process-noise accuracy; include no layout-dependent parasitics; and
provide no manufacturability or reliability qualification. A standalone 3.3 V
family is outside APM v4.

Each family has `families/<id>/spectre/model.scs`, model-only
**experimental/unverified** and not parsed or simulated by Spectre.
