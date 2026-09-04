# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from apm.catalog import load_catalog
from apm.cli import build_parser
from apm.noise import resolve_explicit_vctrl_bias
from apm.noise_catalog import (
    CATALOG_REQUEST_SCHEMA,
    COMPARISON_CROSS_PROCESS,
    COMPARISON_THRESHOLD_EQUAL_BIAS,
    COMPARISON_THRESHOLD_EQUAL_INVERSION,
    DATASET_INVERSION,
    DATASET_LENGTH,
    DATASET_NFIN,
    DATASET_TEMPERATURE,
    _artifact_inventory,
    _finalize_result_manifest,
    _hash_value,
    _integrate_spectrum_band,
    _interpolate_spectrum_value,
    _model_source_closure,
    _validate_completed_result,
    build_noise_catalog_plan,
)

ROOT = Path(__file__).resolve().parents[1]


def _plan() -> dict:
    catalog = load_catalog(ROOT)
    bindings = {}
    for technology in catalog.technologies:
        for family in technology.families:
            bindings[family.selector] = {
                "technology_id": technology.technology_id,
                "family_id": family.family_id,
                "operating_profile_id": family.default_operating_profile,
                "reference_vdd_v": family.operating_profile().reference_vdd_v,
                "compact_model": family.compact_model,
                "model_origin": family.origin,
                "semantic_files": [],
                "osdi_artifacts": [],
                "aggregate_sha256": _hash_value(
                    {"fixture_family_binding": family.selector}
                ),
            }
    return build_noise_catalog_plan(
        ROOT,
        code_identity={"files": [], "aggregate_sha256": "a" * 64},
        tool_identity={
            "ngspice": {"sha256": "b" * 64},
            "openvaf": {"sha256": "c" * 64},
            "required_noise_solver": "Sparse",
            "klu_permitted_for_required_noise": False,
        },
        binding_identities=bindings,
    )


def test_manifest_plan_derives_v4_logical_and_deduplicated_coverage() -> None:
    plan = _plan()
    assert plan["catalog"]["technology_count"] == 5
    assert plan["catalog"]["family_count"] == 15
    assert plan["catalog"]["public_device_count"] == 30
    assert len(plan["catalog"]["selectors"]) == 30
    assert plan["logical_request_counts"] == {
        DATASET_TEMPERATURE: 120,
        DATASET_INVERSION: 150,
        DATASET_LENGTH: 90,
        DATASET_NFIN: 18,
        COMPARISON_THRESHOLD_EQUAL_INVERSION: 18,
        COMPARISON_THRESHOLD_EQUAL_BIAS: 18,
        COMPARISON_CROSS_PROCESS: 10,
    }
    assert plan["logical_request_counts"] == plan[
        "live_catalog_derived_logical_request_counts"
    ]
    assert plan["planned_logical_request_count"] == 424
    assert plan["unique_request_count"] == 330
    assert plan["deduplicated_logical_request_count"] == 94
    assert len({job["request_id"] for job in plan["requests"]}) == 330


def test_catalog_plan_is_deterministic_and_deduplicates_identical_physical_requests() -> None:
    first = _plan()
    second = _plan()
    assert first == second
    canonical = [
        job
        for job in first["requests"]
        if job["request"]["selector"] == "apm350/general/nmos"
        and job["request"]["temperature_c"] == 27
        and job["request"]["bias"]["mode"] == "gm_over_id_target"
        and job["request"]["bias"]["target_per_v"] == 15.0
        and job["request"]["bias"]["relative_tolerance"] == 0.01
        and math.isclose(job["request"]["geometry"]["l_over_lmin"], 2.0)
    ]
    assert len(canonical) == 1
    assert {item["dataset"] for item in canonical[0]["memberships"]} == {
        DATASET_TEMPERATURE,
        DATASET_INVERSION,
        DATASET_LENGTH,
        COMPARISON_CROSS_PROCESS,
    }


def test_request_identity_binds_semantics_and_native_geometry() -> None:
    plan = _plan()
    finfet = next(
        job for job in plan["requests"] if job["request"]["selector"] == "apm016f/svt/nfet"
    )
    assert finfet["request"]["geometry"]["geometry_kind"] == "finfet"
    assert "w_m" not in finfet["request"]["geometry"]
    assert isinstance(finfet["request"]["geometry"]["nfin"], int)
    original_hash = finfet["request_hash"]
    changed = json.loads(json.dumps(finfet["request"]))
    changed["temperature_c"] = 28
    assert _hash_value(changed) != original_hash
    changed = json.loads(json.dumps(finfet["request"]))
    changed["reference_tool_hashes"]["ngspice_sha256"] = "d" * 64
    assert _hash_value(changed) != original_hash
    changed = json.loads(json.dumps(finfet["request"]))
    changed["semantic_binding"]["aggregate_sha256"] = "e" * 64
    assert _hash_value(changed) != original_hash


