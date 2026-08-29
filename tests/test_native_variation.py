# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from apm.cli import build_parser
from apm.native_variation import (
    NATIVE_CORNER_PROFILES,
    NATIVE_MISMATCH_PROFILE,
    NATIVE_MODES,
    NATIVE_PROCESS_PROFILE,
    _correlation,
    parse_mismatch_parameters,
    parse_process_parameters,
)

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "models/apm130/vendor/ihp-sg13g2-models"


def test_native_cli_and_selected_upstream_profiles_are_explicit(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        ["apm130-native-check", "--output", str(tmp_path / "native")]
    )
    assert args.command == "apm130-native-check"
    assert args.output == tmp_path / "native"
    assert NATIVE_CORNER_PROFILES == (
        "mos_tt",
        "mos_ss",
        "mos_ff",
        "mos_sf",
        "mos_fs",
    )
    assert NATIVE_PROCESS_PROFILE == "mos_tt_stat"
    assert NATIVE_MISMATCH_PROFILE == "mos_tt_mismatch"
    assert NATIVE_MODES == ("corner", "process", "mismatch")
    assert "all" not in NATIVE_MODES


def test_upstream_native_process_profile_is_parsed_without_translating_parameters() -> None:
    parameters = parse_process_parameters(
        VENDOR / "cornerMOSlv.lib",
        VENDOR / "sg13g2_moslv_stat.lib",
    )
    assert len(parameters) == 34
    assert {item.polarity for item in parameters} == {"n", "p"}
    assert all(item.num_sigmas == 1.0 for item in parameters)
    by_name = {item.name: item for item in parameters}
    assert by_name["mc_sg13g2_lv_nmos_ctl"].nominal_value == 1.208
    assert by_name["mc_sg13g2_lv_nmos_ctl"].relative_one_sigma == 0.1562
    assert by_name["mc_sg13g2_lv_pmos_ctl"].nominal_value == 1.957
    assert by_name["mc_sg13g2_lv_pmos_ctl"].relative_one_sigma == 0.188
    assert by_name["mc_sg13g2_lv_pmos_dphiblw"].relative_one_sigma == 1e-9
    assert by_name["mc_sg13g2_lv_pmos_dphiblw"].empirically_variable is False
    assert sum(item.empirically_variable for item in parameters) == 33


def test_upstream_native_mismatch_coefficients_and_wrapper_are_explicit() -> None:
    parameters = parse_mismatch_parameters(VENDOR / "sg13g2_moslv_mismatch.lib")
    assert parameters["n"] == {
        "delvto": 0.0039,
        "factuo": 0.005,
        "dw": 4e-9,
        "dl": 2e-9,
    }
    assert parameters["p"] == {
        "delvto": 0.0022,
        "factuo": 0.0033,
        "dw": 4e-9,
        "dl": 2e-9,
    }
    wrapper = (
        ROOT / "models/apm130/ngspice/apm130_native_mismatch_wrappers.inc"
    ).read_text(encoding="utf-8")
    assert ".subckt apm130_nmos d g s b w=1u l=0.13u" in wrapper
    assert ".subckt apm130_pmos d g s b w=1u l=0.13u" in wrapper
    assert wrapper.lower().count("mm_ok=1") == 2
    for forbidden in (" m=", " nf=", " ng="):
        assert forbidden not in wrapper.lower()


def test_local_correlation_helper_is_python39_compatible() -> None:
    assert _correlation([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(-1.0)
