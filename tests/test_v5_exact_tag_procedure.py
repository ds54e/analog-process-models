# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Post-tag publication must fail on identity, completeness or evidence faults."""

import json
from types import SimpleNamespace

import pytest

from apm.research import save, seal
from apm.research_numerics import ResearchError
from tools import requalify_v5_tag as procedure


@pytest.fixture
def rerun(tmp_path):
    output = tmp_path / "candidate-rerun"
    output.mkdir()
    evidence = output / "component.json"
    evidence.write_text('{"status":"PASS"}\n')
    report = {
        "schema": "apm.release-readiness.v5",
        "status": "V5_RELEASE_READY",
        "subject_commit": procedure.CANDIDATE,
        "version": "5.0.0",
        "required_gates": 16,
        "passed_gates": 16,
        "gates": [
            {
                "id": name,
                "status": "PASS",
                "evidence_valid": True,
                "subject_commit": procedure.CANDIDATE,
                "evidence": [procedure.reference(evidence)],
            }
            for name in sorted(procedure.CANDIDATE_GATES)
        ],
    }
    return output / "report.json", report, evidence


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "exit",
        "missing_gate",
        "duplicate",
        "failed_gate",
        "skipped_gate",
        "wrong_commit",
        "wrong_version",
        "empty_evidence",
        "stale_hash",
        "old_directory",
        "seal",
    ],
)
def test_full_rerun_evidence_rejection(rerun, fault):
    path, report, evidence = rerun
    if fault == "missing_gate":
        report["gates"].pop()
    elif fault == "duplicate":
        report["gates"][-1] = report["gates"][0]
    elif fault in ("failed_gate", "skipped_gate"):
        report["gates"][0]["status"] = "FAIL" if fault == "failed_gate" else "SKIP"
    elif fault == "wrong_commit":
        report["subject_commit"] = "0" * 40
    elif fault == "wrong_version":
        report["version"] = "5.0.0+main"
    elif fault == "empty_evidence":
        report["gates"][0]["evidence"] = []
    elif fault == "stale_hash":
        evidence.write_text('{"status":"FAIL"}\n')
    elif fault == "old_directory":
        old = path.parent.parent / "previous-candidate.json"
        old.write_bytes(evidence.read_bytes())
        report["gates"][0]["evidence"] = [procedure.reference(old)]
    save(path, seal(report))
    if fault == "seal":
        tampered = json.loads(path.read_text())
        tampered["version"] = "5.0.0+main"
        save(path, tampered)
    if fault == "none":
        observed, refs = procedure.check_rerun(path, returncode=0)
        assert observed["passed_gates"] == 16 and len(refs) == 1
    else:
        with pytest.raises((ResearchError, ValueError)):
            procedure.check_rerun(path, returncode=1 if fault == "exit" else 0)


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "lightweight",
        "remote_object",
        "peeled_commit",
        "direct_commit",
        "tree",
        "dirty",
        "head",
        "attached",
        "ancestry",
    ],
)
def test_tag_identity_rejects_wrong_or_moving_refs(monkeypatch, tmp_path, fault):
    tag = "refs/tags/" + procedure.TAG
    obj, commit = "a" * 40, procedure.CANDIDATE
    values = {
        ("ls-remote", "--tags", procedure.REMOTE): f"{obj}\t{tag}\n{commit}\t{tag}^{{}}",
        ("cat-file", "-t", tag): "tag",
        ("rev-parse", tag): obj,
        ("rev-parse", tag + "^{}"): commit,
        (
            "cat-file",
            "-p",
            tag,
        ): f"object {commit}\ntype commit\ntag {procedure.TAG}\ntagger Test\n",
        ("rev-parse", procedure.TAG + "^{tree}"): procedure.TREE,
        ("remote", "get-url", "origin"): procedure.REMOTE,
        ("status", "--porcelain", "--untracked-files=all"): "",
        ("rev-parse", "HEAD"): commit,
        ("rev-parse", "origin/main"): "b" * 40,
        ("rev-parse", "--absolute-git-dir"): str(tmp_path / ".git"),
    }
    mutations = {
        "lightweight": (("cat-file", "-t", tag), "commit"),
        "remote_object": (("rev-parse", tag), "c" * 40),
        "peeled_commit": (("rev-parse", tag + "^{}"), "c" * 40),
        "direct_commit": (("cat-file", "-p", tag), "object other\ntype tag\n"),
        "tree": (("rev-parse", procedure.TAG + "^{tree}"), "c" * 40),
        "dirty": (("status", "--porcelain", "--untracked-files=all"), " M file"),
        "head": (("rev-parse", "HEAD"), "c" * 40),
    }
    if fault in mutations:
        key, value = mutations[fault]
        values[key] = value
    monkeypatch.setattr(procedure, "git", lambda root, *args: values[args])

    def run(command, **kwargs):
        return SimpleNamespace(
            returncode=(0 if fault == "attached" else 1)
            if "symbolic-ref" in command
            else (1 if fault == "ancestry" else 0)
        )

    monkeypatch.setattr(procedure.subprocess, "run", run)
    if fault == "none":
        assert procedure.tag_identity(tmp_path, {}, detached=True)["worktree_clean"]
    else:
        with pytest.raises(ResearchError):
            procedure.tag_identity(tmp_path, {}, detached=True)
