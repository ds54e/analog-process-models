# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Replay frozen epoch-3 holdouts with a fresh, portable calibration report.

The first-unseal implementation and its exact calibration hash are immutable.
Source-built ngspice embeds rebuild-local path/time information, so a fresh
clone cannot reproduce that exact metadata.  This adapter verifies a narrow
portable-content binding, adapts only the frozen canonical-hash callback,
delegates every electrical check to that unchanged implementation, and records
the fresh tool/report identity.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib

from . import qualify_families as frozen
from .kernel import NgspiceEvaluator, canonical_json, sha256_bytes, sha256_file

SCHEMA = "apm.modelgen.calibration-replay-binding.v1"
STATE = "PORTABLE_REPLAY_BINDING_AFTER_FIRST_UNSEAL"
RECEIPT_SCHEMA = "apm.mixed-voltage-holdout-replay-receipt.v1"
EXCLUDED_FIELDS = (
    "created_utc",
    "reference_tool.path",
    "reference_tool.sha256",
    "reference_tool.version_output",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def portable_calibration_sha256(report: Mapping[str, Any]) -> str:
    """Hash all calibration content except the four declared local fields."""

    payload = json.loads(canonical_json(report))
    payload.pop("created_utc", None)
    reference_tool = payload.get("reference_tool")
    if not isinstance(reference_tool, dict):
        raise frozen.QualificationError(
            "calibration report has no reference-tool identity"
        )
    for key in ("path", "sha256", "version_output"):
        reference_tool.pop(key, None)
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def _binding_audit(
    *,
    root: Path,
    binding_path: Path,
    qualification_path: Path,
    calibration_path: Path,
    calibration: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    binding = _read_toml(binding_path)
    qualification = _read_toml(qualification_path)
    evidence_path = root / str(binding.get("original_calibration_evidence", "missing"))
    evidence = _read_json(evidence_path) if evidence_path.is_file() else {}
    expected_tool = (root / ".apm/toolchain/ngspice-47/bin/ngspice").resolve()
    current_tool = NgspiceEvaluator(
        ngspice=expected_tool,
        work_directory=root / ".apm/modelgen-replay-tool-identity",
    ).tool_identity()
    reported_tool = calibration.get("reference_tool", {})
    sealed_hash = str(qualification["calibration_canonical_content_sha256"])
    portable_hash = portable_calibration_sha256(calibration)
    evidence_report = evidence.get("full_report", {})
    frozen_path = Path(frozen.__file__).resolve()
    checks = {
        "schema": binding.get("schema") == SCHEMA,
        "state": binding.get("state") == STATE,
        "epochs": int(binding.get("generation_epoch", 0))
        == int(qualification["qualification_epoch"])
        == int(binding.get("qualification_epoch", 0)),
        "qualification_input": binding.get("qualification_input")
        == str(qualification_path.relative_to(root))
        and binding.get("qualification_input_sha256")
        == sha256_file(qualification_path),
        "frozen_qualification_implementation": binding.get(
            "frozen_qualification_implementation"
        )
        == str(frozen_path.relative_to(root))
        and binding.get("frozen_qualification_implementation_sha256")
        == sha256_file(frozen_path),
        "frozen_hash_adapter_target": binding.get("frozen_hash_adapter_target")
        == "qualify_families._canonical_report_sha256",
        "excluded_fields_exact": binding.get("excluded_fields")
        == list(EXCLUDED_FIELDS),
        "sealed_hash_preserved": binding.get(
            "sealed_calibration_canonical_content_sha256"
        )
        == sealed_hash,
        "portable_content_exact": binding.get(
            "portable_calibration_content_sha256"
        )
        == portable_hash,
        "evidence_file_exact": evidence_path.is_file()
        and binding.get("original_calibration_evidence_sha256")
        == sha256_file(evidence_path),
        "evidence_schema_status": evidence.get("schema")
        == "apm.v4-generation-calibration-evidence.v1"
        and evidence.get("status") == "validated",
        "evidence_preserves_original_report": evidence_report.get("sha256")
        == binding.get("original_calibration_report_sha256")
        and evidence_report.get("canonical_content_sha256_excluding_created_utc")
        == sealed_hash,
        "current_report_is_project_local": binding.get("fresh_report_required") is True
        and calibration_path.resolve().is_relative_to((root / ".apm").resolve()),
        "current_tool_identity_exact": reported_tool == current_tool,
        "current_tool_major_exact": str(current_tool.get("major"))
        == str(binding.get("reference_simulator_major")),
        "candidate_parameter_change_forbidden": binding.get(
            "candidate_parameter_change_permitted"
        )
        is False,
        "holdout_change_forbidden": binding.get(
            "holdout_definition_change_permitted"
        )
        is False,
        "criterion_change_forbidden": binding.get(
            "electrical_criterion_change_permitted"
        )
        is False,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise frozen.QualificationError(
            "calibration replay binding mismatch: " + ", ".join(failed)
        )
    audit = {
        "status": "pass",
        "mode": "portable_release_replay",
        "contract": {
            "path": str(binding_path.relative_to(root)),
            "sha256": sha256_file(binding_path),
        },
        "sealed_calibration_canonical_content_sha256": sealed_hash,
        "observed_calibration_canonical_content_sha256": (
            frozen._canonical_report_sha256(calibration)
        ),
        "portable_calibration_content_sha256": portable_hash,
        "excluded_fields": list(EXCLUDED_FIELDS),
        "current_tool_identity": current_tool,
        "checks": checks,
    }
    return binding, audit


def replay(
    *,
    root: Path,
    output: Path,
    qualification_path: Path,
    calibration_path: Path,
    replay_contract_path: Path,
) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise frozen.QualificationError(
            f"one-shot release replay output is not empty: {output}"
        )
    calibration = _read_json(calibration_path)
    binding, audit = _binding_audit(
        root=root,
        binding_path=replay_contract_path,
        qualification_path=qualification_path,
        calibration_path=calibration_path,
        calibration=calibration,
    )

    sealed_hash = str(binding["sealed_calibration_canonical_content_sha256"])
    observed_hash = str(audit["observed_calibration_canonical_content_sha256"])
    portable_hash = str(audit["portable_calibration_content_sha256"])
    frozen_hasher = frozen._canonical_report_sha256

    def _replay_hash_adapter(report: Mapping[str, Any]) -> str:
        if frozen_hasher(report) != observed_hash:
            raise frozen.QualificationError(
                "frozen validator hashed content other than the bound fresh calibration"
            )
        if portable_calibration_sha256(report) != portable_hash:
            raise frozen.QualificationError(
                "fresh calibration changed during frozen-validator replay"
            )
        return sealed_hash

    frozen._canonical_report_sha256 = _replay_hash_adapter
    try:
        report = frozen.qualify(
            root=root,
            output=output,
            qualification_path=qualification_path,
            calibration_report_path=calibration_path,
        )
    finally:
        frozen._canonical_report_sha256 = frozen_hasher
    engine_receipt = report.pop("unseal_receipt")
    fresh_calibration_identity = {
        "path": str(calibration_path),
        "sha256": sha256_file(calibration_path),
        "canonical_content_sha256": frozen_hasher(calibration),
        "portable_content_sha256": portable_calibration_sha256(calibration),
    }
    frozen_preflight_binding = dict(report["preflight"]["calibration"])
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "created_utc": _utc_now(),
        "operation": "release_replay",
        "qualification_epoch": engine_receipt["qualification_epoch"],
        "generation_epoch": engine_receipt["generation_epoch"],
        "git": engine_receipt["git"],
        "qualification_input_sha256": engine_receipt[
            "qualification_input_sha256"
        ],
        "generation_contract_sha256": engine_receipt[
            "generation_contract_sha256"
        ],
        "fresh_calibration_report": fresh_calibration_identity,
        "frozen_engine_hash_adapter": {
            "target": "qualify_families._canonical_report_sha256",
            "observed_fresh_content_sha256": observed_hash,
            "verified_portable_content_sha256": portable_hash,
            "sealed_first_unseal_content_sha256": sealed_hash,
            "electrical_evaluation_code_changed": False,
            "frozen_preflight_binding": frozen_preflight_binding,
        },
        "calibration_binding": audit,
        "definitions_replayed": engine_receipt["definitions_unsealed"],
        "candidate_parameter_modification_after_unseal_permitted": False,
        "failed_holdout_reuse_for_repair_permitted": False,
    }
    report["qualification_operation"] = "release_replay"
    report["qualification_receipt"] = receipt
    report["replay_receipt"] = receipt
    report["frozen_engine_receipt"] = engine_receipt
    report["preflight"]["frozen_engine_calibration_binding"] = (
        frozen_preflight_binding
    )
    report["preflight"]["calibration"] = {
        **fresh_calibration_identity,
        "frozen_engine_binding_sha256": sealed_hash,
    }
    report["preflight"]["release_replay_binding"] = audit
    identity = report.setdefault("artifact_identity", {})
    identity["calibration_report"] = {
        **fresh_calibration_identity,
        "frozen_engine_binding_sha256": sealed_hash,
    }
    identity["qualification_replay_implementation"] = {
        "path": str(Path(__file__).resolve().relative_to(root)),
        "sha256": sha256_file(Path(__file__)),
    }
    _write_json(output / "replay_receipt.json", receipt)
    _write_json(output / "report.json", report)
    return report


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("qualification_epoch_3.toml"),
    )
    parser.add_argument("--calibration-report", type=Path, required=True)
    parser.add_argument(
        "--replay-contract",
        type=Path,
        default=Path(__file__).with_name("calibration_replay_v4.toml"),
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    report = replay(
        root=arguments.root.resolve(),
        output=arguments.output.resolve(),
        qualification_path=arguments.config.resolve(),
        calibration_path=arguments.calibration_report.resolve(),
        replay_contract_path=arguments.replay_contract.resolve(),
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
