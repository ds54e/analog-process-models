#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Requalify the approved v5 tag without changing its candidate or creating refs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from apm.clean_clone_v5 import REMOTE, create_clone, git
from apm.compiler_provenance import digest
from apm.release_validate_v5 import CANDIDATE_GATES
from apm.research import save, seal, verify
from apm.research_numerics import ResearchError
from apm.toolchain import resolve_toolchain

TAG = "v5.0.0"
CANDIDATE = "381517fda5107fabf98af7801d5a5103f38e230c"
TREE = "8751c3ed03dc31c87f52d3eb3c5c0b4da903ed65"
SCHEMA = "apm.release-exact-tag.v5"


def require(condition, message):
    if not condition:
        raise ResearchError(message)


def reference(path):
    return {"path": str(path.resolve()), "sha256": digest(path)}


def tag_identity(root: Path, legacy_tags: dict, *, detached: bool):
    remote = {
        ref: value
        for value, ref in (
            line.split() for line in git(root, "ls-remote", "--tags", REMOTE).splitlines()
        )
    }
    tags = {}
    for name, expected in {**legacy_tags, TAG: {"peeled_commit": CANDIDATE}}.items():
        ref = "refs/tags/" + name
        require(git(root, "cat-file", "-t", ref) == "tag", "ANNOTATED_TAG_REQUIRED")
        obj, commit = git(root, "rev-parse", ref), git(root, "rev-parse", ref + "^{}")
        require(obj == remote.get(ref), "LOCAL_REMOTE_TAG_OBJECT_MISMATCH")
        require(commit == remote.get(ref + "^{}"), "LOCAL_REMOTE_PEELED_COMMIT_MISMATCH")
        require(commit == expected["peeled_commit"], "APPROVED_OR_LEGACY_COMMIT_MISMATCH")
        require(expected.get("object_sha", obj) == obj, "LEGACY_TAG_OBJECT_CHANGED")
        tags[name] = {"object_sha": obj, "peeled_commit": commit}
    tag_body = git(root, "cat-file", "-p", "refs/tags/" + TAG)
    require(
        tag_body.startswith(f"object {CANDIDATE}\ntype commit\ntag {TAG}\n"),
        "TAG_MUST_DIRECTLY_NAME_APPROVED_COMMIT",
    )
    tree = git(root, "rev-parse", TAG + "^{tree}")
    require(tree == TREE, "APPROVED_TREE_MISMATCH")
    require(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", CANDIDATE, "origin/main"],
            cwd=root,
            check=False,
        ).returncode
        == 0,
        "CANDIDATE_NOT_ON_AUTHORITATIVE_MAIN_HISTORY",
    )
    require(git(root, "remote", "get-url", "origin") == REMOTE, "WRONG_ORIGIN")
    clean = not git(root, "status", "--porcelain", "--untracked-files=all")
    require(clean, "WORKTREE_NOT_CLEAN")
    if detached:
        require(git(root, "rev-parse", "HEAD") == CANDIDATE, "WRONG_CHECKOUT")
        require(
            subprocess.run(
                ["git", "symbolic-ref", "--quiet", "HEAD"],
                cwd=root,
                check=False,
                stdout=subprocess.DEVNULL,
            ).returncode
            == 1,
            "DETACHED_HEAD_REQUIRED",
        )
    return {
        "tag_name": TAG,
        "tags": tags,
        "candidate_tree": tree,
        "head": git(root, "rev-parse", "HEAD"),
        "worktree_clean": clean,
        "origin_main": git(root, "rev-parse", "origin/main"),
        "root": str(root.resolve()),
        "git_dir": git(root, "rev-parse", "--absolute-git-dir"),
        "detached_required": detached,
    }


def check_rerun(path: Path, *, returncode: int):
    require(returncode == 0, "CANDIDATE_RERUN_COMMAND_FAILED")
    report = verify(json.loads(path.read_text()), "apm.release-readiness.v5")
    require(report.get("status") == "V5_RELEASE_READY", "CANDIDATE_RERUN_NOT_READY")
    require(report.get("subject_commit") == CANDIDATE, "RERUN_WRONG_CANDIDATE")
    require(report.get("version") == "5.0.0", "RERUN_WRONG_VERSION")
    gates = report.get("gates", [])
    require(
        len(gates) == 16
        and {g["id"] for g in gates} == CANDIDATE_GATES
        and report.get("passed_gates") == report.get("required_gates") == 16,
        "INCOMPLETE_OR_DUPLICATE_GATE_INVENTORY",
    )
    refs = {}
    for gate in gates:
        require(
            gate.get("status") == "PASS"
            and gate.get("evidence_valid") is True
            and gate.get("subject_commit") == CANDIDATE
            and bool(gate.get("evidence")),
            "REQUIRED_GATE_NOT_PASS",
        )
        for ref in gate["evidence"]:
            artifact = Path(ref["path"]).resolve()
            require(path.parent.resolve() in artifact.parents, "EVIDENCE_OUTSIDE_FRESH_RERUN")
            require(digest(artifact) == ref["sha256"], "RERUN_EVIDENCE_HASH_MISMATCH")
            refs[str(artifact)] = ref["sha256"]
    return report, refs


