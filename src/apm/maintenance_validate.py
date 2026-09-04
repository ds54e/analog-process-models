# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed validation for the live post-v4 maintenance tree."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model_build import sha256_file
from .paths import repository_root
from .provenance_validate import ProvenanceValidationError, validate_provenance
from .release_validate import (
    ReleaseValidationError,
    audit_distribution,
    audit_migration,
)
from .release_validate_v4 import (
    _check_map,
    _default_output,
    _failed_validation_report,
    _git,
    _run_logged_command,
    _write_report,
    audit_mixed_voltage_evidence,
    audit_public_evidence,
    audit_v3_immutability,
    audit_v4_catalog,
    audit_v4_release_metadata,
    load_v4_gate_contract,
    run_v3_regression,
)
from .spectre_validate import SpectreStructureError, validate_spectre

V4_TAG_OBJECT = "797cdf9462db9dd634bff558802bcadaaeb70015"
V4_TAGGED_COMMIT = "d224f279921c7e1ae637fd867e00d450067766c6"

# These current-tree bytes are completed release records or released model
# artifacts. Live maintenance documentation is deliberately not hash-bound to
# the v4 release review.
FROZEN_V4_ARTIFACT_SHA256 = {
    "V4_MIXED_VOLTAGE.md": (
        "8490d51889ed49a2c5b578caee7808c8622930baa463d840edf46952840d6569"
    ),
    "RELEASE_V4.md": (
        "b0831dc54375476eb15bcb5394821859c9bf8a9a9b900cb5497a1ee3ca5ad98b"
    ),
    "validation/release_gates_v4.toml": (
        "7005ddd99bb4537a2bc9cf95985afa8a7fd25be141c6d866794b63b0be8ffccb"
    ),
    "validation/release_review_v4.toml": (
        "196dc63493a53114f13c64c5a79375f7ab06ef48d81fa8d9ce662ddc7121d63d"
    ),
    "validation/evidence/v4_generation_epoch1_calibration.json": (
        "8fc0803716c60167c7d86a4b050d263ebe17d790f8542ec0c6011d670a28fd7d"
    ),
    "validation/evidence/v4_generation_epoch3_calibration.json": (
        "889be51c0d7b61040cae56b20cd6030a2b2c4d8f71ea59e3d31c00a1a92bc12b"
    ),
    "validation/evidence/v4_mixed_voltage_qualification.json": (
        "e0f867e3539434dc61dedf0e10a56b76cff092c9f43aaa3608bc153481ff9b9b"
    ),
    "validation/evidence/v4_modelgen_foundation.json": (
        "94d7ad484d8e335e73c8724d89308e98e16216196c573776e0aa2cc66b4003d2"
    ),
    "validation/evidence/v4_post_release_requalification.json": (
        "2ae5392fdd1f4d741b1c77e92a8b0e05f89358987272b8df25d4d1ba746c2685"
    ),
    "validation/evidence/v4_qualification_epoch1_failure.json": (
        "eba0602b191390d4a6c16a2ee89d6dbb8e3d8b194757fc3da7ddd856732a62b5"
    ),
    "validation/evidence/v4_qualification_epoch2_failure.json": (
        "70138b9388b4b0a6d50f32fcf8149c46fd85060be45b17224076b71544396e70"
    ),
    "validation/evidence/v4_release_candidate.json": (
        "54ffd0442c9a0578b4f73f7e19f3ff5b93fb70a8018306637be509866ae2d88b"
    ),
    "validation/evidence/v4_runtime_integration.json": (
        "87f0bdf1c5cd7ad8ba88bdbc19315493d0bcea7a17122775158bd18824d1537d"
    ),
    "models/apm045/families/io18/ngspice/apm045_io18_n.inc": (
        "e639452467891fde0ea51f1fb3e965a01f46acf2bec85b90a437f296d2f1cebe"
    ),
    "models/apm045/families/io18/ngspice/apm045_io18_p.inc": (
        "065dd165f2e1bc3bab41f5205292205adab8ea1d4b39c9bdb813d690eaebd40a"
    ),
    "models/apm045/families/io18/ngspice/wrapper.inc": (
        "cd008255aea5fd5e5363900253cc355be0167f203578066c35d6a2f1ae992ad5"
    ),
    "models/apm045/families/io25/ngspice/apm045_io25_n.inc": (
        "2c2478406b4417e7a5058c46b321ff70dee1041025bda04986bb18758df104a0"
    ),
    "models/apm045/families/io25/ngspice/apm045_io25_p.inc": (
        "8eab45ce29fbd0caf4b089c4e1f7f7e52e14c7cc1572ee9c4245b57fc8ff1cc2"
    ),
    "models/apm045/families/io25/ngspice/wrapper.inc": (
        "c754235bbb5a8df2b88e07ca6d691a687404be08c105a1157be5469f77b64efc"
    ),
}


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _normalized(text: str) -> str:
    return " ".join(text.split())


