# APM022

APM022 is the independently authored 22 nm-class planar-bulk technology in
Analog Process Models. It is a generic comparison model, not a foundry PDK, is
not foundry-correlated, and is not derived from official PTM22 model-card
values.

## Electrical families and public devices

APM022 declares `lvt`, `svt`, and `hvt`. Each family exposes
`apm022_<family>_nmos` and `apm022_<family>_pmos` with terminal order
`d g s b` and only `w,l`. The supported characterization range is L = 25,
50, or 100 nm, nominal W = 1 µm, and a 0.8 V Operating Profile.

SVT is the independently authored base. LVT and HVT are independently generated
threshold-isolated variants: only signed BSIM4 `VTH0` changes, using
−0.08 V LVT and +0.10 V HVT threshold-magnitude intent around SVT. The release
comparison enforces LVT < SVT < HVT threshold magnitude and the inverse
Ion/Ioff ordering for both polarities and all shared points.

## ngspice

```spice
.include "models/apm022/ngspice/apm022_multivt_models.inc"
.include "models/apm022/families/svt/ngspice/wrapper.inc"

Xn d g s b apm022_svt_nmos w=1u l=25n
Xp d g s b apm022_svt_pmos w=1u l=25n
```

ngspice uses native BSIM4; no generated OSDI is needed.

```console
apm characterize apm022 --output .apm/results/apm022
apm compare-set apm022 threshold --output .apm/results/apm022-multivt
```

See [parameter_generation.md](parameter_generation.md) and each
`variant-generation.toml` for research inputs, independent parameter decisions,
the exact allowed single-parameter delta, behavior contracts, and limitations.
`provenance.toml` hash-declares the complete shipped asset set and records the
PTM exclusion boundary.

Each family has `families/<id>/spectre/model.scs`, model-only
**experimental/unverified** and not parsed or simulated by Spectre.
