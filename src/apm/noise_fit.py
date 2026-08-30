# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Versioned, fail-closed contiguous-region fitting for APM noise spectra."""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Sequence
from typing import Any

FIT_METHOD_ID = "apm.noise-fit.contiguous-regions"
FIT_METHOD_VERSION = "1.0.0"
FIT_METHOD_IDENTITY = f"{FIT_METHOD_ID}@{FIT_METHOD_VERSION}"

LOCAL_SLOPE_TARGET_SPAN_DECADES = 0.5
FLICKER_LOCAL_ALPHA_RANGE = (0.5, 1.5)
FLICKER_MIN_SPAN_DECADES = 1.5
FLICKER_MIN_POINTS = 31
FLICKER_MIN_R_SQUARED = 0.98
WHITE_MAX_LOCAL_ABS_SLOPE = 0.10
WHITE_MIN_SPAN_DECADES = 1.0
WHITE_MIN_POINTS = 21
WHITE_MAX_OLS_ABS_SLOPE = 0.10
WHITE_MAX_PSD_RATIO = 1.35
BOLTZMANN_J_PER_K = 1.380649e-23


class NoiseFitError(ValueError):
    """A spectrum cannot be processed without violating fit semantics."""


def _validate_spectrum(
    frequency_hz: Sequence[float], psd: Sequence[float]
) -> tuple[list[float], list[float]]:
    if len(frequency_hz) != len(psd) or len(frequency_hz) < 2:
        raise NoiseFitError("frequency and PSD arrays must have the same non-trivial length")
    try:
        frequencies = [float(value) for value in frequency_hz]
        values = [float(value) for value in psd]
    except (TypeError, ValueError) as error:
        raise NoiseFitError("frequency and PSD arrays must contain numeric values") from error
    if any(not math.isfinite(value) or value <= 0.0 for value in frequencies):
        raise NoiseFitError("fit frequencies must be finite and positive")
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise NoiseFitError("PSD values must be finite and non-negative")
    if any(second <= first for first, second in zip(frequencies, frequencies[1:])):
        raise NoiseFitError("fit frequencies must be strictly increasing")
    return frequencies, values


def _log_ols(frequencies: Sequence[float], values: Sequence[float]) -> dict[str, float]:
    if len(frequencies) < 2 or len(frequencies) != len(values):
        raise NoiseFitError("log-domain fit needs at least two aligned points")
    if any(value <= 0.0 for value in values):
        raise NoiseFitError("log-domain fit region contains zero PSD")
    x = [math.log(value) for value in frequencies]
    y = [math.log(value) for value in values]
    x_mean = statistics.fmean(x)
    y_mean = statistics.fmean(y)
    xx = sum((value - x_mean) ** 2 for value in x)
    if xx <= 0.0:
        raise NoiseFitError("log-domain fit has no frequency span")
    slope = sum((xv - x_mean) * (yv - y_mean) for xv, yv in zip(x, y)) / xx
    intercept = y_mean - slope * x_mean
    residuals = [yv - (intercept + slope * xv) for xv, yv in zip(x, y)]
    residual_sum = sum(value**2 for value in residuals)
    total = sum((yv - y_mean) ** 2 for yv in y)
    r_squared = (
        1.0 - residual_sum / total
        if total > 0.0
        else (1.0 if residual_sum <= 1.0e-28 else 0.0)
    )
    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "residual_rms_log": math.sqrt(residual_sum / len(residuals)),
        "residual_max_abs_log": max(abs(value) for value in residuals),
    }


def integrate_psd(frequency_hz: Sequence[float], psd: Sequence[float]) -> float:
    """Integrate a PSD over the explicitly supplied finite frequency band."""

    frequencies, values = _validate_spectrum(frequency_hz, psd)
    return sum(
        0.5 * (right_value + left_value) * (right_frequency - left_frequency)
        for left_frequency, right_frequency, left_value, right_value in zip(
            frequencies, frequencies[1:], values, values[1:]
        )
    )