def test_model_identity_closes_nested_spice_includes() -> None:
    catalog = load_catalog(ROOT)
    binding = catalog.family("apm130", "lv").backend("ngspice")
    closure = {
        path.relative_to(ROOT).as_posix()
        for path in _model_source_closure(
            ROOT, (binding.wrapper_path, *binding.model_source_files())
        )
    }
    assert "models/apm130/vendor/ihp-sg13g2-models/cornerMOSlv.lib" in closure
    assert "models/apm130/vendor/ihp-sg13g2-models/sg13g2_moslv_mod.lib" in closure
    assert "models/apm130/vendor/ihp-sg13g2-models/sg13g2_moslv_parm.lib" in closure


def _unreachable_fixture(tmp_path: Path) -> tuple[dict, Path]:
    payload = {
        "schema": CATALOG_REQUEST_SCHEMA,
        "selector": "fixture/general/nmos",
        "temperature_c": 27,
        "geometry": {"geometry_kind": "planar", "l_m": 2e-6, "w_m": 1e-6},
        "output_bias": {"vout_v": 0.5},
        "bias": {"mode": "gm_over_id_target", "target_per_v": 15.0},
    }
    request_hash = _hash_value(payload)
    job = {
        "request_id": f"n2-{request_hash[:32]}",
        "request_hash": request_hash,
        "request": payload,
        "memberships": [],
    }
    directory = tmp_path / job["request_id"]
    directory.mkdir()
    (directory / "bias_resolution.json").write_text(
        json.dumps(
            {
                "schema": "apm.noise-bias-resolution.v1",
                "status": "target_not_reachable",
                "target_per_v": 15.0,
                "reason": "fixture",
            }
        ),
        encoding="utf-8",
    )
    _finalize_result_manifest(
        directory,
        job,
        status="target_not_reachable",
        repository_commit="f" * 40,
        detail={"fixture": True},
    )
    return job, directory


def test_resume_reuses_only_exact_completed_request_and_artifact_hashes(tmp_path: Path) -> None:
    job, directory = _unreachable_fixture(tmp_path)
    exact = _validate_completed_result(job, directory)
    assert exact["valid"] is True
    assert exact["reusable"] is True
    changed_job = {**job, "request_hash": "0" * 64}
    mismatch = _validate_completed_result(changed_job, directory)
    assert mismatch == {
        "valid": False,
        "reusable": False,
        "reason": "request_hash_mismatch",
        "status": "target_not_reachable",
    }
    (directory / "bias_resolution.json").write_text("{}\n", encoding="utf-8")
    tampered = _validate_completed_result(job, directory)
    assert tampered["valid"] is False
    assert tampered["reason"] == "artifact_inventory_or_hash_mismatch"


def test_result_content_hash_excludes_only_its_self_describing_manifest(tmp_path: Path) -> None:
    job, directory = _unreachable_fixture(tmp_path)
    inventory = _artifact_inventory(directory)
    assert [item["path"] for item in inventory] == ["bias_resolution.json"]
    assert all(item["path"] != "catalog_result.json" for item in inventory)
    assert _validate_completed_result(job, directory)["valid"]


def test_reference_interpolation_and_common_band_integration_are_deterministic() -> None:
    frequencies = [1.0, 10.0, 100.0]
    values = [100.0, 10.0, 1.0]
    exact, exact_method = _interpolate_spectrum_value(frequencies, values, 10.0)
    interpolated, interpolation_method = _interpolate_spectrum_value(
        frequencies, values, math.sqrt(10.0)
    )
    assert exact == 10.0
    assert exact_method == "exact_grid"
    assert math.isclose(interpolated, math.sqrt(1000.0), rel_tol=1e-12)
    assert interpolation_method == "log_frequency_log_psd_linear"
    integral, method = _integrate_spectrum_band(frequencies, [2.0, 2.0, 2.0], 1.0, 100.0)
    assert integral == 198.0
    assert method.startswith("trapezoidal_linear_frequency")


def test_explicit_vctrl_path_runs_canonical_finite_difference_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    final = {
        "gm_convergence_relative": 0.001,
        "gds_convergence_relative": 0.002,
        "native_gm_relative_error": 0.003,
        "native_gds_relative_error": 0.004,
        "gm_over_id_per_v": 12.5,
    }
    monkeypatch.setattr("apm.noise._precise_bias_evaluation", lambda *args, **kwargs: final)
    resolved = SimpleNamespace(selector="fixture/general/nmos", kit=SimpleNamespace(vdd_v=1.0))
    result = resolve_explicit_vctrl_bias(
        resolved, SimpleNamespace(), tmp_path, vctrl_v=0.5
    )
    assert result["status"] == "resolved"
    assert result["bias_mode"] == "explicit_vctrl"
    assert result["requested_vctrl_v"] == 0.5
    assert result["achieved_per_v"] == 12.5
    assert json.loads((tmp_path / "bias_resolution.json").read_text())["status"] == "resolved"


def test_noise_catalog_cli_contract_preserves_package_version() -> None:
    parser = build_parser()
    fresh = parser.parse_args(["noise-catalog-check", "--output", "/tmp/apm-n2"])
    resumed = parser.parse_args(
        ["noise-catalog-check", "--output", "/tmp/apm-n2", "--resume"]
    )
    assert fresh.command == "noise-catalog-check"
    assert fresh.resume is False
    assert resumed.resume is True
