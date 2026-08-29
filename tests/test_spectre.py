# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from apm.cli import build_parser
from apm.spectre_validate import MODEL_FILES, validate_spectre

ROOT = Path(__file__).resolve().parents[1]


def test_spectre_cli_is_explicitly_structural(tmp_path: Path) -> None:
    args = build_parser().parse_args(["spectre-check", "--output", str(tmp_path)])
    assert args.command == "spectre-check"
    assert args.output == tmp_path


def test_all_spectre_artifacts_pass_static_gate(tmp_path: Path) -> None:
    report = validate_spectre(tmp_path / "spectre")
    assert report["status"] == "structurally_checked"
    assert report["backend_status"] == "experimental_unverified"
    assert report["real_tool_validation_performed"] is False
    assert report["parse_validity_claimed"] is False
    assert report["numerical_conformance_claimed"] is False
    assert all(report["checks"].values())
    persisted = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
    assert persisted["release_gate"] == "spectre.model_only"


def test_spectre_public_names_match_all_ngspice_facing_names() -> None:
    for kit_id, path in MODEL_FILES.items():
        spectre = (ROOT / path).read_text(encoding="utf-8")
        ngspice = (ROOT / f"models/{kit_id}/ngspice/{kit_id}_wrappers.inc").read_text(
            encoding="utf-8"
        )
        for match in re.finditer(r"(?mi)^\.subckt\s+(apm\w+)", ngspice):
            assert f"subckt {match.group(1)} (d g s b)" in spectre


def test_apm130_spectre_psp_derivation_is_reproducible() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/generate_spectre_psp.py", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "up to date" in completed.stdout