def _local_window_shape(frequencies: Sequence[float]) -> dict[str, Any]:
    total_span = math.log10(frequencies[-1] / frequencies[0])
    if total_span <= 0.0:
        raise NoiseFitError("local-slope estimator requires a positive frequency span")
    estimated_points_per_decade = (len(frequencies) - 1) / total_span
    half_width_points = max(
        1,
        round(0.5 * LOCAL_SLOPE_TARGET_SPAN_DECADES * estimated_points_per_decade),
    )
    return {
        "target_span_decades": LOCAL_SLOPE_TARGET_SPAN_DECADES,
        "estimated_points_per_decade": estimated_points_per_decade,
        "half_width_points": half_width_points,
        "window_point_count": 2 * half_width_points + 1,
        "edge_points_unclassified_per_side": half_width_points,
    }


def _local_slopes(
    frequencies: Sequence[float], values: Sequence[float]
) -> tuple[list[float | None], dict[str, Any], list[dict[str, Any]]]:
    shape = _local_window_shape(frequencies)
    half = shape["half_width_points"]
    slopes: list[float | None] = [None] * len(frequencies)
    diagnostics: list[dict[str, Any]] = []
    observed_spans: list[float] = []
    for index, frequency in enumerate(frequencies):
        start = index - half
        stop = index + half
        if start < 0 or stop >= len(frequencies):
            diagnostics.append(
                {
                    "index": index,
                    "frequency_hz": frequency,
                    "status": "edge_unclassified",
                    "local_log_slope": None,
                }
            )
            continue
        window_f = frequencies[start : stop + 1]
        window_s = values[start : stop + 1]
        span = math.log10(window_f[-1] / window_f[0])
        observed_spans.append(span)
        if any(value <= 0.0 for value in window_s):
            diagnostics.append(
                {
                    "index": index,
                    "frequency_hz": frequency,
                    "status": "zero_psd_in_window",
                    "local_log_slope": None,
                    "window_start_hz": window_f[0],
                    "window_stop_hz": window_f[-1],
                    "window_span_decades": span,
                }
            )
            continue
        regression = _log_ols(window_f, window_s)
        slopes[index] = regression["slope"]
        diagnostics.append(
            {
                "index": index,
                "frequency_hz": frequency,
                "status": "classified",
                "local_log_slope": regression["slope"],
                "window_start_hz": window_f[0],
                "window_stop_hz": window_f[-1],
                "window_span_decades": span,
            }
        )
    shape["observed_window_span_decades_min"] = min(observed_spans) if observed_spans else None
    shape["observed_window_span_decades_max"] = max(observed_spans) if observed_spans else None
    return slopes, shape, diagnostics


def _contiguous_runs(
    slopes: Sequence[float | None], predicate: Callable[[float], bool]
) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, slope in enumerate(slopes):
        selected = slope is not None and predicate(slope)
        if selected and start is None:
            start = index
        elif not selected and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(slopes) - 1))
    return runs


