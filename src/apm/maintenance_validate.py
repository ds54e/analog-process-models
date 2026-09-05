# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed current-mission validation preserving immutable release baselines."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib

from . import __version__
from .model_build import sha256_file
from .paths import repository_root, state_directory
from .provenance_validate import ProvenanceValidationError, validate_provenance
from .release_validate import (
    ReleaseValidationError,
    audit_distribution,
    audit_migration,
)
from .release_validate_v4 import (
    audit_mixed_voltage_evidence,
    audit_public_evidence,
    audit_v3_immutability,
    audit_v4_catalog,
    load_v4_gate_contract,
    run_v3_regression,
)
from .spectre_validate import SpectreStructureError, validate_spectre

V4_TAG = "v4.0.0"
V4_TAG_OBJECT = "797cdf9462db9dd634bff558802bcadaaeb70015"
V4_TAGGED_COMMIT = "d224f279921c7e1ae637fd867e00d450067766c6"
V4_FROZEN_AUTHORITY_COMMIT = "02959d4a095062873fa2a3a53936af3cb4598ee3"

# The authority commit is the first post-tag commit containing both the exact
# tagged source and the final candidate/exact-tag evidence records. Selecting
# complete directories here makes additions, removals, modes, and bytes part
# of the comparison without copying dozens of hashes into mutable code.
FROZEN_V4_PATHSPECS = (
    "V4_MIXED_VOLTAGE.md",
    "RELEASE_V4.md",
    "docs/release-validation.md",
    "models/apm045/families/io18",
    "models/apm045/families/io25",
    "models/apm045/mixed_voltage_evidence.toml",
    "models/apm045/provenance.toml",
    "models/apm045/technology.toml",
    "src/apm/clean_clone_v4.py",
    "src/apm/release_validate_v4.py",
    "tools/attest_clean_clone_v4.py",
    "tools/modelgen/apm045_mixed_voltage",
    "validation/mixed_voltage_comparison_v1.toml",
    "validation/release_gates_v4.toml",
    "validation/release_review_v4.toml",
    "validation/evidence",
)
REQUIRED_MODELGEN_RECORDS = frozenset(
    {
        "tools/modelgen/apm045_mixed_voltage/calibration_replay_v4.toml",
        "tools/modelgen/apm045_mixed_voltage/generation_epoch_1.toml",
        "tools/modelgen/apm045_mixed_voltage/generation_epoch_2.toml",
        "tools/modelgen/apm045_mixed_voltage/generation_epoch_3.toml",
        "tools/modelgen/apm045_mixed_voltage/qualification_epoch_1.toml",
        "tools/modelgen/apm045_mixed_voltage/qualification_epoch_2.toml",
        "tools/modelgen/apm045_mixed_voltage/qualification_epoch_3.toml",
        "tools/modelgen/apm045_mixed_voltage/reconstruction.toml",
    }
)


def _is_frozen_selected_path(relative: str) -> bool:
    if relative.startswith("validation/evidence/"):
        return bool(re.fullmatch(r"validation/evidence/v4_.*\.json", relative))
    return True


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReleaseValidationError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout.strip()


