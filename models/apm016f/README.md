# APM016F

APM016F is the 16 nm-class generic FinFET member of Analog Process Models. It
uses the pinned UC Berkeley BSIM-CMG 112.1.0 engine and independently authored
APM parameter cards. It is not a foundry PDK, is not foundry-correlated, and is
not derived from PTM-MG model-card values.

The stable public devices are `apm016f_nfet` and `apm016f_pfet`, with terminal
order `d g s b`. Their only public sizing parameters are `l` and positive,
integer `nfin`. APM v1 deliberately exposes neither a fabricated continuous
width nor multiplicity/finger parameters.

For ngspice, load the generated `bsimcmg-112.1.0.osdi` artifact before analysis,
include `ngspice/apm016f_models.inc`, and then include
`ngspice/apm016f_wrappers.inc`. Generated OSDI binaries are local build products
and are not committed.

```spice
Xn d g s b apm016f_nfet l=16n nfin=2
Xp d g s b apm016f_pfet l=16n nfin=2
```

The supported characterization set uses `l` = 16, 32, or 64 nm and `nfin` = 1,
2, or 4. See [parameter_generation.md](parameter_generation.md) for input
sources, authored choices, and model limitations.
