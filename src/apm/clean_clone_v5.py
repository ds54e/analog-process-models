# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Create a fresh candidate clone before any generated state exists."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .compiler_provenance import digest
from .research import save, seal, verify
from .research_numerics import ResearchError

REMOTE = "https://github.com/ds54e/analog-process-models.git"
SCHEMA = "apm.clean-clone-attestation.v5"


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def create_clone(destination: Path, commit: str) -> dict:
    destination = destination.resolve()
    if destination.exists():
        raise ResearchError("FRESH_CLONE_DESTINATION_MUST_NOT_EXIST")
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ResearchError("EXACT_COMMIT_REQUIRED")
    started = datetime.now(timezone.utc).isoformat()
    subprocess.run(["git", "clone", "--no-local", REMOTE, str(destination)], check=True)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "origin/main"], cwd=destination, check=True
    )
    subprocess.run(["git", "checkout", "--detach", commit], cwd=destination, check=True)
    if git(destination, "rev-parse", "HEAD") != commit or git(
        destination, "status", "--porcelain", "--untracked-files=all"
    ):
        raise ResearchError("CLONE_IDENTITY_OR_CLEANLINESS")
    if (destination / ".apm").exists() or (destination / ".venv").exists():
        raise ResearchError("GENERATED_STATE_PRESENT_BEFORE_ATTESTATION")
    report = seal(
        {
            "schema": SCHEMA,
            "created_utc": started,
            "remote": REMOTE,
            "commit": commit,
            "tree": git(destination, "rev-parse", "HEAD^{tree}"),
            "root": str(destination),
            "origin_main": git(destination, "rev-parse", "origin/main"),
            "git_dir": git(destination, "rev-parse", "--absolute-git-dir"),
            "fresh_generated_state_absent": True,
            "local_alternates_absent": not (destination / ".git/objects/info/alternates").exists(),
            "creation_method": "git clone --no-local from authoritative GitHub remote; no local state copied",
            "creator_sha256": digest(Path(__file__)),
        }
    )
    return save(destination / ".apm/v5/clean-clone-attestation.json", report)


def audit_clone(root: Path) -> dict:
    path = root / ".apm/v5/clean-clone-attestation.json"
    try:
        report = verify(json.loads(path.read_text()), SCHEMA)
        checks = {
            "source_commit": report["commit"] == git(root, "rev-parse", "HEAD"),
            "source_tree": report["tree"] == git(root, "rev-parse", "HEAD^{tree}"),
            "observed_main": report["origin_main"] == git(root, "rev-parse", "origin/main"),
            "candidate_on_main_history": subprocess.run(
                ["git", "merge-base", "--is-ancestor", report["commit"], report["origin_main"]],
                cwd=root,
                check=False,
            ).returncode
            == 0,
            "clone_path": report["root"] == str(root.resolve()),
            "git_directory": report["git_dir"] == git(root, "rev-parse", "--absolute-git-dir"),
            "authoritative_remote": report["remote"]
            == REMOTE
            == git(root, "remote", "get-url", "origin"),
            "no_alternates": report["local_alternates_absent"]
            and not (root / ".git/objects/info/alternates").exists(),
            "fresh_before_execution": report["fresh_generated_state_absent"] is True,
            "creator_matches_candidate": report["creator_sha256"] == digest(Path(__file__)),
            "clean": not git(root, "status", "--porcelain", "--untracked-files=all"),
        }
        return {
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "attestation_path": str(path),
            "attestation_sha256": digest(path),
        }
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        return {"status": "FAIL", "error": str(error), "checks": {}}
