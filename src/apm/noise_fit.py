# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed provisional fitting for persisted APM noise spectra.

The V3-N0 spike deliberately uses fixed review windows.  A failed window is a
recorded observation, not permission to move the window until a metric appears.
Raw spectra remain authoritative and can be reprocessed by a later method.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from typing import Any

FIT_METHOD_ID = "apm.noise-fit.fixed-review-windows"
FIT_METHOD_VERSION = "0.1.0-provisional"
FLICKER_WINDOW_HZ = (1.0, 1.0e3)
WHITE_WINDOW_HZ = (1.0e7, 1.0e8)
MIN_FLICKER_POINTS = 41
MIN_WHITE_POINTS = 21
MIN_FLICKER_R_SQUARED = 0.98
FLICKER_ALPHA_RANGE = (0.5, 1.5)
MAX_WHITE_ABS_LOG_SLOPE = 0.10
MAX_WHITE_PSD_RATIO = 1.35
BOLTZMANN_J_PER_K = 1.380649e-23


class NoiseFitError(ValueError):
    """A spectrum cannot be processed without violating fit semantics."""


def _validate_spectrum(
    frequency_hz: Sequence[float], psd: Sequence[float]
) -> tuple[list[float], list[float]]:
    if len(frequency_hz) != len(psd) or len(frequency_hz) < 2:
        raise NoiseFitError("frequency and PSD arrays must have the same non-trivial length")
    frequencies = [float(value) for value in frequency_hz]
    values = [float(value) for value in psd]
    if any(not math.isfinite(value) or value <= 0.0 for value in frequencies):
        raise NoiseFitError("fit frequencies must be finite and positive")
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise NoiseFitError("PSD values must be finite and non-negative")
    if any(second <= first for first, second in zip(frequencies, frequencies[1:])):
        raise NoiseFitError("fit frequencies must be strictly increasing")
    return frequencies, values


def _fixed_window(
    frequencies: Sequence[float], values: Sequence[float], limits: tuple[float, float]
) -> tuple[list[float], list[float]]:
    selected = [
        (frequency, value)
        for frequency, value in zip(frequencies, values)
        if limits[0] <= frequency <= limits[1]
    ]
    return [item[0] for item in selected], [item[1] for item in selected]


def _log_ols(frequencies: Sequence[float], values: Sequence[float]) -> dict[str, float]:
    if any(value <= 0.0 for value in values):
        raise NoiseFitError("log-domain fit window contains zero PSD")
    x = [math.log(value) for value in frequencies]
    y = [math.log(value) for value in values]
    x_mean = statistics.fmean(x)
    y_mean = statistics.fmean(y)
    xx = sum((value - x_mean) ** 2 for value in x)
    if xx <= 0.0:
        raise NoiseFitError("log-domain fit has no frequency span")
    slope = sum((xv - x_mean) * (yv - y_mean) for xv, yv in zip(x, y)) / xx
    intercept = y_mean - slope * x_mean
    residual = sum((yv - (intercept + slope * xv)) ** 2 for xv, yv in zip(x, y))
    total = sum((yv - y_mean) ** 2 for yv in y)
    r_squared = 1.0 - residual / total if total > 0.0 else (1.0 if residual == 0.0 else 0.0)
    return {"slope": slope, "intercept": intercept, "r_squared": r_squared}


def integrate_psd(frequency_hz: Sequence[float], psd: Sequence[float]) -> float:
    """Integrate a PSD over the explicitly supplied finite frequency band."""

    frequencies, values = _validate_spectrum(frequency_hz, psd)
    return sum(
        0.5 * (right_value + left_value) * (right_frequency - left_frequency)
        for left_frequency, right_frequency, left_value, right_value in zip(
            frequencies, frequencies[1:], values, values[1:]
        )
    )


