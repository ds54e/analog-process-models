# APM130

APM130 exposes the audited IHP SG13G2 LV and HV planar PSP103 MOS families. It
is an upstream-derived open model subset, not an independent APM silicon
correlation and not a complete manufacturable PDK.

## Electrical families and devices

| Family | Public devices | Default profile | L range N/P |
| --- | --- | ---: | --- |
| `apm130/lv` | `apm130_lv_nmos`, `apm130_lv_pmos` | 1.2 V | 0.13–10 µm / 0.13–10 µm |
| `apm130/hv` | `apm130_hv_nmos`, `apm130_hv_pmos` | 3.3 V | 0.45–10 µm / 0.40–10 µm |

All devices use terminal order `d g s b` and only public `w,l`. Upstream
multiplicity/finger/mismatch controls are fixed inside family wrappers. The
1.2 V LV/HV common-overlap profile is a behavior-comparison condition, not a
lifetime, breakdown, or safe-operating-area claim.

## ngspice and OSDI

Run `apm build-models` first. A nominal LV example is:

```spice
.lib models/apm130/vendor/ihp-sg13g2-models/cornerMOSlv.lib mos_tt
.include models/apm130/families/lv/ngspice/wrapper.inc

Xn d g s b apm130_lv_nmos w=1u l=0.13u

.control
pre_osdi .apm/build/osdi/psp103.osdi
pre_osdi .apm/build/osdi/psp103-nqs.osdi
* analyses follow
.endc
```

The cards identify PSP 103.6 and are executed with the pinned,
backward-compatible PSP 103.8.2/JUNCAP 200.6.2 sources. Exact imported files,
licenses, notices, transformations, and SHA-256 hashes are in
`provenance.toml`.

Use:

```console
apm characterize apm130/lv --output .apm/results/apm130-lv
apm characterize apm130/hv --output .apm/results/apm130-hv
apm compare-set apm130 gate_stack --output .apm/results/apm130-gate-stack
apm apm130-native-check --output .apm/results/apm130-native
```

Native corners/process/mismatch retain IHP names and execute as independent LV
and HV cohorts. APM invents neither cross-family correlation nor a native All
mode. See [`docs/native-variation.md`](../../docs/native-variation.md).

Family Spectre artifacts are under `families/{lv,hv}/spectre/model.scs`.
They are model-only **experimental/unverified**; IHP-native Spectre Monte Carlo
is not claimed.
