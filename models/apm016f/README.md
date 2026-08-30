# APM016F

APM016F is the independently authored 16 nm-class generic FinFET technology in
Analog Process Models. It uses the pinned UC Berkeley BSIM-CMG 112.1.0 engine.
It is not a foundry PDK, is not foundry-correlated, and is not derived from
official PTM-MG model-card values.

## Electrical families and public devices

APM016F declares `lvt`, `svt`, and `hvt`. Each family exposes
`apm016f_<family>_nfet` and `apm016f_<family>_pfet` with terminal order
`d g s b` and only `l,nfin`. `nfin` is a positive integer; APM exposes no
fabricated continuous width or common multiplicity/finger parameter.

The characterized set uses L = 16, 32, or 64 nm; NFIN = 1, 2, or 4; and a
0.8 V Operating Profile. SVT is the independently authored base. LVT/HVT are
workfunction-dominant variants that change only polarity-correct BSIM-CMG
`PHIG` by a 0.10 eV spacing. Release checks enforce Vth/Ion/Ioff ordering and
per-fin Id/gm/capacitance plus gm/Id/gm/gds scaling. No planar substitute or
thick-oxide/HV family is supplied.

## ngspice and OSDI

Run `apm build-models` to compile `bsimcmg-112.1.0.osdi`, then include the
shared model card and one family wrapper:

```spice
.include "models/apm016f/ngspice/apm016f_multivt_models.inc"
.include "models/apm016f/families/svt/ngspice/wrapper.inc"

Xn d g s b apm016f_svt_nfet l=16n nfin=2
Xp d g s b apm016f_svt_pfet l=16n nfin=2
```

Load the OSDI artifact with `pre_osdi` before analysis.

```console
apm characterize apm016f --output .apm/results/apm016f
apm compare-set apm016f threshold --output .apm/results/apm016f-multivt
```

See [parameter_generation.md](parameter_generation.md), each
`variant-generation.toml`, and `provenance.toml` for independent inputs,
exact PHIG-only deltas, engine license/notices, archive and file hashes, and
model limitations.

Each family has `families/<id>/spectre/model.scs`, model-only
**experimental/unverified**. Confirm local compact-model support separately;
these files have not been parsed or simulated by Spectre.
