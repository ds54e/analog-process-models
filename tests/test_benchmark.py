# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from apm.benchmark import (
    BenchmarkError,
    load_benchmark_configuration,
    load_resolved_sample,
    resolve_corner,
    resolve_monte_carlo,
    resolved_passive_value_at_temperature,
    write_resolved_sample,
)

ROOT = Path(__file__).resolve().parents[1]


def example_request() -> dict:
    return json.loads((ROOT / "examples/benchmark_request.json").read_text(encoding="utf-8"))


def by_id(sample: dict, collection: str) -> dict[str, dict]:
    return {item["id"]: item for item in sample[collection]}


def test_benchmark_values_are_frozen_and_release_placeholder_free() -> None:
    configuration = load_benchmark_configuration(ROOT)
    variation = configuration["variation"]
    passives = configuration["passives"]
    assert variation["status"] == "v1-values-frozen-2026-08-30"
    assert passives["status"] == "v1-values-frozen-2026-08-30"
    assert variation["mos"]["process"]["vth_shift_sigma"] == 0.012
    assert variation["mos"]["process"]["drive_shift_sigma"] == 0.04
    assert variation["mos"]["mismatch"]["vth_shift_sigma_ref"] == 0.008
    assert variation["mos"]["mismatch"]["drive_shift_sigma_ref"] == 0.025
    assert passives["resistor"]["process_sigma"] == 0.02
    assert passives["capacitor"]["mismatch_sigma_ref"] == 0.01
    for path in (ROOT / "variation/benchmark_v1.toml", ROOT / "passives/benchmark_v1.toml"):
        assert "TBD" not in path.read_text(encoding="utf-8")


def test_same_seed_is_identical_and_different_seed_differs() -> None:
    request = example_request()
    first = resolve_monte_carlo(request, mode="all", seed=20260830, root=ROOT)
    repeated = resolve_monte_carlo(request, mode="all", seed=20260830, root=ROOT)
    different = resolve_monte_carlo(request, mode="all", seed=20260831, root=ROOT)
    assert first == repeated
    assert first["sample_id"] == repeated["sample_id"]
    assert first["sample_id"] != different["sample_id"]
    assert first["draw_order"] != different["draw_order"]


def test_modes_share_draws_but_apply_only_the_documented_components() -> None:
    request = example_request()
    process = resolve_monte_carlo(request, mode="process", seed=77, root=ROOT)
    mismatch = resolve_monte_carlo(request, mode="mismatch", seed=77, root=ROOT)
    combined = resolve_monte_carlo(request, mode="all", seed=77, root=ROOT)
    assert process["draw_order"] == mismatch["draw_order"] == combined["draw_order"]
    assert len(combined["draw_order"]) == 24  # six globals, two per MOS, one per passive
    process_mos = by_id(process, "mos_instances")
    mismatch_mos = by_id(mismatch, "mos_instances")
    combined_mos = by_id(combined, "mos_instances")
    for instance_id, all_result in combined_mos.items():
        polarity = all_result["polarity"]
        global_result = combined["global_process"]["mos"][polarity]
        local_result = mismatch_mos[instance_id]["local_applied"]
        assert process_mos[instance_id]["local_applied"] == {
            "vth_shift_v": 0.0,
            "drive_shift_fraction": 0.0,
        }
        assert mismatch["global_process"]["mos"][polarity]["applied_vth_shift_v"] == 0.0
        assert all_result["total_intents"]["vth_shift_v"] == pytest.approx(
            global_result["applied_vth_shift_v"] + local_result["vth_shift_v"]
        )
        assert all_result["total_intents"]["drive_factor"] == pytest.approx(
            (1.0 + global_result["applied_drive_shift_fraction"])
            * (1.0 + local_result["drive_shift_fraction"])
        )


def test_matching_size_uses_planar_area_and_finfet_nfin_length() -> None:
    request = {
        "schema": "apm.benchmark-request.v1",
        "instances": {
            "mos": [
                {
                    "id": "punit",
                    "kit_id": "apm045",
                    "polarity": "n",
                    "geometry": {"w_m": 1e-6, "l_m": 1e-7},
                },
                {
                    "id": "pquad",
                    "kit_id": "apm045",
                    "polarity": "n",
                    "geometry": {"w_m": 2e-6, "l_m": 2e-7},
                },
                {
                    "id": "funit",
                    "kit_id": "apm016f",
                    "polarity": "n",
                    "geometry": {"l_m": 3.2e-8, "nfin": 1},
                },
                {
                    "id": "fquad",
                    "kit_id": "apm016f",
                    "polarity": "n",
                    "geometry": {"l_m": 6.4e-8, "nfin": 2},
                },
            ],
            "resistors": [],
            "capacitors": [],
        },
    }
    sample = resolve_monte_carlo(request, mode="mismatch", seed=9, root=ROOT)
    results = by_id(sample, "mos_instances")
    assert results["punit"]["match_size"] == pytest.approx(1.0)
    assert results["pquad"]["match_size"] == pytest.approx(4.0)
    assert results["funit"]["match_size"] == pytest.approx(1.0)
    assert results["fquad"]["match_size"] == pytest.approx(4.0)
    assert "w_m" not in results["funit"]["geometry"]
    for result in results.values():
        z_value = result["local_random_draws"]["vth_shift_z"]
        expected = 0.008 * z_value / math.sqrt(result["match_size"])
        assert result["local_sampled"]["vth_shift_v"] == pytest.approx(expected)