def _flicker_candidates(
    frequencies: Sequence[float], values: Sequence[float], slopes: Sequence[float | None]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    runs = _contiguous_runs(
        slopes,
        lambda slope: FLICKER_LOCAL_ALPHA_RANGE[0]
        <= -slope
        <= FLICKER_LOCAL_ALPHA_RANGE[1],
    )
    for candidate_id, (start, stop) in enumerate(runs, start=1):
        selected_f = frequencies[start : stop + 1]
        selected_s = values[start : stop + 1]
        span = math.log10(selected_f[-1] / selected_f[0]) if stop > start else 0.0
        regression = _log_ols(selected_f, selected_s) if len(selected_f) >= 2 else None
        alpha = -regression["slope"] if regression is not None else None
        reasons: list[str] = []
        if span < FLICKER_MIN_SPAN_DECADES:
            reasons.append("span_below_minimum")
        if len(selected_f) < FLICKER_MIN_POINTS:
            reasons.append("point_count_below_minimum")
        if alpha is None or not FLICKER_LOCAL_ALPHA_RANGE[0] <= alpha <= FLICKER_LOCAL_ALPHA_RANGE[1]:
            reasons.append("whole_run_alpha_outside_range")
        if regression is None or regression["r_squared"] < FLICKER_MIN_R_SQUARED:
            reasons.append("whole_run_r_squared_below_minimum")
        candidates.append(
            {
                "candidate_id": f"flicker-{candidate_id}",
                "start_index": start,
                "end_index": stop,
                "start_hz": selected_f[0],
                "stop_hz": selected_f[-1],
                "geometric_center_hz": math.sqrt(selected_f[0] * selected_f[-1]),
                "span_decades": span,
                "point_count": len(selected_f),
                "whole_run_log_slope": regression["slope"] if regression else None,
                "alpha": alpha,
                "r_squared": regression["r_squared"] if regression else None,
                "residual_rms_log": regression["residual_rms_log"] if regression else None,
                "residual_max_abs_log": (
                    regression["residual_max_abs_log"] if regression else None
                ),
                "eligible": not reasons,
                "ineligibility_reasons": reasons,
            }
        )
    return candidates


def _white_candidates(
    frequencies: Sequence[float], values: Sequence[float], slopes: Sequence[float | None]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    runs = _contiguous_runs(slopes, lambda slope: abs(slope) <= WHITE_MAX_LOCAL_ABS_SLOPE)
    for candidate_id, (start, stop) in enumerate(runs, start=1):
        selected_f = frequencies[start : stop + 1]
        selected_s = values[start : stop + 1]
        span = math.log10(selected_f[-1] / selected_f[0]) if stop > start else 0.0
        regression = _log_ols(selected_f, selected_s) if len(selected_f) >= 2 else None
        ratio = max(selected_s) / min(selected_s) if selected_s and min(selected_s) > 0.0 else None
        reasons: list[str] = []
        if span < WHITE_MIN_SPAN_DECADES:
            reasons.append("span_below_minimum")
        if len(selected_f) < WHITE_MIN_POINTS:
            reasons.append("point_count_below_minimum")
        if regression is None or abs(regression["slope"]) > WHITE_MAX_OLS_ABS_SLOPE:
            reasons.append("whole_run_abs_slope_above_maximum")
        if ratio is None or ratio > WHITE_MAX_PSD_RATIO:
            reasons.append("whole_run_psd_ratio_above_maximum")
        candidates.append(
            {
                "candidate_id": f"white-{candidate_id}",
                "start_index": start,
                "end_index": stop,
                "start_hz": selected_f[0],
                "stop_hz": selected_f[-1],
                "geometric_center_hz": math.sqrt(selected_f[0] * selected_f[-1]),
                "span_decades": span,
                "point_count": len(selected_f),
                "whole_run_log_slope": regression["slope"] if regression else None,
                "r_squared": regression["r_squared"] if regression else None,
                "max_to_min_ratio": ratio,
                "median_psd": statistics.median(selected_s),
                "eligible": not reasons,
                "ineligibility_reasons": reasons,
            }
        )
    return candidates


def _selected_flicker(candidates: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [item for item in candidates if item["eligible"]]
    return (
        min(
            eligible,
            key=lambda item: (
                -item["span_decades"],
                -item["point_count"],
                item["geometric_center_hz"],
            ),
        )
        if eligible
        else None
    )


def _selected_white(
    candidates: Sequence[dict[str, Any]], flicker: dict[str, Any] | None
) -> dict[str, Any] | None:
    eligible = [item for item in candidates if item["eligible"]]
    if flicker is not None:
        for item in candidates:
            item["begins_above_selected_flicker"] = item["start_hz"] > flicker["stop_hz"]
        eligible = [item for item in eligible if item["begins_above_selected_flicker"]]
    else:
        for item in candidates:
            item["begins_above_selected_flicker"] = None
    return (
        min(
            eligible,
            key=lambda item: (
                item["start_hz"],
                -item["span_decades"],
                -item["point_count"],
            ),
        )
        if eligible
        else None
    )


def fit_noise_spectrum(
    frequency_hz: Sequence[float],
    drain_psd_a2_per_hz: Sequence[float],
    *,
    gm_s: float,
    temperature_c: float,
) -> dict[str, Any]:
    """Detect deterministic contiguous flicker/white regions and derive metrics.

    The raw spectrum is never altered. A missing region remains an explicit
    null result, including when a spectrum contains zeros that cannot enter a
    logarithmic fit.
    """

    frequencies, values = _validate_spectrum(frequency_hz, drain_psd_a2_per_hz)
    slopes, local_shape, local_diagnostics = _local_slopes(frequencies, values)
    flicker_candidates = _flicker_candidates(frequencies, values, slopes)
    selected_flicker = _selected_flicker(flicker_candidates)
    white_candidates = _white_candidates(frequencies, values, slopes)
    selected_white = _selected_white(white_candidates, selected_flicker)
    result: dict[str, Any] = {
        "method_id": FIT_METHOD_ID,
        "method_version": FIT_METHOD_VERSION,
        "method_identity": FIT_METHOD_IDENTITY,
        "method_status": "qualified",
        "windows_are_fixed": False,
        "frequency_min_hz": frequencies[0],
        "frequency_max_hz": frequencies[-1],
        "input_point_count": len(frequencies),
        "zero_psd_point_count": sum(value == 0.0 for value in values),
        "integrated_drain_noise_a2": integrate_psd(frequencies, values),
        "integrated_drain_noise_status": "valid",
        "thresholds": {
            "local_slope_target_span_decades": LOCAL_SLOPE_TARGET_SPAN_DECADES,
            "flicker_local_alpha_min": FLICKER_LOCAL_ALPHA_RANGE[0],
            "flicker_local_alpha_max": FLICKER_LOCAL_ALPHA_RANGE[1],
            "flicker_min_span_decades": FLICKER_MIN_SPAN_DECADES,
            "flicker_min_points": FLICKER_MIN_POINTS,
            "flicker_min_r_squared": FLICKER_MIN_R_SQUARED,
            "white_max_local_abs_slope": WHITE_MAX_LOCAL_ABS_SLOPE,
            "white_min_span_decades": WHITE_MIN_SPAN_DECADES,
            "white_min_points": WHITE_MIN_POINTS,
            "white_max_ols_abs_slope": WHITE_MAX_OLS_ABS_SLOPE,
            "white_max_psd_ratio": WHITE_MAX_PSD_RATIO,
        },
        "local_slope_estimator": local_shape,
        "local_slope_diagnostics": local_diagnostics,
        "candidate_regions": {
            "flicker": flicker_candidates,
            "white": white_candidates,
        },
    }

    flicker: dict[str, Any] = {
        "status": "invalid_not_observed",
        "reason": "no_eligible_contiguous_flicker_region",
        "window_min_hz": None,
        "window_max_hz": None,
        "point_count": 0,
        "alpha": None,
        "coefficient_a2_per_hz_at_1hz": None,
        "r_squared": None,
        "log_slope": None,
        "residual_rms_log": None,
        "residual_max_abs_log": None,
        "candidate_count": len(flicker_candidates),
        "eligible_candidate_count": sum(item["eligible"] for item in flicker_candidates),
        "selected_candidate_id": None,
        "selection_rationale": (
            "greatest logarithmic span, then greatest point count, then lowest "
            "geometric-center frequency"
        ),
    }
    if selected_flicker is not None:
        regression = _log_ols(
            frequencies[selected_flicker["start_index"] : selected_flicker["end_index"] + 1],
            values[selected_flicker["start_index"] : selected_flicker["end_index"] + 1],
        )
        flicker.update(
            {
                "status": "valid",
                "reason": None,
                "window_min_hz": selected_flicker["start_hz"],
                "window_max_hz": selected_flicker["stop_hz"],
                "point_count": selected_flicker["point_count"],
                "alpha": -regression["slope"],
                "coefficient_a2_per_hz_at_1hz": math.exp(regression["intercept"]),
                "r_squared": regression["r_squared"],
                "log_slope": regression["slope"],
                "residual_rms_log": regression["residual_rms_log"],
                "residual_max_abs_log": regression["residual_max_abs_log"],
                "selected_candidate_id": selected_flicker["candidate_id"],
            }
        )
    result["flicker_fit"] = flicker

    white: dict[str, Any] = {
        "status": "invalid_not_observed",
        "reason": (
            "no_eligible_white_region_above_selected_flicker"
            if selected_flicker is not None
            else "no_eligible_contiguous_white_region"
        ),
        "window_min_hz": None,
        "window_max_hz": None,
        "point_count": 0,
        "floor_a2_per_hz": None,
        "log_slope": None,
        "max_to_min_ratio": None,
        "candidate_count": len(white_candidates),
        "eligible_candidate_count": sum(item["eligible"] for item in white_candidates),
        "selected_candidate_id": None,
        "selection_rationale": (
            "lowest-frequency eligible run above the selected flicker region, then "
            "greatest logarithmic span, then greatest point count"
        ),
    }
    if selected_white is not None:
        white.update(
            {
                "status": "valid",
                "reason": None,
                "window_min_hz": selected_white["start_hz"],
                "window_max_hz": selected_white["stop_hz"],
                "point_count": selected_white["point_count"],
                "floor_a2_per_hz": selected_white["median_psd"],
                "log_slope": selected_white["whole_run_log_slope"],
                "max_to_min_ratio": selected_white["max_to_min_ratio"],
                "selected_candidate_id": selected_white["candidate_id"],
            }
        )
    result["white_fit"] = white

    corner: dict[str, Any] = {
        "status": "invalid_not_observed",
        "frequency_hz": None,
        "reason": "requires_valid_contiguous_flicker_and_white_fits",
        "boundary_tolerance_decades": LOCAL_SLOPE_TARGET_SPAN_DECADES / 2.0,
    }
    if flicker["status"] == "valid" and white["status"] == "valid":
        log_corner = (
            math.log10(flicker["coefficient_a2_per_hz_at_1hz"])
            - math.log10(white["floor_a2_per_hz"])
        ) / flicker["alpha"]
        candidate = 10.0**log_corner
        tolerance = LOCAL_SLOPE_TARGET_SPAN_DECADES / 2.0
        accepted_min = flicker["window_max_hz"] / 10.0**tolerance
        accepted_max = white["window_min_hz"] * 10.0**tolerance
        corner.update(
            {
                "candidate_frequency_hz": candidate,
                "accepted_min_hz": accepted_min,
                "accepted_max_hz": accepted_max,
            }
        )
        if math.isfinite(candidate) and accepted_min <= candidate <= accepted_max:
            corner.update({"status": "valid", "frequency_hz": candidate, "reason": None})
        else:
            corner.update(
                {
                    "status": "invalid",
                    "reason": "fit_regions_inconsistent_with_corner",
                }
            )
    result["flicker_corner"] = corner

    gamma: dict[str, Any] = {"status": "invalid", "value": None}
    temperature_k = float(temperature_c) + 273.15
    if white["status"] != "valid":
        gamma["reason"] = "white_floor_not_observed"
    elif not math.isfinite(gm_s) or gm_s <= 0.0:
        gamma["reason"] = "canonical_gm_is_not_positive"
    elif not math.isfinite(temperature_k) or temperature_k <= 0.0:
        gamma["reason"] = "temperature_is_not_above_absolute_zero"
    else:
        gamma = {
            "status": "valid",
            "value": white["floor_a2_per_hz"]
            / (4.0 * BOLTZMANN_J_PER_K * temperature_k * gm_s),
            "definition": "S_idrain_terminal_white/(4*k*T*gm)",
        }
    result["gamma_eff_total"] = gamma
    return result
