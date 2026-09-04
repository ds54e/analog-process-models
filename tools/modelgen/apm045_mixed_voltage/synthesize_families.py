# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Construct and calibrate deterministic APM045 io18/io25 candidate ensembles.

The calibration-only mode never evaluates a sealed device, charge, or circuit
holdout. It exists so an epoch can be checked and committed before the first
unsealing. Runtime APM never imports this module.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10 reference environments
    import tomli as tomllib

from .kernel import (
    KERNEL_ID,
    KERNEL_VERSION,
    STAGE_ORDER,
    Curve,
    ModelSource,
    NgspiceEvaluator,
    SweepRequest,
    canonical_json,
    hard_constraint_observations,
    qualified_current_floor,
    render_bsim4_card,
    sha256_bytes,
    sha256_file,
    terminal_derivative,
)

SCHEMA = "apm.modelgen.mixed-voltage-calibration.v1"
CALIBRATION_COMPLETION_STATE = "MIXED_VOLTAGE_CALIBRATION_CANDIDATES_FROZEN"
FAMILY_CODES = {"io18": 18, "io25": 25}
POLARITY_CODES = {"n": 1, "p": 2}


class SynthesisError(RuntimeError):
    """A mixed-voltage generation contract or candidate failed closed."""


@dataclass(frozen=True)
class VariationParameter:
    name: str
    stage: str
    mode: str
    span: float

    def resolve(self, center: float, draw: float, scale: float) -> float:
        displacement = self.span * float(draw) * float(scale)
        if self.mode == "absolute":
            value = center + displacement
        elif self.mode == "relative":
            value = center * (1.0 + displacement)
        else:  # pragma: no cover - guarded by configuration validation
            raise SynthesisError(f"{self.name}: unsupported variation mode {self.mode!r}")
        if not math.isfinite(value):
            raise SynthesisError(f"{self.name}: generated parameter is not finite")
        return value