def _git_bytes(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseValidationError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout


def _git_object_bytes(root: Path, revision: str, relative: str) -> bytes:
    return _git_bytes(root, "show", f"{revision}:{relative}")


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseValidationError(
            f"git merge-base --is-ancestor {ancestor} {descendant} failed: {detail}"
        )
    return result.returncode == 0


def _check_map(checks: dict[str, bool], *, context: str) -> dict[str, Any]:
    failed = sorted(name for name, passed in checks.items() if passed is not True)
    return {
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "context": context,
    }


def _write_report(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = str(path)
    report["output_directory"] = str(path.parent)
    return report


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
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = {"schema": fallback_schema, "status": "fail", "checks": {}}
    else:
        report = {"schema": fallback_schema, "status": "fail", "checks": {}}
    report["error"] = str(error)
    report["report_path"] = str(report_path)
    report["output_directory"] = str(report_path.parent)
    return report


def _default_output(root: Path, mode: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return state_directory(root) / "results" / "validation" / f"{mode}-{stamp}"


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _matches(text: str, *patterns: str) -> bool:
    return all(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _documents_tsmc_taxonomy_only(text: str) -> bool:
    return _matches(
        text,
        r"post-release",
        r"taxonomy (?:sanity )?check(?:ing)?",
        r"not (?:a )?numerical input\b.*released\b.*model-generation flow",
    )


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
        "V5_RESEARCH_VARIATION.md",
        "validation/release_gates_v5.toml",
        "variation/research/apm045/sources.toml",
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
    try:
        contract = tomllib.loads(_read(root, "validation/release_gates_v5.toml"))
    except (ValueError, OSError):
        contract = {}
    authorization = contract.get("authorization", {})
    identity = contract.get("identity", {})
    checks = {
        "required_current_documents_present": all(
            (root / relative).is_file() for relative in required_paths
        ),
        "goal_is_post_v5_maintenance": _matches(
            normalized_goal,
            r"# APM post-v5 maintenance",
            r"Maintain the released APM v5\.0\.0 baseline",
            r"5\.0\.0\+main",
            r"separate explicit user authorization",
        ),
        "goal_preserves_released_semantics": _matches(
            normalized_goal,
            r"Do not modify Benchmark v2 distributions",
            r"native variation semantics",
            r"nominal model cards/wrappers/manifests",
            r"frozen v1-v5 records",
        ),
        "historical_candidate_authorization_preserved": authorization.get("implementation") is True
        and authorization.get("candidate_qualification") is True
        and authorization.get("create_tag") is False
        and authorization.get("publish_release") is False,
        "policy_identifies_frozen_v4_authority":
            V4_FROZEN_AUTHORITY_COMMIT in normalized_agents
            and identity.get("frozen_v4_authority") == V4_FROZEN_AUTHORITY_COMMIT
            and identity.get("frozen_v4_tag_object") == V4_TAG_OBJECT
            and identity.get("frozen_v4_tagged_commit") == V4_TAGGED_COMMIT,
        "policy_identifies_frozen_v5_authority": V5_FROZEN_AUTHORITY_COMMIT in normalized_agents,
        "positioning_has_inline_spdx": positioning.startswith(
            "<!-- SPDX-FileCopyrightText: APM contributors -->\n"
            "<!-- SPDX-License-Identifier: Apache-2.0 -->\n"
        ),
        "positioning_preserves_technology_and_family_boundary": _matches(
            normalized_positioning,
            r"generic 40/45 nm-class planar bulk CMOS",
            r"45 nm FreePDK45-based technology namespace",
            r"VTL/VTG/VTH and legacy THKOX",
            r"`io18` and `io25` mixed-voltage families",
        ),
        "positioning_preserves_claim_boundary": _matches(
            normalized_positioning,
            r"not as a TSMC40/45 model",
            r"foundry design-rule minima",
            r"reliability or safe-voltage ratings",
            r"epistemic ensemble as process variation",
            r"Model/release changes required: \*\*NONE\*\*",
        ),
        "positioning_tsmc_information_is_taxonomy_only": (
            _documents_tsmc_taxonomy_only(normalized_positioning)
        ),
        "apm045_readme_tsmc_information_is_taxonomy_only": (
            _documents_tsmc_taxonomy_only(normalized_apm045)
        ),
        "root_readme_tsmc_information_is_taxonomy_only": (
            _documents_tsmc_taxonomy_only(normalized_readme)
        ),
        "apm045_readme_is_current_device_guidance": _matches(
            normalized_apm045,
            r"APM045_POSITIONING\.md",
            r"released `?io18`?/`?io25`? cards|released io18/io25 cards",
            r"current maintenance scope",
        ),
        "security_names_latest_release": _matches(
            normalized_security,
            r"APM v5\.0\.0 is the latest completed release",
            r"post-release maintenance line",
        ),
        "environment_separates_current_and_historical_flows": _matches(
            normalized_environment,
            r"historical v4 release qualification boundary",
            r"current v5 validation",
            r"unflagged `apm validate` checks post-v5 maintenance",
        ),
        "readme_separates_current_and_historical_flows": _matches(
            normalized_readme,
            r"frozen historical records rather than current implementation instructions",
            r"does not reinterpret or update a completed release review",
            r"5\.0\.0\.dev0",
        ),
        "no_prohibited_public_claims": not prohibited_patterns,
    }
    result = _check_map(checks, context="post-v5 maintenance guidance and preserved released claims")
    result.update(
        {
            "reviewed_paths": list(required_paths),
            "prohibited_claim_patterns": prohibited_patterns,
        }
    )
    return result


def _tree_entries(root: Path, revision: str) -> dict[str, dict[str, str]]:
    raw = _git_bytes(
        root,
        "ls-tree",
        "-r",
        "--full-tree",
        "-z",
        revision,
        "--",
        *FROZEN_V4_PATHSPECS,
    )
    entries: dict[str, dict[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split()
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        if _is_frozen_selected_path(relative):
            entries[relative] = {
                "mode": mode,
                "object_type": object_type,
                "object_id": object_id,
            }
    return entries


def _index_entries(root: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    raw = _git_bytes(root, "ls-files", "--stage", "-z", "--", *FROZEN_V4_PATHSPECS)
    entries: dict[str, str] = {}
    conflicts: list[dict[str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, _object_id, stage = metadata.decode("ascii").split()
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        if not _is_frozen_selected_path(relative):
            continue
        if stage == "0":
            entries[relative] = mode
        else:
            conflicts.append({"path": relative, "stage": stage, "mode": mode})
    return entries, conflicts


def _selected_worktree_paths(root: Path) -> set[str]:
    raw = _git_bytes(
        root,
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
        *FROZEN_V4_PATHSPECS,
    )
    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in raw.split(b"\0")
        if item
        and _is_frozen_selected_path(
            item.decode("utf-8", errors="surrogateescape")
        )
    }


def _worktree_bytes(path: Path) -> bytes | None:
    if path.is_symlink():
        return os.fsencode(os.readlink(path))
    if path.is_file():
        return path.read_bytes()
    return None


def _repository_state_identity(root: Path) -> dict[str, Any]:
    """Identify the exact tracked and nonignored source state used by a run."""

    head = _git(root, "rev-parse", "HEAD")
    raw_tracked = _git_bytes(root, "ls-files", "--stage", "-z")
    tracked_records: list[dict[str, str]] = []
    for record in raw_tracked.split(b"\0"):
        if not record:
            continue
        metadata, raw_relative = record.split(b"\t", 1)
        mode, _object_id, stage = metadata.decode("ascii").split()
        relative = raw_relative.decode("utf-8", errors="surrogateescape")
        payload = _worktree_bytes(root / relative)
        tracked_records.append(
            {
                "path": relative,
                "index_mode": mode,
                "index_stage": stage,
                "worktree_sha256": (
                    hashlib.sha256(payload).hexdigest()
                    if payload is not None
                    else "missing"
                ),
            }
        )
    tracked_manifest = json.dumps(
        tracked_records, sort_keys=True, separators=(",", ":")
    ).encode()
    raw_untracked = _git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z")
    untracked_hashes: dict[str, str] = {}
    for raw_relative in raw_untracked.split(b"\0"):
        if not raw_relative:
            continue
        relative = raw_relative.decode("utf-8", errors="surrogateescape")
        payload = _worktree_bytes(root / relative)
        untracked_hashes[relative] = (
            hashlib.sha256(payload).hexdigest() if payload is not None else "missing"
        )
    identity = {
        "repository_head": head,
        "tracked_path_count": len({item["path"] for item in tracked_records}),
        "tracked_worktree_manifest_sha256": hashlib.sha256(
            tracked_manifest
        ).hexdigest(),
        "untracked_nonignored_sha256": untracked_hashes,
    }
    snapshot = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    identity["source_snapshot_sha256"] = hashlib.sha256(snapshot).hexdigest()
    identity["worktree_clean"] = not _git_bytes(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    return identity


def _project_version(data: bytes) -> str:
    try:
        project = tomllib.loads(data.decode("utf-8")).get("project", {})
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return "invalid"
    return str(project.get("version", "missing"))


def _runtime_version(data: bytes) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "invalid"
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return match.group(1) if match else "missing"


def _source_cli_version(data: bytes) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "invalid"
    match = re.search(r'version=["\']APM ([^"\']+)["\']', text)
    return match.group(1) if match else "missing"


def _executed_cli_version(root: Path) -> tuple[str, int, str]:
    result = subprocess.run(
        [sys.executable, "-m", "apm.cli", "--version"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout.strip()
    version = output.removeprefix("APM ") if output.startswith("APM ") else "missing"
    return version, result.returncode, result.stderr.strip()


def audit_maintenance_package_identity(root: Path) -> dict[str, Any]:
    """Distinguish mutable main builds from the immutable released package."""

    current_project = _project_version((root / "pyproject.toml").read_bytes())
    try:
        installed = importlib_metadata.version("analog-process-models")
    except importlib_metadata.PackageNotFoundError:
        installed = "missing"
    cli_version, cli_returncode, cli_stderr = _executed_cli_version(root)
    try:
        tagged_project = _project_version(
            _git_object_bytes(root, V5_TAGGED_COMMIT, "pyproject.toml")
        )
        tagged_runtime = _runtime_version(
            _git_object_bytes(root, V5_TAGGED_COMMIT, "src/apm/__init__.py")
        )
        tagged_cli_source = _git_object_bytes(root, V5_TAGGED_COMMIT, "src/apm/cli.py")
        tagged_cli_bound_to_runtime = (
            b"from . import __version__" in tagged_cli_source
            and b'version=f"APM {__version__}"' in tagged_cli_source
        )
        tagged_cli = tagged_runtime if tagged_cli_bound_to_runtime else "unbound"
        source_error = None
    except ReleaseValidationError as error:
        tagged_project = tagged_runtime = tagged_cli = "missing"
        source_error = str(error)
    expected_release = V5_TAG.removeprefix("v")
    # Released 5.0.0 remains immutable; mutable main has a distinct local identity.
    allowed_current = {"5.0.0+main"}
    expected_main = current_project

    checks = {
        "tagged_source_retains_release_identity": tagged_project
        == tagged_runtime
        == tagged_cli
        == expected_release,
        "main_has_post_release_local_identity": current_project in allowed_current,
        "runtime_version_matches_main_identity": __version__ == expected_main,
        "installed_distribution_matches_main_identity": installed == expected_main,
        "executed_cli_matches_main_identity": cli_returncode == 0
        and cli_version == expected_main,
        "all_current_version_surfaces_agree": current_project
        == __version__
        == installed
        == cli_version,
        "validator_source_is_selected_repository": Path(__file__).resolve()
        == (root / "src/apm/maintenance_validate.py").resolve(),
    }
    result = _check_map(checks, context="post-v5 main package identity and immutable v5 identity")
    result.update(
        {
            "policy": (
                "5.0.0 is the released source; 5.0.0+main identifies mutable maintenance. "
                "Exact identity is supplied by the recorded Git/worktree snapshot."
            ),
            "release_version": expected_release,
            "main_version": expected_main,
            "runtime_version": __version__,
            "installed_distribution_version": installed,
            "cli_version": cli_version,
            "cli_stderr": cli_stderr,
            "validator_source": str(Path(__file__).resolve()),
            "tagged_source_versions": {
                "pyproject": tagged_project,
                "runtime": tagged_runtime,
                "cli": tagged_cli,
            },
            "source_error": source_error,
        }
    )
    return result


def audit_frozen_v4_artifacts(root: Path) -> dict[str, Any]:
    """Compare the complete declared v4 frozen scope to one immutable commit."""

    authority_entries: dict[str, dict[str, str]] = {}
    index_entries: dict[str, str] = {}
    current_paths: set[str] = set()
    conflicts: list[dict[str, str]] = []
    expected_hashes: dict[str, str] = {}
    observed_hashes: dict[str, str] = {}
    byte_mismatches: list[dict[str, str]] = []
    mode_mismatches: list[dict[str, str]] = []
    authority_commit = authority_type = "missing"
    authority_descends_tag = head_descends_authority = False
    tag_object = tag_commit = tag_type = "missing"
    audit_error: str | None = None
    try:
        tag_object = _git(root, "rev-parse", f"refs/tags/{V4_TAG}")
        tag_commit = _git(root, "rev-parse", f"{V4_TAG}^{{commit}}")
        tag_type = _git(root, "cat-file", "-t", f"refs/tags/{V4_TAG}")
        authority_commit = _git(
            root, "rev-parse", f"{V4_FROZEN_AUTHORITY_COMMIT}^{{commit}}"
        )
        authority_type = _git(root, "cat-file", "-t", V4_FROZEN_AUTHORITY_COMMIT)
        authority_descends_tag = _is_ancestor(root, V4_TAGGED_COMMIT, authority_commit)
        head_descends_authority = _is_ancestor(root, authority_commit, "HEAD")
        authority_entries = _tree_entries(root, authority_commit)
        index_entries, conflicts = _index_entries(root)
        current_paths = _selected_worktree_paths(root)
        for relative, entry in sorted(authority_entries.items()):
            expected_bytes = _git_object_bytes(root, authority_commit, relative)
            current_bytes = _worktree_bytes(root / relative)
            expected_hash = hashlib.sha256(expected_bytes).hexdigest()
            observed_hash = (
                hashlib.sha256(current_bytes).hexdigest()
                if current_bytes is not None
                else "missing"
            )
            expected_hashes[relative] = expected_hash
            observed_hashes[relative] = observed_hash
            if observed_hash != expected_hash:
                byte_mismatches.append(
                    {
                        "path": relative,
                        "expected": expected_hash,
                        "actual": observed_hash,
                    }
                )
            actual_mode = index_entries.get(relative, "missing")
            if actual_mode != entry["mode"]:
                mode_mismatches.append(
                    {
                        "path": relative,
                        "expected": entry["mode"],
                        "actual": actual_mode,
                    }
                )
    except (OSError, ReleaseValidationError, ValueError) as error:
        audit_error = str(error)

    expected_paths = set(authority_entries)
    missing_paths = sorted(expected_paths - current_paths)
    unexpected_paths = sorted(current_paths - expected_paths)
    missing_index_paths = sorted(expected_paths - set(index_entries))
    unexpected_index_paths = sorted(set(index_entries) - expected_paths)
    checks = {
        "v4_tag_object_exact": tag_object == V4_TAG_OBJECT,
        "v4_tag_commit_exact": tag_commit == V4_TAGGED_COMMIT,
        "v4_tag_remains_annotated": tag_type == "tag",
        "frozen_authority_commit_exact": authority_commit
        == V4_FROZEN_AUTHORITY_COMMIT,
        "frozen_authority_is_commit": authority_type == "commit",
        "frozen_authority_descends_tagged_release": authority_descends_tag,
        "current_history_contains_frozen_authority": head_descends_authority,
        "frozen_authority_entries_are_blobs": bool(authority_entries)
        and all(entry["object_type"] == "blob" for entry in authority_entries.values()),
        "completed_modelgen_records_in_scope": REQUIRED_MODELGEN_RECORDS
        <= expected_paths,
        "frozen_artifact_inventory_exact": bool(expected_paths)
        and not missing_paths
        and not unexpected_paths
        and not missing_index_paths
        and not unexpected_index_paths
        and not conflicts,
        "frozen_artifact_modes_exact": not mode_mismatches,
        "frozen_artifact_bytes_exact": bool(expected_hashes) and not byte_mismatches,
        "frozen_audit_completed_without_error": audit_error is None,
    }
    result = _check_map(checks, context="frozen v4 release records and model artifacts")
    result.update(
        {
            "v4_tag_object": tag_object,
            "v4_tagged_commit": tag_commit,
            "authority_commit": authority_commit,
            "authority_pathspecs": list(FROZEN_V4_PATHSPECS),
            "artifact_count": len(expected_paths),
            "artifact_paths": sorted(expected_paths),
            "expected_sha256": expected_hashes,
            "artifact_sha256": observed_hashes,
            "missing_paths": missing_paths,
            "unexpected_paths": unexpected_paths,
            "missing_index_paths": missing_index_paths,
            "unexpected_index_paths": unexpected_index_paths,
            "index_conflicts": conflicts,
            "mode_mismatches": mode_mismatches,
            "mismatches": byte_mismatches,
            "audit_error": audit_error,
        }
    )
    return result


PREFLIGHT_COMMIT = "bbb585306f13614b7649c36dd5b7510c845daed9"
PREFLIGHT_PATHS = (
    "V5_PREFLIGHT.md", "tools/v5_preflight",
    "validation/evidence/v5_preflight_preparation.json",
    "validation/evidence/v5_preflight_findings.json",
    "validation/evidence/v5_preflight_source_audit.md",
)


def audit_frozen_preflight(root: Path) -> dict[str, Any]:
    """Preserve the completed exploratory snapshot, including inventories/modes."""
    raw = _git(root, "ls-tree", "-r", PREFLIGHT_COMMIT, "--", *PREFLIGHT_PATHS)
    expected = {}
    for line in raw.splitlines():
        metadata, path = line.split("\t", 1)
        mode, kind, blob = metadata.split()
        expected[path] = {"mode": mode, "blob": blob, "kind": kind}
    current = {}
    for line in _git(root, "ls-files", "--stage", "--", *PREFLIGHT_PATHS).splitlines():
        metadata, path = line.split("\t", 1)
        mode, _, stage = metadata.split()
        current[path] = {"mode": mode, "stage": stage}
    mismatched = []
    for path, entry in expected.items():
        content = _worktree_bytes(root/path)
        if (content is None or content != _git_object_bytes(root, PREFLIGHT_COMMIT, path)
                or current.get(path) != {"mode": entry["mode"], "stage": "0"}):
            mismatched.append(path)
    paths = set(_git(root, "ls-files", "--cached", "--others", "--exclude-standard",
                     "--", *PREFLIGHT_PATHS).splitlines())
    checks = {"inventory_exact": bool(expected) and set(expected) == set(current) == paths,
              "bytes_modes_exact": not mismatched,
              "preflight_in_history": _is_ancestor(root, PREFLIGHT_COMMIT, "HEAD")}
    result = _check_map(checks, context="immutable completed preflight snapshot")
    result.update(authority_commit=PREFLIGHT_COMMIT, artifact_count=len(expected),
                  mismatches=mismatched)
    return result


V5_TAG = "v5.0.0"
V5_TAG_OBJECT = "b1a4246b9189fe33915d457e9d7f2938869b8fdf"
V5_TAGGED_COMMIT = "381517fda5107fabf98af7801d5a5103f38e230c"
V5_FROZEN_AUTHORITY_COMMIT = "150084368815f6a57eae9f3e707f685149e920d3"
FROZEN_V5_PATHS = (
    "V5_RESEARCH_VARIATION.md",
    "RELEASE_V5.md",
    "validation/release_gates_v5.toml",
    "validation/v5_confirmation_plan.toml",
    "validation/v5_reference_constraints.txt",
    "validation/evidence",
    "variation/research/apm045",
    "tools/v5",
    "src/apm/clean_clone_v5.py",
    "src/apm/release_validate_v5.py",
    "tools/attest_clean_clone_v5.py",
    "tools/requalify_v5_tag.py",
    "tests/test_v5_exact_tag_procedure.py",
    "docs/release-readiness-v5.md",
    "docs/release-publication-v5.md",
)


def audit_frozen_v5_artifacts(root: Path) -> dict[str, Any]:
    """Keep released v5 source decisions and qualification records exact."""

    def selected(path):
        return not path.startswith("validation/evidence/") or path.startswith(
            "validation/evidence/v5_"
        )

    try:
        expected = {}
        for line in _git(
            root, "ls-tree", "-r", V5_FROZEN_AUTHORITY_COMMIT, "--", *FROZEN_V5_PATHS
        ).splitlines():
            metadata, path = line.split("\t", 1)
            mode, kind, blob = metadata.split()
            if not selected(path):
                continue
            expected[path] = {"mode": mode, "kind": kind, "blob": blob}
        index = {}
        for line in _git(root, "ls-files", "--stage", "--", *FROZEN_V5_PATHS).splitlines():
            metadata, path = line.split("\t", 1)
            mode, _, stage = metadata.split()
            if not selected(path):
                continue
            index.setdefault(path, []).append({"mode": mode, "stage": stage})
        paths = set(
            _git(
                root,
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                *FROZEN_V5_PATHS,
            ).splitlines()
        )
        paths = {p for p in paths if selected(p)}
        mismatches = []
        hashes = {}
        for path, entry in expected.items():
            full = root / path
            content = _worktree_bytes(full)
            hashes[path] = hashlib.sha256(content).hexdigest() if content is not None else "missing"
            actual_mode = (
                "120000"
                if full.is_symlink()
                else "100755"
                if full.exists() and full.stat().st_mode & 0o111
                else "100644"
            )
            if (
                content is None
                or content != _git_object_bytes(root, V5_FROZEN_AUTHORITY_COMMIT, path)
                or index.get(path) != [{"mode": entry["mode"], "stage": "0"}]
                or actual_mode != entry["mode"]
            ):
                mismatches.append(path)
        checks = {
            "v5_tag_object_exact": _git(root, "rev-parse", f"refs/tags/{V5_TAG}") == V5_TAG_OBJECT,
            "v5_tag_commit_exact": _git(root, "rev-parse", f"{V5_TAG}^{{commit}}")
            == V5_TAGGED_COMMIT,
            "v5_tag_remains_annotated": _git(root, "cat-file", "-t", f"refs/tags/{V5_TAG}")
            == "tag",
            "authority_descends_release": _is_ancestor(
                root, V5_TAGGED_COMMIT, V5_FROZEN_AUTHORITY_COMMIT
            ),
            "authority_in_current_history": _is_ancestor(root, V5_FROZEN_AUTHORITY_COMMIT, "HEAD"),
            "inventory_exact": bool(expected) and set(expected) == set(index) == paths,
            "all_entries_are_blobs": bool(expected)
            and all(x["kind"] == "blob" for x in expected.values()),
            "bytes_and_modes_exact": not mismatches,
            "required_release_evidence_present": {
                "validation/evidence/v5_release_candidate.json",
                "validation/evidence/v5_post_release_requalification.json",
                "validation/evidence/v5_release_authorization.json",
            }
            <= set(expected),
        }
        result = _check_map(checks, context="immutable released v5 methods and evidence")
        result.update(
            authority_commit=V5_FROZEN_AUTHORITY_COMMIT,
            artifact_count=len(expected),
            artifact_sha256=hashes,
            mismatches=mismatches,
            tag_object=V5_TAG_OBJECT,
            tagged_commit=V5_TAGGED_COMMIT,
        )
        return result
    except (OSError, ValueError, ReleaseValidationError) as error:
        return {
            "status": "fail",
            "audit_error": str(error),
            "authority_commit": V5_FROZEN_AUTHORITY_COMMIT,
        }


def run_maintenance_static_audits(root: Path, output: Path) -> dict[str, Any]:
    """Run the ordinary static/regression suite against current maintenance guidance."""

    # This contract is used only as a preserved compatibility baseline. The
    # current maintenance authority is GOAL.md plus the unflagged validator.
    released_contract = load_v4_gate_contract(root)
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
    frozen_v4 = audit_frozen_v4_artifacts(root)
    audits = {
        "package_identity": audit_maintenance_package_identity(root),
        "released_v4_catalog_compatibility": audit_v4_catalog(root, released_contract),
        "migration": audit_migration(root),
        "distribution": audit_distribution(root),
        "current_guidance": audit_current_guidance(root),
        "frozen_v4_artifacts": frozen_v4,
        "frozen_preflight": audit_frozen_preflight(root),
        "frozen_v5_artifacts": audit_frozen_v5_artifacts(root),
        "released_public_evidence_integrity": audit_public_evidence(
            root, released_contract
        ),
        "released_v3_compatibility": audit_v3_immutability(root, released_contract),
        "released_mixed_voltage_evidence_integrity": audit_mixed_voltage_evidence(root),
        "provenance": provenance,
    }
    checks = {
        "current_regression_commands": all(item["status"] == "pass" for item in commands),
        "repository_audits": all(item.get("status") == "pass" for item in audits.values()),
        "v3_regression": v3_regression.get("status") == "pass",
        "spectre_structural": spectre.get("status") == "structurally_checked"
        and all(spectre.get("checks", {}).values()),
    }
    repository_state = _repository_state_identity(root)
    report = {
        "schema": "apm.maintenance-static-audits.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if all(checks.values()) else "fail",
        "repository": str(root),
        "repository_head": repository_state["repository_head"],
        "repository_state": repository_state,
        "released_baseline_contract_path": "validation/release_gates_v4.toml",
        "released_baseline_contract_sha256": sha256_file(
            root / "validation/release_gates_v4.toml"
        ),
        "frozen_v4_authority_commit": V4_FROZEN_AUTHORITY_COMMIT,
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
            "released_compatibility_contract": released_contract,
            "provenance": provenance,
            "spectre_full": spectre,
            "v3_regression_full": v3_regression,
        }
    )
    return result


def validate_maintenance_repository(
    output: Path | None = None, *, root: Path | None = None
) -> dict[str, Any]:
    """Validate post-v5 main without changing frozen release semantics."""

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
        "repository_head": result["repository_state"]["repository_head"],
        "repository_state": result["repository_state"],
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
