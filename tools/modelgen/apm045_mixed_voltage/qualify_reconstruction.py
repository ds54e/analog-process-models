# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Qualify the v4 offline kernel on sealed APM022/SVT and APM045/VTG holdouts."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
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
    TERMINAL_AC_FREQUENCY_HZ,
    Curve,
    FitSettings,
    ModelgenError,
    ModelSource,
    NgspiceEvaluator,
    ParameterBound,
    SweepRequest,
    canonical_json,
    curves_sha256,
    fit_staged,
    hard_constraint_observations,
    qualified_current_floor,
    render_bsim4_card,
    sha256_bytes,
    sha256_file,
    terminal_derivative,
)

SCHEMA = "apm.modelgen.reconstruction-qualification.v1"
COMPLETION_STATE = "MODELGEN_KERNEL_QUALIFIED"
SUBSET_COMPLETION_STATE = "MODELGEN_RECONSTRUCTION_SUBSET_PASS"
REQUIRED_RECORD_IDS = (
    "apm022_svt-n",
    "apm022_svt-p",
    "apm045_vtg-n",
    "apm045_vtg-p",
)


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _percentile(values: Iterable[float], fraction: float) -> float:
    collected = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not collected:
        return math.inf
    if len(collected) == 1:
        return collected[0]
    position = fraction * (len(collected) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return collected[lower]
    weight = position - lower
    return collected[lower] * (1.0 - weight) + collected[upper] * weight


def _grid_requests(fixture: Mapping[str, Any], grid: Mapping[str, Any]) -> list[SweepRequest]:
    requests: list[SweepRequest] = []
    vdd = float(fixture["vdd_v"])
    lmin = float(fixture["lmin_m"])
    points = int(grid["points"])
    for temperature in grid["temperatures_c"]:
        for length_ratio in grid["length_ratios"]:
            for width_um in grid["widths_um"]:
                length = lmin * float(length_ratio)
                width = float(width_um) * 1e-6
                stem = f"t{int(temperature):+d}-lr{float(length_ratio):.4g}-w{float(width_um):.4g}u"
                for fraction in grid["idvg_fixed_bias_fractions"]:
                    requests.append(
                        SweepRequest(
                            request_id=f"{stem}-idvg-vd{float(fraction):.4g}",
                            kind="idvg",
                            temperature_c=int(temperature),
                            l_m=length,
                            w_m=width,
                            fixed_bias_v=vdd * float(fraction),
                            sweep_stop_v=vdd,
                            points=points,
                        )
                    )
                for fraction in grid["idvd_fixed_bias_fractions"]:
                    requests.append(
                        SweepRequest(
                            request_id=f"{stem}-idvd-vg{float(fraction):.4g}",
                            kind="idvd",
                            temperature_c=int(temperature),
                            l_m=length,
                            w_m=width,
                            fixed_bias_v=vdd * float(fraction),
                            sweep_stop_v=vdd,
                            points=points,
                        )
                    )
    return requests


def _reference_source(root: Path, fixture: Mapping[str, Any], polarity: str) -> ModelSource:
    include_key = f"reference_include_{polarity}"
    include_values = fixture.get(include_key, fixture.get("reference_include"))
    if isinstance(include_values, str):
        include_values = [include_values]
    if not isinstance(include_values, list) or not include_values:
        raise ModelgenError(f"{fixture['id']}/{polarity}: reference include is missing")
    includes = tuple((root / value).resolve() for value in include_values)
    if not all(path.is_file() for path in includes):
        raise ModelgenError(f"{fixture['id']}/{polarity}: reference include is missing")
    return ModelSource(
        model_name=str(fixture[f"reference_model_{polarity}"]), include_paths=includes
    )


def _evaluate_by_temperature(
    evaluator: NgspiceEvaluator,
    *,
    source: ModelSource,
    polarity: str,
    requests: Sequence[SweepRequest],
    token_prefix: str,
    measure_terminal_cgg: bool,
) -> dict[str, Curve]:
    grouped: dict[int, list[SweepRequest]] = defaultdict(list)
    for request in requests:
        grouped[request.temperature_c].append(request)
    result: dict[str, Curve] = {}
    for temperature, group in sorted(grouped.items()):
        result.update(
            evaluator.evaluate(
                source=source,
                polarity=polarity,
                requests=group,
                token=f"{token_prefix}-t{temperature:+d}",
                measure_terminal_cgg=measure_terminal_cgg,
            )
        )
    return result


def _threshold(curve: Curve, coefficient_a: float = 1e-7) -> float | None:
    target = coefficient_a * curve.request.w_m / curve.request.l_m
    for index in range(curve.idmag_a.size - 1):
        low = float(curve.idmag_a[index])
        high = float(curve.idmag_a[index + 1])
        if low <= target <= high and high > low:
            fraction = (target - low) / (high - low)
            return float(
                curve.sweep_v[index] + fraction * (curve.sweep_v[index + 1] - curve.sweep_v[index])
            )
    return None


def _finite_difference_step_disagreement(curve: Curve, current_floor_a: float) -> list[float]:
    values: list[float] = []
    x = curve.sweep_v
    y = curve.idmag_a
    for index in range(2, y.size - 2):
        if y[index] < qualified_current_floor(curve.request, current_floor_a):
            continue
        h1 = x[index + 1] - x[index]
        h2 = x[index + 2] - x[index]
        first = (y[index + 1] - y[index - 1]) / (2.0 * h1)
        second = (y[index + 2] - y[index - 2]) / (2.0 * h2)
        scale = max(abs(first), abs(second), 1e-30)
        values.append(abs(first - second) / scale)
    return values


def _trend_observations(
    candidate: Mapping[str, Curve], target: Mapping[str, Curve]
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    grouped: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for request_id, curve in target.items():
        request = curve.request
        key = (
            request.kind,
            request.temperature_c,
            request.w_m,
            request.fixed_bias_v,
        )
        grouped[key].append(request_id)
    for key, request_ids in sorted(grouped.items(), key=lambda item: str(item[0])):
        ordered = sorted(request_ids, key=lambda item: target[item].request.l_m)
        for first_id, second_id in zip(ordered, ordered[1:]):
            target_delta = float(target[second_id].idmag_a[-1] - target[first_id].idmag_a[-1])
            candidate_delta = float(
                candidate[second_id].idmag_a[-1] - candidate[first_id].idmag_a[-1]
            )
            observations.append(
                {
                    "kind": "length_endpoint_current",
                    "first": first_id,
                    "second": second_id,
                    "target_delta_a": target_delta,
                    "candidate_delta_a": candidate_delta,
                    "agrees": target_delta == 0.0
                    or math.copysign(1.0, target_delta) == math.copysign(1.0, candidate_delta),
                }
            )
    temperature_groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for request_id, curve in target.items():
        request = curve.request
        key = (request.kind, request.l_m, request.w_m, request.fixed_bias_v)
        temperature_groups[key].append(request_id)
    for key, request_ids in sorted(temperature_groups.items(), key=lambda item: str(item[0])):
        ordered = sorted(request_ids, key=lambda item: target[item].request.temperature_c)
        for first_id, second_id in zip(ordered, ordered[1:]):
            target_delta = float(target[second_id].idmag_a[-1] - target[first_id].idmag_a[-1])
            candidate_delta = float(
                candidate[second_id].idmag_a[-1] - candidate[first_id].idmag_a[-1]
            )
            observations.append(
                {
                    "kind": "temperature_endpoint_current",
                    "first": first_id,
                    "second": second_id,
                    "target_delta_a": target_delta,
                    "candidate_delta_a": candidate_delta,
                    "agrees": target_delta == 0.0
                    or math.copysign(1.0, target_delta) == math.copysign(1.0, candidate_delta),
                }
            )
    agreement = sum(bool(item["agrees"]) for item in observations) / max(len(observations), 1)
    return {"agreement_fraction": agreement, "observations": observations}


def _holdout_audit(
    candidate: Mapping[str, Curve],
    target: Mapping[str, Curve],
    *,
    current_floor_a: float,
    criteria: Mapping[str, Any],
) -> dict[str, Any]:
    current_log_errors: list[float] = []
    threshold_errors: list[float] = []
    gmid_log_errors: list[float] = []
    gdsid_log_errors: list[float] = []
    cgg_log_errors: list[float] = []
    derivative_step_errors: list[float] = []
    threshold_status: dict[str, str] = {}
    for request_id, reference in sorted(target.items()):
        observed = candidate[request_id]
        qualified_floor_a = qualified_current_floor(reference.request, current_floor_a)
        mask = reference.idmag_a >= qualified_floor_a
        current_log_errors.extend(
            np.abs(
                np.log10(
                    np.maximum(observed.idmag_a[mask], qualified_floor_a)
                    / np.maximum(reference.idmag_a[mask], qualified_floor_a)
                )
            ).tolist()
        )
        derivative_step_errors.extend(
            _finite_difference_step_disagreement(observed, current_floor_a)
        )
        interior = mask.copy()
        interior[:2] = False
        interior[-2:] = False
        if reference.request.kind == "idvg":
            reference_threshold = _threshold(reference)
            observed_threshold = _threshold(observed)
            if reference_threshold is None or observed_threshold is None:
                threshold_status[request_id] = "not_bracketed"
            else:
                threshold_status[request_id] = "validated"
                threshold_errors.append(abs(observed_threshold - reference_threshold))
            reference_gmid = terminal_derivative(reference)[interior] / np.maximum(
                reference.idmag_a[interior], qualified_floor_a
            )
            observed_gmid = terminal_derivative(observed)[interior] / np.maximum(
                observed.idmag_a[interior], qualified_floor_a
            )
            valid = (reference_gmid > 0.0) & (observed_gmid > 0.0)
            gmid_log_errors.extend(
                np.abs(np.log(observed_gmid[valid] / reference_gmid[valid])).tolist()
            )
            if reference.terminal_cgg_f is None or observed.terminal_cgg_f is None:
                raise ModelgenError(f"{request_id}: terminal Cgg observation is missing")
            valid_cgg = (reference.terminal_cgg_f[interior] > 0.0) & (
                observed.terminal_cgg_f[interior] > 0.0
            )
            cgg_log_errors.extend(
                np.abs(
                    np.log(
                        observed.terminal_cgg_f[interior][valid_cgg]
                        / reference.terminal_cgg_f[interior][valid_cgg]
                    )
                ).tolist()
            )
        else:
            reference_gdsid = terminal_derivative(reference)[interior] / np.maximum(
                reference.idmag_a[interior], qualified_floor_a
            )
            observed_gdsid = terminal_derivative(observed)[interior] / np.maximum(
                observed.idmag_a[interior], qualified_floor_a
            )
            valid = (reference_gdsid > 0.0) & (observed_gdsid > 0.0)
            gdsid_log_errors.extend(
                np.abs(np.log(observed_gdsid[valid] / reference_gdsid[valid])).tolist()
            )
    metrics = {
        "current_log_median_dec": _percentile(current_log_errors, 0.50),
        "current_log_p95_dec": _percentile(current_log_errors, 0.95),
        "threshold_error_p95_v": _percentile(threshold_errors, 0.95),
        "gmid_log_p95": _percentile(gmid_log_errors, 0.95),
        "gdsid_log_p95": _percentile(gdsid_log_errors, 0.95),
        "cgg_log_p95": _percentile(cgg_log_errors, 0.95),
        "terminal_derivative_step_p95": _percentile(derivative_step_errors, 0.95),
    }
    trends = _trend_observations(candidate, target)
    hard = hard_constraint_observations(candidate, current_floor_a)
    checks = {
        "numerical_hard_contract": hard["status"] == "pass",
        "all_thresholds_bracketed": bool(threshold_status)
        and all(state == "validated" for state in threshold_status.values()),
        "current_log_median": metrics["current_log_median_dec"]
        <= float(criteria["holdout_current_log_median_max_dec"]),
        "current_log_p95": metrics["current_log_p95_dec"]
        <= float(criteria["holdout_current_log_p95_max_dec"]),
        "threshold_error_p95": metrics["threshold_error_p95_v"]
        <= float(criteria["holdout_threshold_error_p95_max_v"]),
        "gmid_log_p95": metrics["gmid_log_p95"] <= float(criteria["holdout_gmid_log_p95_max"]),
        "gdsid_log_p95": metrics["gdsid_log_p95"] <= float(criteria["holdout_gdsid_log_p95_max"]),
        "cgg_log_p95": metrics["cgg_log_p95"] <= float(criteria["holdout_cgg_log_p95_max"]),
        "terminal_derivative_step_p95": metrics["terminal_derivative_step_p95"]
        <= float(criteria["holdout_terminal_derivative_step_p95_max"]),
        "trend_agreement": trends["agreement_fraction"]
        >= float(criteria["required_trend_agreement_fraction"]),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "metrics": metrics,
        "sample_counts": {
            "current": len(current_log_errors),
            "threshold": len(threshold_errors),
            "gmid": len(gmid_log_errors),
            "gdsid": len(gdsid_log_errors),
            "cgg": len(cgg_log_errors),
            "finite_difference": len(derivative_step_errors),
        },
        "threshold_status": threshold_status,
        "hard_contract": hard,
        "trends": trends,
    }


def _parameter_bounds(configuration: Mapping[str, Any], polarity: str) -> list[ParameterBound]:
    result: list[ParameterBound] = []
    for item in configuration["parameter"]:
        result.append(
            ParameterBound(
                name=str(item["name"]),
                stage=str(item["stage"]),
                lower=float(item["lower"]),
                initial=float(item[f"initial_{polarity}"]),
                upper=float(item["upper"]),
                transform=str(item.get("transform", "linear")),
            )
        )
    return result


def _fit_settings(configuration: Mapping[str, Any]) -> FitSettings:
    return FitSettings(
        seeds=tuple(int(value) for value in configuration["seeds"]),
        starts_per_stage=int(configuration["starts_per_stage"]),
        local_max_nfev=int(configuration["local_max_nfev"]),
        sensitivity_fraction=float(configuration["sensitivity_fraction"]),
        current_floor_a=float(configuration["current_floor_a"]),
        current_log_tolerance_dec=float(configuration["current_log_tolerance_dec"]),
        gmid_log_tolerance=float(configuration["gmid_log_tolerance"]),
        gdsid_log_tolerance=float(configuration["gdsid_log_tolerance"]),
        cgg_log_tolerance=float(configuration["cgg_log_tolerance"]),
    )


def _coverage(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    observed = sorted(str(record["id"]) for record in records)
    expected = sorted(REQUIRED_RECORD_IDS)
    return {
        "required_record_ids": expected,
        "observed_record_ids": observed,
        "full_required_coverage": observed == expected,
    }


def qualify(
    *,
    root: Path,
    output: Path,
    configuration_path: Path,
    fixture_filter: set[str] | None = None,
    polarity_filter: set[str] | None = None,
) -> dict[str, Any]:
    configuration = _load_toml(configuration_path)
    if configuration.get("schema") != "apm.modelgen.reconstruction-input.v1":
        raise ModelgenError("unexpected reconstruction input schema")
    settings = _fit_settings(configuration)
    criteria = configuration["criteria"]
    ngspice = root / ".apm/toolchain/ngspice-47/bin/ngspice"
    if output.exists():
        if any(output.iterdir()):
            raise ModelgenError(f"output directory is not empty: {output}")
    else:
        output.mkdir(parents=True)
    evaluator = NgspiceEvaluator(ngspice=ngspice, work_directory=output / "work")
    tool_identity = evaluator.tool_identity()
    if tool_identity["major"] != str(configuration["reference_simulator_major"]):
        raise ModelgenError("reconstruction requires ngspice 47")
    result_records: list[dict[str, Any]] = []
    cards_directory = output / "cards"
    cards_directory.mkdir()
    for fixture in configuration["fixture"]:
        fixture_id = str(fixture["id"])
        if fixture_filter and fixture_id not in fixture_filter:
            continue
        calibration_requests = _grid_requests(fixture, fixture["calibration"])
        holdout_definition_hash = sha256_bytes(canonical_json(fixture["holdout"]).encode("utf-8"))
        for polarity in ("n", "p"):
            if polarity_filter and polarity not in polarity_filter:
                continue
            record_id = f"{fixture_id}-{polarity}"
            reference = _reference_source(root, fixture, polarity)
            calibration_target = _evaluate_by_temperature(
                evaluator,
                source=reference,
                polarity=polarity,
                requests=calibration_requests,
                token_prefix=f"{record_id}-calibration-reference",
                measure_terminal_cgg=True,
            )
            model_name = f"apm_reconstruction_{fixture_id}_{polarity}"
            fit = fit_staged(
                evaluator=evaluator,
                target=calibration_target,
                requests=calibration_requests,
                polarity=polarity,
                model_name=model_name,
                fixed_parameters={
                    name: float(value) for name, value in configuration["fixed_parameters"].items()
                },
                bounds=_parameter_bounds(configuration, polarity),
                geometry_bounds={
                    key: float(fixture[key]) for key in ("lmin_m", "lmax_m", "wmin_m", "wmax_m")
                },
                settings=settings,
            )
            card_path = cards_directory / f"{record_id}.inc"
            card_path.write_text(fit.rendered_card, encoding="utf-8")
            repeat = render_bsim4_card(
                model_name=model_name,
                polarity=polarity,
                parameters=fit.parameters,
                lmin_m=float(fixture["lmin_m"]),
                lmax_m=float(fixture["lmax_m"]),
                wmin_m=float(fixture["wmin_m"]),
                wmax_m=float(fixture["wmax_m"]),
            )
            regeneration_check = repeat.encode("utf-8") == card_path.read_bytes()

            # The committed definition is unsealed only after fitting is complete.
            holdout_requests = _grid_requests(fixture, fixture["holdout"])
            holdout_target = _evaluate_by_temperature(
                evaluator,
                source=reference,
                polarity=polarity,
                requests=holdout_requests,
                token_prefix=f"{record_id}-holdout-reference",
                measure_terminal_cgg=True,
            )
            holdout_candidate = _evaluate_by_temperature(
                evaluator,
                source=ModelSource(model_name=model_name, rendered_card=fit.rendered_card),
                polarity=polarity,
                requests=holdout_requests,
                token_prefix=f"{record_id}-holdout-candidate",
                measure_terminal_cgg=True,
            )
            holdout = _holdout_audit(
                holdout_candidate,
                holdout_target,
                current_floor_a=settings.current_floor_a,
                criteria=criteria,
            )
            checks = {
                "calibration_objective": fit.objective_rms
                <= float(criteria["calibration_objective_rms_max"]),
                "sealed_holdout": holdout["status"] == "pass",
                "byte_identical_card_regeneration": regeneration_check,
                "staged_parameter_release": len(fit.stage_records) == 5,
                "local_sensitivity_recorded": all(
                    bool(stage["local_sensitivity"]) for stage in fit.stage_records
                ),
                "real_ngspice_47": tool_identity["major"] == "47",
            }
            result_records.append(
                {
                    "id": record_id,
                    "selector": fixture["selector"],
                    "polarity": polarity,
                    "status": "pass" if all(checks.values()) else "fail",
                    "checks": checks,
                    "reference": {
                        "model_name": reference.model_name,
                        "include_sha256": {
                            str(path.relative_to(root)): sha256_file(path)
                            for path in reference.include_paths
                        },
                        "calibration_terminal_data_sha256": curves_sha256(calibration_target),
                        "sealed_holdout_terminal_data_sha256": curves_sha256(holdout_target),
                        "parameters_exposed_to_objective": False,
                    },
                    "fit": {
                        "objective_rms": fit.objective_rms,
                        "evaluation_count": fit.evaluation_count,
                        "parameters": fit.parameters,
                        "stages": list(fit.stage_records),
                    },
                    "generated_card": {
                        "path": str(card_path.relative_to(output)),
                        "sha256": sha256_file(card_path),
                        "byte_identical_regeneration": regeneration_check,
                    },
                    "sealed_holdout": {
                        "definition_sha256": holdout_definition_hash,
                        "used_during_fit": False,
                        "unsealed_after_fit": True,
                        "candidate_terminal_data_sha256": curves_sha256(holdout_candidate),
                        "audit": holdout,
                    },
                }
            )
    if not result_records:
        raise ModelgenError("fixture/polarity filters selected no reconstruction jobs")
    status = "pass" if all(record["status"] == "pass" for record in result_records) else "fail"
    coverage = _coverage(result_records)
    completion_state = None
    if status == "pass":
        completion_state = (
            COMPLETION_STATE if coverage["full_required_coverage"] else SUBSET_COMPLETION_STATE
        )
    report = {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "completion_state": completion_state,
        "coverage": coverage,
        "kernel": {
            "id": KERNEL_ID,
            "version": KERNEL_VERSION,
            "implementation": str(
                Path(__file__).with_name("kernel.py").resolve().relative_to(root)
            ),
            "implementation_sha256": sha256_file(Path(__file__).with_name("kernel.py")),
            "qualification_implementation_sha256": sha256_file(Path(__file__)),
        },
        "input": {
            "path": str(configuration_path.resolve().relative_to(root)),
            "sha256": sha256_file(configuration_path),
            "deterministic_seeds": list(settings.seeds),
        },
        "reference_tool": tool_identity,
        "reference_parameter_access": {
            "objective_uses_terminal_observations_only": True,
            "reference_card_text_or_parameters_parsed": False,
            "original_parameter_recovery_required": False,
        },
        "terminal_observation_methods": {
            "current": "external drain voltage-source branch current",
            "gm_and_gds": "finite difference of external terminal current",
            "cgg": "imag(Ygg)/(2*pi*f) from a 1 V gate-terminal AC excitation",
            "terminal_ac_frequency_hz": TERMINAL_AC_FREQUENCY_HZ,
            "simulator_internal_gm_gds_cgg_used_as_fit_inputs": False,
        },
        "records": result_records,
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("reconstruction.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", action="append", choices=("apm022_svt", "apm045_vtg"))
    parser.add_argument("--polarity", action="append", choices=("n", "p"))
    parser.add_argument("--replace-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    root = arguments.root.resolve()
    output = arguments.output.resolve()
    if arguments.replace_output and output.exists():
        shutil.rmtree(output)
    report = qualify(
        root=root,
        output=output,
        configuration_path=arguments.config.resolve(),
        fixture_filter=set(arguments.fixture) if arguments.fixture else None,
        polarity_filter=set(arguments.polarity) if arguments.polarity else None,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
