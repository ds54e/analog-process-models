# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Promoted v5 scientific/corruption tests; original locators in the check mapping."""
import json
from pathlib import Path

import pytest

from apm.compiler_provenance import digest
from apm.confirmation import validate_run_file
from apm.research import SCHEMAS, save, seal


@pytest.mark.parametrize('fault', ['correct', 'wrong_seed', 'wrong_index', 'unresolved', 'wrong_run_binding', 'corrupt'])
def test_cohort_denominator_is_bound_to_distinct_saved_draws(tmp_path, fault):
    from apm.confirmation import validate_cohort_realization
    realized = seal({'schema': SCHEMAS['realization'], 'seed': 42, 'sample_index': 1000000,
                     'status': 'RESOLVED' if fault != 'unresolved' else 'FAILED'})
    if fault == 'corrupt':
        realized['sample_index'] = 7
    run = seal({'schema': SCHEMAS['run'], 'subject': {'realization_id':
               'wrong' if fault == 'wrong_run_binding' else realized['content_id']}})
    save(tmp_path / 'realization.json', realized)
    save(tmp_path / 'run.json', run)
    assert validate_cohort_realization(tmp_path, 41 if fault == 'wrong_seed' else 42,
                                      999999 if fault == 'wrong_index' else 1000000) is (fault == 'correct')


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
