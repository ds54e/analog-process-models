# APM045

APM045 is APM's 45 nm planar predictive/open reference. It exposes four nominal
FreePDK45 BSIM4 electrical families. The upstream cards disclose customized PTM
ancestry and representative published bulk-Si tuning; they are not a
silicon-correlated PDK and are not numeric source material for APM022.

## Electrical families

| Family | Public devices | Threshold/gate stack | Default profile |
| --- | --- | --- | ---: |
| `vtl` | `apm045_vtl_nmos`, `apm045_vtl_pmos` | low-VT, thin | 1.0 V |
| `vtg` | `apm045_vtg_nmos`, `apm045_vtg_pmos` | general-VT, thin | 1.0 V |
| `vth` | `apm045_vth_nmos`, `apm045_vth_pmos` | high-VT, thin | 1.0 V |
| `thkox` | `apm045_thkox_nmos`, `apm045_thkox_pmos` | general-VT, thick | 2.0 V APM-selected |

Each planar device uses `d g s b` and only `w,l`. The upstream-documented
drawn range is L = 0.05–1 µm and W = 0.09–16 µm. THKOX's 2.0 V profile is an
APM-selected behavior profile, not an upstream reliability rating. VTG/THKOX
common-overlap comparison is separately simulated at 1.0 V.

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
```

The threshold set reports equal-bias/equal-inversion VTL/VTG/VTH views. The
gate-stack set reports native-profile and 1.0 V common-overlap VTG/THKOX views.

Each family has `families/<id>/spectre/model.scs`, model-only
**experimental/unverified** and not parsed or simulated by Spectre.
