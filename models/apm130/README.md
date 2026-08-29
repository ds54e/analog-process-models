# APM130 model kit

APM130 is APM's 130 nm planar reference kit. It uses the open IHP SG13G2
low-voltage MOS parameter cards with the PSP compact-model engine compiled to
OSDI. It is an upstream-derived open model kit, not an independent APM
silicon-correlation claim and not a complete manufacturable PDK.

## Public devices

- `apm130_nmos d g s b w=<length> l=<length>`
- `apm130_pmos d g s b w=<length> l=<length>`

Only `w` and `l` are public sizing parameters. The upstream finger and
multiplicity controls remain fixed inside the wrappers and are not part of the
APM v1 interface. Supported upstream geometry is `L=0.13..10 um` and
`W=0.15..10 um`; the nominal APM characterization width is 1 um and lengths are
`L/Lmin = 1, 2, 4` with `Lmin=0.13 um`.

The nominal supply is 1.2 V, matching IHP's description of the SG13G2
thin-oxide logic device. Model use above the documented upstream voltage or
geometry ranges is not supported by APM.

## ngspice use

Run `apm build-models` first. A nominal netlist then loads:

```spice
.lib models/apm130/vendor/ihp-sg13g2-models/cornerMOSlv.lib mos_tt
.include models/apm130/ngspice/apm130_wrappers.inc

Xn d g s b apm130_nmos w=1u l=0.13u

.control
pre_osdi .apm/build/osdi/psp103.osdi
pre_osdi .apm/build/osdi/psp103-nqs.osdi
* analyses follow
.endc
```

The model cards identify PSP 103.6. Current pinned IHP source supplies the
backward-compatible PSP 103.8.2/JUNCAP 200.6.2 implementation; the exact
distinction, licenses, imported files, and SHA-256 hashes are recorded in
`provenance.toml`.

The upstream library also contains `mos_ss`, `mos_ff`, `mos_sf`, `mos_fs`,
statistical, and mismatch sections. They remain explicitly IHP-native behavior,
not APM benchmark variation. Run the real-tool native regression with:

```text
apm apm130-native-check --output <new-result-directory>
```

The selected profiles are the five `mos_*` corners, `mos_tt_stat` process, and
`mos_tt_mismatch` local mismatch. Native random expressions are evaluated by
ngspice with explicit seeds, not by the APM benchmark Python sampler. The
mismatch run includes `apm130_native_mismatch_wrappers.inc` instead of the
nominal wrapper; it preserves the same public names and `w,l` interface while
fixing upstream `mm_ok=1` internally. No native stochastic process+mismatch
`all` profile is exposed because the selected upstream deck provides none.
See [`docs/native-variation.md`](../../docs/native-variation.md) for exact
semantics and result files.

## Characterization

```text
apm characterize apm130 --output <new-result-directory>
```

The command runs both polarities, all three characterization lengths, and
temperatures -40, 27, 85, and 125 degC. Outputs follow the terminal conventions
in `RESULT_CONTRACT.md`; see `docs/characterization.md` for the concrete file
layout. Generated OSDI binaries and full result directories are deliberately
untracked.

The model-only Spectre artifact is `spectre/apm130.scs`, backed by the
deterministically translated native-PSP103 TT card in the same directory. It
preserves the public names and `w,l` sizing and supports APM benchmark
statistics only. It is **experimental/unverified**; IHP-native Spectre Monte
Carlo is not claimed. See [`docs/spectre.md`](../../docs/spectre.md). Nothing in
this kit provides Virtuoso integration, layout, PCells, DRC, LVS, PEX, or
foundry signoff.
