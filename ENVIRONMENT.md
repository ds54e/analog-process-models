# APM v3 Reference and Release-Candidate Environment

This file records the validated continuation and exact-clone environment for
the v3.0.0 candidate. V3-N3 begins after successful v1/v2 releases and
V3-N0/N1/N2 qualification in the same WSL2/AlmaLinux workspace.

## Validated v1 baseline

The v1 release evidence established a working direct environment with:

- WSL2
- AlmaLinux 9.7 / RHEL-compatible EL9
- x86_64
- Linux filesystem working directory, not `/mnt/c`
- Python 3.9.25
- ngspice 47 with `--enable-predictor --enable-osdi --with-x=no`
- project-local OpenVAF-ReLoaded `v24.0.2mob`, commit `fdf2522b70f42793f64b1c72f0195c96dea0cc19`
- project-local LLVM 20.1.8 path used to build OpenVAF
- PSP103 OSDI artifacts proven by real simulation
- BSIM-CMG 112.1.0 OSDI artifacts proven by real simulation
- native BSIM3/BSIM4 real simulations

See the v1 tag and historical evidence for exact commands/hashes.

## Development continuation expectation

The current implementation session may continue in the same repository and
environment after V3-N2.

Before installing/building anything:

1. inspect the current repository/branch/HEAD/status;
2. inspect `.apm/toolchain`, `.apm/models`/generated OSDI state, caches, and `.venv`;
3. compare tool versions with the validated v1 baseline;
4. run the existing doctor/smoke path if practical;
5. reuse valid local toolchain state.

Do **not** treat v2 as a bare-machine M0 unless the existing toolchain is actually absent/broken/incompatible.

## Reuse policy

Development may reuse:

- source-built ngspice 47;
- source-built OpenVAF-ReLoaded;
- downloaded/pinned source caches;
- compiled PSP103/BSIM-CMG OSDI artifacts;
- existing Python virtual environment, after dependency/project metadata changes are reconciled;
- simulator knowledge/workarounds recorded during v1.

When code/model bindings change, rebuild only affected generated artifacts as required.

If an existing artifact's source/binding/revision changes, do not assume its v1 binary remains valid; rebuild and record the new dependency chain.

## Final v3 release-candidate boundary

Local reuse accelerates development but does not satisfy the v3 clean-clone
release gate.

Before V3-N3 completion, the exact immutable candidate commit must prove the
documented source bootstrap/build/doctor/test/electrical/noise/release-
validation flow from a genuine HTTPS clone on WSL2 + RHEL-compatible EL9
x86_64. The first release N2 catalog run must be fresh; strict resume follows
only after it.

The final clean clone may use documented external network downloads/cache
mechanisms allowed by the release flow, but it must not depend on untracked
files copied from the development checkout.

## Platform policy

Keep source/build/run data on the Linux filesystem.

Do not depend on:

- `/mnt/c` for normal builds/runs;
- user-global `~/.spiceinit` state;
- GUI state;
- shell-startup-file modification as required setup;
- nested container/VM substitution for the required final WSL2/EL9 gate.

Containers/CI may supplement validation but do not replace the final reference environment.

## Spectre/Virtuoso

No real Spectre/Virtuoso environment is assumed for v3 release hardening.

Spectre remains model-only experimental/unverified unless real Spectre access is actually available and intentionally used.

Virtuoso integration remains out of scope.
