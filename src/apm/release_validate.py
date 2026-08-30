# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed repository and v2.0.0 release-gate validation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Callable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib

from .benchmark_validate import validate_benchmark
from .catalog import load_catalog
from .clean_clone import verify_clean_clone_attestation
from .compare import (
    compare_anchors,
    compare_set,
    validate_all_characterizations,
)
from .doctor import run_doctor
from .model_build import MODEL_SOURCES, sha256_file
from .native_variation import validate_apm130_native
from .paths import repository_root, state_directory
from .provenance_validate import ProvenanceValidationError, validate_provenance
from .spectre_validate import SpectreStructureError, validate_spectre
from .toolchain import resolve_toolchain

IMPLEMENTED_GATE_IDS = frozenset(
    {
        "runtime.reference_environment",
        "runtime.compact_models",
        "catalog.manifest_driven",
        "catalog.required_families",
        "models.apm130_lv_hv",
        "models.apm045_families",
        "models.apm022_multivt",
        "models.apm016f_multivt",
        "characterization.v2",
        "comparison.v2",
        "variation.benchmark_v2",
        "variation.apm130_upstream",
        "passives.benchmark",
        "spectre.model_only",
        "licensing.provenance",
        "distribution.self_contained_models",
        "migration.no_v1_runtime_ssot",
        "release.metadata_complete",
        "release.clean_clone",
        "release.claim_audit",
    }
)
REQUIRED_REVIEWED_FILES = frozenset(
    {
        "README.md",
        "CHANGELOG.md",
        "STATUS.md",
        "THIRD_PARTY.md",
        "docs/benchmark-variation.md",
        "docs/characterization.md",
        "docs/native-variation.md",
        "docs/release-validation.md",
        "docs/spectre.md",
        "validation/evidence/v2_release_readiness.md",
    }
)
TRACKED_FORBIDDEN_PARTS = {
    ".apm",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "results",
}
TRACKED_FORBIDDEN_SUFFIXES = {".osdi", ".raw", ".log", ".pyc", ".pyo"}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
INCLUDE_RE = re.compile(
    r"^\s*(?:\.include|include|`include)\s+[\"']?([^\"'\s]+)",
    re.IGNORECASE | re.MULTILINE,
)
BUILTIN_VERILOG_A_INCLUDES = {"discipline.h", "disciplines.vams", "constants.vams"}
PLACEHOLDER_SCAN_PATHS = (
    "pyproject.toml",
    "src/apm/__init__.py",
    "CHANGELOG.md",
    "models/*/provenance.toml",
    "models/*/families/*/variant-generation.toml",
    "variation/benchmark_v2.toml",
    "variation/adapters_v2.toml",
    "passives/benchmark_v2.toml",
)


class ReleaseValidationError(RuntimeError):
    """A repository or required release gate did not pass."""


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ReleaseValidationError(f"cannot read TOML {path}: {error}") from error


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReleaseValidationError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout.strip()


def _check_map(checks: dict[str, bool], *, context: str) -> dict[str, Any]:
    failed = sorted(name for name, passed in checks.items() if passed is not True)
    return {
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "context": context,
    }


def load_gate_contract(root: Path) -> dict[str, Any]:
    contract = _load_toml(root / "validation/release_gates.toml")
    if contract.get("schema") != "apm.release-gates.v2":
        raise ReleaseValidationError("unsupported release-gate schema")
    gates = contract.get("gate")
    if not isinstance(gates, list) or not gates:
        raise ReleaseValidationError("release-gate contract contains no gates")
    identifiers = [gate.get("id") for gate in gates]
    if any(not isinstance(identifier, str) for identifier in identifiers):
        raise ReleaseValidationError("every release gate must have a string id")
    if len(identifiers) != len(set(identifiers)):
        raise ReleaseValidationError("release-gate ids must be unique")
    required = {gate["id"] for gate in gates if gate.get("required") is True}
    missing = required - IMPLEMENTED_GATE_IDS
    stale = IMPLEMENTED_GATE_IDS - required
    if missing or stale:
        raise ReleaseValidationError(
            "release validator/contract mismatch; "
            f"missing implementations={sorted(missing)}, stale implementations={sorted(stale)}"
        )
    if len(required) != 20 or contract.get("target") != "v2.0.0":
        raise ReleaseValidationError("v2 release contract must contain 20 gates for v2.0.0")
    return contract