def audit_current_guidance(root: Path) -> dict[str, Any]:
    """Audit mutable guidance without assigning it historical release meaning."""

    required_paths = (
        "AGENTS.md",
        "APM045_POSITIONING.md",
        "ENVIRONMENT.md",
        "GOAL.md",
        "README.md",
        "SECURITY.md",
        "models/apm045/README.md",
    )
    agents = _read(root, "AGENTS.md")
    positioning = _read(root, "APM045_POSITIONING.md")
    environment = _read(root, "ENVIRONMENT.md")
    goal = _read(root, "GOAL.md")
    readme = _read(root, "README.md")
    security = _read(root, "SECURITY.md")
    apm045 = _read(root, "models/apm045/README.md")
    normalized_agents = _normalized(agents)
    normalized_positioning = _normalized(positioning)
    normalized_environment = _normalized(environment)
    normalized_goal = _normalized(goal)
    normalized_readme = _normalized(readme)
    normalized_security = _normalized(security)
    normalized_apm045 = _normalized(apm045)
    public_text = f"{readme}\n{positioning}\n{apm045}"
    prohibited_patterns = [
        pattern
        for pattern in (
            r"(?i)APM (?:is|provides) (?:a )?manufacturable PDK",
            r"(?i)io(?:18|25) (?:is|are|was|were) (?:TSMC|UMC|foundry)[- ]correlated",
            r"(?i)io(?:18|25) (?:has|have|provides?) (?:a )?safe voltage rating",
            r"(?i)Spectre numerical validation (?:passed|is complete)",
            r"(?i)epistemic ensemble (?:is|represents) process variation",
        )
        if re.search(pattern, public_text)
    ]
    frozen_names = (
        "V4_MIXED_VOLTAGE.md",
        "RELEASE_V4.md",
        "validation/release_gates_v4.toml",
        "validation/release_review_v4.toml",
        "validation/evidence/v4_*.json",
    )
    checks = {
        "required_current_documents_present": all(
            (root / relative).is_file() for relative in required_paths
        ),
        "goal_is_post_v4_maintenance": goal.startswith("# Post-v4 release maintenance")
        and "Current `main` is the post-v4 public-maintenance line" in normalized_goal
        and "Complete and release **APM v4.0.0**" not in normalized_goal,
        "goal_preserves_released_semantics": "model bytes" in normalized_goal
        and "changing released model/evidence semantics" in normalized_goal
        and "must not update a historical release review" in normalized_goal,
        "agents_identify_frozen_v4_records": all(name in agents for name in frozen_names)
        and "it is not current technical" in normalized_agents
        and "Do not rewrite these records" in normalized_agents,
        "positioning_has_inline_spdx": positioning.startswith(
            "<!-- SPDX-FileCopyrightText: APM contributors -->\n"
            "<!-- SPDX-License-Identifier: Apache-2.0 -->\n"
        ),
        "positioning_preserves_family_boundary": (
            "generic 40/45 nm-class planar bulk CMOS" in normalized_positioning
            and "VTL/VTG/VTH and legacy THKOX" in normalized_positioning
            and "`io18` and `io25` mixed-voltage families" in normalized_positioning
        ),
        "positioning_preserves_claim_boundary": (
            "not as a TSMC40/45 model" in normalized_positioning
            and "foundry design-rule minima" in normalized_positioning
            and "reliability or safe-voltage ratings" in normalized_positioning
            and "epistemic ensemble as process variation" in normalized_positioning
            and "Model/release changes required: **NONE**" in normalized_positioning
        ),
        "apm045_readme_is_current_device_guidance": (
            "APM045_POSITIONING.md" in normalized_apm045
            and "released io18/io25 cards" in normalized_apm045
            and "current maintenance scope" in normalized_apm045
        ),
        "security_names_latest_release": "APM v4.0.0 is the latest completed release"
        in normalized_security
        and "post-release public-maintenance line" in normalized_security,
        "environment_separates_current_and_historical_flows": (
            "## Historical v4 release qualification boundary" in normalized_environment
            and "## Current maintenance validation" in normalized_environment
            and "Unflagged `apm validate` checks the live post-v4 maintenance tree"
            in normalized_environment
        ),
        "readme_separates_current_and_historical_flows": (
            "frozen historical records rather than current implementation instructions"
            in normalized_readme
            and "does not reinterpret or update a completed release review"
            in normalized_readme
        ),
        "no_prohibited_public_claims": not prohibited_patterns,
    }
    result = _check_map(checks, context="live post-v4 maintenance guidance")
    result.update(
        {
            "reviewed_paths": list(required_paths),
            "prohibited_claim_patterns": prohibited_patterns,
        }
    )
    return result


