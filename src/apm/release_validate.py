# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed current repository and frozen v3.0.0 release validation."""

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
from .noise_catalog import validate_noise_catalog
from .paths import repository_root, state_directory
from .provenance_validate import ProvenanceValidationError, validate_provenance
from .spectre_validate import SpectreStructureError, validate_spectre
from .toolchain import resolve_toolchain

IMPLEMENTED_GATE_IDS = frozenset(
    {
        "runtime.reference_environment",
        "runtime.compact_models",
        "runtime.noise_sparse",
        "catalog.manifest_driven",
        "characterization.v2",
        "comparison.v2",
        "variation.v2",
        "noise.foundation",
        "noise.method",
        "noise.catalog",
        "noise.resume_integrity",
        "models.claims_immutability",
        "spectre.model_only",
        "licensing.provenance",
        "distribution.public_hygiene",
        "release.metadata_complete",
        "release.clean_clone",
        "release.claim_audit",
    }
)
REQUIRED_REVIEWED_FILES = frozenset(
    {
        "AGENTS.md",
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "DEVICE_FAMILY_MODEL.md",
        "ENVIRONMENT.md",
        "GOAL.md",
        "RELEASE_V3.md",
        "RESEARCH_BASELINE.md",
        "PROJECT_CONTEXT.md",
        "SECURITY.md",
        "STATUS.md",
        "THIRD_PARTY.md",
        "UNATTENDED_EXECUTION.md",
        "NOISE_CHARACTERIZATION.md",
        "NOISE_N1.md",
        "NOISE_N2.md",
        "RESULT_CONTRACT.md",
        "docs/benchmark-variation.md",
        "docs/characterization.md",
        "docs/native-variation.md",
        "docs/release-validation.md",
        "docs/spectre.md",
        "validation/evidence/README.md",
        "validation/release_gates.toml",
    }
)
TRACKED_FORBIDDEN_PARTS = {
    ".apm",
    ".cache",
    ".idea",
    ".venv",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "results",
    "runs",
    "scratch",
    "work",
}
TRACKED_FORBIDDEN_SUFFIXES = {
    ".osdi",
    ".raw",
    ".log",
    ".pyc",
    ".pyo",
    ".swp",
    ".tmp",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "generic_bearer": re.compile(r"(?i)\bAuthorization:\s*Bearer\s+[A-Za-z0-9._~-]{20,}"),
    "private_key_assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[=:]\s*[\"'][^\"']{12,}[\"']"
    ),
}
PRIVATE_PATH_PATTERNS = {
    "posix_home": re.compile(r"/(?:home|Users)/([A-Za-z0-9._-]+)/"),
    "windows_profile": re.compile(r"(?i)\b[A-Z]:\\Users\\([^\\\s]+)\\"),
}
HISTORICAL_REPRODUCIBILITY_PATH_RE = re.compile(
    r"^validation/evidence/(?:m\d+[-_.]|v2_)"
)
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
    if contract.get("schema") != "apm.release-gates.v3":
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
    if len(required) != 18 or contract.get("target") != "v3.0.0":
        raise ReleaseValidationError("v3 release contract must contain 18 gates for v3.0.0")
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
    result = _check_map(checks, context="v3 version, release notes, and placeholder audit")
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
        == int(required["required_public_device_count"])
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
    result = _check_map(checks, context="manifest-driven v3 catalog and family contract")
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
    private_path_hits: list[dict[str, str]] = []
    historical_path_observations: list[dict[str, str]] = []
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
            for name, pattern in PRIVATE_PATH_PATTERNS.items():
                if pattern.search(text):
                    finding = {"path": str(relative), "pattern": name}
                    if HISTORICAL_REPRODUCIBILITY_PATH_RE.match(str(relative)):
                        historical_path_observations.append(finding)
                    else:
                        private_path_hits.append(finding)
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
    gitignore = (root / ".gitignore").read_text(encoding="utf-8", errors="replace")
    required_ignore_rules = {
        ".apm/",
        ".venv/",
        "*.osdi",
        "*.raw",
        "*.log",
        "results/",
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
    }
    checks = {
        "tracked_worktree_files_exist": not missing_tracked,
        "compiler_model_sources_shipped": set(shipped_sources) == set(MODEL_SOURCES),
        "no_unresolved_or_remote_model_includes": not unresolved_includes,
        "no_generated_or_scratch_artifacts_tracked": not forbidden_tracked,
        "no_suspicious_secret_filenames_tracked": not suspicious_names,
        "no_credential_signatures_detected": not secret_hits,
        "no_inappropriate_private_paths": not private_path_hits,
        "no_oversized_tracked_artifacts": not oversized_tracked,
        "generated_osdi_not_tracked": not any(path.suffix.lower() == ".osdi" for path in tracked),
        "generated_state_ignore_rules_complete": required_ignore_rules
        <= set(gitignore.splitlines()),
    }
    result = _check_map(
        checks,
        context="tracked distribution, include closure, generated state, and public hygiene",
    )
    result.update(
        {
            "tracked_file_count": len(tracked),
            "shipped_compiler_sources": shipped_sources,
            "missing_tracked": missing_tracked,
            "unresolved_includes": unresolved_includes,
            "forbidden_tracked": forbidden_tracked,
            "suspicious_names": suspicious_names,
            "secret_hits": secret_hits,
            "private_path_hits": private_path_hits,
            "allowed_historical_reproducibility_path_observations": (
                historical_path_observations
            ),
            "oversized_tracked": oversized_tracked,
            "required_ignore_rules": sorted(required_ignore_rules),
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
    reviewed_public_text = [
        (root / relative).read_text(encoding="utf-8", errors="replace")
        for relative in sorted(REQUIRED_REVIEWED_FILES)
        if (root / relative).is_file()
    ]
    public_text = "\n".join(reviewed_public_text)
    prohibited_patterns = [
        pattern
        for pattern in (
            r"(?i)Spectre[- ]validated",
            r"(?i)real Spectre (?:validation|simulation|parsing) (?:passed|complete)",
            r"(?i)APM (?:is|provides) (?:a )?manufacturable PDK",
            r"(?i)APM-authored .* (?:foundry|silicon)[- ]correlated",
            r"(?i)Benchmark Global (?:is|represents) (?:a )?physical process correlation",
            r"(?i)APM-authored .* (?:is|are) silicon[- ]calibrated",
            r"(?i)planar (?:width|per-width) (?:is|equals|equates to) .*FinFET",
            r"(?i)Spectre numerical validation (?:passed|is complete)",
        )
        if re.search(pattern, public_text)
    ]
    required_topics = set(contract["documentation"]["required_topics"])
    topic_checks = {
        "scope": "## Scope" in readme,
        "device_family_domain_model": "Technology → Electrical Family → Device" in readme,
        "reference_environment": "WSL2" in readme and "EL9" in readme and "x86_64" in readme,
        "installation": "## Quick start" in readme and "tools/bootstrap-el9.sh" in readme,
        "electrical_characterization": "## Characterization" in readme
        and "apm.characterization.v2" in readme,
        "stationary_noise": "## Stationary noise characterization" in readme
        and "apm.noise-characterization.v1" in readme,
        "noise_dataset_meaning": "catalog-wide" in readme.lower()
        and "compact-model predictions" in readme,
        "noise_claim_exclusions": "silicon-calibrated process-noise" in readme.lower()
        and "PSS/PNoise" in readme,
        "model_provenance": "## Model provenance" in readme,
        "model_fidelity_limitations": "## Model fidelity and limitations" in readme,
        "benchmark_vs_upstream_variation": "Benchmark versus upstream variation" in readme,
        "comparison_methodology": "## Comparison methodology" in readme,
        "spectre_status": "experimental/unverified" in public_text.lower()
        and "not been parsed" in docs.get("spectre.md", ""),
        "not_a_manufacturable_pdk": "not a manufacturable PDK" in readme,
    }
    checks = {
        "manual_review_record_complete": review.get("schema") == "apm.release-review.v3"
        and review.get("status") == "complete",
        "manual_review_decisions": review.get("release_state") == "released"
        and review.get("v3_tag_object")
        == "afecec29ea6ed0703ef441d4839fd40a238bef0b"
        and review.get("v3_tag_commit")
        == "995e0ce7cdd0c37ef9f3397008637f9d239c746e"
        and review.get("github_release_url")
        == "https://github.com/ds54e/analog-process-models/releases/tag/v3.0.0"
        and review.get("spectre_real_tool_run") is False
        and review.get("foundry_or_silicon_correlation_claimed") is False
        and review.get("benchmark_physical_family_correlation_claimed") is False
        and review.get("process_noise_calibration_claimed") is False
        and review.get("universal_planar_finfet_width_claimed") is False
        and review.get("unsupported_noise_modes_claimed") is False
        and review.get("repository_visibility_changed") is False
        and review.get("repository_visibility") == "private"
        and review.get("publicization_performed") is False
        and review.get("v3_tag_created") is True
        and review.get("github_release_created") is True
        and review.get("public_readiness_cleanup_complete") is True
        and review.get("current_tree_sensitive_data_audit") == "pass"
        and review.get("whole_history_secret_scan") == "pass"
        and review.get("historical_proprietary_model_audit") == "pass"
        and review.get("third_party_redistribution_audit") == "pass"
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
    result = _check_map(checks, context="hash-bound v3 public-claim review")
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
        "schema": "apm.static-audits.v3",
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
        "schema": "apm.repository-validation.v3",
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


def _report_checks_pass(
    report: dict[str, Any], expected_count: int, expected_ids: set[str]
) -> bool:
    checks = report.get("checks")
    observed_ids = [item.get("id") for item in checks] if isinstance(checks, list) else []
    return (
        isinstance(checks, list)
        and len(checks) == expected_count
        and len(observed_ids) == len(set(observed_ids))
        and set(observed_ids) == expected_ids
        and all(item.get("status") == "pass" for item in checks)
    )


def _read_json_report(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseValidationError(f"cannot read validation report {path}: {error}") from error


def _catalog_component(
    root: Path,
    output: Path,
    toolchain: Any,
    *,
    resume: bool,
) -> dict[str, Any]:
    result = validate_noise_catalog(
        output,
        resume=resume,
        root=root,
        toolchain=toolchain,
        progress=lambda message: print(f"[v3 release] {message}", file=sys.stderr, flush=True),
    )
    # The catalog's current report is intentionally replaced on resume. Bind
    # this component to its immutable per-invocation copy instead.
    return {**result, "report_path": result["run_report_path"]}


def _noise_release_observation(
    root: Path,
    fresh: dict[str, Any],
    resumed: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    catalog_root = Path(fresh["output_directory"])
    fresh_path = Path(fresh["run_report_path"])
    resumed_path = Path(resumed["run_report_path"])
    plan_path = catalog_root / "plan.json"
    coverage_path = catalog_root / "coverage.json"
    comparisons_path = catalog_root / "summary/noise_comparisons.json"
    resume_qualification_path = catalog_root / "resume_qualification/report.json"
    n1_path = catalog_root / "regressions/v3_n1_method/report.json"
    n0_path = catalog_root / "regressions/v3_n1_method/v3_n0_regression/report.json"
    synthetic_path = catalog_root / "regressions/v3_n1_method/synthetic_fit_report.json"

    plan = _read_json_report(plan_path)
    coverage = _read_json_report(coverage_path)
    comparisons = _read_json_report(comparisons_path)
    resume_qualification = _read_json_report(resume_qualification_path)
    n1 = _read_json_report(n1_path)
    n0 = _read_json_report(n0_path)
    synthetic = _read_json_report(synthetic_path)
    noise_contract = contract["noise"]
    head = _git(root, "rev-parse", "HEAD")
    expected_unique = int(noise_contract["catalog_unique_request_count"])
    expected_logical = int(noise_contract["catalog_planned_logical_request_count"])
    required_statuses = set(noise_contract["required_terminal_statuses"])
    terminal_counts = fresh.get("terminal_status_counts", {})
    n1_policy = n1.get("acquisition_policy", {})
    method_identity = str(noise_contract["fit_method_identity"])
    acquisition_identity = str(noise_contract["acquisition_policy_identity"])
    observed_acquisition_identity = (
        f"{n1_policy.get('id')}@{n1_policy.get('version')}"
    )
    required_harness_check_ids = set(noise_contract["required_harness_checks"])
    required_n0_check_ids = required_harness_check_ids | {
        "mos.gm_id_resolution",
        "mos.four_engines_execute",
        "mos.drain_psd_finite_nonnegative",
        "mos.gate_referred_and_complex_transfer",
        "mos.source_breakdown",
        "mos.effective_parameter_provenance",
        "mos.log_audit_sparse",
        "models.no_spike_tuning",
    }
    required_n1_check_ids = {
        "n0.regression",
        "fit.synthetic_cases",
        "canonical.four_engine_adaptive_acquisition",
        "canonical.apm045_extended_diagnostic",
        "low_vds.four_engine_results",
        "low_vds.bsim_cmg_tnoimod1_correlation",
        "fit.fail_closed_metrics",
        "provenance.parameter_level_and_raw_sources",
        "solver.sparse_no_klu",
        "models.v2_card_immutability",
    }
    required_n2_check_ids = {
        "catalog.manifest_5_13_26",
        "plan.stable_identity_and_deduplication",
        "dataset.temperature_complete_status",
        "dataset.inversion_complete_status",
        "dataset.length_manifest_coverage",
        "dataset.nfin_manifest_coverage",
        "results.explicit_terminal_status",
        "results.no_simulation_failures",
        "results.raw_provenance_and_sources",
        "solver.sparse_no_klu",
        "comparison.threshold_views",
        "comparison.cross_process_polarity_and_basis",
        "resume.strict_reuse_and_stale_rejection",
        "regression.v3_n0",
        "regression.v3_n1",
        "models.v2_card_immutability",
    }
    required_resume_check_ids = {
        "exact_completed_result_is_reusable",
        "request_hash_mismatch_is_rejected",
        "artifact_tamper_is_rejected",
        "incomplete_result_is_rejected",
    }
    required_synthetic_case_ids = {
        "pure_white",
        "pure_flicker",
        "known_flicker_white_corner",
        "interior_white_plateau_before_high_frequency_rise",
        "truncated_no_white_plateau",
        "no_flicker_component",
        "insufficient_candidate_span",
        "zero_non_finite_and_malformed_fail_closed",
    }
    required_engine_selectors = set(noise_contract["required_engine_selectors"])
    n0_mos_selectors = {
        item.get("selector")
        for item in n0.get("mos_results", [])
        if item.get("status") == "pass"
    }
    canonical_selectors = {
        item.get("selector")
        for item in n1.get("canonical_results", [])
        if item.get("status") == "pass"
    }
    low_vds_selectors = {
        item.get("selector")
        for item in n1.get("low_vds_results", [])
        if item.get("status") == "pass"
    }
    synthetic_case_ids = {
        item.get("id")
        for item in synthetic.get("cases", [])
        if item.get("status") == "pass"
    }
    expected_logical_counts = {
        str(key): int(value)
        for key, value in noise_contract["catalog_logical_request_counts"].items()
    }
    logical_status_counts = coverage.get("logical_status_counts", {})
    temperature_coverage = coverage.get("temperature_coverage_c", {})
    inversion_coverage = coverage.get("inversion_coverage_per_v", {})
    expected_temperature_keys = {
        str(int(value)) for value in noise_contract["temperature_values_c"]
    }
    expected_inversion_keys = {
        f"{float(value):.1f}" for value in noise_contract["inversion_targets_per_v"]
    }
    n0_check_ids = {item.get("id") for item in n0.get("checks", [])}
    fresh_check_by_id = {
        item.get("id"): item.get("status") for item in fresh.get("checks", [])
    }
    n1_check_by_id = {
        item.get("id"): item.get("status") for item in n1.get("checks", [])
    }

    checks = {
        "foundation": (
            n0.get("schema") == "apm.noise-spike-validation.v1"
            and n0.get("status") == "pass"
            and n0.get("repository_commit") == head
            and n0.get("acceptance_result") == "13/13"
            and _report_checks_pass(n0, 13, required_n0_check_ids)
            and n0_check_ids == required_n0_check_ids
            and n0_mos_selectors == required_engine_selectors
            and n0.get("harness_report", {}).get("status") == "pass"
            and n0.get("correlation", {}).get("status") == "pass"
        ),
        "method": (
            n1.get("schema") == "apm.noise-method-validation.v1"
            and n1.get("status") == "pass"
            and n1.get("repository_commit") == head
            and n1.get("acceptance_result") == "10/10"
            and _report_checks_pass(n1, 10, required_n1_check_ids)
            and n1.get("fit_method", {}).get("identity") == method_identity
            and observed_acquisition_identity == acquisition_identity
            and n1_policy.get("stop_sequence_hz")
            == list(noise_contract["bounded_stop_sequence_hz"])
            and n1_policy.get("points_per_decade")
            == int(noise_contract["points_per_decade"])
            and synthetic.get("status") == "pass"
            and synthetic.get("acceptance_result")
            == f"{int(noise_contract['required_synthetic_fit_case_count'])}/"
            f"{int(noise_contract['required_synthetic_fit_case_count'])}"
            and len(synthetic.get("cases", []))
            == int(noise_contract["required_synthetic_fit_case_count"])
            and synthetic_case_ids == required_synthetic_case_ids
            and canonical_selectors == required_engine_selectors
            and low_vds_selectors == required_engine_selectors
            and n1.get("bsim_cmg_tnoimod1_low_vds", {}).get("status") == "pass"
            and n1.get("bsim_cmg_tnoimod1_low_vds", {}).get(
                "production_card_modified"
            )
            is False
        ),
        "catalog": (
            fresh.get("schema") == "apm.noise-catalog-validation.v1"
            and fresh.get("status") == "pass"
            and fresh.get("repository_commit") == head
            and fresh.get("repository_worktree_status") == []
            and fresh.get("acceptance_result") == "16/16"
            and _report_checks_pass(fresh, 16, required_n2_check_ids)
            and plan.get("schema") == "apm.noise-catalog-plan.v1"
            and plan.get("planned_logical_request_count") == expected_logical
            and plan.get("unique_request_count") == expected_unique
            and plan.get("catalog", {}).get("technology_count") == 5
            and plan.get("catalog", {}).get("family_count") == 13
            and plan.get("catalog", {}).get("public_device_count") == 26
            and plan.get("frozen_methods", {}).get("fit_method") == method_identity
            and plan.get("frozen_methods", {}).get("acquisition_policy")
            == acquisition_identity
            and plan.get("frozen_methods", {}).get("required_solver") == "Sparse"
            and plan.get("reference_tools", {}).get(
                "klu_permitted_for_required_noise"
            )
            is False
            and plan.get("logical_request_counts") == expected_logical_counts
            and fresh.get("plan", {}).get("sha256") == sha256_file(plan_path)
            and fresh.get("coverage", {}).get("sha256") == sha256_file(coverage_path)
            and fresh.get("comparisons", {}).get("sha256")
            == sha256_file(comparisons_path)
            and coverage.get("schema") == "apm.noise-catalog-coverage.v1"
            and coverage.get("plan_hash") == plan.get("plan_hash")
            and coverage.get("planned_logical_request_count") == expected_logical
            and coverage.get("unique_request_count") == expected_unique
            and coverage.get("catalog", {}).get("technology_count") == 5
            and coverage.get("catalog", {}).get("family_count") == 13
            and coverage.get("catalog", {}).get("public_device_count") == 26
            and len(coverage.get("catalog", {}).get("selectors", [])) == 26
            and set(logical_status_counts) == set(expected_logical_counts)
            and all(
                sum(int(count) for count in logical_status_counts[dataset].values())
                == expected_count
                and int(logical_status_counts[dataset].get("simulation_failed", 0)) == 0
                for dataset, expected_count in expected_logical_counts.items()
            )
            and set(temperature_coverage) == expected_temperature_keys
            and all(
                sum(int(count) for count in states.values()) == 26
                for states in temperature_coverage.values()
            )
            and set(inversion_coverage) == expected_inversion_keys
            and all(
                sum(int(count) for count in states.values()) == 26
                for states in inversion_coverage.values()
            )
            and coverage.get("length_request_count")
            == expected_logical_counts["length_scaling"]
            and coverage.get("length_selector_count") == 26
            and coverage.get("nfin_request_count")
            == expected_logical_counts["nfin_scaling"]
            and coverage.get("nfin_selector_count") == 6
            and coverage.get("nfin_values") == list(noise_contract["nfin_values"])
            and comparisons.get("schema") == noise_contract["comparison_schema"]
            and comparisons.get("plan_hash") == plan.get("plan_hash")
            and len(comparisons.get("threshold_groups", [])) == 12
            and len(comparisons.get("cross_process_anchor_groups", [])) == 2
            and comparisons.get("reference_frequencies_hz")
            == [1.0, 1.0e3, 1.0e6, 1.0e7]
            and comparisons.get("gate_referred_integration_band_hz")
            == [1.0, 1.0e7]
            and comparisons.get("universal_noise_ordering_imposed") is False
            and comparisons.get("cross_basis_ratios_produced") is False
            and fresh.get("execution", {}).get("mode") == "fresh"
            and fresh.get("execution", {}).get("fresh_execution_count")
            == expected_unique
            and fresh.get("execution", {}).get("safely_reused_count") == 0
            and fresh.get("execution", {}).get("stale_result_rejection_count") == 0
            and sum(int(value) for value in terminal_counts.values())
            == expected_unique
            and set(terminal_counts) == required_statuses
            and int(terminal_counts.get("simulation_failed", 0)) == 0
            and fresh.get("coverage", {}).get(
                "all_required_noise_jobs_sparse_no_klu"
            )
            is True
            and fresh.get("comparisons", {}).get("threshold_group_count") == 12
            and fresh.get("comparisons", {}).get(
                "cross_process_anchor_group_count"
            )
            == 2
            and fresh.get("comparisons", {}).get("cross_basis_ratios_produced")
            is False
            and fresh_check_by_id.get("results.raw_provenance_and_sources")
            == "pass"
            and fresh_check_by_id.get("results.explicit_terminal_status") == "pass"
            and fresh_check_by_id.get("comparison.threshold_views") == "pass"
            and fresh_check_by_id.get(
                "comparison.cross_process_polarity_and_basis"
            )
            == "pass"
        ),
        "resume_integrity": (
            resumed.get("schema") == "apm.noise-catalog-validation.v1"
            and resumed.get("status") == "pass"
            and resumed.get("repository_commit") == head
            and resumed.get("acceptance_result") == "16/16"
            and _report_checks_pass(resumed, 16, required_n2_check_ids)
            and resumed.get("execution", {}).get("mode") == "resume"
            and resumed.get("execution", {}).get("fresh_execution_count") == 0
            and resumed.get("execution", {}).get("safely_reused_count")
            == expected_unique
            and resumed.get("execution", {}).get("stale_result_rejection_count")
            == 0
            and resumed.get("resume_qualification", {}).get("status") == "pass"
            and resumed.get("resume_qualification", {}).get("acceptance_result")
            == "4/4"
            and resumed.get("resume_qualification", {}).get("sha256")
            == sha256_file(resume_qualification_path)
            and resume_qualification.get("status") == "pass"
            and resume_qualification.get("acceptance_result") == "4/4"
            and {
                item.get("id")
                for item in resume_qualification.get("checks", [])
                if item.get("status") == "pass"
            }
            == required_resume_check_ids
            and resumed.get("regressions", {}).get("execution_disposition")
            == "safely_reused"
        ),
        "sparse_no_klu": (
            n0_check_ids >= {"mos.log_audit_sparse"}
            and next(
                item.get("status")
                for item in n0.get("checks", [])
                if item.get("id") == "mos.log_audit_sparse"
            )
            == "pass"
            and n1_check_by_id.get("solver.sparse_no_klu") == "pass"
            and fresh_check_by_id.get("solver.sparse_no_klu") == "pass"
            and fresh.get("coverage", {}).get(
                "all_required_noise_jobs_sparse_no_klu"
            )
            is True
        ),
        "model_immutability": (
            fresh.get("model_immutability", {}).get("status") == "pass"
            and fresh.get("model_immutability", {}).get("v2_tag_commit")
            == contract["model_immutability"]["baseline_commit"]
            and fresh.get("model_immutability", {}).get(
                "noise_coefficients_tuned_by_n2"
            )
            is False
            and {
                item.get("path")
                for item in fresh.get("model_immutability", {}).get("cards", [])
                if item.get("unchanged") is True
            }
            == set(contract["model_immutability"]["required_unchanged_cards"])
        ),
    }
    evidence = {
        "foundation": [str(n0_path)],
        "method": [str(n1_path), str(synthetic_path)],
        "catalog": [
            str(fresh_path),
            str(plan_path),
            str(coverage_path),
            str(comparisons_path),
        ],
        "resume_integrity": [str(resumed_path), str(resume_qualification_path)],
        "sparse_no_klu": [str(n0_path), str(n1_path), str(fresh_path)],
        "model_immutability": [str(fresh_path)],
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "evidence": evidence,
        "reports": {
            "fresh_catalog": str(fresh_path),
            "resume_catalog": str(resumed_path),
            "plan": str(plan_path),
            "coverage": str(coverage_path),
            "comparisons": str(comparisons_path),
            "resume_qualification": str(resume_qualification_path),
            "v3_n1": str(n1_path),
            "v3_n0": str(n0_path),
            "synthetic": str(synthetic_path),
        },
    }


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
        "clean_clone_initial",
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
        migration_pass = audits["migration"]["status"] == "pass"
        provenance_pass = audits["provenance"].get("status") == "pass"
        distribution_pass = audits["distribution"]["status"] == "pass"
        gate_results["catalog.manifest_driven"] = _gate(
            "pass" if pytest_pass and catalog_pass and migration_pass else "fail",
            static_evidence,
            "manifest-driven 5/13/26 catalog, native geometry, and no v1 SSOT",
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
            "exact-file provenance, redistribution boundaries, notices, and REUSE",
        )
        gate_results["distribution.public_hygiene"] = _gate(
            "pass"
            if provenance_pass and distribution_pass and attestation is not None
            else "fail",
            [*static_evidence, *attestation_evidence],
            "self-contained distribution, generated-state exclusions, secrets/private-path audit",
        )
        gate_results["release.metadata_complete"] = _gate(
            audits["metadata"]["status"],
            static_evidence,
            "3.0.0 package/runtime/CLI/changelog metadata and placeholders",
        )
        gate_results["release.claim_audit"] = _gate(
            audits["claims"]["status"],
            static_evidence,
            "hash-bound v3 public claim and exclusion review",
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
        path for result in comparison_results.values() for path in _report_reference(result)
    ]
    gate_results["comparison.v2"] = _gate(
        "pass" if comparison_pass else "fail",
        comparison_evidence,
        "anchors, threshold equal-bias/equal-inversion, and gate-stack views",
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
    native = (
        _call_component(
            components,
            "apm130_native",
            lambda: validate_apm130_native(destination / "apm130-native", toolchain),
        )
        if toolchain
        else None
    )
    benchmark_pass = _validated(benchmark)
    native_pass = _validated(native)
    gate_results["variation.v2"] = _gate(
        "pass" if benchmark_pass and native_pass else "fail",
        [*_report_reference(benchmark), *_report_reference(native)],
        "Benchmark Global/Local/All, passives, and independent APM130 native variation",
    )

    noise_fresh = (
        _call_component(
            components,
            "noise_catalog_fresh",
            lambda: _catalog_component(
                selected,
                destination / "noise-catalog",
                toolchain,
                resume=False,
            ),
        )
        if toolchain
        else None
    )
    noise_resumed = (
        _call_component(
            components,
            "noise_catalog_resume",
            lambda: _catalog_component(
                selected,
                destination / "noise-catalog",
                toolchain,
                resume=True,
            ),
        )
        if toolchain and noise_fresh
        else None
    )
    noise_observation = None
    if noise_fresh and noise_resumed:
        try:
            noise_observation = _noise_release_observation(
                selected, noise_fresh, noise_resumed, contract
            )
            components["noise_contract"] = {
                "status": noise_observation["status"],
                "checks": noise_observation["checks"],
                "reports": noise_observation["reports"],
            }
        except Exception as error:  # noqa: BLE001 - preserve failure as release evidence
            components["noise_contract"] = {
                "status": "fail",
                "error_type": type(error).__name__,
                "error": str(error),
            }

    if noise_observation:
        observation_checks = noise_observation["checks"]
        observation_evidence = noise_observation["evidence"]
        gate_results["noise.foundation"] = _gate(
            "pass" if observation_checks["foundation"] else "fail",
            observation_evidence["foundation"],
            "V3-N0 analytic harness and four-engine external-noise qualification",
        )
        gate_results["noise.method"] = _gate(
            "pass" if observation_checks["method"] else "fail",
            observation_evidence["method"],
            "frozen N1 acquisition/fit method, synthetic cases, and low-VDS diagnostics",
        )
        gate_results["noise.catalog"] = _gate(
            "pass" if observation_checks["catalog"] else "fail",
            observation_evidence["catalog"],
            "fresh deterministic V3-N2 catalog with complete explicit states and comparisons",
        )
        gate_results["noise.resume_integrity"] = _gate(
            "pass" if observation_checks["resume_integrity"] else "fail",
            observation_evidence["resume_integrity"],
            "exact all-reuse run plus mismatch/tamper/incomplete/stale rejection",
        )
        gate_results["runtime.noise_sparse"] = _gate(
            "pass" if observation_checks["sparse_no_klu"] else "fail",
            observation_evidence["sparse_no_klu"],
            "N0/N1/N2 required noise jobs use normal Sparse and no KLU",
        )
        claims_pass = bool(
            static
            and static["audits"]["claims"]["status"] == "pass"
            and static["audits"]["provenance"].get("status") == "pass"
        )
        gate_results["models.claims_immutability"] = _gate(
            "pass"
            if observation_checks["model_immutability"] and claims_pass
            else "fail",
            [
                *observation_evidence["model_immutability"],
                *static_evidence,
            ],
            "v2 model-card byte identity plus parameter/default and public-claim boundaries",
        )

    final_attestation = _call_component(
        components,
        "clean_clone_final",
        lambda: {
            **verify_clean_clone_attestation(selected),
            "report_path": str(selected / ".apm/clean-clone-attestation.json"),
        },
    )
    gate_results["runtime.reference_environment"] = _gate(
        "pass" if attestation and final_attestation and doctor else "fail",
        [
            *attestation_evidence,
            *_report_reference(doctor),
            *_report_reference(final_attestation),
        ],
        "exact candidate on attested WSL2/RHEL-compatible EL9 x86_64 with ngspice 47",
    )

    required_component_names = (
        "clean_clone_initial",
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
        "noise_catalog_fresh",
        "noise_catalog_resume",
        "noise_contract",
        "clean_clone_final",
    )
    component_pass = all(
        components.get(name, {}).get("status") == "pass"
        for name in required_component_names
    )
    clean_clone_evidence = [
        str(components[name]["report_path"])
        for name in required_component_names
        if components.get(name, {}).get("report_path")
    ]
    if noise_observation:
        clean_clone_evidence.extend(
            path
            for paths in noise_observation["evidence"].values()
            for path in paths
            if path not in clean_clone_evidence
        )
    gate_results["release.clean_clone"] = _gate(
        "pass"
        if component_pass
        and static is not None
        and static.get("status") == "pass"
        else "fail",
        clean_clone_evidence,
        "exact candidate clone completed every automatic v3 release component",
    )

    ordered_gates, overall = evaluate_required_gates(contract, gate_results)
    report: dict[str, Any] = {
        "schema": "apm.release-validation.v3",
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
        "v3_tag_present": subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", "refs/tags/v3.0.0"],
            cwd=selected,
            check=False,
        ).returncode
        == 0,
    }
    report_path = destination / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report["output_directory"] = str(destination)
    report["report_path"] = str(report_path)
    if not overall:
        failed = [
            gate["id"]
            for gate in ordered_gates
            if gate["required"] and not gate["passed"]
        ]
        raise ReleaseValidationError(
            f"release validation failed ({', '.join(failed)}); see {report_path}"
        )
    return report