def audit_release_metadata(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    metadata = contract["release_metadata"]
    target = str(metadata["target_version"])
    project = _load_toml(root / "pyproject.toml")
    package_version = str(project.get("project", {}).get("version", ""))
    init_text = (root / "src/apm/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_text, re.MULTILINE)
    runtime_version = match.group(1) if match else ""
    cli_text = (root / "src/apm/cli.py").read_text(encoding="utf-8")
    cli_match = re.search(r'version=["\']APM ([^"\']+)["\']', cli_text)
    cli_version = cli_match.group(1) if cli_match else ""
    try:
        installed_version = importlib_metadata.version("analog-process-models")
    except importlib_metadata.PackageNotFoundError:
        installed_version = "missing"
    changelog_path = root / str(metadata["release_notes_path"])
    changelog = changelog_path.read_text(encoding="utf-8")
    placeholder_hits: list[dict[str, str]] = []
    tokens = [str(token) for token in metadata["forbidden_release_placeholder_tokens"]]
    for pattern in PLACEHOLDER_SCAN_PATHS:
        for path in sorted(root.glob(pattern)):
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in tokens:
                if re.search(rf"\b{re.escape(token)}\b", text, re.IGNORECASE):
                    placeholder_hits.append(
                        {"path": str(path.relative_to(root)), "token": token}
                    )
    checks = {
        "pyproject_version_matches_target": package_version == target,
        "runtime_version_matches_target": runtime_version == target,
        "cli_version_matches_target": cli_version == target,
        "installed_distribution_version_matches_target": installed_version == target,
        "all_version_metadata_agree": package_version == runtime_version == cli_version,
        "contract_target_matches_version": contract.get("target") == f"v{target}",
        "python_meets_minimum": sys.version_info
        >= tuple(int(item) for item in str(contract["runtime"]["python_minimum"]).split(".")),
        "changelog_has_dated_release_heading": bool(
            re.search(
                rf"^## \[{re.escape(target)}\] - \d{{4}}-\d{{2}}-\d{{2}}$",
                changelog,
                re.MULTILINE,
            )
        ),
        "changelog_has_no_unreleased_section": not bool(
            re.search(r"^## (?:\[)?Unreleased(?:\])?$", changelog, re.MULTILINE)
        ),
        "no_release_placeholder_tokens": not placeholder_hits,
    }
    result = _check_map(checks, context="v2 version, release notes, and placeholder audit")
    result.update(
        {
            "target_version": target,
            "package_version": package_version,
            "runtime_version": runtime_version,
            "cli_version": cli_version,
            "installed_distribution_version": installed_version,
            "placeholder_hits": placeholder_hits,
            "scanned_paths": list(PLACEHOLDER_SCAN_PATHS),
        }
    )
    return result


def audit_catalog(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    catalog = load_catalog(root)
    required = contract["technology_catalog"]
    required_technologies = tuple(required["required_technologies"])
    required_families = required["required_families"]
    actual = {technology.technology_id: technology for technology in catalog.technologies}
    family_selectors = [
        family.selector for technology in catalog.technologies for family in technology.families
    ]
    device_names = [
        device.public_name
        for technology in catalog.technologies
        for family in technology.families
        for device in family.devices
    ]
    family_contracts = all(
        {
            actual[technology_id].family(item).backend(binding).backend_id
            for item in required_families[technology_id]
            for binding in ("ngspice", "spectre")
        }
        == {"ngspice", "spectre"}
        and all(
            family.default_operating_profile
            in {profile.profile_id for profile in family.operating_profiles}
            and {device.polarity for device in family.devices} == {"n", "p"}
            for family in actual[technology_id].families
        )
        for technology_id in required_technologies
    )
    apm045 = actual["apm045"]
    checks = {
        "technology_set_exact": set(actual) == set(required_technologies),
        "family_count_exact": len(family_selectors) == int(required["required_family_count"]),
        "required_families_exact": all(
            {family.family_id for family in actual[technology_id].families}
            == set(required_families[technology_id])
            for technology_id in required_technologies
        ),
        "family_device_profile_backend_contracts": family_contracts,
        "public_device_names_unique_and_family_qualified": len(device_names)
        == len(set(device_names))
        == 26
        and all(
            device.public_name.startswith(f"{family.technology_id}_{family.family_id}_")
            for technology in catalog.technologies
            for family in technology.families
            for device in family.devices
        ),
        "cross_process_anchors_exact": all(
            actual[technology_id].cross_process_anchor
            == required["cross_process_anchors"][technology_id]
            for technology_id in required_technologies
        ),
        "apm045_comparison_sets": apm045.comparison_set("threshold").members
        == ("vtl", "vtg", "vth")
        and apm045.comparison_set("threshold").kind == "threshold_family"
        and apm045.comparison_set("gate_stack").members == ("vtg", "thkox")
        and apm045.comparison_set("gate_stack").common_overlap_profile
        == "common_overlap_1v0",
        "catalog_loader_is_manifest_driven": "apm350" not in (
            root / "src/apm/catalog.py"
        ).read_text(encoding="utf-8")
        and "load_kit" not in (root / "src/apm/characterize.py").read_text(encoding="utf-8"),
    }
    result = _check_map(checks, context="manifest-driven v2 catalog and family contract")
    result.update(
        {
            "technology_ids": sorted(actual),
            "family_selectors": sorted(family_selectors),
            "device_count": len(device_names),
            "snapshot": catalog.snapshot(),
        }
    )
    return result


def audit_migration(root: Path) -> dict[str, Any]:
    old_paths = [
        *sorted((root / "models").glob("*/kit.toml")),
        root / "variation/benchmark_v1.toml",
        root / "variation/adapters_v1.toml",
        root / "passives/benchmark_v1.toml",
    ]
    existing_old_paths = [str(path.relative_to(root)) for path in old_paths if path.exists()]
    audit_modules = {"release_validate.py", "provenance_validate.py"}
    source_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted((root / "src/apm").glob("*.py"))
        if path.name not in audit_modules
    )
    unqualified_aliases: list[str] = []
    for path in sorted((root / "models").glob("*/**/ngspice/*.inc")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for name in re.findall(r"(?mi)^\.subckt\s+(apm(?:350|130|045|022|016f)_\w+)", text):
            parts = name.split("_")
            if len(parts) == 2 and parts[1] in {"nmos", "pmos", "nfet", "pfet"}:
                unqualified_aliases.append(name)
    checks = {
        "old_kit_toml_removed": not existing_old_paths,
        "old_benchmark_v1_sources_removed": not any(
            path.endswith(("benchmark_v1.toml", "adapters_v1.toml"))
            for path in existing_old_paths
        ),
        "no_runtime_load_kit_dependency": "load_kit" not in source_text,
        "no_v1_canonical_runtime_schema": all(
            token not in source_text
            for token in (
                "apm.kit.v1",
                "apm.characterization.v1",
                "apm.benchmark-request.v1",
                "apm.resolved-variation.v1",
                "apm.model-build.v1",
                "apm.doctor.v1",
            )
        ),
        "no_unqualified_v1_public_aliases": not unqualified_aliases,
        "normal_family_dispatch_uses_catalog": "load_family(" in source_text
        and "load_catalog(" in source_text,
    }
    result = _check_map(checks, context="v1 runtime single-source migration audit")
    result.update(
        {
            "existing_old_paths": existing_old_paths,
            "unqualified_aliases": sorted(set(unqualified_aliases)),
        }
    )
    return result


def _tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=False)
    if result.returncode != 0:
        raise ReleaseValidationError("git ls-files failed during distribution audit")
    return [root / os.fsdecode(item) for item in result.stdout.split(b"\0") if item]


def audit_distribution(root: Path) -> dict[str, Any]:
    tracked = _tracked_files(root)
    missing_tracked: list[str] = []
    forbidden_tracked: list[str] = []
    suspicious_names: list[str] = []
    secret_hits: list[dict[str, str]] = []
    oversized_tracked: list[dict[str, Any]] = []
    for path in tracked:
        relative = path.relative_to(root)
        if not path.is_file():
            missing_tracked.append(str(relative))
            continue
        lowered_parts = {part.lower() for part in relative.parts}
        if lowered_parts & TRACKED_FORBIDDEN_PARTS or path.suffix.lower() in (
            TRACKED_FORBIDDEN_SUFFIXES
        ):
            forbidden_tracked.append(str(relative))
        lowered_name = path.name.lower()
        if lowered_name in {"id_rsa", "id_ed25519", "credentials.json", ".env"} or (
            lowered_name.endswith((".pem", ".p12", ".pfx", ".key"))
        ):
            suspicious_names.append(str(relative))
        if path.stat().st_size <= 8 * 1024 * 1024:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    secret_hits.append({"path": str(relative), "pattern": name})
        if path.stat().st_size > 5 * 1024 * 1024:
            oversized_tracked.append(
                {"path": str(relative), "size_bytes": path.stat().st_size}
            )
    unresolved_includes: list[dict[str, str]] = []
    for path in tracked:
        if not path.is_file() or path.suffix.lower() not in {".inc", ".lib", ".va", ".scs", ".sp"}:
            continue
        if "models" not in path.relative_to(root).parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for matched in INCLUDE_RE.findall(text):
            include_name = matched.rstrip(";)")
            if include_name.lower() in BUILTIN_VERILOG_A_INCLUDES:
                continue
            if re.match(r"^[a-z]+://", include_name, re.IGNORECASE) or not (
                path.parent / include_name
            ).resolve().is_file():
                unresolved_includes.append(
                    {"source": str(path.relative_to(root)), "include": include_name}
                )
    shipped_sources = {
        model_id: str(relative)
        for model_id, relative in MODEL_SOURCES.items()
        if (root / relative).is_file()
    }
    checks = {
        "tracked_worktree_files_exist": not missing_tracked,
        "compiler_model_sources_shipped": set(shipped_sources) == set(MODEL_SOURCES),
        "no_unresolved_or_remote_model_includes": not unresolved_includes,
        "no_generated_or_scratch_artifacts_tracked": not forbidden_tracked,
        "no_suspicious_secret_filenames_tracked": not suspicious_names,
        "no_credential_signatures_detected": not secret_hits,
        "no_oversized_tracked_artifacts": not oversized_tracked,
        "generated_osdi_not_tracked": not any(path.suffix.lower() == ".osdi" for path in tracked),
    }
    result = _check_map(checks, context="tracked distribution, include closure, and secret audit")
    result.update(
        {
            "tracked_file_count": len(tracked),
            "shipped_compiler_sources": shipped_sources,
            "missing_tracked": missing_tracked,
            "unresolved_includes": unresolved_includes,
            "forbidden_tracked": forbidden_tracked,
            "suspicious_names": suspicious_names,
            "secret_hits": secret_hits,
            "oversized_tracked": oversized_tracked,
        }
    )
    return result


def audit_claims(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    review_path = root / "validation/release_review.toml"
    review = _load_toml(review_path) if review_path.is_file() else {}
    reviewed_files = review.get("reviewed_files", {})
    mismatches: list[dict[str, str]] = []
    if isinstance(reviewed_files, dict):
        for relative, expected in reviewed_files.items():
            path = root / relative
            actual = sha256_file(path) if path.is_file() else "missing"
            if actual != expected:
                mismatches.append(
                    {"path": relative, "expected": str(expected), "actual": actual}
                )
    readme = (root / "README.md").read_text(encoding="utf-8")
    docs = {
        path.name: path.read_text(encoding="utf-8", errors="replace")
        for path in sorted((root / "docs").glob("*.md"))
    }
    public_text = "\n".join(
        [
            readme,
            (root / "CHANGELOG.md").read_text(encoding="utf-8"),
            *docs.values(),
        ]
    )
    prohibited_patterns = [
        pattern
        for pattern in (
            r"(?i)Spectre[- ]validated",
            r"(?i)real Spectre (?:validation|simulation|parsing) (?:passed|complete)",
            r"(?i)APM (?:is|provides) (?:a )?manufacturable PDK",
            r"(?i)APM-authored .* (?:foundry|silicon)[- ]correlated",
            r"(?i)Benchmark Global (?:is|represents) (?:a )?physical process correlation",
        )
        if re.search(pattern, public_text)
    ]
    required_topics = set(contract["documentation"]["required_topics"])
    topic_checks = {
        "scope": "## Scope" in readme,
        "device_family_domain_model": "Technology → Electrical Family → Device" in readme,
        "operating_profile_vs_validity": "Operating profile versus validity" in readme,
        "model_provenance": "## Model provenance" in readme,
        "model_fidelity_limitations": "## Model fidelity and limitations" in readme,
        "benchmark_vs_upstream_variation": "Benchmark versus upstream variation" in readme,
        "comparison_methodology": "## Comparison methodology" in readme,
        "spectre_status": "experimental/unverified" in public_text.lower()
        and "not been parsed" in docs.get("spectre.md", ""),
        "not_a_manufacturable_pdk": "not a manufacturable PDK" in readme,
    }
    checks = {
        "manual_review_record_complete": review.get("schema") == "apm.release-review.v2"
        and review.get("status") == "complete",
        "manual_review_decisions": review.get("spectre_real_tool_run") is False
        and review.get("foundry_or_silicon_correlation_claimed") is False
        and review.get("benchmark_physical_family_correlation_claimed") is False
        and review.get("repository_visibility_changed") is False
        and review.get("unresolved_claim_findings") == [],
        "manual_review_identity_and_time_present": bool(review.get("reviewer"))
        and bool(
            re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                str(review.get("reviewed_utc", "")),
            )
        ),
        "reviewed_file_set_exact": isinstance(reviewed_files, dict)
        and set(reviewed_files) == REQUIRED_REVIEWED_FILES,
        "reviewed_file_hashes_current": not mismatches,
        "required_documentation_topics": required_topics == set(topic_checks)
        and all(topic_checks.values()),
        "no_prohibited_public_claims": not prohibited_patterns,
    }
    result = _check_map(checks, context="hash-bound v2 public-claim review")
    result.update(
        {
            "review_path": str(review_path.relative_to(root)),
            "review_sha256": sha256_file(review_path) if review_path.is_file() else "missing",
            "topic_checks": topic_checks,
            "review_hash_mismatches": mismatches,
            "prohibited_claim_patterns": prohibited_patterns,
        }
    )
    return result


def _run_logged_command(
    root: Path, output: Path, command_id: str, command: list[str]
) -> dict[str, Any]:
    started = time.monotonic()
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    stdout_path = output / f"{command_id}.stdout.txt"
    stderr_path = output / f"{command_id}.stderr.txt"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    return {
        "id": command_id,
        "command": command,
        "returncode": result.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout_path": str(stdout_path),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_path": str(stderr_path),
        "stderr_sha256": sha256_file(stderr_path),
        "status": "pass" if result.returncode == 0 else "fail",
    }


def _failed_validation_report(
    report_path: Path, error: Exception, *, fallback_schema: str
) -> dict[str, Any]:
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        report = {"schema": fallback_schema, "status": "fail", "checks": {}}
    report["error"] = str(error)
    report["report_path"] = str(report_path)
    report["output_directory"] = str(report_path.parent)
    return report


def run_static_audits(root: Path, output: Path) -> dict[str, Any]:
    contract = load_gate_contract(root)
    output.mkdir(parents=True, exist_ok=False)
    commands = [
        _run_logged_command(root, output, "pytest", [sys.executable, "-m", "pytest", "-q"]),
        _run_logged_command(root, output, "ruff", [sys.executable, "-m", "ruff", "check", "."]),
        _run_logged_command(root, output, "reuse", [sys.executable, "-m", "reuse", "lint"]),
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
    audits = {
        "metadata": audit_release_metadata(root, contract),
        "catalog": audit_catalog(root, contract),
        "migration": audit_migration(root),
        "distribution": audit_distribution(root),
        "claims": audit_claims(root, contract),
        "provenance": provenance,
    }
    checks = {
        "regression_commands": all(command["status"] == "pass" for command in commands),
        "repository_audits": all(audit.get("status") == "pass" for audit in audits.values()),
        "spectre_structural": spectre.get("status") == "structurally_checked"
        and all(spectre.get("checks", {}).values()),
    }
    result: dict[str, Any] = {
        "contract": contract,
        "commands": commands,
        "audits": audits,
        "spectre": spectre,
        "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
    }
    report_path = output / "static_audits.json"
    persisted = {
        "schema": "apm.static-audits.v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": result["status"],
        "contract_sha256": sha256_file(root / "validation/release_gates.toml"),
        "commands": commands,
        "audits": audits,
        "spectre": {
            "status": spectre.get("status"),
            "report_path": spectre.get("report_path"),
            "checks": spectre.get("checks", {}),
        },
        "checks": checks,
    }
    report_path.write_text(json.dumps(persisted, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["report_path"] = str(report_path)
    result["output_directory"] = str(output)
    return result


def _gate(status: str, evidence: list[str], detail: str) -> dict[str, Any]:
    return {"status": status, "evidence": evidence, "detail": detail}


def _report_reference(result: dict[str, Any] | None) -> list[str]:
    if not result:
        return []
    path = result.get("report_path")
    return [str(path)] if path else []


def _call_component(
    components: dict[str, Any], name: str, callback: Callable[[], dict[str, Any]]
) -> dict[str, Any] | None:
    started = time.monotonic()
    try:
        result = callback()
    except Exception as error:  # noqa: BLE001 - preserve all release failures as evidence
        components[name] = {
            "status": "fail",
            "error_type": type(error).__name__,
            "error": str(error),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        return None
    component_status = result.get("status")
    passed_statuses = {"pass", "validated", "verified", "attested", "structurally_checked"}
    report_path = result.get("report_path")
    components[name] = {
        "status": "pass" if component_status in passed_statuses else "fail",
        "duration_seconds": round(time.monotonic() - started, 3),
        "report_path": report_path,
        "report_sha256": sha256_file(Path(report_path))
        if report_path and Path(report_path).is_file()
        else None,
        "component_status": component_status,
    }
    return result


def evaluate_required_gates(
    contract: dict[str, Any], gate_results: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], bool]:
    """Order contract gates and fail closed on missing, skipped, or stale evidence."""

    ordered: list[dict[str, Any]] = []
    overall = True
    for definition in contract["gate"]:
        identifier = definition["id"]
        required = definition.get("required") is True
        result = gate_results.get(identifier) or _gate(
            "missing", [], "validator produced no result for this gate"
        )
        evidence = result.get("evidence")
        evidence_valid = (
            isinstance(evidence, list)
            and bool(evidence)
            and all(isinstance(item, str) and bool(item) and Path(item).is_file() for item in evidence)
        )
        passed = result.get("status") == "pass" and evidence_valid
        if required and not passed:
            overall = False
        ordered.append({**definition, **result, "evidence_valid": evidence_valid, "passed": passed})
    return ordered, overall


def _default_output(root: Path, release: bool) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    mode = "release" if release else "repository"
    return state_directory(root) / "results" / "validation" / f"{mode}-{stamp}"


def validate_repository(output: Path | None = None, *, root: Path | None = None) -> dict[str, Any]:
    selected = (root or repository_root()).resolve()
    destination = (output or _default_output(selected, False)).expanduser().resolve()
    result = run_static_audits(selected, destination)
    report: dict[str, Any] = {
        "schema": "apm.repository-validation.v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": result["status"],
        "repository": str(selected),
        "repository_head": _git(selected, "rev-parse", "HEAD"),
        "commands": result["commands"],
        "audits": result["audits"],
        "spectre": {
            "status": result["spectre"].get("status"),
            "report_path": result["spectre"].get("report_path"),
        },
        "checks": result["checks"],
    }
    report_path = destination / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["output_directory"] = str(destination)
    report["report_path"] = str(report_path)
    if report["status"] != "pass":
        raise ReleaseValidationError(f"repository validation failed; see {report_path}")
    return report


def _validated(result: dict[str, Any] | None) -> bool:
    return bool(
        result
        and result.get("status") == "validated"
        and result.get("checks", {}).get("overall_pass") is True
    )


def _component_error(components: dict[str, Any], name: str) -> str:
    return str(components.get(name, {}).get("error", f"{name} validation did not pass"))


def validate_release(output: Path | None = None, *, root: Path | None = None) -> dict[str, Any]:
    selected = (root or repository_root()).resolve()
    destination = (output or _default_output(selected, True)).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=False)
    contract = load_gate_contract(selected)
    components: dict[str, Any] = {}
    gate_results = {
        identifier: _gate("not_run", [], "required validation has not completed")
        for identifier in IMPLEMENTED_GATE_IDS
    }
    created = datetime.now(timezone.utc).isoformat()

    attestation = _call_component(
        components,
        "clean_clone",
        lambda: {
            **verify_clean_clone_attestation(selected),
            "report_path": str(selected / ".apm/clean-clone-attestation.json"),
        },
    )
    attestation_evidence = _report_reference(attestation)

    static = _call_component(
        components,
        "static",
        lambda: run_static_audits(selected, destination / "static"),
    )
    static_evidence = _report_reference(static)
    if static:
        audits = static["audits"]
        command_by_id = {command["id"]: command for command in static["commands"]}
        pytest_pass = command_by_id.get("pytest", {}).get("status") == "pass"
        catalog_pass = audits["catalog"]["status"] == "pass"
        provenance_pass = audits["provenance"].get("status") == "pass"
        distribution_pass = audits["distribution"]["status"] == "pass"
        gate_results["catalog.manifest_driven"] = _gate(
            "pass" if pytest_pass and catalog_pass else "fail",
            static_evidence,
            "generic fixture-family regression plus production catalog audit",
        )
        gate_results["catalog.required_families"] = _gate(
            audits["catalog"]["status"], static_evidence, "five technologies and 13 families"
        )
        gate_results["migration.no_v1_runtime_ssot"] = _gate(
            "pass" if pytest_pass and audits["migration"]["status"] == "pass" else "fail",
            static_evidence,
            "v1 runtime single-source and alias migration audit",
        )
        gate_results["spectre.model_only"] = _gate(
            "pass"
            if static["spectre"].get("status") == "structurally_checked"
            and all(static["spectre"].get("checks", {}).values())
            else "fail",
            _report_reference(static["spectre"]),
            "13-family model-only Spectre structure; experimental/unverified",
        )
        gate_results["licensing.provenance"] = _gate(
            "pass"
            if provenance_pass and command_by_id.get("reuse", {}).get("status") == "pass"
            else "fail",
            _report_reference(audits["provenance"]),
            "exact-file hashes, redistribution boundaries, and REUSE/SPDX",
        )
        gate_results["distribution.self_contained_models"] = _gate(
            "pass" if provenance_pass and distribution_pass and attestation else "fail",
            [*static_evidence, *attestation_evidence],
            "tracked model closure and generated-output policy in an attested clone",
        )
        gate_results["release.metadata_complete"] = _gate(
            audits["metadata"]["status"], static_evidence, "v2.0.0 metadata and placeholders"
        )
        gate_results["release.claim_audit"] = _gate(
            audits["claims"]["status"], static_evidence, "hash-bound v2 public claim review"
        )

    toolchain = None
    try:
        toolchain = resolve_toolchain(selected)
    except Exception as error:  # noqa: BLE001 - record discovery failure and continue
        components["toolchain"] = {
            "status": "fail",
            "error_type": type(error).__name__,
            "error": str(error),
        }

    doctor = (
        _call_component(components, "doctor", lambda: run_doctor(toolchain))
        if toolchain
        else None
    )
    if doctor:
        smoke_ids = {
            item["id"] for item in doctor.get("smokes", []) if item.get("status") == "pass"
        }
        compact_pass = smoke_ids == {
            "native-bsim3",
            "native-bsim4",
            "psp103-osdi",
            "bsimcmg-osdi",
        }
        gate_results["runtime.compact_models"] = _gate(
            "pass" if compact_pass else "fail",
            _report_reference(doctor),
            "native BSIM3/BSIM4 plus PSP103 and BSIM-CMG OSDI smokes",
        )
    gate_results["runtime.reference_environment"] = _gate(
        "pass" if attestation and doctor else "fail",
        [*attestation_evidence, *_report_reference(doctor)],
        "attested WSL2/RHEL-compatible EL9 x86_64 and ngspice 47 runtime",
    )

    all_families = (
        _call_component(
            components,
            "all_families",
            lambda: validate_all_characterizations(destination / "all-families", toolchain),
        )
        if toolchain
        else None
    )
    all_family_pass = _validated(all_families)
    gate_results["characterization.v2"] = _gate(
        "pass" if all_family_pass else "fail",
        _report_reference(all_families),
        "fresh terminal characterization for all 13 families and 26 devices",
    )

    comparison_calls: tuple[tuple[str, Callable[[], dict[str, Any]]], ...] = (
        (
            "comparison_anchors",
            lambda: compare_anchors(destination / "comparisons/anchors", toolchain),
        ),
        (
            "comparison_apm045_threshold",
            lambda: compare_set(
                "apm045", "threshold", destination / "comparisons/apm045-threshold", toolchain
            ),
        ),
        (
            "comparison_apm045_gate_stack",
            lambda: compare_set(
                "apm045", "gate_stack", destination / "comparisons/apm045-gate-stack", toolchain
            ),
        ),
        (
            "comparison_apm022_multivt",
            lambda: compare_set(
                "apm022", "threshold", destination / "comparisons/apm022-multivt", toolchain
            ),
        ),
        (
            "comparison_apm016f_multivt",
            lambda: compare_set(
                "apm016f", "threshold", destination / "comparisons/apm016f-multivt", toolchain
            ),
        ),
    )
    comparison_results: dict[str, dict[str, Any] | None] = {}
    if toolchain:
        for name, callback in comparison_calls:
            comparison_results[name] = _call_component(components, name, callback)
    else:
        comparison_results = {name: None for name, _ in comparison_calls}
    comparison_pass = all(_validated(result) for result in comparison_results.values())
    comparison_evidence = [
        path
        for result in comparison_results.values()
        for path in _report_reference(result)
    ]
    gate_results["comparison.v2"] = _gate(
        "pass" if comparison_pass else "fail",
        comparison_evidence,
        "anchors, threshold equal-bias/equal-inversion, and gate-stack native/common-overlap",
    )

    benchmark = (
        _call_component(
            components,
            "benchmark",
            lambda: validate_benchmark(destination / "benchmark", toolchain),
        )
        if toolchain
        else None
    )
    benchmark_pass = _validated(benchmark)
    gate_results["variation.benchmark_v2"] = _gate(
        "pass" if benchmark_pass else "fail",
        _report_reference(benchmark),
        "real-ngspice Global/Local/All, corners, adapter calibration, and replay",
    )
    gate_results["passives.benchmark"] = _gate(
        "pass" if benchmark_pass else "fail",
        _report_reference(benchmark),
        "real-ngspice Rbench/Cbench value, matching, temperature, and noise checks",
    )

    native = (
        _call_component(
            components,
            "apm130_native",
            lambda: validate_apm130_native(destination / "apm130-native", toolchain),
        )
        if toolchain
        else None
    )
    native_pass = _validated(native)
    gate_results["variation.apm130_upstream"] = _gate(
        "pass" if native_pass else "fail",
        _report_reference(native),
        "independent IHP LV/HV corners, process/statistical, and mismatch cohorts",
    )

    static_pass = bool(static and static.get("status") == "pass")
    provenance_pass = bool(
        static and static["audits"]["provenance"].get("status") == "pass"
    )
    apm045_comparisons = _validated(
        comparison_results["comparison_apm045_threshold"]
    ) and _validated(comparison_results["comparison_apm045_gate_stack"])
    apm022_comparison = _validated(comparison_results["comparison_apm022_multivt"])
    apm016f_comparison = _validated(comparison_results["comparison_apm016f_multivt"])
    gate_results["models.apm130_lv_hv"] = _gate(
        "pass" if all_family_pass and native_pass and provenance_pass else "fail",
        [*_report_reference(all_families), *_report_reference(native)],
        "APM130 LV/HV terminal and independent native-variation execution",
    )
    gate_results["models.apm045_families"] = _gate(
        "pass" if all_family_pass and apm045_comparisons and provenance_pass else "fail",
        [
            *_report_reference(all_families),
            *_report_reference(comparison_results["comparison_apm045_threshold"]),
            *_report_reference(comparison_results["comparison_apm045_gate_stack"]),
        ],
        "VTL/VTG/VTH/THKOX execution and required comparison sets",
    )
    gate_results["models.apm022_multivt"] = _gate(
        "pass" if all_family_pass and apm022_comparison and provenance_pass else "fail",
        [
            *_report_reference(all_families),
            *_report_reference(comparison_results["comparison_apm022_multivt"]),
        ],
        "independent threshold-isolated LVT/SVT/HVT execution and ordering",
    )
    gate_results["models.apm016f_multivt"] = _gate(
        "pass" if all_family_pass and apm016f_comparison and provenance_pass else "fail",
        [
            *_report_reference(all_families),
            *_report_reference(comparison_results["comparison_apm016f_multivt"]),
        ],
        "BSIM-CMG workfunction-dominant LVT/SVT/HVT execution, ordering, and NFIN",
    )

    required_component_names = (
        "clean_clone",
        "static",
        "doctor",
        "all_families",
        "comparison_anchors",
        "comparison_apm045_threshold",
        "comparison_apm045_gate_stack",
        "comparison_apm022_multivt",
        "comparison_apm016f_multivt",
        "benchmark",
        "apm130_native",
    )
    clean_clone_pass = all(
        components.get(name, {}).get("status") == "pass" for name in required_component_names
    )
    clean_clone_evidence = [
        str(components[name]["report_path"])
        for name in required_component_names
        if components.get(name, {}).get("report_path")
    ]
    gate_results["release.clean_clone"] = _gate(
        "pass" if clean_clone_pass and static_pass else "fail",
        clean_clone_evidence,
        "exact-commit clone completed every automatic v2 release component",
    )

    ordered_gates, overall = evaluate_required_gates(contract, gate_results)
    report: dict[str, Any] = {
        "schema": "apm.release-validation.v2",
        "created_utc": created,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if overall else "fail",
        "target": contract["target"],
        "repository": str(selected),
        "repository_head": _git(selected, "rev-parse", "HEAD"),
        "contract_path": str(selected / "validation/release_gates.toml"),
        "contract_sha256": sha256_file(selected / "validation/release_gates.toml"),
        "components": components,
        "gates": ordered_gates,
        "required_gate_count": sum(1 for gate in ordered_gates if gate["required"]),
        "passed_required_gate_count": sum(
            1 for gate in ordered_gates if gate["required"] and gate["passed"]
        ),
    }
    report_path = destination / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["output_directory"] = str(destination)
    report["report_path"] = str(report_path)
    if not overall:
        failed = [gate["id"] for gate in ordered_gates if gate["required"] and not gate["passed"]]
        raise ReleaseValidationError(
            f"release validation failed ({', '.join(failed)}); see {report_path}"
        )
    return report
