# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from apm.catalog import load_catalog
from apm.cli import build_parser
from apm.spectre_validate import validate_spectre

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
    assert persisted["details"]["model_only_scope"]["artifact_count"] == 35


def test_spectre_public_names_match_all_family_ngspice_names() -> None:
    catalog = load_catalog(ROOT)
    count = 0
    for technology in catalog.technologies:
        for family in technology.families:
            spectre = family.backend("spectre").wrapper_path.read_text(encoding="utf-8")
            ngspice = family.backend("ngspice").wrapper_path.read_text(encoding="utf-8")
            ngspice_names = set(re.findall(r"(?mi)^\.subckt\s+(apm\w+)", ngspice))
            assert ngspice_names == {device.public_name for device in family.devices}
            for public_name in ngspice_names:
                assert f"subckt {public_name} (d g s b)" in spectre
            count += 1
    assert count == 15


def test_spectre_generation_is_byte_reproducible() -> None:
    for tool in ("tools/generate_spectre_psp.py", "tools/generate_spectre_v2.py"):
        completed = subprocess.run(
            [sys.executable, tool, "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert "up to date" in completed.stdout
