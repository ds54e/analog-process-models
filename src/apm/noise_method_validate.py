# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""V3-N1 noise acquisition and fit-method qualification."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model_build import sha256_file
from .noise import (
    ACQUISITION_POLICY_ID,
    ACQUISITION_POLICY_VERSION,
    ADAPTIVE_FREQUENCY_STOPS_HZ,
    DEFAULT_FREQUENCY_START_HZ,
    DEFAULT_POINTS_PER_DECADE,
    NOISE_SCHEMA,
    _prepare_output,
    characterize_noise_selector,
)
from .noise_fit import FIT_METHOD_IDENTITY, NoiseFitError, fit_noise_spectrum
from .noise_validate import (
    SPIKE_SELECTORS,
    _cmg_correlation_diagnostic,
    _v2_model_immutability,
    validate_noise_spike,
)
from .paths import repository_root, state_directory
from .toolchain import Toolchain, resolve_toolchain, run_checked

LOW_VDS_EFFECTIVE_V = 0.05


class NoiseMethodValidationError(RuntimeError):
    """The V3-N1 method qualification contract failed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_output(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return state_directory(root) / "results" / f"v3-n1-noise-method-{stamp}"


def _log_grid(stop_hz: float, points_per_decade: int = 20) -> list[float]:
    count = round(math.log10(stop_hz) * points_per_decade)
    return [10.0 ** (index / points_per_decade) for index in range(count + 1)]


def _relative_error(observed: float, expected: float) -> float:
    return abs(observed - expected) / max(abs(observed), abs(expected), 1.0e-300)


def qualify_synthetic_fit_method() -> dict[str, Any]:
    """Exercise every normative deterministic V3-N1 synthetic case."""

    cases: list[dict[str, Any]] = []

    frequencies = _log_grid(1.0e8)
    white_floor = 3.0e-24
    pure_white = fit_noise_spectrum(
        frequencies,
        [white_floor] * len(frequencies),
        gm_s=1.0e-3,
        temperature_c=27.0,
    )
    pure_white_error = _relative_error(
        pure_white["white_fit"]["floor_a2_per_hz"], white_floor
    )
    cases.append(
        {
            "id": "pure_white",
            "status": (
                "pass"
                if pure_white["white_fit"]["status"] == "valid"
                and pure_white["flicker_fit"]["status"] == "invalid_not_observed"
                and pure_white_error <= 1.0e-12
                else "fail"
            ),
            "expected_white_floor_a2_per_hz": white_floor,
            "observed_white_floor_a2_per_hz": pure_white["white_fit"][
                "floor_a2_per_hz"
            ],
            "white_floor_relative_error": pure_white_error,
            "flicker_status": pure_white["flicker_fit"]["status"],
        }
    )

    flicker_alpha = 1.2
    flicker_a = 8.0e-18
    pure_flicker = fit_noise_spectrum(
        frequencies,
        [flicker_a / frequency**flicker_alpha for frequency in frequencies],
        gm_s=1.0e-3,
        temperature_c=27.0,
    )
    alpha_error = abs(pure_flicker["flicker_fit"]["alpha"] - flicker_alpha)
    coefficient_error = _relative_error(
        pure_flicker["flicker_fit"]["coefficient_a2_per_hz_at_1hz"], flicker_a
    )
    cases.append(
        {
            "id": "pure_flicker",
            "status": (
                "pass"
                if pure_flicker["flicker_fit"]["status"] == "valid"
                and pure_flicker["white_fit"]["status"] == "invalid_not_observed"
                and alpha_error <= 1.0e-10
                and coefficient_error <= 1.0e-10
                else "fail"
            ),
            "expected_alpha": flicker_alpha,
            "observed_alpha": pure_flicker["flicker_fit"]["alpha"],
            "alpha_absolute_error": alpha_error,
            "coefficient_relative_error": coefficient_error,
            "white_status": pure_flicker["white_fit"]["status"],
        }
    )

    frequencies = _log_grid(1.0e10)
    known_a = 1.0e-18
    known_white = 1.0e-24
    known_corner = known_a / known_white
    combined = fit_noise_spectrum(
        frequencies,
        [known_a / frequency + known_white for frequency in frequencies],
        gm_s=1.0e-3,
        temperature_c=27.0,
    )
    combined_corner_error = _relative_error(
        combined["flicker_corner"]["frequency_hz"], known_corner
    )
    combined_floor_error = _relative_error(
        combined["white_fit"]["floor_a2_per_hz"], known_white
    )
    combined_alpha_error = abs(combined["flicker_fit"]["alpha"] - 1.0)
    cases.append(
        {
            "id": "known_flicker_white_corner",
            "status": (
                "pass"
                if combined["flicker_fit"]["status"] == "valid"
                and combined["white_fit"]["status"] == "valid"
                and combined["flicker_corner"]["status"] == "valid"
                and combined_alpha_error <= 0.05
                and combined_floor_error <= 0.02
                and combined_corner_error <= 0.30
                else "fail"
            ),
            "expected_corner_hz": known_corner,
            "observed_corner_hz": combined["flicker_corner"]["frequency_hz"],
            "corner_relative_tolerance": 0.30,
            "corner_relative_error": combined_corner_error,
            "alpha_absolute_tolerance": 0.05,
            "alpha_absolute_error": combined_alpha_error,
            "white_floor_relative_tolerance": 0.02,
            "white_floor_relative_error": combined_floor_error,
        }
    )

    frequencies = _log_grid(1.0e11)
    rise_start_hz = 1.0e9
    interior = fit_noise_spectrum(
        frequencies,
        [
            known_a / frequency
            + known_white
            + known_white * (frequency / rise_start_hz) ** 2
            for frequency in frequencies
        ],
        gm_s=1.0e-3,
        temperature_c=27.0,
    )
    interior_floor_error = _relative_error(
        interior["white_fit"]["floor_a2_per_hz"], known_white
    )
    cases.append(
        {
            "id": "interior_white_plateau_before_high_frequency_rise",
            "status": (
                "pass"
                if interior["white_fit"]["status"] == "valid"
                and interior["white_fit"]["window_max_hz"] < rise_start_hz
                and interior["white_fit"]["window_max_hz"] < frequencies[-1]
                and interior_floor_error <= 0.10
                else "fail"
            ),
            "rise_scale_hz": rise_start_hz,
            "selected_white_start_hz": interior["white_fit"]["window_min_hz"],
            "selected_white_stop_hz": interior["white_fit"]["window_max_hz"],
            "white_floor_relative_tolerance": 0.10,
            "white_floor_relative_error": interior_floor_error,
            "selected_highest_decade": interior["white_fit"]["window_max_hz"]
            >= frequencies[-1] / 10.0,
        }
    )

    frequencies = _log_grid(1.0e4)
    truncated = fit_noise_spectrum(
        frequencies,
        [known_a / frequency + known_white for frequency in frequencies],
        gm_s=1.0e-3,
        temperature_c=27.0,
    )
    cases.append(
        {
            "id": "truncated_no_white_plateau",
            "status": (
                "pass"
                if truncated["white_fit"]["status"] == "invalid_not_observed"
                and truncated["white_fit"]["floor_a2_per_hz"] is None
                and truncated["flicker_corner"]["frequency_hz"] is None
                and truncated["gamma_eff_total"]["value"] is None
                else "fail"
            ),
            "white_status": truncated["white_fit"]["status"],
            "white_floor": truncated["white_fit"]["floor_a2_per_hz"],
            "corner": truncated["flicker_corner"]["frequency_hz"],
            "gamma": truncated["gamma_eff_total"]["value"],
        }
    )

    frequencies = _log_grid(1.0e9)
    no_flicker = fit_noise_spectrum(
        frequencies,
        [known_white * (1.0 + (frequency / 1.0e7) ** 2) for frequency in frequencies],
        gm_s=1.0e-3,
        temperature_c=27.0,
    )
    cases.append(
        {
            "id": "no_flicker_component",
            "status": (
                "pass"
                if no_flicker["flicker_fit"]["status"] == "invalid_not_observed"
                and no_flicker["white_fit"]["status"] == "valid"
                else "fail"
            ),
            "flicker_status": no_flicker["flicker_fit"]["status"],
            "white_status": no_flicker["white_fit"]["status"],
        }
    )

    frequencies = _log_grid(10.0)
    insufficient = fit_noise_spectrum(
        frequencies,
        [known_a / frequency for frequency in frequencies],
        gm_s=1.0e-3,
        temperature_c=27.0,
    )
    cases.append(
        {
            "id": "insufficient_candidate_span",
            "status": (
                "pass"
                if insufficient["flicker_fit"]["status"] == "invalid_not_observed"
                and insufficient["white_fit"]["status"] == "invalid_not_observed"
                and insufficient["candidate_regions"]["flicker"]
                and all(
                    not item["eligible"]
                    for item in insufficient["candidate_regions"]["flicker"]
                )
                else "fail"
            ),
            "flicker_candidates": insufficient["candidate_regions"]["flicker"],
        }
    )

    malformed_checks: list[dict[str, Any]] = []
    malformed_inputs = (
        ("non_finite_frequency", [1.0, math.inf], [1.0, 1.0]),
        ("non_finite_psd", [1.0, 2.0], [1.0, math.nan]),
        ("non_increasing_frequency", [1.0, 1.0], [1.0, 1.0]),
        ("negative_psd", [1.0, 2.0], [1.0, -1.0]),
        ("length_mismatch", [1.0, 2.0], [1.0]),
    )
    for identifier, malformed_f, malformed_s in malformed_inputs:
        try:
            fit_noise_spectrum(
                malformed_f, malformed_s, gm_s=1.0e-3, temperature_c=27.0
            )
        except NoiseFitError as error:
            malformed_checks.append(
                {"id": identifier, "status": "pass", "error": str(error)}
            )
        else:
            malformed_checks.append({"id": identifier, "status": "fail", "error": None})
    zero_result = fit_noise_spectrum(
        [1.0, 10.0, 100.0], [0.0, 0.0, 0.0], gm_s=1.0e-3, temperature_c=27.0
    )
    zero_pass = (
        zero_result["zero_psd_point_count"] == 3
        and zero_result["flicker_fit"]["status"] == "invalid_not_observed"
        and zero_result["white_fit"]["status"] == "invalid_not_observed"
        and zero_result["white_fit"]["floor_a2_per_hz"] is None
    )
    cases.append(
        {
            "id": "zero_non_finite_and_malformed_fail_closed",
            "status": (
                "pass"
                if all(item["status"] == "pass" for item in malformed_checks) and zero_pass
                else "fail"
            ),
            "malformed_checks": malformed_checks,
            "zero_psd_check": {
                "status": "pass" if zero_pass else "fail",
                "white_floor": zero_result["white_fit"]["floor_a2_per_hz"],
            },
        }
    )

    report = {
        "schema": "apm.noise-fit-synthetic-qualification.v1",
        "method_identity": FIT_METHOD_IDENTITY,
        "status": "pass" if all(item["status"] == "pass" for item in cases) else "fail",
        "cases": cases,
        "acceptance_result": f"{sum(item['status'] == 'pass' for item in cases)}/{len(cases)}",
        "thresholds": combined["thresholds"],
        "local_slope_estimator": combined["local_slope_estimator"],
    }
    if report["status"] != "pass":
        failed = [item["id"] for item in cases if item["status"] != "pass"]
        raise NoiseMethodValidationError(f"synthetic fit qualification failed: {failed}")
    return report


def _read_single_csv(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise NoiseMethodValidationError(f"expected one row in {path}")
    return rows[0]


def _nullable_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
    directory = Path(result["output_directory"])
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    acquisition = json.loads((directory / "acquisition.json").read_text(encoding="utf-8"))
    snapshot = json.loads(
        (directory / "noise_model_snapshot.json").read_text(encoding="utf-8")
    )
    sources = json.loads((directory / "source_breakdown.json").read_text(encoding="utf-8"))
    metrics = _read_single_csv(directory / "noise_metrics.csv")
    operating_point = _read_single_csv(directory / "operating_points.csv")
    with (directory / "noise_spectrum.csv").open(encoding="utf-8", newline="") as handle:
        spectrum = list(csv.DictReader(handle))
    required_spectrum_fields = {
        "s_idrain_terminal_a2_per_hz",
        "s_vgate_equivalent_v2_per_hz",
        "y_dg_real_s",
        "y_dg_imag_s",
    }
    psd = [float(item["s_idrain_terminal_a2_per_hz"]) for item in spectrum]
    transfer_finite = all(
        math.isfinite(float(item[field]))
        for item in spectrum
        for field in ("s_vgate_equivalent_v2_per_hz", "y_dg_real_s", "y_dg_imag_s")
    )
    return {
        "status": result["status"],
        "schema": metadata["schema"],
        "selector": result["selector"],
        "output_directory": str(directory),
        "effective_vout_v": float(operating_point["vout_v"]),
        "gm_over_id_per_v": float(operating_point["gm_over_id_per_v"]),
        "gm_over_id_relative_error": float(operating_point["gm_over_id_relative_error"]),
        "gm_convergence_relative": float(operating_point["gm_convergence_relative"]),
        "gds_convergence_relative": float(operating_point["gds_convergence_relative"]),
        "minimum_drain_psd_a2_per_hz": min(psd),
        "maximum_drain_psd_a2_per_hz": max(psd),
        "spectrum_finite_nonnegative": all(math.isfinite(value) and value >= 0.0 for value in psd),
        "canonical_spectrum_fields_present": required_spectrum_fields.issubset(spectrum[0]),
        "gate_referred_and_transfer_finite": transfer_finite,
        "fit_method_identity": (
            f"{metrics['fit_method_id']}@{metrics['fit_method_version']}"
        ),
        "flicker_fit_status": metrics["flicker_fit_status"],
        "flicker_fit_reason": metrics["flicker_fit_reason"] or None,
        "flicker_alpha": _nullable_float(metrics["flicker_alpha"]),
        "flicker_region_start_hz": _nullable_float(metrics["flicker_window_min_hz"]),
        "flicker_region_stop_hz": _nullable_float(metrics["flicker_window_max_hz"]),
        "white_fit_status": metrics["white_fit_status"],
        "white_fit_reason": metrics["white_fit_reason"] or None,
        "white_floor_a2_per_hz": _nullable_float(metrics["white_floor_a2_per_hz"]),
        "white_region_start_hz": _nullable_float(metrics["white_window_min_hz"]),
        "white_region_stop_hz": _nullable_float(metrics["white_window_max_hz"]),
        "flicker_corner_status": metrics["flicker_corner_status"],
        "flicker_corner_hz": _nullable_float(metrics["flicker_corner_hz"]),
        "gamma_eff_total": _nullable_float(metrics["gamma_eff_total"]),
        "acquisition": acquisition,
        "effective_parameter_count": len(snapshot["parameters"]),
        "effective_parameter_snapshot_available": snapshot[
            "effective_parameter_snapshot_available"
        ],
        "parameter_value_sources": sorted(
            {item["value_source"] for item in snapshot["parameters"]}
        ),
        "source_vector_names": [item["raw_vector_name"] for item in sources["sources"]],
        "metadata_sha256": sha256_file(directory / "metadata.json"),
        "acquisition_sha256": sha256_file(directory / "acquisition.json"),
        "noise_spectrum_sha256": sha256_file(directory / "noise_spectrum.csv"),
        "noise_metrics_sha256": sha256_file(directory / "noise_metrics.csv"),
        "source_breakdown_sha256": sha256_file(directory / "source_breakdown.json"),
        "noise_model_snapshot_sha256": sha256_file(
            directory / "noise_model_snapshot.json"
        ),
        "fit_diagnostics_sha256": sha256_file(directory / "fit_diagnostics.json"),
    }


def _acquisition_valid(summary: dict[str, Any]) -> bool:
    acquisition = summary["acquisition"]
    attempts = acquisition["attempts"]
    observed_stops = [item["stop_hz"] for item in attempts]
    expected_prefix = list(ADAPTIVE_FREQUENCY_STOPS_HZ[: len(attempts)])
    if (
        acquisition["policy_id"] != ACQUISITION_POLICY_ID
        or acquisition["policy_version"] != ACQUISITION_POLICY_VERSION
        or acquisition["base_start_hz"] != DEFAULT_FREQUENCY_START_HZ
        or acquisition["base_stop_hz"] != ADAPTIVE_FREQUENCY_STOPS_HZ[0]
        or acquisition["points_per_decade"] != DEFAULT_POINTS_PER_DECADE
        or observed_stops != expected_prefix
        or not attempts
    ):
        return False
    if any(
        item["start_hz"] != DEFAULT_FREQUENCY_START_HZ
        or item["points_per_decade"] != DEFAULT_POINTS_PER_DECADE
        or item["sparse_attestation_count"] < 1
        or item["klu_attestation_count"] != 0
        or item["log_critical_diagnostic_count"] != 0
        for item in attempts
    ):
        return False
    first_white = next(
        (index for index, item in enumerate(attempts) if item["white_region_observed"]), None
    )
    if first_white is not None:
        return (
            first_white == len(attempts) - 1
            and acquisition["selected_attempt"] == attempts[-1]["attempt_id"]
            and acquisition["white_region_status"] == "observed"
        )
    return (
        observed_stops[-1] == ADAPTIVE_FREQUENCY_STOPS_HZ[-1]
        and acquisition["white_region_status"]
        == "white_region_not_observed_within_search_cap"
        and not acquisition["white_region_observed"]
    )


def _fail_closed_metrics(summary: dict[str, Any]) -> bool:
    if summary["white_fit_status"] == "valid":
        return summary["white_floor_a2_per_hz"] is not None and summary["gamma_eff_total"] is not None
    return (
        summary["white_floor_a2_per_hz"] is None
        and summary["flicker_corner_hz"] is None
        and summary["gamma_eff_total"] is None
    )


def validate_noise_method(
    output: Path | None = None,
    *,
    root: Path | None = None,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    """Run the complete real-tool V3-N1 qualification."""

    resolved_root = (root or repository_root()).resolve()
    result_directory = _prepare_output(output or _default_output(resolved_root))
    selected_toolchain = toolchain or resolve_toolchain(resolved_root)
    synthetic = qualify_synthetic_fit_method()
    _write_json(result_directory / "synthetic_fit_report.json", synthetic)

    n0_report = validate_noise_spike(
        result_directory / "v3_n0_regression",
        root=resolved_root,
        toolchain=selected_toolchain,
    )
    canonical = [_result_summary(item) for item in n0_report["mos_results"]]

    low_results: list[dict[str, Any]] = []
    low_directories: dict[str, Path] = {}
    for selector in SPIKE_SELECTORS:
        directory = result_directory / "low_vds" / selector.replace("/", "__")
        result = characterize_noise_selector(
            selector,
            directory,
            vout_v=LOW_VDS_EFFECTIVE_V,
            root=resolved_root,
            toolchain=selected_toolchain,
        )
        low_results.append(result)
        low_directories[selector] = directory
    low_vds = [_result_summary(item) for item in low_results]

    cmg_low_vds = _cmg_correlation_diagnostic(
        resolved_root,
        result_directory,
        selected_toolchain,
        low_directories["apm016f/svt/nfet"],
    )
    immutability = _v2_model_immutability(resolved_root)
    apm045 = next(item for item in canonical if item["selector"] == "apm045/vtg/nmos")
    apm045_attempts = apm045["acquisition"]["attempts"]
    apm045_needed_extension = not apm045_attempts[0]["white_region_observed"]
    apm045_diagnosed = (
        len(apm045_attempts) > 1 and apm045_attempts[-1]["stop_hz"] > 1.0e8
        if apm045_needed_extension
        else True
    )
    all_summaries = [*canonical, *low_vds]
    checks = [
        {
            "id": "n0.regression",
            "status": (
                "pass"
                if n0_report["status"] == "pass"
                and n0_report["acceptance_result"] == "13/13"
                else "fail"
            ),
            "evidence": "v3_n0_regression/report.json",
        },
        {
            "id": "fit.synthetic_cases",
            "status": synthetic["status"],
            "evidence": "synthetic_fit_report.json",
        },
        {
            "id": "canonical.four_engine_adaptive_acquisition",
            "status": (
                "pass"
                if len(canonical) == 4
                and {item["selector"] for item in canonical} == set(SPIKE_SELECTORS)
                and all(_acquisition_valid(item) for item in canonical)
                else "fail"
            ),
        },
        {
            "id": "canonical.apm045_extended_diagnostic",
            "status": "pass" if apm045_diagnosed else "fail",
        },
        {
            "id": "low_vds.four_engine_results",
            "status": (
                "pass"
                if len(low_vds) == 4
                and {item["selector"] for item in low_vds} == set(SPIKE_SELECTORS)
                and all(
                    item["status"] == "pass"
                    and item["schema"] == NOISE_SCHEMA
                    and math.isclose(item["effective_vout_v"], LOW_VDS_EFFECTIVE_V)
                    and item["gm_over_id_relative_error"] <= 0.01
                    and item["spectrum_finite_nonnegative"]
                    and item["canonical_spectrum_fields_present"]
                    and item["gate_referred_and_transfer_finite"]
                    and _acquisition_valid(item)
                    for item in low_vds
                )
                else "fail"
            ),
        },
        {
            "id": "low_vds.bsim_cmg_tnoimod1_correlation",
            "status": (
                "pass"
                if cmg_low_vds["status"] == "pass"
                and math.isclose(cmg_low_vds["effective_vout_v"], LOW_VDS_EFFECTIVE_V)
                and cmg_low_vds["diagnostic_tnoimod"] == 1
                and not cmg_low_vds["production_card_modified"]
                and cmg_low_vds["correlation_source_vectors"]
                else "fail"
            ),
        },
        {
            "id": "fit.fail_closed_metrics",
            "status": (
                "pass" if all(_fail_closed_metrics(item) for item in all_summaries) else "fail"
            ),
        },
        {
            "id": "provenance.parameter_level_and_raw_sources",
            "status": (
                "pass"
                if all(
                    item["effective_parameter_snapshot_available"]
                    and item["effective_parameter_count"] > 0
                    and item["source_vector_names"]
                    for item in all_summaries
                )
                else "fail"
            ),
        },
        {
            "id": "solver.sparse_no_klu",
            "status": (
                "pass"
                if all(
                    all(
                        attempt["sparse_attestation_count"] > 0
                        and attempt["klu_attestation_count"] == 0
                        and attempt["log_critical_diagnostic_count"] == 0
                        for attempt in item["acquisition"]["attempts"]
                    )
                    for item in all_summaries
                )
                and cmg_low_vds["log_audit"]["sparse_attestations"]
                and not cmg_low_vds["log_audit"]["klu_attestations"]
                else "fail"
            ),
        },
        {"id": "models.v2_card_immutability", "status": immutability["status"]},
    ]
    status = "pass" if all(item["status"] == "pass" for item in checks) else "fail"
    repository_commit = run_checked(
        ["git", "rev-parse", "HEAD"], cwd=resolved_root
    ).stdout.strip()
    report = {
        "schema": "apm.noise-method-validation.v1",
        "milestone": "V3-N1",
        "status": status,
        "created_utc": _utc_now(),
        "repository_commit": repository_commit,
        "reference_environment": {
            "platform": "WSL2 + AlmaLinux/RHEL-compatible EL9 x86_64",
            "ngspice": run_checked([selected_toolchain.ngspice, "--version"]).stdout.strip(),
            "openvaf": run_checked(
                [selected_toolchain.openvaf, "--version"],
                environment=selected_toolchain.environment(),
            ).stdout.strip(),
            "required_noise_solver": "Sparse",
        },
        "fit_method": {
            "identity": FIT_METHOD_IDENTITY,
            "thresholds": synthetic["thresholds"],
            "local_slope_estimator": synthetic["local_slope_estimator"],
            "synthetic_report_path": "synthetic_fit_report.json",
            "synthetic_report_sha256": sha256_file(
                result_directory / "synthetic_fit_report.json"
            ),
            "synthetic_acceptance_result": synthetic["acceptance_result"],
        },
        "acquisition_policy": {
            "id": ACQUISITION_POLICY_ID,
            "version": ACQUISITION_POLICY_VERSION,
            "start_hz": DEFAULT_FREQUENCY_START_HZ,
            "stop_sequence_hz": list(ADAPTIVE_FREQUENCY_STOPS_HZ),
            "points_per_decade": DEFAULT_POINTS_PER_DECADE,
            "stop_at_first_valid_white_region": True,
            "missing_at_cap_is_valid_null": True,
        },
        "v3_n0_regression": {
            "status": n0_report["status"],
            "acceptance_result": n0_report["acceptance_result"],
            "report_path": "v3_n0_regression/report.json",
            "report_sha256": sha256_file(
                result_directory / "v3_n0_regression" / "report.json"
            ),
        },
        "canonical_results": canonical,
        "apm045_upper_frequency_diagnostic": {
            "base_white_observed": not apm045_needed_extension,
            "extension_required": apm045_needed_extension,
            "diagnosed_beyond_100mhz": apm045_diagnosed,
            "attempts": apm045_attempts,
            "selected_white_status": apm045["white_fit_status"],
            "selected_white_region_start_hz": apm045["white_region_start_hz"],
            "selected_white_region_stop_hz": apm045["white_region_stop_hz"],
        },
        "low_vds_results": low_vds,
        "bsim_cmg_tnoimod1_low_vds": cmg_low_vds,
        "model_immutability": immutability,
        "checks": checks,
        "acceptance_result": f"{sum(item['status'] == 'pass' for item in checks)}/{len(checks)}",
        "v3_n2_recommendation": {
            "ready_to_expand_all_26_devices": status == "pass",
            "reason": (
                "The frozen method passed all four compact-model engines at canonical and "
                "50 mV VOUT points, including bounded null handling, provenance, and Sparse audits."
                if status == "pass"
                else "Resolve failed V3-N1 checks before catalog-wide expansion."
            ),
            "scope_boundary": (
                "Expansion would characterize existing predictions only; it does not authorize "
                "process-noise coefficient tuning or a silicon-calibration claim."
            ),
        },
        "claim_boundary": (
            "V3-N1 qualifies acquisition/fitting and current compact-model predictions. It is "
            "not a v3 release and not silicon/process-noise calibration for APM-authored models."
        ),
        "output_directory": str(result_directory),
        "report_path": str(result_directory / "report.json"),
    }
    _write_json(result_directory / "report.json", report)
    report["report_sha256"] = sha256_file(result_directory / "report.json")
    if status != "pass":
        failed = [item["id"] for item in checks if item["status"] != "pass"]
        raise NoiseMethodValidationError(f"V3-N1 failed checks: {failed}")
    return report
