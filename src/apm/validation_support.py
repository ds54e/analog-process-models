# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Promoted current distribution checks; origin and equivalence in releases/helper-migration.json."""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .lifecycle import ValidationError as ReleaseValidationError
from .model_build import MODEL_SOURCES, sha256_file

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



def _check_map(checks: dict[str, bool], *, context: str) -> dict[str, Any]:
    failed = sorted(name for name, passed in checks.items() if passed is not True)
    return {
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "context": context,
    }



def audit_migration(root: Path) -> dict[str, Any]:
    old_paths = [
        *sorted((root / "models").glob("*/kit.toml")),
        root / "variation/benchmark_v1.toml",
        root / "variation/adapters_v1.toml",
        root / "passives/benchmark_v1.toml",
    ]
    existing_old_paths = [str(path.relative_to(root)) for path in old_paths if path.exists()]
    audit_modules = {"validation_support.py", "release_validate.py", "provenance_validate.py"}
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

