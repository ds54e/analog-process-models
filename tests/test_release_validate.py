# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from apm import clean_clone
from apm.cli import build_parser
from apm.release_validate import (
    IMPLEMENTED_GATE_IDS,
    ReleaseValidationError,
    audit_catalog,
    audit_claims,
    audit_distribution,
    audit_migration,
    audit_release_metadata,
    evaluate_required_gates,
    load_gate_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def _pass_results(contract: dict[str, object], evidence: Path) -> dict[str, dict[str, object]]:
    gates = contract["gate"]
    assert isinstance(gates, list)
    return {
        gate["id"]: {"status": "pass", "evidence": [str(evidence)], "detail": "test"}
        for gate in gates
        if gate["required"] is True
    }


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=True
    )


def test_release_contract_and_implementation_are_exact() -> None:
    contract = load_gate_contract(ROOT)
    required = {gate["id"] for gate in contract["gate"] if gate["required"] is True}
    assert contract["schema"] == "apm.release-gates.v3"
    assert contract["target"] == "v3.0.0"
    assert len(required) == 18
    assert required == IMPLEMENTED_GATE_IDS
    assert {
        "runtime.noise_sparse",
        "noise.foundation",
        "noise.method",
        "noise.catalog",
        "noise.resume_integrity",
        "models.claims_immutability",
        "distribution.public_hygiene",
    } <= required


@pytest.mark.parametrize(
    ("mutation", "expected_status"),
    (("missing", "missing"), ("skipped", "skipped"), ("empty_evidence", "pass")),
)
def test_gate_evaluation_fails_closed(
    tmp_path: Path, mutation: str, expected_status: str
) -> None:
    contract = load_gate_contract(ROOT)
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    results = _pass_results(contract, evidence)
    identifier = "runtime.compact_models"
    if mutation == "missing":
        del results[identifier]
    elif mutation == "skipped":
        results[identifier]["status"] = "skipped"
    else:
        results[identifier]["evidence"] = []
    ordered, overall = evaluate_required_gates(contract, results)
    selected = next(gate for gate in ordered if gate["id"] == identifier)
    assert selected["status"] == expected_status
    assert selected["passed"] is False
    assert overall is False


def test_gate_evaluation_rejects_stale_or_nonexistent_evidence(tmp_path: Path) -> None:
    contract = load_gate_contract(ROOT)
    evidence = tmp_path / "missing.json"
    results = _pass_results(contract, evidence)
    ordered, overall = evaluate_required_gates(contract, results)
    assert overall is False
    assert all(gate["evidence_valid"] is False for gate in ordered)


def test_release_repository_audits_pass() -> None:
    contract = load_gate_contract(ROOT)
    assert audit_release_metadata(ROOT, contract)["status"] == "pass"
    assert audit_catalog(ROOT, contract)["status"] == "pass"
    assert audit_migration(ROOT)["status"] == "pass"
    distribution = audit_distribution(ROOT)
    assert distribution["status"] == "pass"
    assert distribution["private_path_hits"] == []
    assert distribution["secret_hits"] == []
    assert {
        item["path"] for item in distribution[
            "allowed_historical_reproducibility_path_observations"
        ]
    } == {"validation/evidence/m0-runtime.md", "validation/evidence/m10-release.md"}
    assert audit_claims(ROOT, contract)["status"] == "pass"


def test_metadata_audit_rejects_development_versions(tmp_path: Path) -> None:
    contract = load_gate_contract(ROOT)
    (tmp_path / "src/apm").mkdir(parents=True)
    (tmp_path / "models/fixture/families/only").mkdir(parents=True)
    (tmp_path / "variation").mkdir()
    (tmp_path / "passives").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "0.0.0"\n', encoding="utf-8"
    )
    (tmp_path / "src/apm/__init__.py").write_text(
        '__version__ = "0.0.0"\n', encoding="utf-8"
    )
    (tmp_path / "src/apm/cli.py").write_text(
        'parser.add_argument("--version", version="APM 0.0.0")\n', encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## Unreleased\n", encoding="utf-8")
    result = audit_release_metadata(tmp_path, contract)
    assert result["status"] == "fail"
    assert "pyproject_version_matches_target" in result["failed_checks"]
    assert "runtime_version_matches_target" in result["failed_checks"]
    assert "cli_version_matches_target" in result["failed_checks"]


def test_clean_clone_attestation_is_tied_to_exact_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "clone"
    root.mkdir()
    (root / "validation").mkdir()
    (root / "validation/release_gates.toml").write_text(
        'schema = "apm.release-gates.v3"\n', encoding="utf-8"
    )
    (root / ".gitignore").write_text(".apm/\n", encoding="utf-8")
    _git(root, "init")
    _git(root, "config", "user.name", "APM test")
    _git(root, "config", "user.email", "apm-test@example.invalid")
    _git(root, "remote", "add", "origin", clean_clone.EXPECTED_REMOTE)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    observation = {
        "kernel_release": "fixture-microsoft-standard-WSL2",
        "kernel_version": "fixture WSL2",
        "architecture": "x86_64",
        "os_release": {"ID": "almalinux", "VERSION_ID": "9"},
        "filesystem": {"type": "ext4", "source": "fixture", "target": "/"},
        "checks": {
            "wsl2": True,
            "rhel_compatible_el9": True,
            "x86_64": True,
            "linux_filesystem_path": True,
        },
    }
    monkeypatch.setattr(clean_clone, "_platform_observation", lambda _: observation)

    created = clean_clone.create_clean_clone_attestation(root)
    assert created["schema"] == "apm.clean-clone-attestation.v3"
    assert clean_clone.verify_clean_clone_attestation(root)["status"] == "verified"

    (root / "validation/release_gates.toml").write_text(
        'schema = "apm.release-gates.v3"\ntarget = "v3.0.0"\n', encoding="utf-8"
    )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "later commit")
    with pytest.raises(clean_clone.CleanCloneError, match="exact_attested_commit"):
        clean_clone.verify_clean_clone_attestation(root)


def test_clean_clone_inventory_detects_ignored_generated_state(tmp_path: Path) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / "models/fixture").mkdir(parents=True)
    (tmp_path / "models/fixture/generated.osdi").write_bytes(b"fixture")
    assert clean_clone._generated_state_paths(tmp_path) == [
        ".venv",
        "models/fixture/generated.osdi",
    ]


def test_clean_clone_tag_audit_detects_final_v3_tag(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "file.txt").write_text("fixture\n", encoding="utf-8")
    _git(root, "init")
    _git(root, "config", "user.name", "APM test")
    _git(root, "config", "user.email", "apm-test@example.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    assert clean_clone._tag_exists(root, "v3.0.0") is False
    _git(root, "tag", "v3.0.0")
    assert clean_clone._tag_exists(root, "v3.0.0") is True


def test_validate_cli_exposes_release_output() -> None:
    args = build_parser().parse_args(
        ["validate", "--release", "--output", "/tmp/apm-release-test"]
    )
    assert args.command == "validate"
    assert args.release is True
    assert args.output == Path("/tmp/apm-release-test")


def test_contract_mismatch_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "validation").mkdir()
    (tmp_path / "validation/release_gates.toml").write_text(
        """schema = "apm.release-gates.v3"
target = "v3.0.0"
[[gate]]
id = "unknown.required"
required = true
""",
        encoding="utf-8",
    )
    with pytest.raises(ReleaseValidationError, match="validator/contract mismatch"):
        load_gate_contract(tmp_path)