def audit_frozen_v4_artifacts(root: Path) -> dict[str, Any]:
    """Verify that maintenance did not rewrite completed v4 records or models."""

    observed = {
        relative: sha256_file(root / relative) if (root / relative).is_file() else "missing"
        for relative in FROZEN_V4_ARTIFACT_SHA256
    }
    mismatches = [
        {
            "path": relative,
            "expected": expected,
            "actual": observed[relative],
        }
        for relative, expected in FROZEN_V4_ARTIFACT_SHA256.items()
        if observed[relative] != expected
    ]
    try:
        tag_object = _git(root, "rev-parse", "refs/tags/v4.0.0")
        tag_commit = _git(root, "rev-parse", "v4.0.0^{commit}")
        tag_type = _git(root, "cat-file", "-t", "refs/tags/v4.0.0")
    except ReleaseValidationError:
        tag_object = "missing"
        tag_commit = "missing"
        tag_type = "missing"
    checks = {
        "v4_tag_object_exact": tag_object == V4_TAG_OBJECT,
        "v4_tag_commit_exact": tag_commit == V4_TAGGED_COMMIT,
        "v4_tag_remains_annotated": tag_type == "tag",
        "completed_v4_artifact_hashes_exact": not mismatches,
    }
    result = _check_map(checks, context="frozen v4 release records and model artifacts")
    result.update(
        {
            "v4_tag_object": tag_object,
            "v4_tagged_commit": tag_commit,
            "artifact_count": len(FROZEN_V4_ARTIFACT_SHA256),
            "artifact_sha256": observed,
            "mismatches": mismatches,
        }
    )
    return result


