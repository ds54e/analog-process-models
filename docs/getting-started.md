# Getting started

Work at the root of a full APM source checkout on the Linux filesystem. The
reference host is x86_64 WSL2 running a RHEL-compatible EL9 distribution. You need
Git, Python 3.9 or later with venv/pip, a C/C++ build environment, autoconf,
automake, bison, flex, make, curl, tar, cpio, rpm2cpio and SHA-256 tools. The build
uses network downloads of hash-pinned sources, LLVM RPMs and Rust; Python packages
come from the configured package index. The existing host must already supply
these external prerequisites. APM does not replace system tools.

## Cold setup

Use this block once with **absent** `.apm/tutorial-cold` and
`.apm/tutorial-python` directories. It builds ngspice 47 and the pinned OpenVAF
compiler in an empty local prefix and records actual compiler provenance. Do not
copy an installed compiler or virtual environment into that prefix. Verified
source-download caches may be used; ordinary reuse is described below.

<!-- apm-journey: cold -->
```bash
(
unset APM_TOOLCHAIN_DIR APM_NGSPICE APM_OPENVAF APM_OPENVAF_RECEIPT
APM_BUILD_JOBS=4 APM_STATE_DIR="$PWD/.apm/tutorial-cold" tools/bootstrap-el9.sh
APM_VENV="$PWD/.apm/tutorial-python" PIP_CONSTRAINT="$PWD/validation/v5_reference_constraints.txt" tools/setup-python.sh
APM_STATE_DIR="$PWD/.apm/tutorial-cold" .apm/tutorial-python/bin/apm build-models
APM_STATE_DIR="$PWD/.apm/tutorial-cold" .apm/tutorial-python/bin/apm doctor
APM_STATE_DIR="$PWD/.apm/tutorial-cold" .apm/tutorial-python/bin/apm characterize apm045/vtg/nmos --output .apm/tutorial-first-result
)
```

Inspect `.apm/tutorial-cold/build/osdi/build.json` for bound source/compiler/OSDI
hashes and the doctor report for actual smoke execution. The final command writes
its signed terminal data, derived tables and report to `.apm/tutorial-first-result`.
Successful simulation describes these compact-model predictions; it establishes
neither silicon calibration nor a manufacturing or voltage reliability rating.

## Returning to an existing checkout

Preserve the existing toolchain prefix and its receipts. Reconcile editable Python
metadata after pulling changes, then run doctor and current validation. If you used
the cold example above, its exact prefix and Python commands remain valid; do not
rerun bootstrap over the occupied compiler installation. For the usual `.venv` and
`.apm/toolchain` installation, use:

<!-- apm-journey: warm -->
```bash
PIP_CONSTRAINT="$PWD/validation/v5_reference_constraints.txt" tools/setup-python.sh
.venv/bin/apm --version
.venv/bin/apm doctor
.venv/bin/apm validate --output .apm/tutorial-current-validation
```

Doctor checks the observed compiler receipt, source pin and binary as well as
native/OSDI simulation. An unknown or stale receipt is a failed reference check.
Build repairs use a fresh ignored prefix; keep the previous installation and logs.
Choose a new result directory when a destination is occupied.

`APM_REPO_ROOT` explicitly chooses a valid source root. `APM_STATE_DIR` explicitly
chooses generated state; otherwise it is `<root>/.apm`. An invalid explicit root is
an error. Tools can also be selected with `APM_TOOLCHAIN_DIR`, `APM_NGSPICE` and
`APM_OPENVAF`, with their real receipt and library dependencies retained.

Next: [use models in a circuit](using-models.md),
[characterize devices](characterization.md), or [choose a variation flow](variation.md).
Current environment details are in [ENVIRONMENT.md](../ENVIRONMENT.md).
