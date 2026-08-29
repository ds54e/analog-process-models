# APM022

APM022 is the independently authored 22 nm-class planar-bulk member of Analog
Process Models. It is a generic comparison model, not a foundry PDK, is not
foundry-correlated, and is not derived from official PTM22 model-card values.

The stable public devices are `apm022_nmos` and `apm022_pmos`, with terminal
order `d g s b`. Their only public sizing parameters are `w` and `l`; APM does
not expose multiplicity or finger parameters. The characterized and supported
v1 length range is 25 to 100 nm, with a nominal 1 um width and 0.8 V supply.

ngspice uses its native BSIM4 implementation. Include the authored model cards
and public wrappers before analysis:

```spice
.include "models/apm022/ngspice/apm022_models.inc"
.include "models/apm022/ngspice/apm022_wrappers.inc"

Xn d g s b apm022_nmos w=1u l=25n
Xp d g s b apm022_pmos w=1u l=25n
```

See [parameter_generation.md](parameter_generation.md) for the independent
input sources, authored parameter decisions, measured behavior contract, and
limitations. Use `apm characterize apm022 --output DIR` to regenerate the
complete nominal terminal-characterization evidence.
