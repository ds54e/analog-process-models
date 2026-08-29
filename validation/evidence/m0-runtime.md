# M0 runtime qualification

Status: `validated`

Run time: 2026-08-29 14:59 UTC (2026-08-30 JST)

## Reference host

- Direct WSL2 kernel: `6.18.33.2-microsoft-standard-WSL2`
- Distribution: AlmaLinux 9.7 (`x86_64`)
- Checkout: `/home/admin/src/analog-process-models` on `/dev/sdd`, `ext4`
- Python: 3.9.25

## Reproducible toolchain

`APM_BUILD_JOBS=20 tools/bootstrap-el9.sh` completed from an empty project-local
`.apm` state directory. The script verifies every downloaded artifact before use,
builds ngspice with `--enable-predictor --enable-osdi`, and installs generated
software only below `.apm/toolchain` by default.

- ngspice: 47, binary SHA-256
  `34d24e813da266ee2a5deef72596de1351b63d489f96372ec4364648676cdc21`
- ngspice source archive SHA-256:
  `894e649651f1838a14095e5a5439e7d3aa63e87ede14d283173fda4fcdef675f`
- OpenVAF-ReLoaded: tag `v24.0.2mob`, commit
  `fdf2522b70f42793f64b1c72f0195c96dea0cc19`
- Locally built OpenVAF binary SHA-256:
  `6bde23f4802efd7336d02f00f68744c9fe409dc248d0926ae832c45930b51ac6`
- Rust: 1.98.0; LLVM: AlmaLinux 20.1.8 packages pinned by exact RPM hashes in
  `tools/bootstrap-el9.sh`

The official OpenVAF release binary (archive SHA-256
`b12b7b1726d103e18c2588c3a1f91f8475cf03df8a3bde14d919797d221e3110`)
cannot execute on EL9: it requests `GLIBC_2.35`, `GLIBC_2.39`, and
`libLLVM.so.18.1`. Building the required `openvaf-driver` package at the same
tag/commit against locally extracted AlmaLinux LLVM 20 resolves this without
changing the reference distribution or requiring root access. OpenVAF prints
`OpenVAF-reloaded unknown`; the immutable source commit above is the compiler
identity used by APM.

## Real-tool results

Commands:

```text
PYTHONPATH=src python -m apm.cli build-models
PYTHONPATH=src python -m apm.cli doctor
```

Both returned exit status 0. `build-models` compiled the vendored PSP 103.8.2
and BSIM-CMG 112.1.0 sources with `--target_cpu generic`. `doctor` then ran
headless `ngspice -n -b` simulations without reading user configuration.

| Smoke | Engine/load path | Observed result |
| --- | --- | --- |
| Native BSIM3 | ngspice level 49 | `i(vd)=-1.02563e-4 A`, `gm=4.069746e-4 S` |
| Native BSIM4 | ngspice level 54 | `i(vd)=-1.66537e-4 A`, `gm=6.958207e-4 S` |
| PSP103 | PSP 103.8.2 OSDI + IHP PSP 103.6 nominal card | `i(vd)=-2.26855e-4 A` |
| BSIM-CMG | BSIM-CMG 112.1.0 OSDI + synthetic M0-only engine card | `i(vd)=-6.32387e-5 A` |

The BSIM-CMG smoke card is an APM-authored runtime fixture only. It does not
stand in for the independently authored APM016F release parameter deck, and
this evidence makes no APM016F fidelity or NFIN-scaling claim.

The generated detailed report is `.apm/doctor/report.json`; OSDI binaries,
netlists, and logs remain intentionally untracked. Re-running `apm doctor`
regenerates them.

## Gates supported by this evidence

- `runtime.wsl2_el9`
- `runtime.ngspice_headless`
- `runtime.psp103_osdi`
- `runtime.bsimcmg_osdi`

No device-kit, characterization, variation, Spectre, or release-readiness gate
is claimed by M0.

`reuse lint` 5.1.1 also returned exit status 0 for this checkpoint: 66/66
tracked files had copyright and license information, with Apache-2.0, ECL-2.0,
and `LicenseRef-Si2-PSP-103.8.2` as the only used licenses. This confirms the
M0 imports are annotated correctly; it is not a claim that the final all-kit
`licensing.provenance` release gate has already passed.
