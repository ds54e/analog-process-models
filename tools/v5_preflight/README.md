<!-- SPDX-FileCopyrightText: 2026 APM preflight contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM v5 preflight tools

Start with the repository [`GOAL.md`](../../GOAL.md) and
[`V5_PREFLIGHT.md`](../../V5_PREFLIGHT.md). This directory is the repository-owned
replacement for the earlier standalone handoff packet. No ZIP is needed.

- `V5_MINIMUM_EXPERIMENT.md`: numerical and ngspice experiment specification.
- `source_audit.toml`: public-source leads, unresolved beta normalization, and
  artificial test inputs. It is not an approved statistical profile.
- `numerical_core.py`: experimental extraction, mapping, and sampling helpers.
- `run_spike.py`: unqualified native-BSIM4 ngspice-47 scaffold. Review before use.
- `tests/`: artificial numerical and deck-construction tests; no real-SPICE claim.
- `CODEX_PROMPT.md`: short English launch prompt referring to repository authority.

From the repository root:

```sh
PYTHONPATH=tools/v5_preflight .venv/bin/python -m pytest -q tools/v5_preflight/tests
.venv/bin/python tools/v5_preflight/run_spike.py \
  --repo "$PWD" \
  --ngspice /absolute/path/to/the/existing/ngspice \
  --output "$PWD/.apm/v5-preflight/run-001"
```

Find the real binary in the existing project toolchain; the example path is a
placeholder. The output directory must be new. The repository's default pytest
configuration targets `tests/`; explicitly run this isolated suite as shown above.
Use an ignored output directory, not this directory or `models/`.

The input model Git blob identities are checked by the runner. Existing cards are
read only. The script uses no approved measured beta coefficient and cannot qualify
v5 on its own. Normalized controls, convergence tolerances, and raw bounds are
preflight engineering choices, not process statistics or reliability ratings.

Known review points: the imported scaffold initially couples application and MG
extraction, stops its combined run on the first failure, and requires
review of real-tool failure diagnostics. The imported bad-path classification has been
tightened to reject unrelated solver failures, but is not real-ngspice-qualified. The main
contract requires independent reporting; fix the scaffold from real evidence without
changing that requirement. A Python-only PASS is not a simulator PASS.

Preparation provenance and actually rerun checks are recorded in
[`v5_preflight_preparation.json`](../../validation/evidence/v5_preflight_preparation.json).
The experiment code was originally supplied in APM_V5_Preflight.zip and normalized
for repository style during import. All preparation tests use artificial quantities.
