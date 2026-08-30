# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from apm.cli import build_parser
from apm.noise import (
    NOISE_SCHEMA,
    NoiseCharacterizationError,
    _noise_wrdata,
    audit_ngspice_log,
    canonical_noise_observables,
    resolve_gm_over_id_bias,
    resolve_noise_device,
)
from apm.noise_fit import NoiseFitError, fit_noise_spectrum
from apm.noise_provenance import ENGINE_PARAMETERS, parse_showmod_values
from apm.noise_validate import SPIKE_SELECTORS

ROOT = Path(__file__).resolve().parents[1]


def _log_grid(start: float = 1.0, stop: float = 1.0e8, ppd: int = 20) -> list[float]:
    decades = math.log10(stop / start)
    return [start * 10.0 ** (index / ppd) for index in range(int(decades * ppd) + 1)]


def test_noise_domain_is_separate_and_spike_selectors_are_exact() -> None:
    assert NOISE_SCHEMA == "apm.noise-characterization.v1"
    assert SPIKE_SELECTORS == (
        "apm350/general/nmos",
        "apm130/lv/nmos",
        "apm045/vtg/nmos",
        "apm016f/svt/nfet",
    )


def test_noise_geometry_preserves_native_planar_and_finfet_semantics() -> None:
    planar = resolve_noise_device("apm350/general/nmos", ROOT)
    assert planar.geometry.result_fields(planar.device.lmin_m) == {
        "w_m": 1.0e-6,
        "l_m": 8.0e-7,
        "l_over_lmin": 2.0,
    }
    finfet = resolve_noise_device("apm016f/svt/nfet", ROOT)
    fields = finfet.geometry.result_fields(finfet.device.lmin_m)
    assert fields == {"l_m": 3.2e-8, "nfin": 1, "l_over_lmin": 2.0}
    assert "w_m" not in fields


def test_canonical_probe_conversion_preserves_sign_scale_and_psd_units() -> None:
    result = canonical_noise_observables(4.0e-24, -2.0e-3, 1.0e-3)
    assert result["s_idrain_terminal_a2_per_hz"] == 4.0e-24
    assert result["y_dg_real_s"] == 2.0e-3
    assert result["y_dg_imag_s"] == -1.0e-3
    assert math.isclose(result["s_vgate_equivalent_v2_per_hz"], 8.0e-19)
    # The function stores PSD directly; it must not take an ASD square root.
    assert result["s_idrain_terminal_a2_per_hz"] != math.sqrt(4.0e-24)
    with pytest.raises(NoiseCharacterizationError, match="non-negative"):
        canonical_noise_observables(-1.0, 1.0, 0.0)
    with pytest.raises(NoiseCharacterizationError, match="transfer"):
        canonical_noise_observables(1.0, 0.0, 0.0)


def test_noise_wrdata_preserves_backend_source_names_without_universal_mapping(
    tmp_path: Path,
) -> None:
    path = tmp_path / "noise.dat"
    path.write_text(
        " frequency frequency inoise_spectrum onoise_native_id onoise_native_weird "
        "onoise_spectrum\n"
        " 1 1 2e-12 3e-24 4e-24 7e-24\n",
        encoding="utf-8",
    )
    records, breakdown = _noise_wrdata(path)
    assert records[0]["onoise_spectrum"] == 7e-24
    assert breakdown == {
        "onoise_native_id": [3e-24],
        "onoise_native_weird": [4e-24],
    }


def test_bias_refinement_resolves_target_instead_of_returning_nearest_coarse_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import apm.noise as noise_module

    coarse = {
        "rows": [
            {"vctrl_v": 0.70, "coarse_gm_over_id_per_v": 16.0},
            {"vctrl_v": 0.80, "coarse_gm_over_id_per_v": 14.0},
        ]
    }

    def fake_coarse(*_args: object, **_kwargs: object) -> dict:
        return coarse

    def fake_precise(
        _resolved: object,
        _toolchain: object,
        _output: Path,
        vctrl_v: float,
        evaluation_id: int,
    ) -> dict:
        # Exact target is at 0.75 V; neither coarse row is acceptable as final.
        return {
            "evaluation_id": evaluation_id,
            "vctrl_v": vctrl_v,
            "gm_over_id_per_v": 30.0 - 20.0 * vctrl_v,
            "gm_convergence_relative": 1.0e-4,
            "gds_convergence_relative": 2.0e-4,
            "native_gm_relative_error": 3.0e-4,
            "native_gds_relative_error": 4.0e-4,
        }

    monkeypatch.setattr(noise_module, "_coarse_bias_sweep", fake_coarse)
    monkeypatch.setattr(noise_module, "_precise_bias_evaluation", fake_precise)
    resolved = SimpleNamespace(selector="fixture/family/device")
    result = resolve_gm_over_id_bias(
        resolved, object(), tmp_path, target_per_v=15.0, relative_tolerance=0.01
    )
    assert result["status"] == "resolved"
    assert math.isclose(result["final"]["vctrl_v"], 0.75)
    assert result["relative_target_error"] == 0.0
    assert result["finite_difference_validation"]["status"] == "pass"
    assert result["native_oracle_validation"]["status"] == "pass"
    assert result["final"]["vctrl_v"] not in {0.70, 0.80}


