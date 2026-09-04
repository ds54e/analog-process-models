# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Create and verify candidate/exact-tag clean-clone attestations for v4."""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_REMOTE = "https://github.com/ds54e/analog-process-models"
V3_TAG = "v3.0.0"
V3_TAG_OBJECT = "afecec29ea6ed0703ef441d4839fd40a238bef0b"
V3_TAG_COMMIT = "995e0ce7cdd0c37ef9f3397008637f9d239c746e"
V4_TAG = "v4.0.0"
ATTESTATION_PATH = Path(".apm/clean-clone-attestation-v4.json")
PHASES = frozenset({"candidate", "exact-tag"})
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


class CleanCloneV4Error(RuntimeError):
    """A checkout cannot qualify as the required v4 clean-clone environment."""


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
        raise CleanCloneV4Error(f"command failed: {' '.join(command)}: {detail}")
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


def _tag_identity(root: Path, tag: str) -> dict[str, Any]:
    exists = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if exists.returncode not in {0, 1}:
        raise CleanCloneV4Error(f"cannot inspect local tag {tag}")
    if exists.returncode == 1:
        return {"present": False, "object": None, "object_type": None, "commit": None}
    object_id = _run(root, ["git", "rev-parse", f"refs/tags/{tag}"])
    object_type = _run(root, ["git", "cat-file", "-t", f"refs/tags/{tag}"])
    commit = _run(root, ["git", "rev-parse", f"refs/tags/{tag}^{{commit}}"])
    return {
        "present": True,
        "object": object_id,
        "object_type": object_type,
        "commit": commit,
    }


def _remote_tag_identity(root: Path, tag: str) -> dict[str, Any]:
    output = _run(
        root,
        [
            "git",
            "ls-remote",
            "--tags",
            "origin",
            f"refs/tags/{tag}",
            f"refs/tags/{tag}^{{}}",
        ],
    )
    refs: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        object_id, ref = line.split(maxsplit=1)
        refs[ref] = object_id
    return {
        "present": f"refs/tags/{tag}" in refs,
        "object": refs.get(f"refs/tags/{tag}"),
        "commit": refs.get(f"refs/tags/{tag}^{{}}"),
        "refs": refs,
    }


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise CleanCloneV4Error("cannot determine remote-main ancestry")
    return result.returncode == 0


def _phase_checks(
    phase: str,
    *,
    head: str,
    origin_main: str,
    local_v4: dict[str, Any],
    remote_v4: dict[str, Any],
    root: Path,
) -> dict[str, bool]:
    if phase == "candidate":
        return {
            "candidate_is_exact_origin_main": head == origin_main,
            "v4_tag_absent_locally": local_v4["present"] is False,
            "v4_tag_absent_remotely": remote_v4["present"] is False,
        }
    return {
        "v4_tag_is_annotated": local_v4["object_type"] == "tag",
        "v4_tag_commit_is_head": local_v4["commit"] == head,
        "remote_v4_tag_object_matches": remote_v4["object"] == local_v4["object"],
        "remote_v4_tag_commit_matches": remote_v4["commit"] == head,
        "exact_tag_is_on_origin_main_history": _is_ancestor(root, head, origin_main),
    }