@dataclass(frozen=True)
class Geometry:
    family: str
    lmin_m: float
    lmax_m: float
    wmin_m: float
    wmax_m: float
    native_vdd_v: float


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _percentile(values: Iterable[float], fraction: float) -> float:
    finite = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not finite:
        return math.inf
    if len(finite) == 1:
        return finite[0]
    position = fraction * (len(finite) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return finite[lower]
    weight = position - lower
    return finite[lower] * (1.0 - weight) + finite[upper] * weight


def _geometry(configuration: Mapping[str, Any], family: str) -> Geometry:
    data = configuration["geometry"][family]
    return Geometry(
        family=family,
        lmin_m=float(data["lmin_m"]),
        lmax_m=float(data["lmax_m"]),
        wmin_m=float(data["wmin_m"]),
        wmax_m=float(data["wmax_m"]),
        native_vdd_v=float(data["native_vdd_v"]),
    )


def _variation_parameters(configuration: Mapping[str, Any]) -> tuple[VariationParameter, ...]:
    return tuple(
        VariationParameter(
            name=str(item["name"]),
            stage=str(item["stage"]),
            mode=str(item["mode"]),
            span=float(item["span"]),
        )
        for item in configuration["variation_parameter"]
    )


def _center_parameters(
    configuration: Mapping[str, Any], family: str, polarity: str
) -> dict[str, float]:
    return {
        **{name: float(value) for name, value in configuration["card_defaults"].items()},
        **{
            name: float(value)
            for name, value in configuration["center"][family][polarity].items()
        },
    }


def _validate_configuration(configuration: Mapping[str, Any], root: Path) -> dict[str, Any]:
    if configuration.get("schema") != "apm.modelgen.mixed-voltage-generation.v1":
        raise SynthesisError("unexpected mixed-voltage generation schema")
    if int(configuration.get("generation_epoch", 0)) < 1:
        raise SynthesisError("generation epoch must be positive")
    if configuration.get("epoch_state") != "SEALED_BEFORE_FINAL_CANDIDATE_GENERATION":
        raise SynthesisError("generation epoch is not sealed before final candidate generation")
    if configuration.get("kernel") != f"{KERNEL_ID}@{KERNEL_VERSION}":
        raise SynthesisError("generation contract does not name the executing kernel version")
    seeds = [int(value) for value in configuration["seeds"]]
    minimum = int(configuration["minimum_retained_candidates_per_family"])
    if len(seeds) != len(set(seeds)) or len(seeds) < minimum or minimum < 3:
        raise SynthesisError("generation seeds do not satisfy the retained-ensemble contract")
    variations = _variation_parameters(configuration)
    if len({item.name for item in variations}) != len(variations):
        raise SynthesisError("variation parameter names must be unique")
    stage_counts = {
        stage: sum(item.stage == stage for item in variations) for stage in STAGE_ORDER
    }
    release = _load_toml(root / "validation/release_gates_v4.toml")
    limits = release["modelgen"]["stage_limits"]
    for stage, count in stage_counts.items():
        if count > int(limits[f"{stage}_max_free_parameters"]):
            raise SynthesisError(f"{stage}: stage parameter limit exceeded")
    for item in variations:
        if item.stage not in STAGE_ORDER or item.mode not in {"absolute", "relative"}:
            raise SynthesisError(f"{item.name}: invalid variation declaration")
        if not math.isfinite(item.span) or item.span <= 0.0:
            raise SynthesisError(f"{item.name}: variation span must be positive and finite")
    for family in FAMILY_CODES:
        geometry = _geometry(configuration, family)
        if not (
            0.0 < geometry.lmin_m < geometry.lmax_m
            and 0.0 < geometry.wmin_m < geometry.wmax_m
            and geometry.native_vdd_v > 0.0
        ):
            raise SynthesisError(f"{family}: invalid geometry or voltage declaration")
        for polarity in POLARITY_CODES:
            parameters = _center_parameters(configuration, family, polarity)
            render_bsim4_card(
                model_name=f"apm045_{family}_{polarity}core",
                polarity=polarity,
                parameters=parameters,
                lmin_m=geometry.lmin_m,
                lmax_m=geometry.lmax_m,
                wmin_m=geometry.wmin_m,
                wmax_m=geometry.wmax_m,
            )
        candidate_floors_m = [
            float(value) * 1e-6
            for value in release["geometry"][family]["initial_candidate_l_floor_um"]
        ]
        if not any(math.isclose(geometry.lmin_m, value) for value in candidate_floors_m):
            raise SynthesisError(f"{family}: selected L floor was not in the frozen search set")
    challenged_widths = [
        float(value) for value in release["geometry"]["width_challenge"]["initial_widths_um"]
    ]
    configured_widths = [
        float(value) for value in configuration["width_challenge"]["widths_um"]
    ]
    if configured_widths != challenged_widths:
        raise SynthesisError("calibration does not cover the frozen width challenge")
    width_outcome = str(configuration["calibration"]["criteria"]["width_outcome"])
    if width_outcome not in release["geometry"]["width_challenge"]["allowed_outcomes"]:
        raise SynthesisError("width outcome is not permitted by the release contract")
    if width_outcome == "WIDTH_INVARIANT_IN_SCOPE":
        for family in FAMILY_CODES:
            if not math.isclose(_geometry(configuration, family).wmin_m, challenged_widths[0] * 1e-6):
                raise SynthesisError(f"{family}: invariant width outcome must retain the challenged floor")
    calibration = configuration["calibration"]["dc"]
    calibration_temperatures = {
        int(value)
        for section in ("dc", "charge", "temperature")
        for value in configuration["calibration"][section]["temperatures_c"]
    }
    holdout = configuration["sealed_device_holdout"]
    separation_checks = {
        "temperature_disjoint": calibration_temperatures.isdisjoint(
            int(value) for value in holdout["temperatures_c"]
        ),
        "length_disjoint": set(calibration["length_ratios"]).isdisjoint(
            holdout["length_ratios"]
        ),
        "width_disjoint": set(calibration["widths_um"]).isdisjoint(holdout["widths_um"]),
        "idvg_bias_disjoint": set(calibration["idvg_fixed_bias_fractions"]).isdisjoint(
            holdout["idvg_fixed_bias_fractions"]
        ),
        "idvd_bias_disjoint": set(calibration["idvd_fixed_bias_fractions"]).isdisjoint(
            holdout["idvd_fixed_bias_fractions"]
        ),
    }
    if not all(separation_checks.values()):
        raise SynthesisError("calibration and sealed device holdout coordinates overlap")
    charge_calibration = configuration["calibration"]["charge"]
    charge_holdout = configuration["sealed_charge_holdout"]
    charge_separation_checks = {
        "temperature_disjoint": set(charge_calibration["temperatures_c"]).isdisjoint(
            charge_holdout["temperatures_c"]
        ),
        "length_disjoint": set(charge_calibration["length_ratios"]).isdisjoint(
            charge_holdout["length_ratios"]
        ),
        "width_disjoint": set(charge_calibration["widths_um"]).isdisjoint(
            charge_holdout["widths_um"]
        ),
        "bias_disjoint": set(
            charge_calibration["idvg_fixed_bias_fractions"]
        ).isdisjoint(charge_holdout["idvg_fixed_bias_fractions"]),
        "frequency_disjoint": set(charge_calibration["frequencies_hz"]).isdisjoint(
            charge_holdout["frequencies_hz"]
        ),
    }
    if not all(charge_separation_checks.values()):
        raise SynthesisError("calibration and sealed charge holdout coordinates overlap")
    return {
        "stage_parameter_counts": stage_counts,
        "calibration_holdout_separation": separation_checks,
        "charge_calibration_holdout_separation": charge_separation_checks,
        "width_challenge_um": challenged_widths,
        "declared_width_outcome": width_outcome,
    }


def _draws(
    configuration: Mapping[str, Any], family: str, polarity: str, seed: int
) -> dict[str, float]:
    sequence = np.random.SeedSequence([seed, FAMILY_CODES[family], POLARITY_CODES[polarity]])
    rng = np.random.default_rng(sequence)
    return {
        item.name: float(draw)
        for item, draw in zip(
            _variation_parameters(configuration),
            rng.uniform(-1.0, 1.0, len(configuration["variation_parameter"])),
        )
    }


def _candidate_parameters(
    configuration: Mapping[str, Any],
    family: str,
    polarity: str,
    draws: Mapping[str, float],
    scale: float,
) -> dict[str, float]:
    result = _center_parameters(configuration, family, polarity)
    for item in _variation_parameters(configuration):
        result[item.name] = item.resolve(result[item.name], draws[item.name], scale)
    return result


def _render_candidate(
    configuration: Mapping[str, Any],
    family: str,
    polarity: str,
    parameters: Mapping[str, float],
) -> str:
    geometry = _geometry(configuration, family)
    return render_bsim4_card(
        model_name=f"apm045_{family}_{polarity}core",
        polarity=polarity,
        parameters=parameters,
        lmin_m=geometry.lmin_m,
        lmax_m=geometry.lmax_m,
        wmin_m=geometry.wmin_m,
        wmax_m=geometry.wmax_m,
    )


def _grid_requests(
    *, family: str, geometry: Geometry, grid: Mapping[str, Any]
) -> tuple[SweepRequest, ...]:
    requests: list[SweepRequest] = []
    for temperature in grid["temperatures_c"]:
        for length_ratio in grid["length_ratios"]:
            for width_um in grid["widths_um"]:
                stem = (
                    f"{family}-t{int(temperature):+d}-lr{float(length_ratio):.4g}"
                    f"-w{float(width_um):.4g}u"
                )
                for fraction in grid["idvg_fixed_bias_fractions"]:
                    requests.append(
                        SweepRequest(
                            request_id=f"{stem}-idvg-vd{float(fraction):.4g}",
                            kind="idvg",
                            temperature_c=int(temperature),
                            l_m=geometry.lmin_m * float(length_ratio),
                            w_m=float(width_um) * 1e-6,
                            fixed_bias_v=geometry.native_vdd_v * float(fraction),
                            sweep_stop_v=geometry.native_vdd_v,
                            points=int(grid["points"]),
                        )
                    )
                for fraction in grid.get("idvd_fixed_bias_fractions", []):
                    requests.append(
                        SweepRequest(
                            request_id=f"{stem}-idvd-vg{float(fraction):.4g}",
                            kind="idvd",
                            temperature_c=int(temperature),
                            l_m=geometry.lmin_m * float(length_ratio),
                            w_m=float(width_um) * 1e-6,
                            fixed_bias_v=geometry.native_vdd_v * float(fraction),
                            sweep_stop_v=geometry.native_vdd_v,
                            points=int(grid["points"]),
                        )
                    )
    return tuple(requests)


def _threshold(curve: Curve, coefficient_a: float = 1e-7) -> float | None:
    target = coefficient_a * curve.request.w_m / curve.request.l_m
    for index in range(curve.idmag_a.size - 1):
        low = float(curve.idmag_a[index])
        high = float(curve.idmag_a[index + 1])
        if low <= target <= high and high > low:
            fraction = (target - low) / (high - low)
            return float(
                curve.sweep_v[index]
                + fraction * (curve.sweep_v[index + 1] - curve.sweep_v[index])
            )
    return None


def _gmid_solution(
    curve: Curve, target_per_v: float, *, current_floor_a: float, endpoint_guard: int
) -> dict[str, Any]:
    derivative = terminal_derivative(curve)
    qualified = curve.idmag_a >= qualified_current_floor(curve.request, current_floor_a)
    qualified[:endpoint_guard] = False
    qualified[-endpoint_guard:] = False
    indices = np.flatnonzero(qualified & (derivative > 0.0))
    if indices.size < 2:
        return {"state": "target_not_reachable", "target_per_v": target_per_v}
    gmid = derivative / np.maximum(curve.idmag_a, current_floor_a)
    candidates: list[tuple[float, int]] = []
    for first, second in zip(indices, indices[1:]):
        if second != first + 1:
            continue
        first_error = float(gmid[first] - target_per_v)
        second_error = float(gmid[second] - target_per_v)
        if first_error == 0.0 or first_error * second_error <= 0.0:
            candidates.append((min(abs(first_error), abs(second_error)), first))
    if not candidates:
        return {
            "state": "target_not_reachable",
            "target_per_v": target_per_v,
            "qualified_gmid_min_per_v": float(np.min(gmid[indices])),
            "qualified_gmid_max_per_v": float(np.max(gmid[indices])),
        }
    _, first = min(candidates)
    second = first + 1
    y0 = float(gmid[first])
    y1 = float(gmid[second])
    fraction = 0.0 if y1 == y0 else (target_per_v - y0) / (y1 - y0)
    vctrl = float(curve.sweep_v[first] + fraction * (curve.sweep_v[second] - curve.sweep_v[first]))
    current = float(curve.idmag_a[first] + fraction * (curve.idmag_a[second] - curve.idmag_a[first]))
    gds_or_gm = float(derivative[first] + fraction * (derivative[second] - derivative[first]))
    achieved = gds_or_gm / current
    return {
        "state": "validated",
        "target_per_v": target_per_v,
        "vctrl_v": vctrl,
        "idmag_a": current,
        "gm_s": gds_or_gm,
        "achieved_per_v": achieved,
        "relative_error": abs(achieved / target_per_v - 1.0),
        "bracket_indices": [int(first), int(second)],
        "endpoint_reused": False,
    }


def _dc_audit(
    curves: Mapping[str, Curve],
    *,
    configuration: Mapping[str, Any],
    geometry: Geometry,
) -> dict[str, Any]:
    criteria = configuration["calibration"]["criteria"]
    utility = configuration["calibration"]["utility"]
    current_floor = float(configuration["numerical"]["current_floor_a"])
    hard = hard_constraint_observations(curves, current_floor)
    thresholds: dict[str, float | None] = {
        request_id: _threshold(curve)
        for request_id, curve in curves.items()
        if curve.request.kind == "idvg"
    }
    threshold_values = [value for value in thresholds.values() if value is not None]
    threshold_fractions = [value / geometry.native_vdd_v for value in threshold_values]

    idvg_groups: dict[tuple[int, float, float], list[tuple[float, Curve]]] = defaultdict(list)
    for curve in curves.values():
        if curve.request.kind == "idvg":
            key = (curve.request.temperature_c, curve.request.l_m, curve.request.w_m)
            idvg_groups[key].append((curve.request.fixed_bias_v, curve))
    dibl_values: list[float] = []
    for group in idvg_groups.values():
        ordered = sorted(group, key=lambda item: item[0])
        low_v, low_curve = ordered[0]
        high_v, high_curve = ordered[-1]
        low_threshold = _threshold(low_curve)
        high_threshold = _threshold(high_curve)
        if low_threshold is not None and high_threshold is not None and high_v > low_v:
            dibl_values.append((low_threshold - high_threshold) / (high_v - low_v))

    density_groups: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    for curve in curves.values():
        key = (
            curve.request.temperature_c,
            curve.request.kind,
            curve.request.l_m,
            curve.request.fixed_bias_v,
        )
        density_groups[key].append(float(curve.idmag_a[-1] / curve.request.w_m))
    width_errors: list[float] = []
    for densities in density_groups.values():
        center = float(np.median(densities))
        width_errors.extend(abs(value / center - 1.0) for value in densities if center > 0.0)
    challenged_widths_um = sorted(
        {float(curve.request.w_m * 1e6) for curve in curves.values()}
    )

    length_groups: dict[tuple[Any, ...], list[tuple[float, float]]] = defaultdict(list)
    for curve in curves.values():
        key = (
            curve.request.temperature_c,
            curve.request.kind,
            curve.request.w_m,
            curve.request.fixed_bias_v,
        )
        length_groups[key].append((curve.request.l_m, float(curve.idmag_a[-1])))
    length_checks: list[bool] = []
    for group in length_groups.values():
        ordered = sorted(group)
        length_checks.extend(second[1] < first[1] for first, second in zip(ordered, ordered[1:]))
    length_fraction = sum(length_checks) / max(len(length_checks), 1)

    gmid_solutions: list[dict[str, Any]] = []
    for length_ratio in utility["gmid_length_ratios"]:
        for vds_fraction in utility["gmid_vds_fractions"]:
            matches = [
                curve
                for curve in curves.values()
                if curve.request.kind == "idvg"
                and curve.request.temperature_c == 27
                and math.isclose(curve.request.l_m, geometry.lmin_m * float(length_ratio))
                and math.isclose(curve.request.w_m, 1.0e-6)
                and math.isclose(
                    curve.request.fixed_bias_v,
                    geometry.native_vdd_v * float(vds_fraction),
                )
            ]
            if len(matches) != 1:
                raise SynthesisError("calibration grid does not contain one requested gm/Id curve")
            for target in utility["gmid_targets_per_v"]:
                solution = _gmid_solution(
                    matches[0],
                    float(target),
                    current_floor_a=current_floor,
                    endpoint_guard=int(utility["endpoint_guard_points"]),
                )
                solution.update(
                    {
                        "length_ratio": float(length_ratio),
                        "vds_fraction": float(vds_fraction),
                        "request_id": matches[0].request.request_id,
                    }
                )
                gmid_solutions.append(solution)

    checks = {
        "numerical_hard_contract": hard["status"] == "pass",
        "all_thresholds_bracketed": len(threshold_values) == len(thresholds),
        "threshold_guardrail": bool(threshold_fractions)
        and min(threshold_fractions) >= float(criteria["threshold_over_vdd_min"])
        and max(threshold_fractions) <= float(criteria["threshold_over_vdd_max"]),
        "dibl_guardrail": bool(dibl_values)
        and min(dibl_values) >= float(criteria["dibl_min_v_per_v"])
        and max(dibl_values) <= float(criteria["dibl_max_v_per_v"]),
        "gmid_targets_bracketed": bool(gmid_solutions)
        and all(item["state"] == "validated" for item in gmid_solutions),
        "gmid_target_accuracy": bool(gmid_solutions)
        and all(
            item.get("relative_error", math.inf)
            <= float(criteria["gmid_target_relative_tolerance_max"])
            for item in gmid_solutions
        ),
        "gmid_endpoint_reuse_forbidden": bool(gmid_solutions)
        and all(not item.get("endpoint_reused", True) for item in gmid_solutions),
        "width_current_density": _percentile(width_errors, 0.95)
        <= float(criteria["width_current_density_p95_relative_max"]),
        "length_current_order": length_fraction
        >= float(criteria["required_length_current_order_fraction"]),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "hard_contract": hard,
        "metrics": {
            "threshold_over_vdd_min": min(threshold_fractions, default=math.inf),
            "threshold_over_vdd_median": float(np.median(threshold_fractions))
            if threshold_fractions
            else math.inf,
            "threshold_over_vdd_max": max(threshold_fractions, default=math.inf),
            "dibl_min_v_per_v": min(dibl_values, default=math.inf),
            "dibl_median_v_per_v": float(np.median(dibl_values))
            if dibl_values
            else math.inf,
            "dibl_max_v_per_v": max(dibl_values, default=math.inf),
            "width_current_density_p95_relative": _percentile(width_errors, 0.95),
            "length_current_order_fraction": length_fraction,
            "endpoint_current_density_median_a_per_m": float(
                np.median(
                    [curve.idmag_a[-1] / curve.request.w_m for curve in curves.values()]
                )
            ),
        },
        "width_challenge": {
            "challenged_widths_um": challenged_widths_um,
            "p95_relative_to_group_median": _percentile(width_errors, 0.95),
            "max_relative_to_group_median": max(width_errors, default=math.inf),
            "selected_wmin_m": geometry.wmin_m,
            "outcome": (
                str(criteria["width_outcome"])
                if checks["width_current_density"]
                else None
            ),
        },
        "thresholds_v": thresholds,
        "gmid_solutions": gmid_solutions,
    }


def _width_challenge_audit(
    curves: Mapping[str, Curve],
    *,
    configuration: Mapping[str, Any],
    geometry: Geometry,
) -> dict[str, Any]:
    criteria = configuration["calibration"]["criteria"]
    current_floor = float(configuration["numerical"]["current_floor_a"])
    hard = hard_constraint_observations(curves, current_floor)
    expected_widths_um = sorted(
        float(value) for value in configuration["width_challenge"]["widths_um"]
    )
    observed_widths_um = sorted(
        {float(curve.request.w_m * 1e6) for curve in curves.values()}
    )
    density_groups: dict[tuple[Any, ...], list[tuple[float, float]]] = defaultdict(list)
    for curve in curves.values():
        key = (
            curve.request.temperature_c,
            curve.request.kind,
            curve.request.l_m,
            curve.request.fixed_bias_v,
        )
        density_groups[key].append(
            (curve.request.w_m, float(curve.idmag_a[-1] / curve.request.w_m))
        )
    width_errors: list[float] = []
    raw_current_order: list[bool] = []
    for group in density_groups.values():
        densities = [item[1] for item in group]
        center = float(np.median(densities))
        width_errors.extend(
            abs(value / center - 1.0) for value in densities if center > 0.0
        )
        ordered = sorted(group)
        raw_current_order.extend(
            second[0] * second[1] > first[0] * first[1]
            for first, second in zip(ordered, ordered[1:])
        )
    p95 = _percentile(width_errors, 0.95)
    checks = {
        "numerical_hard_contract": hard["status"] == "pass",
        "all_frozen_widths_challenged": len(observed_widths_um) == len(expected_widths_um)
        and all(
            math.isclose(observed, expected)
            for observed, expected in zip(observed_widths_um, expected_widths_um)
        ),
        "current_density_invariant": p95
        <= float(criteria["width_current_density_p95_relative_max"]),
        "raw_current_strictly_increases_with_width": bool(raw_current_order)
        and all(raw_current_order),
        "selected_floor_matches_challenge_floor": math.isclose(
            geometry.wmin_m, expected_widths_um[0] * 1e-6
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "hard_contract": hard,
        "challenged_widths_um": observed_widths_um,
        "selected_wmin_m": geometry.wmin_m,
        "outcome": str(criteria["width_outcome"]) if all(checks.values()) else None,
        "metrics": {
            "current_density_p95_relative_to_group_median": p95,
            "current_density_max_relative_to_group_median": max(
                width_errors, default=math.inf
            ),
            "raw_current_order_fraction": sum(raw_current_order)
            / max(len(raw_current_order), 1),
        },
    }


def _geometry_floor_study(
    *,
    evaluator: NgspiceEvaluator,
    configuration: Mapping[str, Any],
    root: Path,
) -> dict[str, Any]:
    """Select the shortest calibration-feasible L floor from the frozen search."""

    release = _load_toml(root / "validation/release_gates_v4.toml")
    study_grid = {**configuration["calibration"]["dc"], "widths_um": [1.0]}
    families: dict[str, Any] = {}
    all_selected_match = True
    for family in ("io25", "io18"):
        configured = _geometry(configuration, family)
        candidates: list[dict[str, Any]] = []
        for candidate_um in release["geometry"][family]["initial_candidate_l_floor_um"]:
            geometry = Geometry(
                family=family,
                lmin_m=float(candidate_um) * 1e-6,
                lmax_m=configured.lmax_m,
                wmin_m=configured.wmin_m,
                wmax_m=configured.wmax_m,
                native_vdd_v=configured.native_vdd_v,
            )
            polarity_records: dict[str, Any] = {}
            for polarity in ("n", "p"):
                parameters = _center_parameters(configuration, family, polarity)
                model_name = f"apm045_{family}_{polarity}core"
                card = render_bsim4_card(
                    model_name=model_name,
                    polarity=polarity,
                    parameters=parameters,
                    lmin_m=geometry.lmin_m,
                    lmax_m=geometry.lmax_m,
                    wmin_m=geometry.wmin_m,
                    wmax_m=geometry.wmax_m,
                )
                curves = evaluator.evaluate_many(
                    source=ModelSource(model_name=model_name, rendered_card=card),
                    polarity=polarity,
                    requests=_grid_requests(
                        family=family,
                        geometry=geometry,
                        grid=study_grid,
                    ),
                    token=f"{family}-{polarity}-lfloor-{float(candidate_um):.4g}",
                    measure_terminal_cgg=False,
                )
                audit = _dc_audit(curves, configuration=configuration, geometry=geometry)
                polarity_records[polarity] = {
                    "status": audit["status"],
                    "checks": audit["checks"],
                    "metrics": audit["metrics"],
                }
            candidates.append(
                {
                    "l_floor_um": float(candidate_um),
                    "status": (
                        "pass"
                        if all(item["status"] == "pass" for item in polarity_records.values())
                        else "fail"
                    ),
                    "polarities": polarity_records,
                }
            )
        eligible = [item for item in candidates if item["status"] == "pass"]
        selected_um = min((item["l_floor_um"] for item in eligible), default=math.inf)
        selected_matches = math.isclose(configured.lmin_m, selected_um * 1e-6)
        all_selected_match = all_selected_match and selected_matches
        families[family] = {
            "search_candidates_um": [item["l_floor_um"] for item in candidates],
            "qualification_length_ratios": [
                float(value) for value in study_grid["length_ratios"]
            ],
            "reference_width_um": 1.0,
            "candidates": candidates,
            "shortest_calibration_feasible_um": selected_um,
            "configured_lmin_m": configured.lmin_m,
            "configured_floor_is_shortest_calibration_feasible": selected_matches,
            "selection_state": "PROVISIONAL_PENDING_SEALED_HOLDOUT",
        }
    return {
        "status": "pass" if all_selected_match else "fail",
        "families": families,
        "claim_boundary": (
            "This calibration study selects an APM-supported candidate floor; "
            "it is not a foundry design-rule minimum and remains provisional until "
            "the sealed holdout passes."
        ),
    }


def _charge_audit(
    curves: Mapping[str, Curve], *, configuration: Mapping[str, Any]
) -> dict[str, Any]:
    criteria = configuration["calibration"]["criteria"]
    current_floor = float(configuration["numerical"]["current_floor_a"])
    hard = hard_constraint_observations(curves, current_floor)
    densities: list[float] = []
    trajectories: dict[str, float] = {}
    for request_id, curve in curves.items():
        if curve.terminal_cgg_f is None:
            raise SynthesisError(f"{request_id}: terminal Cgg is absent")
        densities.extend((curve.terminal_cgg_f / (curve.request.w_m * curve.request.l_m)).tolist())
        trajectories[request_id] = float(
            np.sum(
                0.5
                * (curve.terminal_cgg_f[:-1] + curve.terminal_cgg_f[1:])
                * np.diff(curve.sweep_v)
            )
        )
    checks = {
        "numerical_hard_contract": hard["status"] == "pass",
        "terminal_cgg_present": bool(densities),
        "terminal_cgg_density_guardrail": bool(densities)
        and min(densities) >= float(criteria["cgg_density_min_f_per_m2"])
        and max(densities) <= float(criteria["cgg_density_max_f_per_m2"]),
        "positive_integrated_gate_charge": bool(trajectories)
        and all(value > 0.0 and math.isfinite(value) for value in trajectories.values()),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "hard_contract": hard,
        "metrics": {
            "cgg_density_min_f_per_m2": min(densities, default=math.inf),
            "cgg_density_median_f_per_m2": float(np.median(densities))
            if densities
            else math.inf,
            "cgg_density_max_f_per_m2": max(densities, default=math.inf),
            "integrated_gate_charge_min_c": min(trajectories.values(), default=math.inf),
            "integrated_gate_charge_max_c": max(trajectories.values(), default=math.inf),
        },
        "integrated_gate_charge_c": trajectories,
    }


def _temperature_audit(
    curves: Mapping[str, Curve],
    *,
    configuration: Mapping[str, Any],
    geometry: Geometry,
) -> dict[str, Any]:
    criteria = configuration["calibration"]["criteria"]
    grid = configuration["calibration"]["temperature"]
    current_floor = float(configuration["numerical"]["current_floor_a"])
    hard = hard_constraint_observations(curves, current_floor)
    expected_temperatures = sorted(int(value) for value in grid["temperatures_c"])
    observed_temperatures = sorted(
        {curve.request.temperature_c for curve in curves.values()}
    )

    endpoint_groups: dict[tuple[Any, ...], list[tuple[int, float]]] = defaultdict(list)
    thresholds: list[float] = []
    for curve in curves.values():
        key = (
            curve.request.kind,
            curve.request.l_m,
            curve.request.w_m,
            curve.request.fixed_bias_v,
        )
        endpoint_groups[key].append(
            (curve.request.temperature_c, float(curve.idmag_a[-1]))
        )
        if curve.request.kind == "idvg":
            threshold = _threshold(curve)
            if threshold is not None:
                thresholds.append(threshold)

    current_ratios: list[float] = []
    for group in endpoint_groups.values():
        values = [item[1] for item in sorted(group)]
        if values and min(values) > 0.0:
            current_ratios.append(max(values) / min(values))
    threshold_span = (
        (max(thresholds) - min(thresholds)) / geometry.native_vdd_v
        if thresholds
        else math.inf
    )
    checks = {
        "numerical_hard_contract": hard["status"] == "pass",
        "all_calibration_temperatures_observed": observed_temperatures
        == expected_temperatures,
        "all_idvg_thresholds_bracketed": len(thresholds)
        == sum(curve.request.kind == "idvg" for curve in curves.values()),
        "finite_bounded_current_ratio": bool(current_ratios)
        and min(current_ratios)
        >= float(criteria["calibration_temperature_current_ratio_min"])
        and max(current_ratios)
        <= float(criteria["calibration_temperature_current_ratio_max"]),
        "threshold_span_guardrail": threshold_span
        <= float(criteria["temperature_threshold_span_over_vdd_max"]),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "hard_contract": hard,
        "temperatures_c": observed_temperatures,
        "metrics": {
            "endpoint_current_ratio_min": min(current_ratios, default=math.inf),
            "endpoint_current_ratio_median": float(np.median(current_ratios))
            if current_ratios
            else math.inf,
            "endpoint_current_ratio_max": max(current_ratios, default=math.inf),
            "threshold_span_over_vdd": threshold_span,
        },
    }


def _evaluate_calibration_domains(
    *,
    evaluator: NgspiceEvaluator,
    configuration: Mapping[str, Any],
    geometry: Geometry,
    family: str,
    polarity: str,
    parameters: Mapping[str, float],
    token: str,
    domains: tuple[str, ...],
) -> dict[str, Any]:
    card = _render_candidate(configuration, family, polarity, parameters)
    source = ModelSource(
        model_name=f"apm045_{family}_{polarity}core", rendered_card=card
    )
    audits: dict[str, Any] = {}
    if "dc" in domains:
        curves = evaluator.evaluate_many(
            source=source,
            polarity=polarity,
            requests=_grid_requests(
                family=family,
                geometry=geometry,
                grid=configuration["calibration"]["dc"],
            ),
            token=f"{token}-dc",
            measure_terminal_cgg=False,
        )
        audits["dc"] = _dc_audit(
            curves, configuration=configuration, geometry=geometry
        )
    if "width" in domains:
        curves = evaluator.evaluate_many(
            source=source,
            polarity=polarity,
            requests=_grid_requests(
                family=family,
                geometry=geometry,
                grid=configuration["width_challenge"],
            ),
            token=f"{token}-width",
            measure_terminal_cgg=False,
        )
        audits["width"] = _width_challenge_audit(
            curves,
            configuration=configuration,
            geometry=geometry,
        )
    if "charge" in domains:
        charge_grid = {
            **configuration["calibration"]["charge"],
            "idvd_fixed_bias_fractions": [],
        }
        curves = evaluator.evaluate_many(
            source=source,
            polarity=polarity,
            requests=_grid_requests(
                family=family,
                geometry=geometry,
                grid=charge_grid,
            ),
            token=f"{token}-charge",
            measure_terminal_cgg=True,
        )
        audits["charge"] = _charge_audit(curves, configuration=configuration)
    if "temperature" in domains:
        curves = evaluator.evaluate_many(
            source=source,
            polarity=polarity,
            requests=_grid_requests(
                family=family,
                geometry=geometry,
                grid=configuration["calibration"]["temperature"],
            ),
            token=f"{token}-temperature",
            measure_terminal_cgg=False,
        )
        audits["temperature"] = _temperature_audit(
            curves,
            configuration=configuration,
            geometry=geometry,
        )
    if set(audits) != set(domains):
        raise SynthesisError(f"unsupported calibration domain set: {domains!r}")
    return {
        "status": (
            "pass" if audits and all(item["status"] == "pass" for item in audits.values()) else "fail"
        ),
        "audits": audits,
    }


def _qualify_polarity_candidate(
    *,
    evaluator: NgspiceEvaluator,
    configuration: Mapping[str, Any],
    output: Path,
    family: str,
    polarity: str,
    seed: int,
) -> dict[str, Any]:
    geometry = _geometry(configuration, family)
    draws = _draws(configuration, family, polarity, seed)
    center = _center_parameters(configuration, family, polarity)
    parameters = dict(center)
    stage_domains = {
        "electrostatics": ("dc",),
        "transport": ("dc", "width"),
        "output": ("dc",),
        "charge": ("charge",),
        "temperature": ("temperature",),
    }
    stage_records: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        stage_parameters = [
            item for item in _variation_parameters(configuration) if item.stage == stage
        ]
        attempts: list[dict[str, Any]] = []
        accepted_parameters: dict[str, float] | None = None
        for scale in configuration["stage_refinement_factors"]:
            trial = dict(parameters)
            for item in stage_parameters:
                trial[item.name] = item.resolve(
                    center[item.name], draws[item.name], float(scale)
                )
            evaluation = _evaluate_calibration_domains(
                evaluator=evaluator,
                configuration=configuration,
                geometry=geometry,
                family=family,
                polarity=polarity,
                parameters=trial,
                token=(
                    f"{family}-{seed}-{polarity}-stage-{stage}"
                    f"-scale-{float(scale):.2f}"
                ),
                domains=stage_domains[stage],
            )
            attempts.append(
                {
                    "scale": float(scale),
                    "status": evaluation["status"],
                    "parameter_sha256": sha256_bytes(
                        canonical_json(trial).encode("utf-8")
                    ),
                    "audits": evaluation["audits"],
                }
            )
            if evaluation["status"] == "pass":
                accepted_parameters = trial
                break
        stage_record = {
            "stage": stage,
            "parameters": [item.name for item in stage_parameters],
            "status": "pass" if accepted_parameters is not None else "fail",
            "selected_refinement_scale": (
                attempts[-1]["scale"] if accepted_parameters is not None else None
            ),
            "attempts": attempts,
        }
        stage_records.append(stage_record)
        if accepted_parameters is None:
            return {
                "family": family,
                "polarity": polarity,
                "seed": seed,
                "status": "fail",
                "failure_stage": stage,
                "draws": draws,
                "stages": stage_records,
            }
        parameters = accepted_parameters

    final = _evaluate_calibration_domains(
        evaluator=evaluator,
        configuration=configuration,
        geometry=geometry,
        family=family,
        polarity=polarity,
        parameters=parameters,
        token=f"{family}-{seed}-{polarity}-final",
        domains=("dc", "width", "charge", "temperature"),
    )
    if final["status"] != "pass":
        return {
            "family": family,
            "polarity": polarity,
            "seed": seed,
            "status": "fail",
            "failure_stage": "final_cross_domain_recheck",
            "draws": draws,
            "stages": stage_records,
            "final_calibration": final["audits"],
        }
    card = _render_candidate(configuration, family, polarity, parameters)
    card_directory = output / "cards" / family / str(seed)
    card_directory.mkdir(parents=True, exist_ok=True)
    card_path = card_directory / f"{polarity}.inc"
    card_path.write_text(card, encoding="utf-8")
    return {
        "family": family,
        "polarity": polarity,
        "seed": seed,
        "status": "pass",
        "draws": draws,
        "selected_refinement_scales": {
            item["stage"]: item["selected_refinement_scale"] for item in stage_records
        },
        "parameters": parameters,
        "parameter_sha256": sha256_bytes(
            canonical_json(parameters).encode("utf-8")
        ),
        "card": {
            "path": str(card_path.relative_to(output)),
            "sha256": sha256_file(card_path),
            "byte_identical_regeneration": card_path.read_bytes()
            == _render_candidate(
                configuration, family, polarity, parameters
            ).encode("utf-8"),
        },
        "stages": stage_records,
        "calibration": final["audits"],
    }


def calibrate(
    *, root: Path, output: Path, configuration_path: Path
) -> dict[str, Any]:
    configuration = _load_toml(configuration_path)
    configuration_audit = _validate_configuration(configuration, root)
    if output.exists():
        if any(output.iterdir()):
            raise SynthesisError(f"output directory is not empty: {output}")
    else:
        output.mkdir(parents=True)
    ngspice = root / ".apm/toolchain/ngspice-47/bin/ngspice"
    evaluator = NgspiceEvaluator(ngspice=ngspice, work_directory=output / "work")
    tool_identity = evaluator.tool_identity()
    if tool_identity["major"] != str(configuration["reference_simulator_major"]):
        raise SynthesisError("mixed-voltage generation requires ngspice 47")

    geometry_floor_study = _geometry_floor_study(
        evaluator=evaluator,
        configuration=configuration,
        root=root,
    )

    records: list[dict[str, Any]] = []
    for family in ("io25", "io18"):
        for seed in configuration["seeds"]:
            for polarity in ("n", "p"):
                records.append(
                    _qualify_polarity_candidate(
                        evaluator=evaluator,
                        configuration=configuration,
                        output=output,
                        family=family,
                        polarity=polarity,
                        seed=int(seed),
                    )
                )

    retained: dict[str, list[int]] = {}
    ensemble_checks: dict[str, Any] = {}
    for family in ("io25", "io18"):
        by_seed: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            if record["family"] == family:
                by_seed[int(record["seed"])].append(record)
        retained[family] = sorted(
            seed
            for seed, pair in by_seed.items()
            if len(pair) == 2 and all(item["status"] == "pass" for item in pair)
        )
        parameter_hashes = {
            item["parameter_sha256"]
            for item in records
            if item["family"] == family
            and int(item["seed"]) in retained[family]
            and item["status"] == "pass"
        }
        ensemble_checks[family] = {
            "retained_count": len(retained[family]),
            "minimum_required": int(configuration["minimum_retained_candidates_per_family"]),
            "minimum_count": len(retained[family])
            >= int(configuration["minimum_retained_candidates_per_family"]),
            "independently_seeded": len(parameter_hashes) == 2 * len(retained[family]),
        }
    status = (
        "pass"
        if geometry_floor_study["status"] == "pass" and all(
            item["minimum_count"] and item["independently_seeded"]
            for item in ensemble_checks.values()
        )
        else "fail"
    )
    sealed_sections = {
        name: {
            "definition_sha256": sha256_bytes(
                canonical_json(configuration[name]).encode("utf-8")
            ),
            "evaluated": False,
        }
        for name in (
            "sealed_device_holdout",
            "sealed_charge_holdout",
            "sealed_circuit_holdout",
        )
    }
    report = {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "completion_state": CALIBRATION_COMPLETION_STATE if status == "pass" else None,
        "mode": "calibration_only",
        "generation_epoch": int(configuration["generation_epoch"]),
        "configuration": {
            "path": str(configuration_path.relative_to(root)),
            "sha256": sha256_file(configuration_path),
            "audit": configuration_audit,
        },
        "kernel": {
            "id": KERNEL_ID,
            "version": KERNEL_VERSION,
            "implementation": str(Path(__file__).with_name("kernel.py").relative_to(root)),
            "implementation_sha256": sha256_file(Path(__file__).with_name("kernel.py")),
            "synthesis_implementation": str(Path(__file__).relative_to(root)),
            "synthesis_implementation_sha256": sha256_file(Path(__file__)),
        },
        "reference_tool": tool_identity,
        "public_input": {
            "evidence_matrix": "models/apm045/mixed_voltage_evidence.toml",
            "evidence_matrix_sha256": sha256_file(
                root / "models/apm045/mixed_voltage_evidence.toml"
            ),
            "private_or_proprietary_parameter_input": False,
            "source_card_parameter_input": False,
        },
        "ensemble": {
            "candidate_seeds": [int(seed) for seed in configuration["seeds"]],
            "retained_seeds": retained,
            "checks": ensemble_checks,
            "epistemic_not_process_variation": True,
        },
        "geometry_floor_study": geometry_floor_study,
        "sealed_definitions": sealed_sections,
        "simulator_evaluation_count": evaluator.evaluation_count,
        "records": records,
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("generation_epoch_1.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibration-only", action="store_true", required=True)
    parser.add_argument("--replace-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    root = arguments.root.resolve()
    output = arguments.output.resolve()
    if arguments.replace_output and output.exists():
        shutil.rmtree(output)
    report = calibrate(
        root=root,
        output=output,
        configuration_path=arguments.config.resolve(),
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
