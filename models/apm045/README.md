# APM045 model kit

APM045 is APM's 45 nm planar predictive reference kit. It exposes the nominal
general-threshold FreePDK45 VTG NMOS and PMOS cards through native ngspice
BSIM4. It is an upstream-derived predictive/open model kit, not a
silicon-correlated PDK or an APM-authored parameter deck.

The FreePDK45 cards disclose that they were generated from the 45 nm Nano-CMOS
Predictive Technology Model and tuned toward representative published bulk-Si
technology. This ancestry is specific to APM045. The card values are not input
to the independently authored APM022 deck.

## Public devices

- `apm045_nmos d g s b w=<length> l=<length>`
- `apm045_pmos d g s b w=<length> l=<length>`

Only `w` and `l` are public sizing parameters. The FreePDK45 device definition
documents drawn `L=0.05..1 um` and `W=0.09..16 um`; nominal APM
characterization uses W=1 um and `L/Lmin = 1, 2, 4` with `Lmin=0.05 um`.
The nominal thin-oxide supply is 1.0 V.

## ngspice use

The model is native BSIM4 and needs no generated OSDI artifact:

```spice
.include models/apm045/vendor/freepdk45/NMOS_VTG.inc
.include models/apm045/vendor/freepdk45/PMOS_VTG.inc
.include models/apm045/ngspice/apm045_wrappers.inc

Xn d g s b apm045_nmos w=1u l=0.05u
```

The imported cards, upstream license/readme/manual, exact revision, and every
SHA-256 hash are recorded in `provenance.toml`. Only nominal VTG cards are
shipped. FreePDK45's optional fast/slow cards are outside the APM045 v1 kit;
they must not be confused with APM benchmark variation.

## Characterization

```text
apm characterize apm045 --output <new-result-directory>
```

The command runs both polarities, all three characterization lengths, and
temperatures -40, 27, 85, and 125 degC. Outputs follow the terminal conventions
in `RESULT_CONTRACT.md`; see `docs/characterization.md` for the concrete file
layout. Full result directories are deliberately untracked.

The model-only Spectre artifact is `spectre/apm045.scs`. It preserves the same
public names and `w,l` sizing and selects native Spectre BSIM4 through the
SPICE level-54 mapping. It is **experimental/unverified**; see
[`docs/spectre.md`](../../docs/spectre.md). This kit does not provide layout,
PCells, DRC, LVS, PEX, standard cells, or Virtuoso integration.
