# APM350

APM350 is the open generic mature-planar anchor in Analog Process Models. Its
technology class is 0.35 um, while its honest actual minimum modeled length is
0.4 um. The BSIM3 parameter deck is independently authored by APM and is not
foundry-correlated or a manufacturable PDK.

The stable public devices are `apm350_nmos` and `apm350_pmos`, with terminal
order `d g s b`. Their only public sizing parameters are `w` and `l`; internal
source/drain diffusion geometry is fixed by the wrapper and no multiplicity,
finger, or layout parameter is exposed. The supported v1 length range is
0.4–10 um, the supported width range is 0.6–100 um, and the nominal supply is
5 V.

ngspice uses its native BSIM3 implementation:

```spice
.include "models/apm350/ngspice/apm350_models.inc"
.include "models/apm350/ngspice/apm350_wrappers.inc"

Xn d g s b apm350_nmos w=1u l=0.4u
Xp d g s b apm350_pmos w=1u l=0.4u
```

See [parameter_generation.md](parameter_generation.md) for the rejected-source
license audit, independent parameter choices, terminal behavior contract, and
limitations. Regenerate nominal evidence with
`apm characterize apm350 --output DIR`.