def test_fail_closed_fit_never_uses_last_point_as_white_floor() -> None:
    frequencies = _log_grid()
    pure_flicker = [1.0e-18 / frequency for frequency in frequencies]
    result = fit_noise_spectrum(frequencies, pure_flicker, gm_s=1.0e-3, temperature_c=27)
    assert result["flicker_fit"]["status"] == "valid"
    assert result["white_fit"]["status"] == "invalid_not_observed"
    assert result["white_fit"]["floor_a2_per_hz"] is None
    assert result["flicker_corner"]["frequency_hz"] is None
    assert result["gamma_eff_total"]["value"] is None


def test_flat_spectrum_records_no_flicker_but_valid_white_region() -> None:
    frequencies = _log_grid()
    values = [3.0e-24] * len(frequencies)
    result = fit_noise_spectrum(frequencies, values, gm_s=1.0e-3, temperature_c=27)
    assert result["flicker_fit"]["status"] == "invalid_not_observed"
    assert result["flicker_fit"]["alpha"] is None
    assert result["white_fit"]["status"] == "valid"
    assert result["white_fit"]["floor_a2_per_hz"] == 3.0e-24
    with pytest.raises(NoiseFitError, match="non-negative"):
        fit_noise_spectrum(frequencies, [-1.0] * len(frequencies), gm_s=1e-3, temperature_c=27)


def test_showmod_parser_requires_parameter_level_values_and_preserves_sentinels() -> None:
    lines = ["APM_NOISE_SHOWMOD_BEGIN"]
    for name, _role in ENGINE_PARAMETERS["bsim4"]:
        if name == "lintnoi":
            lines.append(" lintnoi <<NAN, error = 7>>")
        elif name in {"tnoic", "rnoic"}:
            lines.append(f" {name} ??????????")
        else:
            lines.append(f" {name} 1")
    lines.append("APM_NOISE_SHOWMOD_END")
    parsed = parse_showmod_values("\n".join(lines), "bsim4")
    assert parsed["lintnoi"] == "backend_unavailable"
    assert parsed["tnoic"] == "unknown"
    broken = "APM_NOISE_SHOWMOD_BEGIN\n noimod 1\nAPM_NOISE_SHOWMOD_END"
    with pytest.raises(RuntimeError, match="omitted required"):
        parse_showmod_values(broken, "bsim3")


def test_required_noise_log_must_attest_sparse_and_reject_klu() -> None:
    passed = audit_ngspice_log(
        "Using SPARSE 1.3 as Direct Linear Solver\nngspice-47 done\n", require_sparse=True
    )
    assert passed["required_solver"] == "Sparse"
    with pytest.raises(NoiseCharacterizationError, match="KLU"):
        audit_ngspice_log(
            "Using KLU as Direct Linear Solver\nngspice-47 done\n", require_sparse=True
        )
    with pytest.raises(NoiseCharacterizationError, match="Sparse"):
        audit_ngspice_log("ngspice-47 done\n", require_sparse=True)


def test_analytic_correlation_fixture_is_decisive_and_single_source() -> None:
    common_psd = 1.0e-18
    correlated = common_psd * (1.0 - 0.9) ** 2
    independent = common_psd * (1.0**2 + 0.9**2)
    assert independent / correlated == pytest.approx(181.0)
    source = (ROOT / "validation/fixtures/noise/apm_noise_correlated.va").read_text(
        encoding="utf-8"
    )
    assert source.count("white_noise(") == 1
    assert "common_noise" in source and "copied_noise" in source


def test_noise_cli_contracts_do_not_change_release_version() -> None:
    parser = build_parser()
    noise = parser.parse_args(
        ["noise", "apm130/lv/nmos", "--output", "/tmp/apm-noise-test"]
    )
    assert noise.command == "noise"
    assert noise.selector == "apm130/lv/nmos"
    check = parser.parse_args(["noise-check", "--output", "/tmp/apm-noise-check-test"])
    assert check.command == "noise-check"
    assert (ROOT / "src/apm/__init__.py").read_text(encoding="utf-8").count('"2.0.0"') == 1
