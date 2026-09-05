# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Candidate acceptance rejects incomplete evidence, independently of gate producers."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from apm.clean_clone_v5 import audit_clone, create_clone
from apm.cli import build_parser
from apm.compiler_provenance import digest
from apm.release_validate_v5 import CANDIDATE_GATES, evaluate_gates, validate_run_file
from apm.research import SCHEMAS, save, seal
from apm.research_numerics import ResearchError

COMMIT = "a" * 40


def evidence(tmp_path):
    path = tmp_path / "evidence.json"
    save(path, {"observed": True})
    contract = {
        "gate": [{"id": k, "phase": "candidate", "required": True} for k in sorted(CANDIDATE_GATES)]
        + [{"id": "release.exact_tag_requalification", "phase": "post_tag", "required": True}]
    }
    results = [
        {
            "id": k,
            "subject_commit": COMMIT,
            "status": "PASS",
            "evidence": [{"path": str(path), "sha256": digest(path)}],
        }
        for k in sorted(CANDIDATE_GATES)
    ]
    return contract, results, path


def test_all_candidate_gates_pass_without_post_tag(tmp_path):
    contract, results, _ = evidence(tmp_path)
    evaluated, passed = evaluate_gates(contract, results, COMMIT)
    assert passed and len(evaluated) == 16


@pytest.mark.parametrize(
    "failure",
    [
        "missing_gate",
        "empty_results",
        "empty_evidence",
        "missing_file",
        "hash_drift",
        "stale_subject",
        "duplicate",
        "extra_gate",
        "FAIL",
        "NOT_RUN",
        "SKIPPED",
        "UNKNOWN",
    ],
)
def test_incomplete_or_stale_candidate_never_passes(tmp_path, failure):
    contract, results, path = evidence(tmp_path)
    if failure == "missing_gate":
        results.pop()
    elif failure == "empty_results":
        results.clear()
    elif failure == "empty_evidence":
        results[0]["evidence"] = []
    elif failure == "missing_file":
        path.unlink()
    elif failure == "hash_drift":
        path.write_text("{}")
    elif failure == "stale_subject":
        results[0]["subject_commit"] = "b" * 40
    elif failure == "duplicate":
        results.append(copy.deepcopy(results[0]))
    elif failure == "extra_gate":
        results.append({**results[0], "id": "unknown"})
    else:
        results[0]["status"] = failure
    _, passed = evaluate_gates(contract, results, COMMIT)
    assert not passed


@pytest.mark.parametrize("failure", ["removed", "duplicate", "optional"])
def test_required_contract_cannot_be_silently_weakened(tmp_path, failure):
    contract, results, _ = evidence(tmp_path)
    if failure == "removed":
        contract["gate"].pop(0)
    elif failure == "duplicate":
        contract["gate"].append(copy.deepcopy(contract["gate"][0]))
    else:
        contract["gate"][0]["required"] = False
    with pytest.raises(ResearchError, match="INVENTORY_DRIFT"):
        evaluate_gates(contract, results, COMMIT)


def test_raw_receipt_requires_exact_inventory_hash_and_success(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_text("observed\n")
    path = tmp_path / "run.json"
    value = {"schema": SCHEMAS["run"], "status": "PASS", "files": {raw.name: digest(raw)}}
    save(path, seal(value))
    expected = digest(path)
    assert validate_run_file(path, expected)
    extra = tmp_path / "unexpected.txt"
    extra.write_text("extra")
    assert not validate_run_file(path, expected)
    extra.unlink()
    raw.write_text("changed")
    assert not validate_run_file(path, expected)
    save(path, seal({**value, "status": "FAIL"}))
    assert not validate_run_file(path, digest(path))


def test_fresh_clone_requires_new_destination_and_sealed_attestation(tmp_path):
    with pytest.raises(ResearchError, match="DESTINATION"):
        create_clone(tmp_path, COMMIT)
    with pytest.raises(ResearchError, match="EXACT_COMMIT"):
        create_clone(tmp_path / "new", "main")
    assert audit_clone(tmp_path)["status"] == "FAIL"
    path = tmp_path / ".apm/v5/clean-clone-attestation.json"
    save(path, {"schema": "apm.clean-clone-attestation.v5", "commit": COMMIT})
    assert audit_clone(tmp_path)["status"] == "FAIL"


def test_cli_candidate_only_and_release_modes_exclusive():
    parser = build_parser()
    assert parser.parse_args(["validate", "--release-v5", "candidate"]).release_v5 == "candidate"
    with pytest.raises(SystemExit):
        parser.parse_args(["validate", "--release-v5", "exact-tag"])
    with pytest.raises(SystemExit):
        parser.parse_args(["validate", "--release-v5", "candidate", "--release"])


def test_shipped_registry_explicitly_blocks_original_beta():
    from apm.release_validate_v5 import tomllib

    root = Path(__file__).resolve().parents[1]
    registry = tomllib.loads((root / "variation/research/apm045/sources.toml").read_text())
    original = next(x for x in registry["source"] if x["id"] == "hart2020_st40_original")
    assert (
        original["beta_status_n"] == original["beta_status_p"] == "BLOCKED_NORMALIZATION_CONFLICT"
    )
    assert len(registry["approved_runtime_profiles"]) == 1
    profile = json.loads((root / registry["approved_runtime_profiles"][0]["path"]).read_text())
    assert profile["tier"] == "SOURCE_TRANSFER_HYPOTHESIS"


@pytest.mark.parametrize(
    "field,value", [("w_um", [1.0]), ("pure_pairs", 10), ("circuit_realizations_per_family", 8)]
)
def test_confirmation_plan_cannot_omit_required_scope(field, value):
    from apm.release_validate_v5 import audit_plan, tomllib

    root = Path(__file__).resolve().parents[1]
    plan = tomllib.loads((root / "validation/v5_confirmation_plan.toml").read_text())
    assert audit_plan(plan)["status"] == "PASS"
    plan[field] = value
    assert audit_plan(plan)["status"] == "FAIL"
