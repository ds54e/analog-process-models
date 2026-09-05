# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Promoted v5 scientific/corruption tests; original locators in the check mapping."""
import json
from pathlib import Path

import pytest

from apm.compiler_provenance import digest
from apm.confirmation import validate_run_file
from apm.research import SCHEMAS, save, seal


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


def test_shipped_registry_explicitly_blocks_original_beta():
    from apm.history import tomllib

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
    from apm.confirmation import audit_plan
    from apm.history import tomllib

    root = Path(__file__).resolve().parents[1]
    plan = tomllib.loads((root / "validation/v5_confirmation_plan.toml").read_text())
    assert audit_plan(plan)["status"] == "PASS"
    plan[field] = value
    assert audit_plan(plan)["status"] == "FAIL"