def run_maintenance_static_audits(root: Path, output: Path) -> dict[str, Any]:
    """Run the ordinary static/regression suite against current maintenance guidance."""

    baseline_contract = load_v4_gate_contract(root)
    output.mkdir(parents=True, exist_ok=False)
    commands = [
        _run_logged_command(root, output, "pytest", [sys.executable, "-m", "pytest", "-q"]),
        _run_logged_command(
            root, output, "ruff", [sys.executable, "-m", "ruff", "check", "."]
        ),
        _run_logged_command(
            root, output, "reuse", [sys.executable, "-m", "reuse", "lint"]
        ),
    ]
    provenance_output = output / "provenance"
    try:
        provenance = validate_provenance(provenance_output, root=root)
    except ProvenanceValidationError as error:
        provenance = _failed_validation_report(
            provenance_output / "provenance_validation_report.json",
            error,
            fallback_schema="apm.provenance-validation.v2",
        )
    spectre_output = output / "spectre"
    try:
        spectre = validate_spectre(spectre_output, root=root)
    except SpectreStructureError as error:
        spectre = _failed_validation_report(
            spectre_output / "spectre_structural_report.json",
            error,
            fallback_schema="apm.spectre-structural-report.v2",
        )
    try:
        v3_regression = run_v3_regression(root, output / "v3-regression")
    except Exception as error:  # noqa: BLE001 - preserve the exact failure in evidence
        v3_regression = _failed_validation_report(
            output / "v3-regression/report.json",
            error,
            fallback_schema="apm.v3-regression-from-v4.v1",
        )
    audits = {
        "release_baseline_metadata": audit_v4_release_metadata(root, baseline_contract),
        "catalog": audit_v4_catalog(root, baseline_contract),
        "migration": audit_migration(root),
        "distribution": audit_distribution(root),
        "current_guidance": audit_current_guidance(root),
        "frozen_v4_artifacts": audit_frozen_v4_artifacts(root),
        "public_evidence": audit_public_evidence(root, baseline_contract),
        "v3_immutability": audit_v3_immutability(root, baseline_contract),
        "mixed_voltage_evidence": audit_mixed_voltage_evidence(root),
        "provenance": provenance,
    }
    checks = {
        "current_regression_commands": all(item["status"] == "pass" for item in commands),
        "repository_audits": all(item.get("status") == "pass" for item in audits.values()),
        "v3_regression": v3_regression.get("status") == "pass",
        "spectre_structural": spectre.get("status") == "structurally_checked"
        and all(spectre.get("checks", {}).values()),
    }
    report = {
        "schema": "apm.maintenance-static-audits.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if all(checks.values()) else "fail",
        "repository": str(root),
        "repository_head": _git(root, "rev-parse", "HEAD"),
        "released_baseline_contract_path": "validation/release_gates_v4.toml",
        "released_baseline_contract_sha256": sha256_file(
            root / "validation/release_gates_v4.toml"
        ),
        "commands": commands,
        "audits": audits,
        "v3_regression": {
            "status": v3_regression.get("status"),
            "report_path": v3_regression.get("report_path"),
            "checks": v3_regression.get("checks", {}),
        },
        "spectre": {
            "status": spectre.get("status"),
            "backend_status": spectre.get("backend_status"),
            "real_tool_validation_performed": spectre.get(
                "real_tool_validation_performed"
            ),
            "report_path": spectre.get("report_path"),
            "checks": spectre.get("checks", {}),
        },
        "checks": checks,
    }
    result = _write_report(output / "static_audits.json", report)
    result.update(
        {
            "baseline_contract": baseline_contract,
            "provenance": provenance,
            "spectre_full": spectre,
            "v3_regression_full": v3_regression,
        }
    )
    return result


def validate_maintenance_repository(
    output: Path | None = None, *, root: Path | None = None
) -> dict[str, Any]:
    """Validate the live post-v4 tree without changing frozen release semantics."""

    selected = (root or repository_root()).resolve()
    destination = (
        output or _default_output(selected, "repository-maintenance")
    ).expanduser().resolve()
    result = run_maintenance_static_audits(selected, destination)
    report = {
        "schema": "apm.repository-validation.maintenance.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": result["status"],
        "repository": str(selected),
        "repository_head": _git(selected, "rev-parse", "HEAD"),
        "static_report_path": result["report_path"],
        "static_report_sha256": sha256_file(Path(result["report_path"])),
        "checks": result["checks"],
        "audits": result["audits"],
    }
    report = _write_report(destination / "report.json", report)
    if report["status"] != "pass":
        raise ReleaseValidationError(
            f"maintenance repository validation failed; see {report['report_path']}"
        )
    return report
