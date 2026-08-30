# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Create and verify the exact-commit clean-clone release attestation."""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_REMOTE = "https://github.com/ds54e/analog-process-models"
ATTESTATION_PATH = Path(".apm/clean-clone-attestation.json")
ATTESTATION_CHECK_IDS = frozenset(
    {
        "initial_worktree_clean",
        "state_absent_before_attestation",
        "expected_origin",
        "wsl2",
        "rhel_compatible_el9",
        "x86_64",
        "linux_filesystem_path",
        "project_generated_state_absent",
        "v3_tag_absent",
    }
)
GENERATED_STATE_NAMES = frozenset(
    {
        ".apm",
        ".cache",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "results",
        "runs",
        "venv",
        "work",
    }
)


class CleanCloneError(RuntimeError):
    """A checkout cannot qualify as the required clean-clone environment."""


def _run(root: Path, command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise CleanCloneError(f"command failed: {' '.join(command)}: {detail}")
    return result.stdout.strip()


def _os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def _filesystem(root: Path) -> dict[str, str]:
    result = subprocess.run(
        ["findmnt", "--noheadings", "--output", "FSTYPE,SOURCE,TARGET", "--target", root],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        fields = result.stdout.strip().split(maxsplit=2)
        if len(fields) == 3:
            return {"type": fields[0], "source": fields[1], "target": fields[2]}
    fallback = _run(root, ["stat", "--file-system", "--format=%T", str(root)])
    return {"type": fallback, "source": "unavailable", "target": "unavailable"}


def _platform_observation(root: Path) -> dict[str, Any]:
    release = _os_release()
    kernel_release = platform.release()
    kernel_version = platform.version()
    architecture = platform.machine()
    distribution_id = release.get("ID", "").lower()
    distribution_like = release.get("ID_LIKE", "").lower().split()
    major = release.get("VERSION_ID", "").split(".", 1)[0]
    checks = {
        "wsl2": "microsoft" in kernel_release.lower()
        and ("wsl2" in kernel_release.lower() or "wsl2" in kernel_version.lower()),
        "rhel_compatible_el9": major == "9"
        and (
            distribution_id in {"almalinux", "rhel", "rocky", "centos"}
            or "rhel" in distribution_like
            or "fedora" in distribution_like
        ),
        "x86_64": architecture == "x86_64",
        "linux_filesystem_path": not str(root).startswith("/mnt/c"),
    }
    return {
        "kernel_release": kernel_release,
        "kernel_version": kernel_version,
        "architecture": architecture,
        "os_release": release,
        "filesystem": _filesystem(root),
        "checks": checks,
    }


def _generated_state_paths(root: Path) -> list[str]:
    """Return project-local generated/build/cache state present before bootstrap."""

    observed: set[str] = set()
    for name in GENERATED_STATE_NAMES:
        direct = root / name
        if direct.exists():
            observed.add(direct.relative_to(root).as_posix())
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if path.name in GENERATED_STATE_NAMES or path.suffix.lower() == ".osdi":
            observed.add(relative.as_posix())
    return sorted(observed)


def _tag_exists(root: Path, tag: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise CleanCloneError(f"cannot inspect tag {tag}")
    return result.returncode == 0


def create_clean_clone_attestation(
    root: Path,
    output: Path | None = None,
) -> dict[str, Any]:
    """Attest an untouched fresh checkout before project-local setup creates state."""

    selected = root.expanduser().resolve()
    if not (selected / ".git").exists():
        raise CleanCloneError(f"not a Git checkout: {selected}")
    if not (selected / "validation/release_gates.toml").is_file():
        raise CleanCloneError(f"not an APM checkout: {selected}")
    destination = (output or (selected / ATTESTATION_PATH)).expanduser().resolve()
    state = selected / ".apm"
    state_absent = not state.exists()
    generated_state_paths = _generated_state_paths(selected)
    v3_tag_present = _tag_exists(selected, "v3.0.0")
    status = _run(selected, ["git", "status", "--porcelain", "--untracked-files=all"])
    remote = _run(selected, ["git", "remote", "get-url", "origin"]).removesuffix(".git")
    head = _run(selected, ["git", "rev-parse", "HEAD"])
    symbolic_branch = _run(selected, ["git", "branch", "--show-current"])
    platform_observation = _platform_observation(selected)
    checks = {
        "initial_worktree_clean": status == "",
        "state_absent_before_attestation": state_absent,
        "expected_origin": remote == EXPECTED_REMOTE,
        "project_generated_state_absent": not generated_state_paths,
        "v3_tag_absent": not v3_tag_present,
        **platform_observation["checks"],
    }
    if not all(checks.values()):
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        raise CleanCloneError(f"clean-clone attestation failed: {failed}")
    report: dict[str, Any] = {
        "schema": "apm.clean-clone-attestation.v3",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "attested",
        "repository": str(selected),
        "repository_head": head,
        "symbolic_branch": symbolic_branch,
        "origin": remote,
        "initial_git_status_porcelain": status,
        "initial_generated_state_paths": generated_state_paths,
        "v3_tag_present": v3_tag_present,
        "platform": platform_observation,
        "checks": checks,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["attestation_path"] = str(destination)
    return report


def verify_clean_clone_attestation(root: Path) -> dict[str, Any]:
    """Verify that release validation still runs at the exact attested clean commit."""

    selected = root.expanduser().resolve()
    path = selected / ATTESTATION_PATH
    if not path.is_file():
        raise CleanCloneError(
            "clean-clone attestation missing; run tools/attest_clean_clone.py immediately "
            "after cloning and before bootstrap"
        )
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CleanCloneError(f"invalid clean-clone attestation: {path}: {error}") from error
    head = _run(selected, ["git", "rev-parse", "HEAD"])
    status = _run(selected, ["git", "status", "--porcelain", "--untracked-files=all"])
    remote = _run(selected, ["git", "remote", "get-url", "origin"]).removesuffix(".git")
    platform_observation = _platform_observation(selected)
    v3_tag_present = _tag_exists(selected, "v3.0.0")
    attested_checks = report.get("checks", {})
    checks = {
        "schema": report.get("schema") == "apm.clean-clone-attestation.v3",
        "attestation_status": report.get("status") == "attested",
        "attested_checks_complete": isinstance(attested_checks, dict)
        and set(attested_checks) == ATTESTATION_CHECK_IDS
        and all(value is True for value in attested_checks.values()),
        "same_checkout_path": report.get("repository") == str(selected),
        "exact_attested_commit": report.get("repository_head") == head,
        "current_worktree_clean": status == "",
        "expected_origin": report.get("origin") == remote == EXPECTED_REMOTE,
        "current_platform_matches_gate": all(platform_observation["checks"].values()),
        "v3_tag_still_absent": report.get("v3_tag_present") is False
        and not v3_tag_present,
    }
    if not all(checks.values()):
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        raise CleanCloneError(f"clean-clone verification failed: {failed}")
    return {
        "status": "verified",
        "attestation_path": str(path),
        "repository_head": head,
        "origin": remote,
        "platform": platform_observation,
        "v3_tag_present": v3_tag_present,
        "checks": checks,
    }
