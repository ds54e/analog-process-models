# APM350

APM350 is the open generic mature-planar anchor in Analog Process Models. Its
technology class is 0.35 µm; its honest minimum modeled length is 0.4 µm. The
BSIM3 parameter deck is independently APM-authored, not foundry-correlated, and
not a manufacturable PDK.

## Electrical family and devices

The v2 catalog declares one family, `apm350/general`:

- `apm350_general_nmos d g s b w=<length> l=<length>`
- `apm350_general_pmos d g s b w=<length> l=<length>`

Only `w,l` are public. Internal diffusion geometry is fixed by the wrapper;
multiplicity, finger, and layout parameters are not exposed. The documented
model range is L = 0.4–10 µm and W = 0.6–100 µm. Its default Operating Profile
uses 5.0 V at −40, 27, 85, and 125 °C; this is characterization metadata, not a
reliability rating.

## ngspice

APM350 uses native BSIM3 and needs no OSDI artifact:

```spice
.include "models/apm350/ngspice/apm350_models.inc"
.include "models/apm350/families/general/ngspice/wrapper.inc"

Xn d g s b apm350_general_nmos w=1u l=0.4u
Xp d g s b apm350_general_pmos w=1u l=0.4u
```

Run `apm characterize apm350/general --output DIR` for nominal terminal
characterization. `technology.toml`, `family.toml`, and backend
`binding.toml` files are the runtime source of truth.

See [parameter_generation.md](parameter_generation.md) for independent choices,
the rejected-source licensing audit, behavior targets, and limitations.
`provenance.toml` declares every shipped model asset and hash.

The family Spectre artifact is
`families/general/spectre/model.scs`. It is model-only
**experimental/unverified** and has not been parsed or simulated by Spectre.