def test_fourfold_matching_size_halves_local_sigma_for_the_same_draw() -> None:
    request = example_request()
    request["instances"]["mos"] = [request["instances"]["mos"][0]]
    request["instances"]["resistors"] = []
    request["instances"]["capacitors"] = []
    unit = resolve_monte_carlo(request, mode="mismatch", seed=1234, root=ROOT)
    request["instances"]["mos"][0]["geometry"] = {"w_m": 2.0e-6, "l_m": 5.2e-7}
    quadruple = resolve_monte_carlo(request, mode="mismatch", seed=1234, root=ROOT)
    unit_instance = unit["mos_instances"][0]
    quadruple_instance = quadruple["mos_instances"][0]
    assert unit_instance["match_size"] == pytest.approx(1.0)
    assert quadruple_instance["match_size"] == pytest.approx(4.0)
    assert unit_instance["local_random_draws"] == quadruple_instance["local_random_draws"]
    assert quadruple_instance["local_sampled"]["vth_shift_v"] == pytest.approx(
        unit_instance["local_sampled"]["vth_shift_v"] / 2.0
    )
    assert quadruple_instance["local_sampled"]["drive_shift_fraction"] == pytest.approx(
        unit_instance["local_sampled"]["drive_shift_fraction"] / 2.0
    )


def test_corner_semantics_map_canonical_polarity_to_measured_raw_signs() -> None:
    fast = resolve_corner(example_request(), corner="bench_ff", root=ROOT)
    results = by_id(fast, "mos_instances")
    for result in results.values():
        assert result["total_intents"]["vth_shift_v"] == pytest.approx(-0.036)
        assert result["total_intents"]["drive_shift_fraction"] == pytest.approx(0.12)
        assert result["raw_adapter"]["drive_value"] > 1.0
    assert results["mn130"]["raw_adapter"]["vth_value"] < 0.0
    assert results["mp130"]["raw_adapter"]["vth_value"] < 0.0
    assert results["mn045"]["raw_adapter"]["vth_value"] < 0.0
    assert results["mp045"]["raw_adapter"]["vth_value"] > 0.0
    assert results["mn022"]["raw_adapter"]["vth_value"] < 0.0
    assert results["mp022"]["raw_adapter"]["vth_value"] > 0.0
    assert results["mn016f"]["raw_adapter"]["vth_value"] > 0.0
    assert results["mp016f"]["raw_adapter"]["vth_value"] > 0.0
    assert all(result["raw_adapter"]["vth_within_calibrated_raw_range"] for result in results.values())
    assert all(
        result["raw_adapter"]["drive_within_calibrated_raw_range"]
        for result in results.values()
    )


def test_passive_composition_and_temperature_are_explicit() -> None:
    process = resolve_monte_carlo(example_request(), mode="process", seed=42, root=ROOT)
    mismatch = resolve_monte_carlo(example_request(), mode="mismatch", seed=42, root=ROOT)
    combined = resolve_monte_carlo(example_request(), mode="all", seed=42, root=ROOT)
    process_results = by_id(process, "passive_instances")
    mismatch_results = by_id(mismatch, "passive_instances")
    combined_results = by_id(combined, "passive_instances")
    for instance_id, result in combined_results.items():
        nominal = result["value"]
        expected_factor = process_results[instance_id]["resolved_scale_factor"] * mismatch_results[
            instance_id
        ]["resolved_scale_factor"]
        assert result["resolved_scale_factor"] == pytest.approx(expected_factor)
        assert result["resolved_value_at_27c"] == pytest.approx(nominal * expected_factor)
        expected_85 = result["resolved_value_at_27c"] * (
            1.0 + result["tc1_per_c"] * (85.0 - 27.0)
        )
        assert resolved_passive_value_at_temperature(result, 85.0) == pytest.approx(expected_85)


def test_resolved_sample_hash_detects_tampering_and_write_is_non_destructive(tmp_path: Path) -> None:
    sample = resolve_monte_carlo(example_request(), mode="all", seed=5, root=ROOT)
    output = tmp_path / "sample.json"
    assert write_resolved_sample(sample, output) == output
    assert write_resolved_sample(sample, output) == output
    assert load_resolved_sample(output) == sample
    tampered = json.loads(output.read_text(encoding="utf-8"))
    tampered["rng"]["seed"] = 6
    output.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(BenchmarkError, match="hash mismatch"):
        load_resolved_sample(output)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda request: request["instances"]["mos"][6]["geometry"].update(nfin=1.5), "nfin"),
        (
            lambda request: request["instances"]["resistors"][0].update(match_size=0.0),
            "match_size",
        ),
    ],
)
def test_invalid_geometry_or_matching_size_is_rejected(change, message: str) -> None:
    request = example_request()
    change(request)
    with pytest.raises(BenchmarkError, match=message):
        resolve_monte_carlo(request, mode="all", seed=1, root=ROOT)