def create_clean_clone_v4_attestation(
    root: Path,
    *,
    phase: str,
    output: Path | None = None,
) -> dict[str, Any]:
    """Attest an untouched detached HTTPS clone before project-local setup."""

    if phase not in PHASES:
        raise CleanCloneV4Error(f"unsupported v4 attestation phase: {phase}")
    selected = root.expanduser().resolve()
    if not (selected / ".git").exists():
        raise CleanCloneV4Error(f"not a Git checkout: {selected}")
    if not (selected / "validation/release_gates_v4.toml").is_file():
        raise CleanCloneV4Error(f"not an APM v4 checkout: {selected}")
    destination = (output or (selected / ATTESTATION_PATH)).expanduser().resolve()
    state_absent = not (selected / ".apm").exists()
    generated_state_paths = _generated_state_paths(selected)
    status = _run(selected, ["git", "status", "--porcelain", "--untracked-files=all"])
    remote = _run(selected, ["git", "remote", "get-url", "origin"]).removesuffix(".git")
    head = _run(selected, ["git", "rev-parse", "HEAD"])
    symbolic_branch = _run(selected, ["git", "branch", "--show-current"])
    origin_main = _run(selected, ["git", "rev-parse", "refs/remotes/origin/main"])
    local_v3 = _tag_identity(selected, V3_TAG)
    local_v4 = _tag_identity(selected, V4_TAG)
    remote_v4 = _remote_tag_identity(selected, V4_TAG)
    platform_observation = _platform_observation(selected)
    checks = {
        "initial_worktree_clean": status == "",
        "state_absent_before_attestation": state_absent,
        "project_generated_state_absent": not generated_state_paths,
        "expected_https_origin": remote == EXPECTED_REMOTE,
        "detached_head": symbolic_branch == "",
        "v3_tag_is_immutable_annotated_object": local_v3
        == {
            "present": True,
            "object": V3_TAG_OBJECT,
            "object_type": "tag",
            "commit": V3_TAG_COMMIT,
        },
        **platform_observation["checks"],
        **_phase_checks(
            phase,
            head=head,
            origin_main=origin_main,
            local_v4=local_v4,
            remote_v4=remote_v4,
            root=selected,
        ),
    }
    if not all(checks.values()):
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        raise CleanCloneV4Error(f"v4 clean-clone attestation failed: {failed}")
    report: dict[str, Any] = {
        "schema": "apm.clean-clone-attestation.v4",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "attested",
        "phase": phase,
        "repository": str(selected),
        "repository_head": head,
        "origin_main_commit": origin_main,
        "symbolic_branch": symbolic_branch,
        "origin": remote,
        "initial_git_status_porcelain": status,
        "initial_generated_state_paths": generated_state_paths,
        "v3_tag": local_v3,
        "v4_tag": {"local": local_v4, "remote": remote_v4},
        "platform": platform_observation,
        "checks": checks,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["attestation_path"] = str(destination)
    return report


def verify_clean_clone_v4_attestation(root: Path, *, phase: str) -> dict[str, Any]:
    """Verify that v4 qualification still runs at the exact attested clean commit."""

    if phase not in PHASES:
        raise CleanCloneV4Error(f"unsupported v4 attestation phase: {phase}")
    selected = root.expanduser().resolve()
    path = selected / ATTESTATION_PATH
    if not path.is_file():
        raise CleanCloneV4Error(
            "v4 clean-clone attestation missing; run tools/attest_clean_clone_v4.py "
            "immediately after detached checkout and before bootstrap"
        )
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CleanCloneV4Error(f"invalid v4 clean-clone attestation: {path}: {error}") from error
    head = _run(selected, ["git", "rev-parse", "HEAD"])
    status = _run(selected, ["git", "status", "--porcelain", "--untracked-files=all"])
    remote = _run(selected, ["git", "remote", "get-url", "origin"]).removesuffix(".git")
    origin_main = _run(selected, ["git", "rev-parse", "refs/remotes/origin/main"])
    local_v3 = _tag_identity(selected, V3_TAG)
    local_v4 = _tag_identity(selected, V4_TAG)
    remote_v4 = _remote_tag_identity(selected, V4_TAG)
    platform_observation = _platform_observation(selected)
    attested_checks = report.get("checks", {})
    phase_checks = _phase_checks(
        phase,
        head=head,
        origin_main=origin_main,
        local_v4=local_v4,
        remote_v4=remote_v4,
        root=selected,
    )
    checks = {
        "schema": report.get("schema") == "apm.clean-clone-attestation.v4",
        "attestation_status": report.get("status") == "attested",
        "phase_matches": report.get("phase") == phase,
        "attested_checks_complete_and_passing": isinstance(attested_checks, dict)
        and bool(attested_checks)
        and all(value is True for value in attested_checks.values()),
        "same_checkout_path": report.get("repository") == str(selected),
        "exact_attested_commit": report.get("repository_head") == head,
        "same_origin_main_snapshot": report.get("origin_main_commit") == origin_main,
        "current_worktree_clean": status == "",
        "expected_https_origin": report.get("origin") == remote == EXPECTED_REMOTE,
        "detached_head": _run(selected, ["git", "branch", "--show-current"]) == "",
        "current_platform_matches_gate": all(platform_observation["checks"].values()),
        "v3_tag_still_immutable": local_v3 == report.get("v3_tag"),
        "v4_tag_state_matches_attestation": report.get("v4_tag")
        == {"local": local_v4, "remote": remote_v4},
        **phase_checks,
    }
    if not all(checks.values()):
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        raise CleanCloneV4Error(f"v4 clean-clone verification failed: {failed}")
    return {
        "schema": "apm.clean-clone-verification.v4",
        "status": "verified",
        "phase": phase,
        "attestation_path": str(path),
        "repository_head": head,
        "origin_main_commit": origin_main,
        "origin": remote,
        "v3_tag": local_v3,
        "v4_tag": {"local": local_v4, "remote": remote_v4},
        "platform": platform_observation,
        "checks": checks,
        "report_path": str(path),
    }
