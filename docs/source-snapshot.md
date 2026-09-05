# Use a configured source snapshot without Git

Ordinary model use requires the complete current source/model/notice closure and
configured tools. It does not require historical Git objects or runtime downloads
of source papers. A standalone wheel without the source/model tree is not the
supported distribution model.

This explicit maintainer example starts at the root of a **clean, committed**
configured checkout with `.venv`. It exports that current tree to a new source
snapshot, reuses the verified toolchain, and produces new ordinary outputs. It
then demonstrates that strict history verification is unavailable. Do not run
this while expecting uncommitted source edits to appear in the export.

<!-- apm-journey: snapshot -->
```bash
apm_python="$PWD/.venv/bin/python"
apm_tools="${APM_TOOLCHAIN_DIR:-$PWD/.apm/toolchain}"
mkdir .apm/tutorial-snapshot
git archive --format=tar HEAD | tar -xf - -C .apm/tutorial-snapshot
(
cd .apm/tutorial-snapshot
export APM_REPO_ROOT="$PWD"
export APM_STATE_DIR="$PWD/.apm"
export APM_TOOLCHAIN_DIR="$apm_tools"
export PYTHONPATH="$PWD/src"
"$apm_python" -m apm.cli list technologies
"$apm_python" -m apm.cli describe apm045/vtg/nmos
"$apm_python" -m apm.cli build-models
"$apm_python" -m apm.cli characterize apm045/vtg/nmos --output .apm/device
"$apm_python" -m apm.cli research sample --profile variation/research/apm045/derived/hart_tsmc40_profile.json --request examples/research/request.json --seed 1001 --index 0 --state .apm/maps --output .apm/realization.json
"$apm_python" -m apm.cli research run --request examples/research/request.json --realization .apm/realization.json --output .apm/runs
"$apm_python" -m apm.cli validate --scope product --output .apm/product-check
if "$apm_python" -m apm.cli history verify > .apm/history.json; then exit 1; fi
)
```

Inspect `.apm/tutorial-snapshot/.apm/device`, `realization.json`, the reported run
directory and `product-check/report.json`. The product report explicitly excludes
history, maintainer tests and real-tool regressions; the preceding commands supply
the actual ordinary simulations. `history.json` must say `NOT_VERIFIED` with
`MISSING_HISTORY`. It must not find the parent checkout's Git directory and pass.

Retain the complete model/source/notice tree when distributing a source snapshot.
For strict auditing, use [the full-clone or bundle remedy](history.md#offline-and-incomplete-history).
A successful ordinary source-snapshot run is not archive or release qualification.
