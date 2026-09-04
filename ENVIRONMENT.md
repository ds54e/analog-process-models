# APM v4 Reference Environment and Release Record

APM v4.0.0 uses the same required real-tool platform as the released v3
baseline: WSL2, RHEL-compatible EL9 Linux, x86_64, and a Linux-filesystem
checkout. This file records reusable environment guidance and immutable
historical release context. The active phase-specific v4 commands are in
`docs/release-validation.md`.

The annotated `v3.0.0` tag peels to
`995e0ce7cdd0c37ef9f3397008637f9d239c746e`, and exact-tag qualification passed
18/18 on the documented WSL2/AlmaLinux reference environment.

## V4 release qualification boundary

Development may reuse the project-local toolchain, but neither a development
run nor a reused checkout satisfies a v4 release gate. The v4 candidate and
exact-tag phases each start in a separate fresh authoritative HTTPS clone,
checked out detached, and run `tools/attest_clean_clone_v4.py` before any
project-local generated state exists. Each phase then bootstraps, installs,
builds, runs doctor, and executes its complete validator. The candidate phase
requires 15/15 pre-tag gates; the exact-tag phase independently requires all
16/16 gates before GitHub Release creation.

Both runs require ngspice 47 and the pinned OpenVAF-Re-Loaded `v24.0.2mob`
toolchain. The bootstrap uses the immutable rustup 1.29.1 archive, verified as
SHA-256 `dda7234360b7f578ca8b0ddcb80145646fa61a67c1720a5abc7051b35c9fcb71`,
to install the pinned Rust 1.98.0 toolchain. Spectre remains model-only and
**experimental/unverified**; a real Spectre or Virtuoso environment is neither
assumed nor claimed.

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

## Development continuation and reuse

Development may continue in the same repository and environment when the
project-local toolchain remains valid.

Before installing/building anything:

1. inspect the current repository/branch/HEAD/status;
2. inspect `.apm/toolchain`, `.apm/models`/generated OSDI state, caches, and `.venv`;
3. compare tool versions with the validated v1 baseline;
4. run the existing doctor/smoke path if practical;
5. reuse valid local toolchain state.

Do **not** treat maintenance work as a bare-machine bootstrap unless the
existing toolchain is actually absent, broken, or incompatible.

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

## Historical v3 release qualification boundary

Local reuse accelerated development but did not satisfy the v3 clean-clone
release gate.

Before V3-N3 completion, the exact immutable candidate commit was required to
prove the documented source bootstrap/build/doctor/test/electrical/noise/
release-validation flow from a genuine HTTPS clone on WSL2 + RHEL-compatible
EL9 x86_64. The first release N2 catalog run was fresh; strict resume followed
only after it. Exact-tag post-release requalification independently repeated
that flow; see `validation/evidence/v3_post_release_requalification.json`.

The release clone used documented external network downloads/cache mechanisms
allowed by the release flow and did not depend on untracked files copied from
the development checkout.

## Platform policy

Keep source/build/run data on the Linux filesystem.

Do not depend on:

- `/mnt/c` for normal builds/runs;
- user-global `~/.spiceinit` state;
- GUI state;
- shell-startup-file modification as required setup;
- nested container/VM substitution for any future required WSL2/EL9 gate.

Containers/CI may supplement validation but do not replace an explicitly
required reference-environment qualification.

## Spectre/Virtuoso

No real Spectre/Virtuoso environment was used for v3 release hardening or is
assumed for post-release maintenance.

Spectre remains model-only experimental/unverified unless real Spectre access is actually available and intentionally used.

Virtuoso integration remains out of scope.
