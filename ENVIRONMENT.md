# Reference environment

APM's required reference is **WSL2, RHEL-compatible EL9 Linux, x86_64**, with
ngspice **47** and OSDI on a Linux filesystem. Keep normal source/build/run state
below ignored project-local paths. A container or different platform can supplement
checks; it does not replace the declared reference gate. Spectre remains model-only
experimental/unverified, with no real Spectre/Virtuoso qualification.

[Getting started](docs/getting-started.md) contains the exact cold and returning-user
commands. The bootstrap pins the ngspice source archive, LLVM 20.1.8 RPM hashes,
Rust 1.98.0/rustup 1.29.1 and OpenVAF-Re-Loaded commit
`fdf2522b70f42793f64b1c72f0195c96dea0cc19`, including clean source/submodules.
Its checked-in [bootstrap script](tools/bootstrap-el9.sh) records authoritative
URLs and SHA-256 values. External build commands/development libraries must already
be available; APM does not replace system tools or modify shell startup files.

## Observed identity and reuse

A configured revision or version banner is not an observed build. The controlled
compiler receipt binds clean before/after source and submodules, actual Rust/Cargo
binaries behind launchers, LLVM configuration, linked libraries, build log and
compiler binary. [Compiler provenance](src/apm/compiler_provenance.py) rechecks these
bindings. `apm.model-build.v3` additionally binds each generated OSDI artifact to
model inputs and the observed compiler receipt; stale asserted-pin metadata cannot
be reused as verified evidence.

`apm doctor` separates actual native/OSDI smoke execution from reference provenance.
Inspect an existing prefix first and reuse it only when its receipts remain valid.
Reconcile editable Python metadata after code/version/dependency changes. Preserve
valid existing compilers, environments and raw evidence. A required repair builds
into a new ignored prefix, keeping the unchanged compiler pin and system tools.
Native-BSIM4 Research runs do not use OpenVAF; complete-catalog qualification does.

`APM_REPO_ROOT` explicitly selects a valid source tree; invalid explicit roots fail.
Otherwise discovery searches the working-directory ancestry and installed source
location using project identity and current assets. `APM_STATE_DIR` chooses generated
state (default `<root>/.apm`). `APM_TOOLCHAIN_DIR` selects a tool prefix;
`APM_NGSPICE`/`APM_OPENVAF` can select exact executables. Preserve their receipt,
source and dynamic-library dependencies. Do not require `~/.spiceinit`, GUI state,
Windows-mounted source or user-global configuration.

## Qualification versus ordinary use

A cold build starts in an empty prefix with new installed tools/environment; a
copied installed compiler/environment is reuse. Hash-verified download caches are
allowed. A warm check retains the verified binary/source receipts and creates fresh
outputs where required. The reviewed Python constraints remain byte-exact at
[validation/v5_reference_constraints.txt](validation/v5_reference_constraints.txt).
They are retained dependency data, not an instruction to rerun a v5 release.

Research runs explicitly set one simulator thread, normal Sparse/no-KLU and the
binary-prefix system startup path, whose spinit is hashed. `-n` disables user
initialization; it does not mean system spinit was ignored. Unknown provenance and
missing required real-tool evidence are non-PASS states.

The [current coordinator](docs/maintainers/index.md#current-candidate-lifecycle)
requires an authoritative fresh GitHub clone and exact clean candidate identity.
A source snapshot can perform [ordinary use without Git](docs/source-snapshot.md),
while strict historical/release checks remain unavailable. Older environment and
release records are reconstructible through [history operations](docs/history.md).
