# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from apm.cli import TECHNOLOGIES, build_parser
from apm.compare import (
    REQUIRED_KITS,
    ComparisonError,
    _comparison_checks,
    _pairwise_relations,
    compare_technologies,
)


def comparison_row(kit_id: str, polarity: str, *, finfet: bool) -> dict:
    geometry = {"nfin": 1} if finfet else {"w_m": 1e-6}
    return {
        "kit_id": kit_id,
        "public_device": f"{kit_id}_{polarity}",
        "polarity": polarity,
        "compact_model": "bsim_cmg" if finfet else "bsim4",
        "model_revision": "test",
        "architecture": "finfet" if finfet else "planar_bulk",
        "nominal_vdd_v": 1.0,
        "model_lmin_m": 1e-7,
        **geometry,
        "l_m": 2e-7,
        "l_over_lmin": 2.0,
        "vctrl_v": 0.5,
        "vctrl_over_vdd": 0.5,
        "vout_v": 0.5,
        "vout_over_vdd": 0.5,
        "idmag_a": 1e-5,
        "gm_s": 1.5e-4,
        "gds_s": 5e-6,
        "gm_over_id_per_v": 15.0,
        "gm_over_gds": 30.0,
        "normalization_basis": "per_fin" if finfet else "per_um_drawn_width",
        "normalization_count": 1,
        "id_normalized_a_per_unit": 1e-5,
        "gm_normalized_s_per_unit": 1.5e-4,
        "vth_high_magnitude_v": 0.4,
        "dibl_v_per_v": 0.05,
        "capacitance_frequency_hz": 1e5,
        "cgg_f": 1e-15,
        "cgd_f": 2e-16,
        "cgs_f": 5e-16,
        "cgg_normalized_f_per_unit": 1e-15,
        "cgd_normalized_f_per_unit": 2e-16,
        "cgs_normalized_f_per_unit": 5e-16,
        "variation_origin": "none",
        "variation_mode": "nominal",
        "source_result_directory": "/tmp/test",
    }


def test_comparison_cli_and_all_kit_runner_are_concrete_contracts(tmp_path: Path) -> None:
    parser = build_parser()
    pair = parser.parse_args(
        ["compare", "apm350", "apm016f", "--output", str(tmp_path / "pair")]
    )
    assert pair.command == "compare"
    assert pair.technology_a == "apm350"
    assert pair.technology_b == "apm016f"
    assert pair.output == tmp_path / "pair"
    all_kits = parser.parse_args(
        ["characterization-check", "--output", str(tmp_path / "all")]
    )
    assert all_kits.command == "characterization-check"
    assert all_kits.output == tmp_path / "all"
    assert REQUIRED_KITS == TECHNOLOGIES


def test_normalized_comparison_preserves_planar_and_finfet_geometry_semantics() -> None:
    rows = [
        comparison_row(kit, polarity, finfet=kit == "apm016f")
        for kit in ("apm022", "apm016f")
        for polarity in ("n", "p")
    ]
    checks = _comparison_checks(rows, ("apm022", "apm016f"))
    assert checks["overall_pass"] is True
    relations = _pairwise_relations(rows, "apm022", "apm016f")
    assert all(item["normalized_current_ratio_b_over_a"] is None for item in relations)
    assert all(item["normalized_capacitance_ratio_b_over_a"] is None for item in relations)
    assert all(
        item["normalization_ratio_status"]
        == "not_reported_across_per_width_and_per_fin_bases"
        for item in relations
    )


def test_pairwise_planar_ratios_are_reported_only_on_the_same_basis() -> None:
    rows = [
        comparison_row(kit, polarity, finfet=False)
        for kit in ("apm045", "apm022")
        for polarity in ("n", "p")
    ]
    for row in rows:
        if row["kit_id"] == "apm022":
            row["id_normalized_a_per_unit"] *= 2.0
            row["cgg_normalized_f_per_unit"] *= 3.0
    relations = _pairwise_relations(rows, "apm045", "apm022")
    assert all(item["normalized_current_ratio_b_over_a"] == pytest.approx(2.0) for item in relations)
    assert all(
        item["normalized_capacitance_ratio_b_over_a"] == pytest.approx(3.0)
        for item in relations
    )
    assert all(item["normalization_ratio_status"] == "comparable_same_basis" for item in relations)


def test_comparison_rejects_identical_technologies_before_running_tools() -> None:
    with pytest.raises(ComparisonError, match="distinct"):
        compare_technologies("apm045", "apm045")
