# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from apm.catalog import load_catalog
from apm.cli import build_parser
from apm.compare import (
    REQUIRED_TECHNOLOGIES,
    ComparisonError,
    _comparison_checks,
    _relations,
    compare_families,
)

ROOT = Path(__file__).resolve().parents[1]


def comparison_row(
    technology_id: str,
    family_id: str,
    polarity: str,
    *,
    finfet: bool,
    kind: str = "threshold_equal_bias",
) -> dict:
    geometry = {"nfin": 1} if finfet else {"w_m": 1e-6}
    return {
        "technology_id": technology_id,
        "family_id": family_id,
        "device_id": (
            "nfet" if finfet and polarity == "n" else "pfet" if finfet else f"{polarity}mos"
        ),
        "public_device": f"{technology_id}_{family_id}_{polarity}",
        "polarity": polarity,
        "comparison_kind": kind,
        "comparison_set_id": None,
        "operating_profile_id": "nominal",
        "operating_profile_origin": "upstream" if not finfet else "apm_selected",
        "operating_profile_evidence": "test",
        "reference_vdd_v": 1.0,
        "terminal_metric_profile_id": "nominal",
        "family_metric_profile_id": "nominal",
        "metric_basis_note": "test basis",
        "architecture": "finfet" if finfet else "planar_bulk",
        "compact_model": "bsim_cmg" if finfet else "bsim4",
        "model_origin": "apm_authored",
        "gate_stack_id": "test",
        "gate_stack_class": "test",
        "threshold_class": "native",
        "temperature_c": 27,
        **geometry,
        "l_m": 2e-7,
        "l_over_lmin": 2.0,
        "bias_mode": "equal_bias",
        "vctrl_v": 0.5,
        "vctrl_over_vdd": 0.5,
        "vout_v": 0.5,
        "vout_over_vdd": 0.5,
        "idmag_a": 1e-5,
        "gm_s": 1.5e-4,
        "gds_s": 5e-6,
        "gm_over_id_per_v": 15.0,
        "gm_over_gds": 30.0,
        "normalization_basis": "fin_count" if finfet else "planar_drawn_width",
        "normalized_unit": "A/fin and F/fin" if finfet else "A/m and F/m",
        "id_normalized": 1e-5,
        "gm_normalized": 1.5e-4,
        "vth_high_magnitude_v": 0.4,
        "dibl_v_per_v": 0.05,
        "ion_a": 2e-5,
        "ioff_a": 1e-10,
        "ion_normalized": 2e-5,
        "ioff_normalized": 1e-10,
        "log10_ion_over_ioff": 5.3,
        "ss_v_per_decade": 0.08,
        "ss_r_squared": 0.999,
        "capacitance_bias_mode": "equal_bias",
        "capacitance_frequency_hz": 1e5,
        "cgg_f": 1e-15,
        "cgd_f": 2e-16,
        "cgs_f": 5e-16,
        "cgg_normalized": 1e-15,
        "cgd_normalized": 2e-16,
        "cgs_normalized": 5e-16,
        "variation_origin": "none",
        "variation_mode": "nominal",
        "source_result_directory": "/tmp/test",
        "source_bias_view_directory": None,
    }


def test_comparison_cli_and_catalog_sets_are_concrete_contracts(tmp_path: Path) -> None:
    parser = build_parser()
    pair = parser.parse_args(
        ["compare", "apm350", "apm016f/svt", "--output", str(tmp_path / "pair")]
    )
    assert pair.command == "compare"
    assert pair.selector_a == "apm350"
    assert pair.selector_b == "apm016f/svt"
    assert pair.output == tmp_path / "pair"
    all_families = parser.parse_args(
        ["characterization-check", "--output", str(tmp_path / "all")]
    )
    assert all_families.command == "characterization-check"
    assert REQUIRED_TECHNOLOGIES == (
        "apm350",
        "apm130",
        "apm045",
        "apm022",
        "apm016f",
    )
    catalog = load_catalog(ROOT)
    assert catalog.technology("apm045").comparison_set("threshold").members == (
        "vtl",
        "vtg",
        "vth",
    )
    assert catalog.technology("apm045").comparison_set("gate_stack").members == (
        "vtg",
        "thkox",
    )


def test_cross_process_relations_do_not_mix_planar_and_finfet_bases() -> None:
    rows = [
        comparison_row("apm022", "svt", polarity, finfet=False)
        for polarity in ("n", "p")
    ] + [
        comparison_row("apm016f", "svt", polarity, finfet=True)
        for polarity in ("n", "p")
    ]
    checks = _comparison_checks(
        rows, ("apm022/svt", "apm016f/svt"), "threshold_equal_bias"
    )
    assert checks["overall_pass"] is True
    relations = _relations(rows)
    assert all(item["normalized_current_ratio_second_over_first"] is None for item in relations)
    assert all(
        item["normalized_capacitance_ratio_second_over_first"] is None for item in relations
    )
    assert all(
        item["normalization_ratio_status"]
        == "not_reported_across_per_width_and_per_fin_bases"
        for item in relations
    )


def test_same_basis_planar_relations_report_normalized_ratios() -> None:
    rows = [
        comparison_row(technology, "anchor", polarity, finfet=False)
        for technology in ("apm045", "apm022")
        for polarity in ("n", "p")
    ]
    for row in rows:
        if row["technology_id"] == "apm045":
            row["id_normalized"] *= 2.0
            row["cgg_normalized"] *= 3.0
    relations = _relations(rows)
    assert all(
        item["normalized_current_ratio_second_over_first"] == pytest.approx(2.0)
        for item in relations
    )
    assert all(
        item["normalized_capacitance_ratio_second_over_first"] == pytest.approx(3.0)
        for item in relations
    )
    assert all(item["normalization_ratio_status"] == "comparable_same_basis" for item in relations)


def test_comparison_rejects_identical_selectors_before_running_tools() -> None:
    with pytest.raises(ComparisonError, match="distinct"):
        compare_families("apm045/vtg", "apm045/vtg")