def fit_noise_spectrum(
    frequency_hz: Sequence[float],
    drain_psd_a2_per_hz: Sequence[float],
    *,
    gm_s: float,
    temperature_c: float,
) -> dict[str, Any]:
    """Return provisional metrics with an explicit status for every fit.

    The windows and thresholds are intentionally fixed and versioned for the
    spike.  This function never substitutes the last point for a white floor.
    """

    frequencies, values = _validate_spectrum(frequency_hz, drain_psd_a2_per_hz)
    result: dict[str, Any] = {
        "method_id": FIT_METHOD_ID,
        "method_version": FIT_METHOD_VERSION,
        "method_status": "provisional",
        "windows_are_fixed": True,
        "frequency_min_hz": frequencies[0],
        "frequency_max_hz": frequencies[-1],
        "integrated_drain_noise_a2": integrate_psd(frequencies, values),
        "integrated_drain_noise_status": "valid",
    }

    flicker_f, flicker_s = _fixed_window(frequencies, values, FLICKER_WINDOW_HZ)
    flicker: dict[str, Any] = {
        "status": "invalid_not_observed",
        "window_min_hz": FLICKER_WINDOW_HZ[0],
        "window_max_hz": FLICKER_WINDOW_HZ[1],
        "point_count": len(flicker_f),
        "alpha": None,
        "coefficient_a2_per_hz_at_1hz": None,
        "r_squared": None,
        "reason": None,
    }
    if len(flicker_f) < MIN_FLICKER_POINTS:
        flicker["reason"] = "fixed_window_has_insufficient_points"
    elif any(value <= 0.0 for value in flicker_s):
        flicker["reason"] = "fixed_window_contains_zero_psd"
    else:
        regression = _log_ols(flicker_f, flicker_s)
        alpha = -regression["slope"]
        flicker["r_squared"] = regression["r_squared"]
        if not FLICKER_ALPHA_RANGE[0] <= alpha <= FLICKER_ALPHA_RANGE[1]:
            flicker["reason"] = "fixed_window_slope_is_not_flicker_like"
        elif regression["r_squared"] < MIN_FLICKER_R_SQUARED:
            flicker["reason"] = "fixed_window_log_fit_quality_is_insufficient"
        else:
            flicker.update(
                {
                    "status": "valid",
                    "alpha": alpha,
                    "coefficient_a2_per_hz_at_1hz": math.exp(regression["intercept"]),
                    "reason": None,
                }
            )
    result["flicker_fit"] = flicker

    white_f, white_s = _fixed_window(frequencies, values, WHITE_WINDOW_HZ)
    white: dict[str, Any] = {
        "status": "invalid_not_observed",
        "window_min_hz": WHITE_WINDOW_HZ[0],
        "window_max_hz": WHITE_WINDOW_HZ[1],
        "point_count": len(white_f),
        "floor_a2_per_hz": None,
        "log_slope": None,
        "max_to_min_ratio": None,
        "reason": None,
    }
    if len(white_f) < MIN_WHITE_POINTS:
        white["reason"] = "fixed_window_has_insufficient_points"
    elif any(value <= 0.0 for value in white_s):
        white["reason"] = "fixed_window_contains_zero_psd"
    else:
        regression = _log_ols(white_f, white_s)
        ratio = max(white_s) / min(white_s)
        white["log_slope"] = regression["slope"]
        white["max_to_min_ratio"] = ratio
        if abs(regression["slope"]) > MAX_WHITE_ABS_LOG_SLOPE:
            white["reason"] = "fixed_window_is_not_flat"
        elif ratio > MAX_WHITE_PSD_RATIO:
            white["reason"] = "fixed_window_psd_spread_is_too_large"
        else:
            white.update(
                {
                    "status": "valid",
                    "floor_a2_per_hz": statistics.median(white_s),
                    "reason": None,
                }
            )
    result["white_fit"] = white

    corner: dict[str, Any] = {"status": "invalid_not_observed", "frequency_hz": None}
    if flicker["status"] == "valid" and white["status"] == "valid":
        candidate = (
            flicker["coefficient_a2_per_hz_at_1hz"] / white["floor_a2_per_hz"]
        ) ** (1.0 / flicker["alpha"])
        if frequencies[0] <= candidate <= frequencies[-1]:
            corner = {"status": "valid", "frequency_hz": candidate}
        else:
            corner["reason"] = "fitted_intersection_is_outside_swept_band"
    else:
        corner["reason"] = "requires_valid_fixed_window_flicker_and_white_fits"
    result["flicker_corner"] = corner

    gamma: dict[str, Any] = {"status": "invalid", "value": None}
    temperature_k = float(temperature_c) + 273.15
    if white["status"] != "valid":
        gamma["reason"] = "white_floor_not_observed"
    elif not math.isfinite(gm_s) or gm_s <= 0.0:
        gamma["reason"] = "canonical_gm_is_not_positive"
    else:
        gamma = {
            "status": "valid",
            "value": white["floor_a2_per_hz"] / (4.0 * BOLTZMANN_J_PER_K * temperature_k * gm_s),
            "definition": "S_idrain_terminal_white/(4*k*T*gm)",
        }
    result["gamma_eff_total"] = gamma
    return result
