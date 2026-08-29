#!/usr/bin/env bash
# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

apm_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
apm_python="${APM_PYTHON:-python3}"
apm_venv="${APM_VENV:-${apm_repo_root}/.venv}"

command -v "${apm_python}" >/dev/null 2>&1 || {
  echo "setup-python: Python executable not found: ${apm_python}" >&2
  exit 1
}

"${apm_python}" - <<'PY'
import sys
if sys.version_info < (3, 9):
    raise SystemExit("APM requires Python 3.9 or newer")
PY

if [[ ! -x "${apm_venv}/bin/python" ]]; then
  "${apm_python}" -m venv "${apm_venv}"
fi

"${apm_venv}/bin/python" -m pip install --upgrade "pip>=24"
"${apm_venv}/bin/python" -m pip install --editable "${apm_repo_root}[dev]"

echo "APM Python environment ready: ${apm_venv}"
echo "Run commands with ${apm_venv}/bin/apm or activate ${apm_venv}/bin/activate"
