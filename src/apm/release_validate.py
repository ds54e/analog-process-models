# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed repository and v1.0 release-gate validation."""

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

try:  # pragma: no cover - Python 3.11+ takes this branch
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the EL9 Python 3.9 path
    import tomli as tomllib

from .benchmark_validate import validate_benchmark
from .clean_clone import verify_clean_clone_attestation
from .compare import validate_all_characterizations
from .doctor import run_doctor
from .model_build import MODEL_SOURCES, sha256_file
from .native_variation import validate_apm130_native
from .paths import repository_root, state_directory
from .spectre_validate import validate_spectre
from .toolchain import resolve_toolchain

REQUIRED_KITS = ("apm350", "apm130", "apm045", "apm022", "apm016f")
IMPLEMENTED_GATE_IDS = frozenset(
    {
        "runtime.wsl2_el9",
        "runtime.ngspice_headless",
        "runtime.psp103_osdi",
        "runtime.bsimcmg_osdi",
        "models.all_kits",
        "characterization.all_kits",
        "passives.benchmark",
        "variation.benchmark",
        "variation.apm130_native",
        "finfet.integrity",
        "spectre.model_only",
        "licensing.provenance",
        "distribution.self_contained_models",
        "release.metadata_complete",
        "release.clean_clone",
        "release.claim_audit",
    }
)

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
INCLUDE_RE = re.compile(
    r"^\s*(?:\.include|include|`include)\s+[\"']?([^\"'\s]+)", re.IGNORECASE | re.MULTILINE
)
BUILTIN_VERILOGA_INCLUDES = {"discipline.h", "disciplines.vams", "constants.vams"}
EXPECTED_KIT_LICENSES = {
    "apm350": {"Apache-2.0"},
    "apm130": {"Apache-2.0", "LicenseRef-Si2-PSP-103.8.2"},
    "apm045": {"Apache-2.0"},
    "apm022": {"Apache-2.0"},
    "apm016f": {"Apache-2.0", "ECL-2.0"},
}
REQUIRED_REVIEWED_FILES = frozenset(
    {
        "README.md",
        "CHANGELOG.md",
        "STATUS.md",
        "THIRD_PARTY.md",
        "docs/spectre.md",
        "docs/release-validation.md",
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
    "private_key": re.compile(r"-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}


class ReleaseValidationError(RuntimeError):
    """A repository or release requirement did not pass."""


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


def load_gate_contract(root: Path) -> dict[str, Any]:
    contract_path = root / "validation/release_gates.toml"
    contract = _load_toml(contract_path)
    if contract.get("schema") != "apm.release-gates.v1":
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
    missing_implementations = required - IMPLEMENTED_GATE_IDS
    stale_implementations = IMPLEMENTED_GATE_IDS - required
    if missing_implementations or stale_implementations:
        raise ReleaseValidationError(
            "release validator/contract mismatch; missing implementations="
            f"{sorted(missing_implementations)}, stale implementations={sorted(stale_implementations)}"
        )
    return contract


def _check_map(checks: dict[str, bool], *, context: str) -> dict[str, Any]:
    failed = sorted(name for name, passed in checks.items() if passed is not True)
    return {
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "context": context,
    }


def audit_release_metadata(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    metadata = contract["release_metadata"]
    target = str(metadata["target_version"])
    project = _load_toml(root / "pyproject.toml")
    package_version = str(project.get("project", {}).get("version", ""))
    init_text = (root / "src/apm/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_text, re.MULTILINE)
    runtime_version = match.group(1) if match else ""
    try:
        installed_version = importlib_metadata.version("analog-process-models")
    except importlib_metadata.PackageNotFoundError:
        installed_version = "missing"
    changelog = (root / metadata["release_notes_path"]).read_text(encoding="utf-8")
    placeholder_hits: list[dict[str, str]] = []
    tokens = [str(token) for token in metadata["forbidden_release_placeholder_tokens"]]
    for pattern in metadata["placeholder_scan_paths"]:
        for path in sorted(root.glob(pattern)):
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in tokens:
                if re.search(re.escape(token), text, re.IGNORECASE):
                    placeholder_hits.append({"path": str(path.relative_to(root)), "token": token})
    checks = {
        "pyproject_version_matches_target": package_version == target,
        "runtime_version_matches_target": runtime_version == target,
        "installed_distribution_version_matches_target": installed_version == target,
        "version_metadata_agree": package_version == runtime_version,
        "contract_target_matches_version": contract.get("target") == f"v{target}",
        "python_meets_minimum": sys.version_info
        >= tuple(int(item) for item in str(contract["runtime"]["python_minimum"]).split(".")),
        "changelog_has_dated_release_heading": bool(
            re.search(
                rf"^## \[{re.escape(target)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.MULTILINE
            )
        ),
        "changelog_not_development_placeholder": "Initial v1.0 implementation is in progress"
        not in changelog,
        "changelog_has_no_unreleased_section": not bool(
            re.search(r"^## (?:\[)?Unreleased(?:\])?$", changelog, re.MULTILINE)
        ),
        "no_release_placeholder_tokens": not placeholder_hits,
    }
    result = _check_map(checks, context="release metadata and release-critical placeholder audit")
    result.update(
        {
            "target_version": target,
            "package_version": package_version,
            "runtime_version": runtime_version,
            "installed_distribution_version": installed_version,
            "placeholder_hits": placeholder_hits,
        }
    )
    return result


def _declared_file_tables(source: dict[str, Any]) -> dict[str, dict[str, str]]:
    names = ("imported_files", "authored_files", "apm_authored_files", "transformed_files")
    return {name: source.get(name, {}) for name in names if isinstance(source.get(name), dict)}


def audit_provenance(root: Path) -> dict[str, Any]:
    kit_results: dict[str, Any] = {}
    global_checks: dict[str, bool] = {}
    for kit in REQUIRED_KITS:
        kit_root = root / "models" / kit
        provenance_path = kit_root / "provenance.toml"
        provenance = _load_toml(provenance_path)
        source = provenance.get("source", {})
        declared_tables = _declared_file_tables(source)
        declared_paths: dict[str, str] = {}
        bad_hashes: list[dict[str, str]] = []
        duplicates: list[str] = []
        for category, entries in declared_tables.items():
            for relative, expected_hash in entries.items():
                if relative in declared_paths:
                    duplicates.append(relative)
                declared_paths[relative] = category
                path = kit_root / relative
                actual_hash = sha256_file(path) if path.is_file() else "missing"
                if not isinstance(expected_hash, str) or not HASH_RE.fullmatch(expected_hash):
                    bad_hashes.append(
                        {"path": relative, "expected": str(expected_hash), "actual": actual_hash}
                    )
                elif actual_hash != expected_hash:
                    bad_hashes.append(
                        {"path": relative, "expected": expected_hash, "actual": actual_hash}
                    )
        vendor_files = (
            {
                str(path.relative_to(kit_root))
                for path in (kit_root / "vendor").rglob("*")
                if path.is_file()
            }
            if (kit_root / "vendor").is_dir()
            else set()
        )
        imported_files = set(declared_tables.get("imported_files", {}))
        source_license_fields = [
            key
            for key, value in source.items()
            if (key == "license" or key.endswith("_license")) and isinstance(value, str) and value
        ]
        source_licenses = {str(source[key]) for key in source_license_fields}
        redistribution = provenance.get("redistribution", {})
        spectre = provenance.get("spectre", {})
        kit_checks = {
            "provenance_identity": provenance.get("id") == kit,
            "source_status_complete": isinstance(source.get("status"), str)
            and bool(source.get("status")),
            "all_declared_hashes_match": not bad_hashes,
            "declared_paths_unique": not duplicates,
            "vendor_files_exactly_imported": vendor_files == imported_files,
            "third_party_license_identified": not vendor_files or bool(source_license_fields),
            "kit_license_set_exact": source_licenses == EXPECTED_KIT_LICENSES[kit],
            "declared_license_texts_shipped": all(
                (root / "LICENSES" / f"{identifier}.txt").is_file()
                for identifier in source_licenses
            ),
            "redistribution_explicit": isinstance(redistribution, dict)
            and redistribution.get("ship_in_repo") is True,
            "upstream_notices_preserved": not vendor_files
            or redistribution.get("upstream_notices_preserved") is True,
            "spectre_claim_boundary": spectre.get("status") == "experimental_unverified"
            and spectre.get("real_tool_validation") is False,
        }
        if spectre.get("generator"):
            generator_path = root / str(spectre["generator"])
            kit_checks["spectre_generator_hash"] = generator_path.is_file() and sha256_file(
                generator_path
            ) == spectre.get("generator_sha256")
        if kit == "apm022":
            kit_checks.update(
                {
                    "apm022_not_ptm_derived": provenance.get("ptm_derived") is False,
                    "apm022_no_third_party_model_assets": not vendor_files,
                    "apm022_generation_record": (
                        root
                        / str(
                            provenance.get("development", {}).get(
                                "generation_record", "models/apm022/parameter_generation.md"
                            )
                        )
                    ).is_file(),
                }
            )
        if kit == "apm016f":
            kit_checks.update(
                {
                    "apm016f_not_ptm_mg_derived": provenance.get("ptm_mg_derived") is False,
                    "apm016f_parameter_deck_declared_authored": "ngspice/apm016f_models.inc"
                    in declared_tables.get("authored_files", {}),
                    "bsim_cmg_license_and_notice_shipped": {
                        "vendor/bsim-cmg-112.1.0/LICENSE.txt",
                        "vendor/bsim-cmg-112.1.0/NOTICE.txt",
                    }.issubset(vendor_files),
                }
            )
        kit_result = _check_map(kit_checks, context=f"{kit} exact-file provenance")
        kit_result.update(
            {
                "provenance_path": str(provenance_path.relative_to(root)),
                "provenance_sha256": sha256_file(provenance_path),
                "declared_file_count": len(declared_paths),
                "vendor_file_count": len(vendor_files),
                "bad_hashes": bad_hashes,
                "duplicate_paths": duplicates,
                "uncovered_vendor_files": sorted(vendor_files - imported_files),
                "stale_imported_entries": sorted(imported_files - vendor_files),
                "source_license_fields": source_license_fields,
                "source_licenses": sorted(source_licenses),
            }
        )
        kit_results[kit] = kit_result
        global_checks[f"{kit}_provenance"] = kit_result["status"] == "pass"
    result = _check_map(global_checks, context="all-kit licensing and exact-file provenance")
    result["kits"] = kit_results
    return result


def _tracked_files(root: Path) -> list[Path]:
    output = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=False)
    if output.returncode != 0:
        raise ReleaseValidationError("git ls-files failed during distribution audit")
    return [root / os.fsdecode(item) for item in output.stdout.split(b"\0") if item]


def audit_distribution(root: Path) -> dict[str, Any]:
    tracked = _tracked_files(root)
    forbidden_tracked: list[str] = []
    suspicious_names: list[str] = []
    secret_hits: list[dict[str, str]] = []
    oversized_tracked: list[dict[str, Any]] = []
    for path in tracked:
        relative = path.relative_to(root)
        lowered_parts = {part.lower() for part in relative.parts}
        if (
            lowered_parts & TRACKED_FORBIDDEN_PARTS
            or path.suffix.lower() in TRACKED_FORBIDDEN_SUFFIXES
        ):
            forbidden_tracked.append(str(relative))
        lowered_name = path.name.lower()
        if lowered_name in {
            "id_rsa",
            "id_ed25519",
            "credentials.json",
            ".env",
        } or lowered_name.endswith((".pem", ".p12", ".pfx", ".key")):
            suspicious_names.append(str(relative))
        if path.is_file() and path.stat().st_size <= 8 * 1024 * 1024:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    secret_hits.append({"path": str(relative), "pattern": name})
        if path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
            oversized_tracked.append({"path": str(relative), "size_bytes": path.stat().st_size})

    unresolved_includes: list[dict[str, str]] = []
    model_source_suffixes = {".inc", ".lib", ".va", ".scs", ".sp"}
    for path in tracked:
        if (
            "models" not in path.relative_to(root).parts
            or path.suffix.lower() not in model_source_suffixes
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for matched in INCLUDE_RE.findall(text):
            include_name = matched.rstrip(";)")
            if include_name.lower() in BUILTIN_VERILOGA_INCLUDES:
                continue
            if re.match(r"^[a-z]+://", include_name, re.IGNORECASE):
                unresolved_includes.append(
                    {"source": str(path.relative_to(root)), "include": include_name}
                )
                continue
            if not (path.parent / include_name).resolve().is_file():
                unresolved_includes.append(
                    {"source": str(path.relative_to(root)), "include": include_name}
                )

    model_sources = {
        model_id: str(relative)
        for model_id, relative in MODEL_SOURCES.items()
        if (root / relative).is_file()
    }
    kit_checks: dict[str, bool] = {}
    for kit in REQUIRED_KITS:
        kit_root = root / "models" / kit
        parsed = _load_toml(kit_root / "kit.toml")
        public = parsed.get("public_devices", {})
        expected_parameters = ["l", "nfin"] if kit == "apm016f" else ["w", "l"]
        kit_checks[f"{kit}_public_contract"] = (
            parsed.get("schema") == "apm.kit.v1"
            and parsed.get("id") == kit
            and public.get("terminals") == ["d", "g", "s", "b"]
            and public.get("parameters") == expected_parameters
            and all((kit_root / area).is_dir() for area in ("ngspice", "spectre"))
        )
    checks = {
        "all_compiler_model_sources_shipped": set(model_sources) == set(MODEL_SOURCES),
        "all_kit_public_contracts_shipped": all(kit_checks.values()),
        "no_unresolved_or_remote_model_includes": not unresolved_includes,
        "no_generated_or_scratch_artifacts_tracked": not forbidden_tracked,
        "no_suspicious_secret_filenames_tracked": not suspicious_names,
        "no_credential_signatures_detected": not secret_hits,
        "no_oversized_tracked_artifacts": not oversized_tracked,
        "generated_osdi_not_tracked": not any(path.suffix.lower() == ".osdi" for path in tracked),
    }
    result = _check_map(checks, context="self-contained source distribution and credential audit")
    result.update(
        {
            "tracked_file_count": len(tracked),
            "model_sources": model_sources,
            "kit_checks": kit_checks,
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
    review_hash_mismatches: list[dict[str, str]] = []
    if isinstance(reviewed_files, dict):
        for relative, expected in reviewed_files.items():
            path = root / relative
            actual = sha256_file(path) if path.is_file() else "missing"
            if actual != expected:
                review_hash_mismatches.append(
                    {"path": relative, "expected": str(expected), "actual": actual}
                )
    readme = (root / "README.md").read_text(encoding="utf-8")
    spectre_doc = (root / "docs/spectre.md").read_text(encoding="utf-8")
    public_claim_text = "\n".join(
        (root / relative).read_text(encoding="utf-8", errors="replace")
        for relative in ("README.md", "CHANGELOG.md", "STATUS.md", "docs/spectre.md")
    )
    prohibited_claims = [
        pattern
        for pattern in (
            r"\bSpectre[- ]validated\b",
            r"\bvalidated (?:on|with|using) (?:Cadence )?Spectre\b",
            r"\bfoundry[- ]validated\b",
            r"\bsilicon[- ]validated\b",
            r"\bsilicon[- ]correlated APM\b",
        )
        if re.search(pattern, public_claim_text, re.IGNORECASE)
    ]
    required_topics = set(contract.get("documentation", {}).get("required_topics", []))
    topic_checks = {
        "scope": "## Scope" in readme,
        "installation": "## Installation" in readme,
        "model_provenance": "## Model provenance" in readme,
        "model_fidelity_limitations": "## Model fidelity and limitations" in readme,
        "benchmark_vs_native_variation": "benchmark" in readme.lower()
        and "native" in readme.lower()
        and "docs/native-variation.md" in readme,
        "benchmark_passives": "Rbench" in readme and "Cbench" in readme,
        "comparison_methodology": "## Comparison methodology" in readme,
        "spectre_status": "Experimental / unverified" in readme
        and "experimental_unverified" in spectre_doc,
        "not_a_manufacturable_pdk": "not a manufacturable PDK" in readme,
    }
    checks = {
        "manual_review_record_complete": review.get("schema") == "apm.release-review.v1"
        and review.get("status") == "complete",
        "manual_review_has_required_decisions": review.get("spectre_real_tool_run") is False
        and review.get("foundry_or_silicon_correlation_claimed") is False
        and review.get("repository_visibility_changed") is False
        and review.get("unresolved_claim_findings") == [],
        "manual_review_identity_and_time_present": bool(review.get("reviewer"))
        and bool(
            re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                str(review.get("reviewed_utc", "")),
            )
        ),
        "reviewed_file_hashes_present": isinstance(reviewed_files, dict)
        and set(reviewed_files) == REQUIRED_REVIEWED_FILES,
        "reviewed_file_hashes_current": not review_hash_mismatches,
        "all_required_readme_topics": required_topics == set(topic_checks)
        and all(topic_checks.values()),
        "no_prohibited_public_claims": not prohibited_claims,
        "spectre_boundary_explicit": bool(
            re.search(r"not considered\s+validated", readme, re.IGNORECASE)
        )
        and bool(re.search(r"real[- ]Spectre", spectre_doc, re.IGNORECASE)),
    }
    result = _check_map(checks, context="manual release claim review plus stale-review detection")
    result.update(
        {
            "review_path": str(review_path.relative_to(root)),
            "review_sha256": sha256_file(review_path) if review_path.is_file() else "missing",
            "topic_checks": topic_checks,
            "review_hash_mismatches": review_hash_mismatches,
            "prohibited_claim_patterns": prohibited_claims,
        }
    )
    return result


def _run_logged_command(
    root: Path,
    output: Path,
    command_id: str,
    command: list[str],
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


def run_static_audits(root: Path, output: Path) -> dict[str, Any]:
    contract = load_gate_contract(root)
    output.mkdir(parents=True, exist_ok=False)
    commands = [
        _run_logged_command(root, output, "pytest", [sys.executable, "-m", "pytest", "-q"]),
        _run_logged_command(root, output, "ruff", [sys.executable, "-m", "ruff", "check", "."]),
        _run_logged_command(root, output, "reuse", [sys.executable, "-m", "reuse", "lint"]),
    ]
    audits = {
        "metadata": audit_release_metadata(root, contract),
        "provenance": audit_provenance(root),
        "distribution": audit_distribution(root),
        "claims": audit_claims(root, contract),
    }
    spectre = validate_spectre(output / "spectre")
    checks = {
        "regression_commands": all(command["status"] == "pass" for command in commands),
        "static_audits": all(audit["status"] == "pass" for audit in audits.values()),
        "spectre_structural": spectre["status"] == "structurally_checked"
        and all(spectre["checks"].values()),
    }
    result = {
        "contract": contract,
        "commands": commands,
        "audits": audits,
        "spectre": spectre,
        "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
    }
    report_path = output / "static-audits.json"
    report_path.write_text(
        json.dumps(
            {
                "schema": "apm.static-audits.v1",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "status": result["status"],
                "contract_sha256": sha256_file(root / "validation/release_gates.toml"),
                "commands": commands,
                "audits": audits,
                "spectre": {
                    "status": spectre["status"],
                    "report_path": spectre["report_path"],
                    "checks": spectre["checks"],
                },
                "checks": checks,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    result["report_path"] = str(report_path)
    return result


def _gate(status: str, evidence: list[str], detail: str) -> dict[str, Any]:
    return {"status": status, "evidence": evidence, "detail": detail}


def _report_reference(result: dict[str, Any]) -> list[str]:
    path = result.get("report_path")
    return [str(path)] if path else []


def _call_component(
    components: dict[str, Any],
    name: str,
    callback: Callable[[], dict[str, Any]],
) -> dict[str, Any] | None:
    started = time.monotonic()
    try:
        result = callback()
    except Exception as error:  # noqa: BLE001 - retain every component failure in the report
        components[name] = {
            "status": "fail",
            "error_type": type(error).__name__,
            "error": str(error),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        return None
    component_status = result.get("status")
    components[name] = {
        "status": "pass"
        if component_status in {None, "pass", "validated", "verified", "attested"}
        else "fail",
        "duration_seconds": round(time.monotonic() - started, 3),
        "report_path": result.get("report_path"),
        "report_sha256": sha256_file(Path(result["report_path"]))
        if result.get("report_path") and Path(result["report_path"]).is_file()
        else None,
        "component_status": result.get("status"),
    }
    return result


def evaluate_required_gates(
    contract: dict[str, Any], gate_results: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], bool]:
    """Return ordered gates and fail closed on missing/skipped/non-pass evidence."""

    ordered: list[dict[str, Any]] = []
    overall = True
    for gate_definition in contract["gate"]:
        identifier = gate_definition["id"]
        required = gate_definition.get("required") is True
        result = gate_results.get(identifier)
        if result is None:
            result = _gate("missing", [], "validator produced no result for this gate")
        evidence = result.get("evidence")
        status = result.get("status")
        passed = status == "pass" and isinstance(evidence, list) and bool(evidence)
        if required and not passed:
            overall = False
        ordered.append(
            {
                **gate_definition,
                **result,
                "passed": passed,
            }
        )
    return ordered, overall


def _default_output(root: Path, release: bool) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    mode = "release" if release else "repository"
    return state_directory(root) / "results" / "validation" / f"{mode}-{stamp}"


def validate_repository(output: Path | None = None, *, root: Path | None = None) -> dict[str, Any]:
    selected = (root or repository_root()).resolve()
    destination = (output or _default_output(selected, False)).expanduser().resolve()
    result = run_static_audits(selected, destination)
    report = {
        "schema": "apm.repository-validation.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": result["status"],
        "repository": str(selected),
        "repository_head": _git(selected, "rev-parse", "HEAD"),
        "commands": result["commands"],
        "audits": result["audits"],
        "spectre": {
            "status": result["spectre"]["status"],
            "report_path": result["spectre"]["report_path"],
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
    static_regression_pass = False
    static_command_evidence: list[str] = []

    attestation = _call_component(
        components,
        "clean_clone",
        lambda: {
            **verify_clean_clone_attestation(selected),
            "report_path": str(selected / ".apm/clean-clone-attestation.json"),
        },
    )
    if attestation:
        attestation_evidence = [attestation["report_path"]]
        gate_results["runtime.wsl2_el9"] = _gate(
            "pass",
            attestation_evidence,
            "current WSL2 EL9 x86_64 platform matches exact-commit attestation",
        )
        gate_results["release.clean_clone"] = _gate(
            "not_run",
            attestation_evidence,
            "exact-commit clone attested; full clean-clone sequence is still running",
        )
    else:
        detail = components["clean_clone"]["error"]
        gate_results["runtime.wsl2_el9"] = _gate("fail", ["clean_clone component"], detail)
        gate_results["release.clean_clone"] = _gate("fail", ["clean_clone component"], detail)

    static_output = destination / "static"
    static = _call_component(
        components, "static", lambda: run_static_audits(selected, static_output)
    )
    if static:
        audits = static["audits"]
        command_evidence = [command["stdout_path"] for command in static["commands"]]
        command_by_id = {command["id"]: command for command in static["commands"]}
        static_report_evidence = [str(static["report_path"])]
        static_command_evidence = command_evidence
        gate_results["licensing.provenance"] = _gate(
            "pass"
            if audits["provenance"]["status"] == "pass"
            and command_by_id.get("reuse", {}).get("status") == "pass"
            else "fail",
            [
                *static_report_evidence,
                str(static_output / "reuse.stdout.txt"),
                *[str(selected / "models" / kit / "provenance.toml") for kit in REQUIRED_KITS],
            ],
            "exact-file provenance and REUSE/SPDX audit",
        )
        gate_results["distribution.self_contained_models"] = _gate(
            audits["distribution"]["status"],
            static_report_evidence,
            "vendored model sources, local includes, credentials, binaries, and scratch-data audit",
        )
        gate_results["release.metadata_complete"] = _gate(
            audits["metadata"]["status"],
            [
                *static_report_evidence,
                str(selected / "pyproject.toml"),
                str(selected / "src/apm/__init__.py"),
                str(selected / "CHANGELOG.md"),
            ],
            "version, release notes, and placeholder audit",
        )
        gate_results["release.claim_audit"] = _gate(
            audits["claims"]["status"],
            [
                *static_report_evidence,
                str(selected / "validation/release_review.toml"),
                str(selected / "README.md"),
                str(selected / "docs/spectre.md"),
            ],
            "completed manual claim review with current content hashes",
        )
        spectre = static["spectre"]
        gate_results["spectre.model_only"] = _gate(
            "pass"
            if spectre["status"] == "structurally_checked" and all(spectre["checks"].values())
            else "fail",
            _report_reference(spectre),
            "all-kit Spectre structure; real backend remains experimental/unverified",
        )
        static_regression_pass = all(command["status"] == "pass" for command in static["commands"])
        if not static_regression_pass:
            for identifier in ("models.all_kits", "passives.benchmark", "finfet.integrity"):
                gate_results[identifier] = _gate(
                    "fail", command_evidence, "full regression command failed"
                )
    else:
        detail = components["static"]["error"]
        for identifier in (
            "models.all_kits",
            "passives.benchmark",
            "finfet.integrity",
            "spectre.model_only",
            "licensing.provenance",
            "distribution.self_contained_models",
            "release.metadata_complete",
            "release.claim_audit",
        ):
            gate_results[identifier] = _gate("fail", ["static component"], detail)

    toolchain = None
    try:
        toolchain = resolve_toolchain(selected)
    except Exception as error:  # noqa: BLE001 - convert discovery failure into gate evidence
        components["toolchain"] = {
            "status": "fail",
            "error_type": type(error).__name__,
            "error": str(error),
        }

    doctor = (
        _call_component(components, "doctor", lambda: run_doctor(toolchain)) if toolchain else None
    )
    if doctor:
        evidence = _report_reference(doctor)
        smoke_ids = {
            item["id"] for item in doctor.get("smokes", []) if item.get("status") == "pass"
        }
        gate_results["runtime.ngspice_headless"] = _gate(
            "pass", evidence, "ngspice 47 headless native and OSDI smoke suite"
        )
        gate_results["runtime.psp103_osdi"] = _gate(
            "pass" if "psp103-osdi" in smoke_ids else "fail",
            evidence,
            "PSP103 OSDI compile/load/simulate smoke",
        )
        gate_results["runtime.bsimcmg_osdi"] = _gate(
            "pass" if "bsimcmg-osdi" in smoke_ids else "fail",
            evidence,
            "BSIM-CMG OSDI compile/load/simulate smoke",
        )
    else:
        detail = components.get("doctor", components.get("toolchain", {})).get(
            "error", "doctor unavailable"
        )
        for identifier in (
            "runtime.ngspice_headless",
            "runtime.psp103_osdi",
            "runtime.bsimcmg_osdi",
        ):
            gate_results[identifier] = _gate("fail", ["doctor component"], detail)

    benchmark = (
        _call_component(
            components,
            "benchmark",
            lambda: validate_benchmark(destination / "benchmark", toolchain),
        )
        if toolchain
        else None
    )
    if benchmark:
        status = (
            "pass"
            if benchmark.get("status") == "validated"
            and benchmark.get("checks", {}).get("overall_pass") is True
            else "fail"
        )
        evidence = _report_reference(benchmark)
        gate_results["passives.benchmark"] = _gate(
            status, evidence, "real-ngspice Rbench/Cbench and process/mismatch/all validation"
        )
        gate_results["variation.benchmark"] = _gate(
            status, evidence, "deterministic five-kit benchmark variation validation"
        )
    else:
        detail = components.get("benchmark", components.get("toolchain", {})).get(
            "error", "benchmark unavailable"
        )
        for identifier in ("passives.benchmark", "variation.benchmark"):
            gate_results[identifier] = _gate("fail", ["benchmark component"], detail)

    native = (
        _call_component(
            components,
            "apm130_native",
            lambda: validate_apm130_native(destination / "apm130-native", toolchain),
        )
        if toolchain
        else None
    )
    if native:
        status = (
            "pass"
            if native.get("status") == "validated"
            and native.get("checks", {}).get("overall_pass") is True
            else "fail"
        )
        gate_results["variation.apm130_native"] = _gate(
            status,
            _report_reference(native),
            "IHP-native corners, process, and mismatch real-ngspice validation",
        )
    else:
        detail = components.get("apm130_native", components.get("toolchain", {})).get(
            "error", "native variation unavailable"
        )
        gate_results["variation.apm130_native"] = _gate("fail", ["apm130_native component"], detail)

    all_kits = (
        _call_component(
            components,
            "all_kits",
            lambda: validate_all_characterizations(destination / "all-kits", toolchain),
        )
        if toolchain
        else None
    )
    if all_kits:
        all_kit_tool_pass = (
            all_kits.get("status") == "validated"
            and all_kits.get("checks", {}).get("overall_pass") is True
        )
        status = "pass" if all_kit_tool_pass and static_regression_pass else "fail"
        evidence = [*_report_reference(all_kits), *static_command_evidence]
        gate_results["models.all_kits"] = _gate(
            status, evidence, "all five public kits execute and pass result-contract audits"
        )
        gate_results["characterization.all_kits"] = _gate(
            "pass" if all_kit_tool_pass else "fail",
            evidence,
            "all required metrics and temperatures plus finite-difference/Y-matrix checks",
        )
        gate_results["finfet.integrity"] = _gate(
            status, evidence, "APM016F BSIM-CMG characterization and NFIN integrity checks"
        )
    else:
        detail = components.get("all_kits", components.get("toolchain", {})).get(
            "error", "all-kit characterization unavailable"
        )
        for identifier in ("models.all_kits", "characterization.all_kits", "finfet.integrity"):
            gate_results[identifier] = _gate("fail", ["all_kits component"], detail)

    clean_clone_component_names = (
        "clean_clone",
        "static",
        "doctor",
        "benchmark",
        "apm130_native",
        "all_kits",
    )
    clean_clone_sequence_pass = attestation is not None and all(
        components.get(name, {}).get("status") == "pass" for name in clean_clone_component_names
    )
    gate_results["release.clean_clone"] = _gate(
        "pass" if clean_clone_sequence_pass else "fail",
        [
            str(selected / ".apm/clean-clone-attestation.json"),
            *[
                str(components[name]["report_path"])
                for name in clean_clone_component_names
                if components.get(name, {}).get("report_path")
            ],
        ],
        "exact-commit clean clone completed setup-independent audits, doctor, tests, and all real-tool release validations",
    )

    ordered_gates, overall = evaluate_required_gates(contract, gate_results)
    report: dict[str, Any] = {
        "schema": "apm.release-validation.v1",
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