def logged(command, root, log, environment=None):
    print("Executing " + " ".join(map(str, command)), flush=True)
    with log.open("x") as stream:
        result = subprocess.run(
            list(map(str, command)),
            cwd=root,
            env=environment,
            check=False,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
    return {
        "command": list(map(str, command)),
        "returncode": result.returncode,
        "log": reference(log),
    }


def requalify(destination: Path, source_pdf: Path, toolchain: Path, constraints: Path):
    root = Path(__file__).resolve().parents[1]
    helper_hash = digest(Path(__file__))
    authorization_path = root / "validation/evidence/v5_release_authorization.json"
    authorization = json.loads(authorization_path.read_text())
    require(
        authorization["approved_candidate"] == CANDIDATE
        and authorization["candidate_tree"] == TREE
        and authorization["publish_only_after_fresh_exact_tag_17_of_17"] is True,
        "EXACT_CANDIDATE_APPROVAL_REQUIRED",
    )
    summary_path = root / authorization["candidate_evidence"]["path"]
    require(
        digest(summary_path) == authorization["candidate_evidence"]["sha256"],
        "APPROVED_CANDIDATE_EVIDENCE_CHANGED",
    )
    approved = json.loads(summary_path.read_text())
    before_main = tag_identity(root, authorization["legacy_tags"], detached=False)
    require(not destination.exists(), "FRESH_DESTINATION_MUST_NOT_EXIST")
    tool = resolve_toolchain(root)
    require(
        digest(tool.ngspice) == authorization["reference_inputs"]["ngspice_sha256"],
        "REFERENCE_NGSPICE_CHANGED",
    )
    require(
        digest(constraints) == authorization["reference_inputs"]["constraints_sha256"],
        "REFERENCE_DEPENDENCY_CONSTRAINTS_CHANGED",
    )
    require(
        digest(source_pdf) == "0f1a691225d51db40440d5e71081bda819a34fda8bda4b08099f5830418e7f5a",
        "PINNED_COMPANION_PDF_REQUIRED",
    )
    started = datetime.now(timezone.utc).isoformat()
    # The unchanged creator first attests the approved commit with empty generated
    # state. Selecting the annotated tag explicitly must leave that commit intact.
    attestation = create_clone(destination, CANDIDATE)
    subprocess.run(["git", "checkout", "--detach", TAG], cwd=destination, check=True)
    raw = destination / ".apm/v5/exact-tag"
    raw.mkdir(parents=True, exist_ok=False)
    result = {
        "schema": SCHEMA,
        "status": "FAIL",
        "started_utc": started,
        "tag_name": TAG,
        "approved_candidate": CANDIDATE,
        "candidate_tree": TREE,
        "tooling_commit": before_main["head"],
        "tooling_sha256": helper_hash,
        "authorization": reference(authorization_path),
        "main_before": before_main,
        "fresh_clone_attestation": attestation,
        "candidate_evidence": reference(summary_path),
        "executions": [],
        "github_release_creation_authorized": False,
        "required_gates": 17,
        "passed_gates": 0,
        "candidate_required_gates": 16,
    }
    try:
        before = tag_identity(destination, authorization["legacy_tags"], detached=True)
        require(before["tags"] == before_main["tags"], "TAG_CHANGED_DURING_CLONE")
        result["before"] = before
        save(raw / "before.json", seal(before))
        require(not (destination / ".venv").exists(), "COPIED_ENVIRONMENT_REJECTED")
        execution = logged([sys.executable, "-m", "venv", ".venv"], destination, raw / "venv.log")
        result["executions"].append(execution)
        require(execution["returncode"] == 0, "FRESH_VENV_CREATION_FAILED")
        python = destination / ".venv/bin/python"
        environment = dict(os.environ)
        for key in ("PYTHONPATH", "PYTHONHOME"):
            environment.pop(key, None)
        environment.update(
            {
                "APM_REPO_ROOT": str(destination),
                "APM_STATE_DIR": str(destination / ".apm/v5/state"),
                "APM_TOOLCHAIN_DIR": str(toolchain),
                "APM_V5_SOURCE_PDF": str(source_pdf),
                "PYTHONUNBUFFERED": "1",
            }
        )
        execution = logged(
            [python, "-m", "pip", "install", "-c", constraints, "-e", ".[dev,research-audit]"],
            destination,
            raw / "install.log",
            environment,
        )
        result["executions"].append(execution)
        require(execution["returncode"] == 0, "FRESH_INSTALL_FAILED")
        alias = destination / ".apm/toolchain/ngspice-47/bin/ngspice"
        alias.parent.mkdir(parents=True)
        alias.symlink_to(tool.ngspice)
        inputs = {
            "schema": "apm.exact-tag-inputs.v5",
            "source_pdf": reference(source_pdf),
            "constraints": reference(constraints),
            "ngspice": reference(tool.ngspice),
            "shared_toolchain": str(toolchain),
            "fresh_environment": str(python),
            "state_directory": environment["APM_STATE_DIR"],
            "source_reuse_policy": "Only pinned source/compiler receipts and dependency constraints shared; no environment or numerical results copied.",
        }
        save(raw / "inputs.json", seal(inputs))
        output = raw / "candidate-rerun"
        require(
            not output.exists() and not Path(environment["APM_STATE_DIR"]).exists(),
            "EXISTING_NUMERICAL_STATE_REJECTED",
        )
        result["generated_numerical_state_absent_before_run"] = True
        execution = logged(
            [
                destination / ".venv/bin/apm",
                "validate",
                "--release-v5",
                "candidate",
                "--output",
                output,
            ],
            destination,
            raw / "candidate-console.log",
            environment,
        )
        result["executions"].append(execution)
        report_path = output / "report.json"
        if report_path.exists():
            result["candidate_report"] = reference(report_path)
        report, references = check_rerun(report_path, returncode=execution["returncode"])
        result.update(
            {
                "candidate_passed_gates": 16,
                "passed_gates": 16,
                "gate_results": [{"id": g["id"], "status": g["status"]} for g in report["gates"]],
            }
        )
        require(
            report["gate_contract_sha256"]
            == digest(destination / "validation/release_gates_v5.toml"),
            "TAGGED_GATE_CONTRACT_CHANGED",
        )
        compiler = json.loads((output / "compiler.json").read_text())
        for key, value in approved["compiler_provenance"].items():
            require(compiler[key] == value, "REFERENCE_COMPILER_CHANGED: " + key)
        platform = json.loads((output / "platform.json").read_text())
        require(
            platform["dependencies"] == approved["environment"]["dependencies"],
            "REFERENCE_DEPENDENCIES_CHANGED",
        )
        require(
            digest(tool.ngspice) == inputs["ngspice"]["sha256"],
            "REFERENCE_NGSPICE_CHANGED_DURING_RUN",
        )
        after = tag_identity(destination, authorization["legacy_tags"], detached=True)
        require(after == before, "TAG_OR_CHECKOUT_CHANGED_DURING_REQUALIFICATION")
        require(digest(Path(__file__)) == helper_hash, "REQUALIFICATION_TOOL_CHANGED_DURING_RUN")
        result.update(
            {
                "status": "PASS",
                "passed_gates": 17,
                "candidate_passed_gates": 16,
                "after": after,
                "candidate_gate_evidence_rechecked": references,
                "gate_results": [{"id": g["id"], "status": g["status"]} for g in report["gates"]]
                + [{"id": "release.exact_tag_requalification", "status": "PASS"}],
                "component_evidence": [
                    reference(output / name)
                    for name in (
                        "compiler.json",
                        "doctor.json",
                        "source.json",
                        "platform.json",
                        "confirmation_audit.json",
                    )
                ],
                "input_evidence": reference(raw / "inputs.json"),
                "github_release_creation_authorized": True,
            }
        )
    except Exception as error:  # noqa: BLE001 - preserve failed post-tag evidence, never touch tag
        result["error"] = f"{type(error).__name__}: {error}"
        result.setdefault("gate_results", []).append(
            {"id": "release.exact_tag_requalification", "status": "FAIL"}
        )
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    save(raw / "report.json", seal(result))
    print(
        json.dumps(
            {
                "status": result["status"],
                "report": str(raw / "report.json"),
                "passed_gates": result["passed_gates"],
                "required_gates": 17,
            }
        ),
        flush=True,
    )
    require(
        result["status"] == "PASS", "EXACT_TAG_FAILED: retain tag/evidence; publication forbidden"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("destination", "source-pdf", "toolchain", "constraints"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    requalify(
        *(
            getattr(args, name).resolve()
            for name in ("destination", "source_pdf", "toolchain", "constraints")
        )
    )
