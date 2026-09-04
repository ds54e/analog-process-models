# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Unseal and qualify the frozen APM045 io18/io25 candidate ensembles.

The default preflight is non-holdout and may be repeated.  ``--unseal`` is a
one-shot operation against a clean committed implementation: it writes an
unseal receipt before invoking ngspice and never modifies candidate parameters.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .circuit_fixtures import BasicCircuitRequest, CircuitEvaluator, PassCase
from .kernel import (
    KERNEL_ID,
    KERNEL_VERSION,
    Curve,
    ModelSource,
    NgspiceEvaluator,
    SweepRequest,
    canonical_json,
    hard_constraint_observations,
    sha256_bytes,
    sha256_file,
)
from .synthesize_families import (
    CALIBRATION_COMPLETION_STATE,
    _geometry,
    _gmid_solution,
    _grid_requests,
    _load_toml,
    _percentile,
    _render_candidate,
    _threshold,
    _validate_configuration,
)
from .terminal_observables import (
    TERMINALS,
    BiasPoint,
    BodySweep,
    GateTrajectory,
    TerminalEvaluator,
)

SCHEMA = "apm.mixed-voltage-qualification.v1"
PREFLIGHT_SCHEMA = "apm.mixed-voltage-qualification-preflight.v1"
COMPLETION_STATE = "MIXED_VOLTAGE_ENSEMBLE_QUALIFIED"


class QualificationError(RuntimeError):
    """The sealed qualification contract or its evidence failed closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _median(values: Iterable[float]) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return float(np.median(finite)) if finite else None


def _minimum(values: Iterable[float]) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return min(finite) if finite else None


def _maximum(values: Iterable[float]) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return max(finite) if finite else None


def _canonical_report_sha256(report: Mapping[str, Any]) -> str:
    payload = dict(report)
    payload.pop("created_utc", None)
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def _git_identity(root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {"commit": commit, "worktree_clean": not status, "status_lines": status}


def _record_map(report: Mapping[str, Any]) -> dict[tuple[str, int, str], Mapping[str, Any]]:
    result: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for record in report["records"]:
        key = (str(record["family"]), int(record["seed"]), str(record["polarity"]))
        if key in result:
            raise QualificationError(f"duplicate calibration candidate record: {key}")
        result[key] = record
    return result


def _validate_contracts(
    *,
    root: Path,
    qualification_path: Path,
    calibration_report_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    qualification = _load_toml(qualification_path)
    if qualification.get("schema") != "apm.modelgen.mixed-voltage-qualification-input.v1":
        raise QualificationError("unexpected mixed-voltage qualification input schema")
    if qualification.get("state") != "SEALED_BEFORE_FIRST_HOLDOUT_EVALUATION":
        raise QualificationError("qualification epoch was not sealed before first evaluation")
    if int(qualification.get("qualification_epoch", 0)) < 1:
        raise QualificationError("qualification epoch must be positive")
    if qualification.get("failed_holdout_reuse_for_repair") is not False:
        raise QualificationError("failed holdout reuse for repair must be explicitly false")

    generation_path = root / str(qualification["generation_contract"])
    generation = _load_toml(generation_path)
    generation_audit = _validate_configuration(generation, root)
    if int(qualification["qualification_epoch"]) != int(generation["generation_epoch"]):
        raise QualificationError("qualification and generation epoch identities differ")
    if int(qualification["qualification_epoch"]) > 1:
        if qualification.get("prior_holdout_reuse") is not False:
            raise QualificationError("later epoch must explicitly forbid prior holdout reuse")
        prior_path = root / str(qualification["prior_failure_evidence"])
        if sha256_file(prior_path) != qualification["prior_failure_evidence_sha256"]:
            raise QualificationError("prior failed-epoch evidence hash mismatch")
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        if (
            prior.get("schema") != "apm.v4-mixed-voltage-qualification-failure.v1"
            or prior.get("status") != "failed_closed"
            or int(prior["qualification_epoch"])
            != int(qualification["prior_failed_qualification_epoch"])
            or prior["failure_policy"]["epoch_1_holdout_reuse_for_repair"] is not False
        ):
            raise QualificationError("prior failed epoch is not valid fail-closed evidence")
        if {int(seed) for seed in generation["seeds"]} & {
            int(seed) for seed in prior["observed_outcome"]["candidate_seeds"]
        }:
            raise QualificationError("later generation epoch reused a failed-epoch seed")
        for name in (
            "sealed_device_holdout",
            "sealed_charge_holdout",
            "sealed_circuit_holdout",
        ):
            current_hash = sha256_bytes(canonical_json(generation[name]).encode("utf-8"))
            if current_hash == prior["sealed_definition_sha256"][name]:
                raise QualificationError(f"later generation epoch reused {name}")
    if sha256_file(generation_path) != qualification["generation_contract_sha256"]:
        raise QualificationError("generation contract hash does not match qualification seal")
    device_criteria = qualification["device_holdout"]["criteria"]
    minimum_reachable = int(
        device_criteria.get(
            "minimum_reachable_intermediate_targets_per_curve",
            len(generation["sealed_device_holdout"]["intermediate_gmid_targets_per_v"]),
        )
    )
    if not 1 <= minimum_reachable <= len(
        generation["sealed_device_holdout"]["intermediate_gmid_targets_per_v"]
    ):
        raise QualificationError("invalid intermediate gm/Id reachability coverage")
    if int(qualification["qualification_epoch"]) > 1 and not (
        device_criteria.get("target_not_reachable_outside_qualified_region_permitted")
        is True
        and device_criteria.get("near_off_control_region_exclusion_required") is True
    ):
        raise QualificationError("later epoch must seal explicit near-off solver semantics")
    synthesis_path = Path(__file__).with_name("synthesize_families.py")
    terminal_path = Path(__file__).with_name("terminal_observables.py")
    circuit_path = Path(__file__).with_name("circuit_fixtures.py")
    implementation_checks = {
        "synthesis": sha256_file(synthesis_path)
        == qualification["synthesis_implementation_sha256"],
        "terminal_observables": sha256_file(terminal_path)
        == qualification["terminal_observables_implementation_sha256"],
        "circuit_fixtures": sha256_file(circuit_path)
        == qualification["circuit_fixtures_implementation_sha256"],
    }
    if not all(implementation_checks.values()):
        raise QualificationError("sealed implementation hash mismatch")

    calibration = json.loads(calibration_report_path.read_text(encoding="utf-8"))
    if calibration.get("schema") != "apm.modelgen.mixed-voltage-calibration.v1":
        raise QualificationError("unexpected calibration result schema")
    if (
        calibration.get("status") != "pass"
        or calibration.get("completion_state") != CALIBRATION_COMPLETION_STATE
        or calibration.get("mode") != "calibration_only"
    ):
        raise QualificationError("calibration result is not a completed passing freeze")
    if _canonical_report_sha256(calibration) != qualification[
        "calibration_canonical_content_sha256"
    ]:
        raise QualificationError("calibration canonical-content hash mismatch")
    if calibration["configuration"]["sha256"] != sha256_file(generation_path):
        raise QualificationError("calibration used a different generation contract")
    expected_kernel = {
        "id": KERNEL_ID,
        "version": KERNEL_VERSION,
        "implementation_sha256": sha256_file(Path(__file__).with_name("kernel.py")),
        "synthesis_implementation_sha256": sha256_file(synthesis_path),
    }
    for key, value in expected_kernel.items():
        if calibration["kernel"].get(key) != value:
            raise QualificationError(f"calibration kernel binding mismatch: {key}")
    if str(calibration["reference_tool"]["major"]) != str(
        qualification["reference_simulator_major"]
    ):
        raise QualificationError("calibration reference simulator major mismatch")

    sealed_names = (
        "sealed_device_holdout",
        "sealed_charge_holdout",
        "sealed_circuit_holdout",
    )
    sealed_checks: dict[str, bool] = {}
    for name in sealed_names:
        expected = sha256_bytes(canonical_json(generation[name]).encode("utf-8"))
        observed = calibration["sealed_definitions"][name]
        sealed_checks[name] = (
            observed["definition_sha256"] == expected and observed["evaluated"] is False
        )
    if not all(sealed_checks.values()):
        raise QualificationError("calibration report did not preserve sealed definitions")

    records = _record_map(calibration)
    candidate_checks: dict[str, Any] = {}
    for family in ("io18", "io25"):
        retained = [int(seed) for seed in calibration["ensemble"]["retained_seeds"][family]]
        family_checks: list[dict[str, Any]] = []
        for seed in retained:
            for polarity in ("n", "p"):
                key = (family, seed, polarity)
                if key not in records:
                    raise QualificationError(f"calibration candidate missing: {key}")
                record = records[key]
                card_path = calibration_report_path.parent / record["card"]["path"]
                rendered = _render_candidate(
                    generation, family, polarity, record["parameters"]
                ).encode("utf-8")
                check = {
                    "seed": seed,
                    "polarity": polarity,
                    "status_pass": record["status"] == "pass",
                    "card_hash": card_path.is_file()
                    and sha256_file(card_path) == record["card"]["sha256"],
                    "byte_identical_regeneration": card_path.is_file()
                    and card_path.read_bytes() == rendered,
                }
                family_checks.append(check)
        candidate_checks[family] = {
            "retained_seeds": retained,
            "minimum_count": len(retained)
            >= int(qualification["ensemble"]["minimum_retained_candidates_per_family"]),
            "records": family_checks,
        }
    if not all(
        item["minimum_count"]
        and all(
            record["status_pass"]
            and record["card_hash"]
            and record["byte_identical_regeneration"]
            for record in item["records"]
        )
        for item in candidate_checks.values()
    ):
        raise QualificationError("calibration candidate regeneration audit failed")

    release = _load_toml(root / "validation/release_gates_v4.toml")
    sealed_circuit = generation["sealed_circuit_holdout"]
    qualified_circuit = qualification["circuit_holdout"]
    release_checks = {
        "schema": qualification["schema"]
        == "apm.modelgen.mixed-voltage-qualification-input.v1",
        "result_schema": release["mixed_voltage_qualification"]["result_schema"]
        == SCHEMA,
        "terminal_order": qualification["terminal_y"]["criteria"]["terminal_order"]
        == release["characterization"]["terminal_order"],
        "numerical_fd": math.isclose(
            float(qualification["device_holdout"]["criteria"]["finite_difference_p95_relative_max"]),
            float(release["mixed_voltage_qualification"]["numerical"]["finite_difference_p95_relative_max"]),
        ),
        "numerical_native": math.isclose(
            float(qualification["device_holdout"]["criteria"]["native_oracle_p95_relative_max"]),
            float(release["mixed_voltage_qualification"]["numerical"]["native_oracle_p95_relative_max"]),
        ),
        "ensemble_minimum": int(
            qualification["ensemble"]["minimum_retained_candidates_per_family"]
        )
        >= int(release["epistemic_ensemble"]["minimum_retained_feasible_candidates_per_family"]),
        "fixture_classes": qualification["circuit_holdout"]["fixture_classes"]
        == release["circuit_qualification"]["required_fixture_classes"],
        "pass_scenarios": qualification["circuit_holdout"]["pass_scenarios"]
        == release["circuit_qualification"]["pass_device"]["required_scenarios"],
        "circuit_temperature_seal": qualified_circuit["temperatures_c"]
        == sealed_circuit["temperatures_c"],
        "circuit_length_seal": qualified_circuit["length_ratios"]
        == sealed_circuit["intermediate_length_ratios"],
        "circuit_load_seal": qualified_circuit["pass_load_currents_a"]
        == sealed_circuit["load_currents_a"],
        "circuit_scenario_seal": qualified_circuit["pass_scenarios"]
        == sealed_circuit["pass_scenarios"],
        "circuit_unit_width_seal": math.isclose(
            float(qualified_circuit["unit_width_um"]) * 1e-6,
            float(sealed_circuit["explicit_parallel_unit_width_m"]),
        ),
        "circuit_maximum_units_seal": int(qualified_circuit["maximum_parallel_units"])
        == int(sealed_circuit["maximum_units"]),
    }
    if not all(release_checks.values()):
        raise QualificationError("qualification seal does not satisfy the release contract")

    audit = {
        "status": "pass",
        "qualification_input": {
            "path": str(qualification_path.relative_to(root)),
            "sha256": sha256_file(qualification_path),
        },
        "generation_contract": {
            "path": str(generation_path.relative_to(root)),
            "sha256": sha256_file(generation_path),
            "audit": generation_audit,
        },
        "calibration": {
            "path": str(calibration_report_path),
            "sha256": sha256_file(calibration_report_path),
            "canonical_content_sha256": _canonical_report_sha256(calibration),
        },
        "implementation_checks": implementation_checks,
        "sealed_definition_checks": sealed_checks,
        "candidate_checks": candidate_checks,
        "release_contract_checks": release_checks,
    }
    return qualification, generation, calibration, audit


def _source(
    generation: Mapping[str, Any], record: Mapping[str, Any]
) -> ModelSource:
    family = str(record["family"])
    polarity = str(record["polarity"])
    return ModelSource(
        model_name=f"apm045_{family}_{polarity}core",
        rendered_card=_render_candidate(generation, family, polarity, record["parameters"]),
    )


def _dibl_values(curves: Mapping[str, Curve]) -> list[float]:
    groups: dict[tuple[Any, ...], list[tuple[float, Curve]]] = defaultdict(list)
    for curve in curves.values():
        if curve.request.kind == "idvg":
            key = (
                curve.request.temperature_c,
                curve.request.l_m,
                curve.request.w_m,
            )
            groups[key].append((curve.request.fixed_bias_v, curve))
    values: list[float] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: item[0])
        low_v, low_curve = ordered[0]
        high_v, high_curve = ordered[-1]
        low_threshold = _threshold(low_curve)
        high_threshold = _threshold(high_curve)
        if low_threshold is not None and high_threshold is not None and high_v > low_v:
            values.append((low_threshold - high_threshold) / (high_v - low_v))
    return values


def _length_order_fraction(curves: Mapping[str, Curve]) -> float:
    groups: dict[tuple[Any, ...], list[tuple[float, float]]] = defaultdict(list)
    for curve in curves.values():
        key = (
            curve.request.temperature_c,
            curve.request.kind,
            curve.request.w_m,
            curve.request.fixed_bias_v,
        )
        groups[key].append((curve.request.l_m, float(curve.idmag_a[-1])))
    checks = [
        second[1] < first[1]
        for group in groups.values()
        for first, second in zip(sorted(group), sorted(group)[1:])
    ]
    return sum(checks) / max(len(checks), 1)


def _temperature_ratios(curves: Mapping[str, Curve]) -> list[float]:
    groups: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    for curve in curves.values():
        key = (
            curve.request.kind,
            curve.request.l_m,
            curve.request.w_m,
            curve.request.fixed_bias_v,
        )
        groups[key].append(float(curve.idmag_a[-1]))
    return [max(group) / min(group) for group in groups.values() if min(group) > 0.0]


def _device_holdout(
    *,
    evaluator: NgspiceEvaluator,
    terminal: TerminalEvaluator,
    generation: Mapping[str, Any],
    qualification: Mapping[str, Any],
    record: Mapping[str, Any],
    token: str,
) -> dict[str, Any]:
    family = str(record["family"])
    polarity = str(record["polarity"])
    geometry = _geometry(generation, family)
    source = _source(generation, record)
    grid = generation["sealed_device_holdout"]
    requests = _grid_requests(family=family, geometry=geometry, grid=grid)
    curves = evaluator.evaluate_many(
        source=source,
        polarity=polarity,
        requests=requests,
        token=f"{token}-curves",
        measure_terminal_cgg=False,
    )
    current_floor = float(generation["numerical"]["current_floor_a"])
    hard = hard_constraint_observations(curves, current_floor)
    thresholds = {
        key: _threshold(curve)
        for key, curve in curves.items()
        if curve.request.kind == "idvg"
    }
    threshold_values = [value for value in thresholds.values() if value is not None]
    dibl = _dibl_values(curves)
    temperature_ratios = _temperature_ratios(curves)
    criteria = qualification["device_holdout"]["criteria"]

    solutions: list[dict[str, Any]] = []
    bias_points: list[BiasPoint] = []
    for curve in curves.values():
        if curve.request.kind != "idvg":
            continue
        for target in grid["intermediate_gmid_targets_per_v"]:
            solution = _gmid_solution(
                curve,
                float(target),
                current_floor_a=current_floor,
                endpoint_guard=int(grid["endpoint_guard_points"]),
            )
            solution.update(
                {
                    "request_id": curve.request.request_id,
                    "temperature_c": curve.request.temperature_c,
                    "l_m": curve.request.l_m,
                    "w_m": curve.request.w_m,
                    "vout_v": curve.request.fixed_bias_v,
                }
            )
            if solution["state"] == "validated":
                control_fraction = float(solution["vctrl_v"]) / geometry.native_vdd_v
                solution["vctrl_fraction_vdd"] = control_fraction
                solution["qualification_state"] = (
                    "validated"
                    if float(criteria["qualified_vctrl_fraction_min"])
                    <= control_fraction
                    <= float(criteria["qualified_vctrl_fraction_max"])
                    else "excluded_near_off_control_region"
                )
            else:
                solution["qualification_state"] = solution["state"]
            solutions.append(solution)
            if solution["qualification_state"] == "validated":
                bias_points.append(
                    BiasPoint(
                        point_id=(
                            f"{curve.request.request_id}-gmid-{float(target):.4g}"
                        ),
                        temperature_c=curve.request.temperature_c,
                        l_m=curve.request.l_m,
                        w_m=curve.request.w_m,
                        vctrl_v=float(solution["vctrl_v"]),
                        vout_v=curve.request.fixed_bias_v,
                    )
                )
    derivatives = terminal.evaluate_derivatives(
        source=source,
        model_name=source.model_name,
        polarity=polarity,
        points=bias_points,
        vdd_v=geometry.native_vdd_v,
        step_fraction_vdd=float(criteria["finite_difference_step_fraction_vdd"]),
        token=f"{token}-derivatives",
    )
    derivative_by_id = {item["point_id"]: item for item in derivatives}
    for solution in solutions:
        point_id = f"{solution['request_id']}-gmid-{float(solution['target_per_v']):.4g}"
        if point_id in derivative_by_id:
            observation = derivative_by_id[point_id]
            solution.update(
                {
                    "terminal_gm_s": observation["gm_s"],
                    "terminal_gds_s": observation["gds_s"],
                    "terminal_gm_over_id_per_v": observation["gm_over_id_per_v"],
                    "terminal_gds_over_id_per_v": observation["gds_over_id_per_v"],
                    "terminal_gm_over_gds": observation["gm_over_gds"],
                }
            )
    fd_errors = [
        value
        for item in derivatives
        for value in (item["gm_convergence_relative"], item["gds_convergence_relative"])
    ]
    native_errors = [
        value
        for item in derivatives
        for value in (item["native_gm_relative_error"], item["native_gds_relative_error"])
    ]
    threshold_fractions = [value / geometry.native_vdd_v for value in threshold_values]
    length_fraction = _length_order_fraction(curves)
    solution_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    target_groups: dict[float, list[Mapping[str, Any]]] = defaultdict(list)
    for solution in solutions:
        solution_groups[str(solution["request_id"])].append(solution)
        target_groups[float(solution["target_per_v"])].append(solution)
    minimum_reachable = int(
        criteria.get(
            "minimum_reachable_intermediate_targets_per_curve",
            len(grid["intermediate_gmid_targets_per_v"]),
        )
    )
    allowed_solver_states = {"validated", "target_not_reachable"}
    validated_solutions = [
        item for item in solutions if item["qualification_state"] == "validated"
    ]
    qualified_vctrl = [
        float(criteria["qualified_vctrl_fraction_min"])
        <= float(item["vctrl_v"]) / geometry.native_vdd_v
        <= float(criteria["qualified_vctrl_fraction_max"])
        for item in validated_solutions
    ]
    checks = {
        "numerical_hard_contract": hard["status"] == "pass",
        "all_thresholds_bracketed": len(threshold_values) == len(thresholds),
        "threshold_guardrail": bool(threshold_fractions)
        and min(threshold_fractions) >= float(criteria["threshold_over_vdd_min"])
        and max(threshold_fractions) <= float(criteria["threshold_over_vdd_max"]),
        "dibl_guardrail": bool(dibl)
        and min(dibl) >= float(criteria["dibl_min_v_per_v"])
        and max(dibl) <= float(criteria["dibl_max_v_per_v"]),
        "solver_states_explicit": bool(solutions)
        and all(item["state"] in allowed_solver_states for item in solutions),
        "intermediate_gmid_reachability_coverage": bool(solution_groups)
        and all(
            sum(item["qualification_state"] == "validated" for item in group)
            >= minimum_reachable
            for group in solution_groups.values()
        )
        and all(
            len(group) == len(solution_groups)
            for group in target_groups.values()
        ),
        "intermediate_gmid_accuracy": bool(solutions)
        and all(
            item.get("relative_error", math.inf)
            <= float(criteria["gmid_target_relative_tolerance_max"])
            for item in validated_solutions
        ),
        "validated_control_voltage_region": bool(qualified_vctrl)
        and all(qualified_vctrl),
        "length_current_order": length_fraction
        >= float(criteria["required_length_current_order_fraction"]),
        "temperature_current_ratio": bool(temperature_ratios)
        and min(temperature_ratios)
        >= float(criteria["temperature_endpoint_current_ratio_min"])
        and max(temperature_ratios)
        <= float(criteria["temperature_endpoint_current_ratio_max"]),
        "finite_difference_convergence": bool(fd_errors)
        and _percentile(fd_errors, 0.95)
        <= float(criteria["finite_difference_p95_relative_max"]),
        "native_oracle_agreement": bool(native_errors)
        and _percentile(native_errors, 0.95)
        <= float(criteria["native_oracle_p95_relative_max"]),
        "external_terminal_derivatives": bool(derivatives)
        and all(item["gm_s"] > 0.0 and item["gds_s"] > 0.0 for item in derivatives),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "hard_contract": hard,
        "coordinates": {
            "temperatures_c": sorted({item.temperature_c for item in requests}),
            "length_ratios": [float(value) for value in grid["length_ratios"]],
            "widths_um": [float(value) for value in grid["widths_um"]],
            "idvg_fixed_bias_fractions": [
                float(value) for value in grid["idvg_fixed_bias_fractions"]
            ],
            "idvd_fixed_bias_fractions": [
                float(value) for value in grid["idvd_fixed_bias_fractions"]
            ],
            "intermediate_gmid_targets_per_v": [
                float(value) for value in grid["intermediate_gmid_targets_per_v"]
            ],
            "minimum_reachable_intermediate_targets_per_curve": minimum_reachable,
        },
        "metrics": {
            "threshold_v_median": _median(threshold_values),
            "threshold_over_vdd_min": _minimum(threshold_fractions),
            "threshold_over_vdd_max": _maximum(threshold_fractions),
            "dibl_v_per_v_median": _median(dibl),
            "dibl_v_per_v_min": _minimum(dibl),
            "dibl_v_per_v_max": _maximum(dibl),
            "length_current_order_fraction": length_fraction,
            "temperature_endpoint_current_ratio_median": _median(temperature_ratios),
            "temperature_endpoint_current_ratio_min": _minimum(temperature_ratios),
            "temperature_endpoint_current_ratio_max": _maximum(temperature_ratios),
            "finite_difference_p95_relative": _percentile(fd_errors, 0.95),
            "native_oracle_p95_relative": _percentile(native_errors, 0.95),
            "id_per_width_at_gmid_median_a_per_m": _median(
                item["idmag_a"] / item["w_m"]
                for item in solutions
                if item["qualification_state"] == "validated"
            ),
            "gds_over_id_median_per_v": _median(
                item["gds_over_id_per_v"] for item in derivatives
            ),
            "gm_over_gds_median": _median(item["gm_over_gds"] for item in derivatives),
            "gmid_solution_state_counts": {
                state: sum(item["qualification_state"] == state for item in solutions)
                for state in (
                    "validated",
                    "excluded_near_off_control_region",
                    "target_not_reachable",
                )
            },
        },
        "thresholds_v": thresholds,
        "gmid_solutions": solutions,
        "terminal_derivative_observations": derivatives,
    }


def _charge_holdout(
    *,
    terminal: TerminalEvaluator,
    generation: Mapping[str, Any],
    qualification: Mapping[str, Any],
    record: Mapping[str, Any],
    token: str,
) -> dict[str, Any]:
    family = str(record["family"])
    polarity = str(record["polarity"])
    geometry = _geometry(generation, family)
    source = _source(generation, record)
    grid = generation["sealed_charge_holdout"]
    trajectories: list[GateTrajectory] = []
    for temperature in grid["temperatures_c"]:
        for length_ratio in grid["length_ratios"]:
            for width_um in grid["widths_um"]:
                for vout_fraction in grid["idvg_fixed_bias_fractions"]:
                    trajectory_id = (
                        f"{family}-{polarity}-t{int(temperature):+d}"
                        f"-lr{float(length_ratio):.4g}-w{float(width_um):.4g}u"
                        f"-vd{float(vout_fraction):.4g}"
                    )
                    trajectories.append(
                        GateTrajectory(
                            trajectory_id=trajectory_id,
                            temperature_c=int(temperature),
                            l_m=geometry.lmin_m * float(length_ratio),
                            w_m=float(width_um) * 1e-6,
                            fixed_vout_v=geometry.native_vdd_v * float(vout_fraction),
                            vctrl_values_v=tuple(
                                float(value)
                                for value in np.linspace(
                                    0.0, geometry.native_vdd_v, int(grid["points"])
                                )
                            ),
                        )
                    )
    observations = terminal.evaluate_gate_trajectories(
        source=source,
        model_name=source.model_name,
        polarity=polarity,
        trajectories=trajectories,
        frequencies_hz=[float(value) for value in grid["frequencies_hz"]],
        token=token,
    )
    criteria = qualification["charge_holdout"]["criteria"]
    densities = [
        item["cgg_f"] / (item["w_m"] * item["l_m"]) for item in observations
    ]
    ratios = [abs(item["cgd_f"]) / item["cgg_f"] for item in observations]
    groups: dict[tuple[str, float], list[Mapping[str, Any]]] = defaultdict(list)
    trajectory_groups: dict[tuple[str, float], list[Mapping[str, Any]]] = defaultdict(list)
    for item in observations:
        groups[(str(item["trajectory_id"]), float(item["vctrl_v"]))].append(item)
        trajectory_groups[(str(item["trajectory_id"]), float(item["frequency_hz"]))].append(
            item
        )
    frequency_changes: list[float] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: float(item["frequency_hz"]))
        for first, second in zip(ordered, ordered[1:]):
            for name in ("cgg_f", "cgd_f", "cgs_f", "cgb_f"):
                scale = max(abs(float(first[name])), abs(float(second[name])))
                cgg_scale = max(abs(float(first["cgg_f"])), abs(float(second["cgg_f"])))
                if scale > cgg_scale * 1e-6:
                    frequency_changes.append(
                        abs(float(first[name]) - float(second[name])) / scale
                    )
    integrated: dict[str, float] = {}
    for (trajectory_id, frequency), group in trajectory_groups.items():
        ordered = sorted(group, key=lambda item: float(item["vctrl_v"]))
        integrated[f"{trajectory_id}@{frequency:.12g}Hz"] = float(
            np.trapezoid(
                [float(item["cgg_f"]) for item in ordered],
                [float(item["vctrl_v"]) for item in ordered],
            )
        )
    checks = {
        "finite_terminal_quantities": bool(observations)
        and all(
            math.isfinite(float(item[name]))
            for item in observations
            for name in ("cgg_f", "cgd_f", "cgs_f", "cgb_f")
        ),
        "positive_cgg": bool(densities) and all(value > 0.0 for value in densities),
        "cgg_density_guardrail": bool(densities)
        and min(densities) >= float(criteria["cgg_density_min_f_per_m2"])
        and max(densities) <= float(criteria["cgg_density_max_f_per_m2"]),
        "cgd_over_cgg_guardrail": bool(ratios)
        and min(ratios) >= float(criteria["cgd_over_cgg_min"])
        and max(ratios) <= float(criteria["cgd_over_cgg_max"]),
        "frequency_consistency": bool(frequency_changes)
        and max(frequency_changes) <= float(criteria["frequency_relative_change_max"]),
        "positive_integrated_gate_charge": bool(integrated)
        and all(value > 0.0 and math.isfinite(value) for value in integrated.values()),
        "terminal_kcl": all(
            float(item["kcl_normalized_residual"])
            <= float(qualification["terminal_y"]["criteria"]["kcl_normalized_residual_max"])
            for item in observations
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "coordinates": {
            "temperatures_c": [int(value) for value in grid["temperatures_c"]],
            "length_ratios": [float(value) for value in grid["length_ratios"]],
            "widths_um": [float(value) for value in grid["widths_um"]],
            "vout_fractions": [
                float(value) for value in grid["idvg_fixed_bias_fractions"]
            ],
            "frequencies_hz": [float(value) for value in grid["frequencies_hz"]],
        },
        "metrics": {
            "cgg_density_min_f_per_m2": _minimum(densities),
            "cgg_density_median_f_per_m2": _median(densities),
            "cgg_density_max_f_per_m2": _maximum(densities),
            "cgd_over_cgg_min": _minimum(ratios),
            "cgd_over_cgg_median": _median(ratios),
            "cgd_over_cgg_max": _maximum(ratios),
            "frequency_relative_change_max": _maximum(frequency_changes),
            "integrated_gate_charge_min_c": _minimum(integrated.values()),
            "integrated_gate_charge_max_c": _maximum(integrated.values()),
        },
        "integrated_gate_charge_c": integrated,
        "gate_terminal_observations": observations,
    }


def _terminal_y_holdout(
    *,
    terminal: TerminalEvaluator,
    generation: Mapping[str, Any],
    qualification: Mapping[str, Any],
    record: Mapping[str, Any],
    token: str,
) -> dict[str, Any]:
    family = str(record["family"])
    polarity = str(record["polarity"])
    geometry = _geometry(generation, family)
    source = _source(generation, record)
    settings = generation["terminal_y"]
    points: list[BiasPoint] = []
    for temperature in settings["holdout_temperatures_c"]:
        for length_ratio in settings["holdout_length_ratios"]:
            for width_um in settings["holdout_widths_um"]:
                for vctrl_fraction, vout_fraction in settings["holdout_bias_fractions"]:
                    points.append(
                        BiasPoint(
                            point_id=(
                                f"{family}-{polarity}-t{int(temperature):+d}"
                                f"-lr{float(length_ratio):.4g}-w{float(width_um):.4g}u"
                                f"-vg{float(vctrl_fraction):.4g}-vd{float(vout_fraction):.4g}"
                            ),
                            temperature_c=int(temperature),
                            l_m=geometry.lmin_m * float(length_ratio),
                            w_m=float(width_um) * 1e-6,
                            vctrl_v=geometry.native_vdd_v * float(vctrl_fraction),
                            vout_v=geometry.native_vdd_v * float(vout_fraction),
                        )
                    )
    observations = terminal.evaluate_y(
        source=source,
        model_name=source.model_name,
        polarity=polarity,
        points=points,
        frequencies_hz=[float(value) for value in settings["holdout_frequencies_hz"]],
        token=token,
    )
    criteria = qualification["terminal_y"]["criteria"]
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in observations:
        groups[str(item["point_id"])].append(item)
    frequency_changes: list[float] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: float(item["frequency_hz"]))
        for first, second in zip(ordered, ordered[1:]):
            first_frequency = float(first["frequency_hz"])
            second_frequency = float(second["frequency_hz"])
            first_matrix = np.asarray(first["y_imag_s"], dtype=float) / first_frequency
            second_matrix = np.asarray(second["y_imag_s"], dtype=float) / second_frequency
            scale = np.maximum(np.abs(first_matrix), np.abs(second_matrix))
            significant = scale > np.max(scale) * 1e-8
            if np.any(significant):
                frequency_changes.extend(
                    (
                        np.abs(first_matrix - second_matrix)[significant]
                        / scale[significant]
                    ).tolist()
                )
    all_matrix_values = [
        value
        for item in observations
        for matrix_name in ("y_real_s", "y_imag_s")
        for row in item[matrix_name]
        for value in row
    ]
    checks = {
        "terminal_order": bool(observations)
        and all(item["terminal_order"] == list(TERMINALS) for item in observations),
        "finite_matrix": bool(all_matrix_values)
        and all(math.isfinite(float(value)) for value in all_matrix_values),
        "kcl_absolute": all(
            max(item["kcl_column_sum_abs_s"])
            <= float(criteria["kcl_absolute_residual_max_s"])
            for item in observations
        ),
        "kcl_normalized": all(
            float(item["kcl_max_normalized_residual"])
            <= float(criteria["kcl_normalized_residual_max"])
            for item in observations
        ),
        "frequency_consistency": bool(frequency_changes)
        and max(frequency_changes) <= float(criteria["frequency_relative_change_max"]),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "metrics": {
            "kcl_absolute_max_s": _maximum(
                value
                for item in observations
                for value in item["kcl_column_sum_abs_s"]
            ),
            "kcl_normalized_max": _maximum(
                item["kcl_max_normalized_residual"] for item in observations
            ),
            "frequency_relative_change_max": _maximum(frequency_changes),
        },
        "raw_ordered_complex_y": observations,
    }


def _threshold_from_body(result: Mapping[str, Any], coefficient_a: float = 1e-7) -> float | None:
    request: BodySweep = result["request"]
    target = coefficient_a * request.w_m / request.l_m
    currents = result["idmag_a"]
    voltages = result["vctrl_v"]
    for index in range(len(currents) - 1):
        low = float(currents[index])
        high = float(currents[index + 1])
        if low <= target <= high and high > low:
            fraction = (target - low) / (high - low)
            return float(voltages[index] + fraction * (voltages[index + 1] - voltages[index]))
    return None


def _body_effect(
    *,
    terminal: TerminalEvaluator,
    generation: Mapping[str, Any],
    qualification: Mapping[str, Any],
    record: Mapping[str, Any],
    token: str,
) -> dict[str, Any]:
    family = str(record["family"])
    polarity = str(record["polarity"])
    geometry = _geometry(generation, family)
    source = _source(generation, record)
    settings = qualification["body_effect"]
    sweeps: list[BodySweep] = []
    for length_ratio in settings["length_ratios"]:
        for vds_fraction in settings["vds_fractions"]:
            for body_fraction in settings["reverse_body_bias_fractions"]:
                sweeps.append(
                    BodySweep(
                        sweep_id=(
                            f"{family}-{polarity}-lr{float(length_ratio):.4g}"
                            f"-vd{float(vds_fraction):.4g}-vb{float(body_fraction):.4g}"
                        ),
                        temperature_c=int(settings["temperature_c"]),
                        l_m=geometry.lmin_m * float(length_ratio),
                        w_m=float(settings["width_um"]) * 1e-6,
                        fixed_vout_v=geometry.native_vdd_v * float(vds_fraction),
                        reverse_body_bias_v=geometry.native_vdd_v * float(body_fraction),
                        sweep_stop_v=geometry.native_vdd_v,
                        points=int(settings["points"]),
                    )
                )
    raw = terminal.evaluate_body_sweeps(
        source=source,
        model_name=source.model_name,
        polarity=polarity,
        sweeps=sweeps,
        token=token,
    )
    observations: list[dict[str, Any]] = []
    for sweep in sweeps:
        result = raw[sweep.sweep_id]
        observations.append(
            {
                "sweep_id": sweep.sweep_id,
                "temperature_c": sweep.temperature_c,
                "l_m": sweep.l_m,
                "w_m": sweep.w_m,
                "vout_v": sweep.fixed_vout_v,
                "reverse_body_bias_v": sweep.reverse_body_bias_v,
                "threshold_v": _threshold_from_body(result),
                "current_min_a": float(np.min(result["idmag_a"])),
                "current_max_a": float(np.max(result["idmag_a"])),
            }
        )
    groups: dict[tuple[float, float], list[Mapping[str, Any]]] = defaultdict(list)
    for item in observations:
        groups[(float(item["l_m"]), float(item["vout_v"]))].append(item)
    monotonic: list[bool] = []
    shifts: list[float] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: float(item["reverse_body_bias_v"]))
        thresholds = [item["threshold_v"] for item in ordered]
        if all(value is not None for value in thresholds):
            numeric = [float(value) for value in thresholds]
            monotonic.extend(
                second >= first for first, second in zip(numeric, numeric[1:])
            )
            shifts.append(max(numeric) - min(numeric))
    checks = {
        "all_thresholds_bracketed": all(
            item["threshold_v"] is not None for item in observations
        ),
        "threshold_magnitude_nondecreasing": bool(monotonic) and all(monotonic),
        "threshold_shift_bounded": bool(shifts)
        and max(shifts) / geometry.native_vdd_v
        <= float(settings["maximum_threshold_shift_over_vdd"]),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "metrics": {
            "threshold_shift_median_v": _median(shifts),
            "threshold_shift_max_v": _maximum(shifts),
            "threshold_shift_over_vdd_max": (
                max(shifts) / geometry.native_vdd_v if shifts else None
            ),
        },
        "observations": observations,
        "holdout": False,
        "role": "predeclared calibration-coordinate body-effect qualification",
    }


def _cgg_from_y(observation: Mapping[str, Any]) -> float:
    frequency = float(observation["frequency_hz"])
    return float(observation["y_imag_s"][1][1]) / (2.0 * math.pi * frequency)


def _structural_qualification(
    *,
    root: Path,
    terminal: TerminalEvaluator,
    generation: Mapping[str, Any],
    qualification: Mapping[str, Any],
    records: Mapping[tuple[str, int, str], Mapping[str, Any]],
    eligible: Mapping[str, Sequence[int]],
) -> dict[str, Any]:
    settings = qualification["structural"]
    frequency = float(settings["frequency_hz"])
    points = [
        BiasPoint(
            point_id=f"vtg-{polarity}-l{length:.12g}",
            temperature_c=int(settings["temperature_c"]),
            l_m=float(length),
            w_m=float(settings["width_um"]) * 1e-6,
            vctrl_v=float(settings["vctrl_v"]),
            vout_v=float(settings["vout_v"]),
        )
        for polarity in ("n", "p")
        for length in settings["physical_lengths_m"]
    ]
    vtg: dict[tuple[str, float], float] = {}
    for polarity in ("n", "p"):
        polarity_points = [item for item in points if f"vtg-{polarity}-" in item.point_id]
        native_name = "NMOS_VTG" if polarity == "n" else "PMOS_VTG"
        source = ModelSource(
            model_name=native_name,
            include_paths=(
                root
                / "models/apm045/vendor/freepdk45"
                / ("NMOS_VTG.inc" if polarity == "n" else "PMOS_VTG.inc"),
            ),
        )
        observations = terminal.evaluate_y(
            source=source,
            model_name=native_name,
            polarity=polarity,
            points=polarity_points,
            frequencies_hz=[frequency],
            token=f"structural-vtg-{polarity}",
        )
        for item in observations:
            vtg[(polarity, float(item["l_m"]))] = _cgg_from_y(item) / (
                float(item["w_m"]) * float(item["l_m"])
            )

    candidates: dict[tuple[str, int, str, float], float] = {}
    raw_observations: list[dict[str, Any]] = []
    for family in ("io18", "io25"):
        for seed in eligible[family]:
            for polarity in ("n", "p"):
                record = records[(family, int(seed), polarity)]
                source = _source(generation, record)
                candidate_points = [
                    BiasPoint(
                        point_id=f"{family}-{seed}-{polarity}-l{float(length):.12g}",
                        temperature_c=int(settings["temperature_c"]),
                        l_m=float(length),
                        w_m=float(settings["width_um"]) * 1e-6,
                        vctrl_v=float(settings["vctrl_v"]),
                        vout_v=float(settings["vout_v"]),
                    )
                    for length in settings["physical_lengths_m"]
                ]
                observations = terminal.evaluate_y(
                    source=source,
                    model_name=source.model_name,
                    polarity=polarity,
                    points=candidate_points,
                    frequencies_hz=[frequency],
                    token=f"structural-{family}-{seed}-{polarity}",
                )
                for item in observations:
                    density = _cgg_from_y(item) / (
                        float(item["w_m"]) * float(item["l_m"])
                    )
                    candidates[(family, int(seed), polarity, float(item["l_m"]))] = density
                    raw_observations.append(
                        {
                            "family": family,
                            "seed": int(seed),
                            "polarity": polarity,
                            "l_m": float(item["l_m"]),
                            "cgg_f": _cgg_from_y(item),
                            "cgg_density_f_per_m2": density,
                            "frequency_hz": frequency,
                        }
                    )
    comparisons: list[dict[str, Any]] = []
    for polarity in ("n", "p"):
        for length in [float(value) for value in settings["physical_lengths_m"]]:
            for io18_seed in eligible["io18"]:
                for io25_seed in eligible["io25"]:
                    values = {
                        "apm045/vtg": vtg[(polarity, length)],
                        "apm045/io18": candidates[
                            ("io18", int(io18_seed), polarity, length)
                        ],
                        "apm045/io25": candidates[
                            ("io25", int(io25_seed), polarity, length)
                        ],
                    }
                    passed = (
                        values["apm045/vtg"]
                        > values["apm045/io18"]
                        > values["apm045/io25"]
                    )
                    comparisons.append(
                        {
                            "polarity": polarity,
                            "l_m": length,
                            "io18_seed": int(io18_seed),
                            "io25_seed": int(io25_seed),
                            "cgg_density_f_per_m2": values,
                            "required_order": settings[
                                "required_capacitance_density_order"
                            ],
                            "passed": passed,
                        }
                    )
    checks = {
        "all_candidate_pairs_strictly_ordered": bool(comparisons)
        and all(item["passed"] for item in comparisons),
        "every_declared_physical_length": {
            item["l_m"] for item in comparisons
        }
        == {float(value) for value in settings["physical_lengths_m"]},
        "both_polarities": {item["polarity"] for item in comparisons} == {"n", "p"},
        "geometry_hierarchy_review": (
            _geometry(generation, "io18").lmin_m
            > float(
                _load_toml(root / "models/apm045/families/vtg/family.toml")[
                    "device"
                ][0]["lmin_m"]
            )
            and _geometry(generation, "io25").lmin_m
            > _geometry(generation, "io18").lmin_m
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "claim_class": (
            "ROBUST_ACROSS_ENSEMBLE"
            if checks["all_candidate_pairs_strictly_ordered"]
            else "EPISTEMICALLY_UNRESOLVED"
        ),
        "comparison_count": len(comparisons),
        "comparisons": comparisons,
        "candidate_observations": raw_observations,
        "vtg_cgg_density_f_per_m2": [
            {"polarity": key[0], "l_m": key[1], "value": value}
            for key, value in sorted(vtg.items())
        ],
    }


def _distinctness_candidate_observations(
    *,
    evaluator: NgspiceEvaluator,
    terminal: TerminalEvaluator,
    generation: Mapping[str, Any],
    qualification: Mapping[str, Any],
    record: Mapping[str, Any],
    token: str,
) -> list[dict[str, Any]]:
    family = str(record["family"])
    seed = int(record["seed"])
    polarity = str(record["polarity"])
    geometry = _geometry(generation, family)
    settings = qualification["distinctness"]
    vdd = float(settings["common_vdd_v"])
    points = int(settings["points"])
    requests: list[SweepRequest] = []
    coordinates: dict[str, dict[str, Any]] = {}
    for length in settings["physical_lengths_m"]:
        for vds_fraction in settings["vds_fractions"]:
            request_id = (
                f"{family}-{seed}-{polarity}-physical-l{float(length):.12g}"
                f"-vd{float(vds_fraction):.4g}"
            )
            requests.append(
                SweepRequest(
                    request_id=request_id,
                    kind="idvg",
                    temperature_c=int(settings["temperature_c"]),
                    l_m=float(length),
                    w_m=float(settings["width_um"]) * 1e-6,
                    fixed_bias_v=vdd * float(vds_fraction),
                    sweep_stop_v=vdd,
                    points=points,
                )
            )
            coordinates[request_id] = {
                "view": "equal_physical_l",
                "coordinate": float(length),
                "vds_fraction": float(vds_fraction),
            }
    for length_ratio in settings["relative_length_ratios"]:
        for vds_fraction in settings["vds_fractions"]:
            request_id = (
                f"{family}-{seed}-{polarity}-relative-lr{float(length_ratio):.4g}"
                f"-vd{float(vds_fraction):.4g}"
            )
            requests.append(
                SweepRequest(
                    request_id=request_id,
                    kind="idvg",
                    temperature_c=int(settings["temperature_c"]),
                    l_m=geometry.lmin_m * float(length_ratio),
                    w_m=float(settings["width_um"]) * 1e-6,
                    fixed_bias_v=vdd * float(vds_fraction),
                    sweep_stop_v=vdd,
                    points=points,
                )
            )
            coordinates[request_id] = {
                "view": "equal_relative_l",
                "coordinate": float(length_ratio),
                "vds_fraction": float(vds_fraction),
            }
    source = _source(generation, record)
    curves = evaluator.evaluate_many(
        source=source,
        polarity=polarity,
        requests=requests,
        token=f"{token}-curves",
    )
    solutions: list[dict[str, Any]] = []
    y_points: list[BiasPoint] = []
    current_floor = float(generation["numerical"]["current_floor_a"])
    for request_id, curve in curves.items():
        for target in settings["gmid_targets_per_v"]:
            solution = _gmid_solution(
                curve,
                float(target),
                current_floor_a=current_floor,
                endpoint_guard=int(settings["endpoint_guard_points"]),
            )
            solution.update(
                {
                    **coordinates[request_id],
                    "request_id": request_id,
                    "family": family,
                    "seed": seed,
                    "polarity": polarity,
                    "l_m": curve.request.l_m,
                    "w_m": curve.request.w_m,
                    "vout_v": curve.request.fixed_bias_v,
                }
            )
            solutions.append(solution)
            if solution["state"] == "validated":
                y_points.append(
                    BiasPoint(
                        point_id=f"{request_id}-gmid-{float(target):.4g}",
                        temperature_c=curve.request.temperature_c,
                        l_m=curve.request.l_m,
                        w_m=curve.request.w_m,
                        vctrl_v=float(solution["vctrl_v"]),
                        vout_v=curve.request.fixed_bias_v,
                    )
                )
    y_observations = terminal.evaluate_y(
        source=source,
        model_name=source.model_name,
        polarity=polarity,
        points=y_points,
        frequencies_hz=[float(settings["frequency_hz"])],
        token=f"{token}-cgg",
    )
    by_id = {str(item["point_id"]): item for item in y_observations}
    result: list[dict[str, Any]] = []
    for solution in solutions:
        point_id = f"{solution['request_id']}-gmid-{float(solution['target_per_v']):.4g}"
        item = dict(solution)
        if point_id in by_id:
            y = by_id[point_id]
            cgg = _cgg_from_y(y)
            cgd = -float(y["y_imag_s"][0][1]) / (
                2.0 * math.pi * float(y["frequency_hz"])
            )
            item.update(
                {
                    "cgg_f": cgg,
                    "cgg_density_f_per_m2": cgg / (item["w_m"] * item["l_m"]),
                    "cgd_over_cgg": abs(cgd) / cgg,
                    "id_per_width_a_per_m": item["idmag_a"] / item["w_m"],
                }
            )
        result.append(item)
    return result


def _distinctness_qualification(
    *,
    evaluator: NgspiceEvaluator,
    terminal: TerminalEvaluator,
    generation: Mapping[str, Any],
    qualification: Mapping[str, Any],
    records: Mapping[tuple[str, int, str], Mapping[str, Any]],
    eligible: Mapping[str, Sequence[int]],
) -> dict[str, Any]:
    observations: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for family in ("io18", "io25"):
        for seed in eligible[family]:
            for polarity in ("n", "p"):
                key = (family, int(seed), polarity)
                observations[key] = _distinctness_candidate_observations(
                    evaluator=evaluator,
                    terminal=terminal,
                    generation=generation,
                    qualification=qualification,
                    record=records[key],
                    token=f"distinct-{family}-{seed}-{polarity}",
                )
    indexed: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for key, items in observations.items():
        for item in items:
            identity = (
                key,
                item["view"],
                float(item["coordinate"]),
                float(item["vds_fraction"]),
                float(item["target_per_v"]),
            )
            indexed[identity] = item
    comparisons: list[dict[str, Any]] = []
    for io18_seed in eligible["io18"]:
        for io25_seed in eligible["io25"]:
            for polarity in ("n", "p"):
                for view, coordinate_values in (
                    ("equal_physical_l", qualification["distinctness"]["physical_lengths_m"]),
                    ("equal_relative_l", qualification["distinctness"]["relative_length_ratios"]),
                ):
                    for coordinate in coordinate_values:
                        for vds_fraction in qualification["distinctness"]["vds_fractions"]:
                            for target in qualification["distinctness"]["gmid_targets_per_v"]:
                                first = indexed[
                                    (
                                        ("io18", int(io18_seed), polarity),
                                        view,
                                        float(coordinate),
                                        float(vds_fraction),
                                        float(target),
                                    )
                                ]
                                second = indexed[
                                    (
                                        ("io25", int(io25_seed), polarity),
                                        view,
                                        float(coordinate),
                                        float(vds_fraction),
                                        float(target),
                                    )
                                ]
                                valid = (
                                    first["state"] == "validated"
                                    and second["state"] == "validated"
                                    and "cgg_density_f_per_m2" in first
                                    and "cgg_density_f_per_m2" in second
                                )
                                comparisons.append(
                                    {
                                        "io18_seed": int(io18_seed),
                                        "io25_seed": int(io25_seed),
                                        "polarity": polarity,
                                        "view": view,
                                        "coordinate": float(coordinate),
                                        "vds_fraction": float(vds_fraction),
                                        "gmid_target_per_v": float(target),
                                        "validated": valid,
                                        "capacitance_density_ratio_io18_over_io25": (
                                            first["cgg_density_f_per_m2"]
                                            / second["cgg_density_f_per_m2"]
                                            if valid
                                            else None
                                        ),
                                        "current_density_ratio_io18_over_io25": (
                                            first["id_per_width_a_per_m"]
                                            / second["id_per_width_a_per_m"]
                                            if valid
                                            else None
                                        ),
                                        "control_voltage_io18_v": first.get("vctrl_v"),
                                        "control_voltage_io25_v": second.get("vctrl_v"),
                                    }
                                )
    valid = [item for item in comparisons if item["validated"]]
    capacitance_ratios = [
        float(item["capacitance_density_ratio_io18_over_io25"]) for item in valid
    ]
    current_ratios = [
        float(item["current_density_ratio_io18_over_io25"]) for item in valid
    ]
    settings = qualification["distinctness"]
    current_success = [
        value >= float(settings["current_density_ratio_majority_min"])
        for value in current_ratios
    ]
    design_records: list[dict[str, Any]] = []
    for comparison in valid:
        ratio = float(comparison["current_density_ratio_io18_over_io25"])
        for current in settings["fixed_current_a"]:
            # Required width is I/(I/W); therefore W_io25/W_io18 equals
            # the measured current-density ratio at equal inversion.
            design_records.append(
                {
                    "io18_seed": comparison["io18_seed"],
                    "io25_seed": comparison["io25_seed"],
                    "polarity": comparison["polarity"],
                    "view": comparison["view"],
                    "coordinate": comparison["coordinate"],
                    "vds_fraction": comparison["vds_fraction"],
                    "gmid_target_per_v": comparison["gmid_target_per_v"],
                    "fixed_current_a": float(current),
                    "required_width_ratio_io25_over_io18": ratio,
                    "control_voltage_delta_io25_minus_io18_v": (
                        float(comparison["control_voltage_io25_v"])
                        - float(comparison["control_voltage_io18_v"])
                    ),
                }
            )
    design_success = [
        item["required_width_ratio_io25_over_io18"]
        >= float(settings["required_width_ratio_majority_min"])
        for item in design_records
    ]
    checks = {
        "all_comparisons_reachable": len(valid) == len(comparisons) and bool(valid),
        "IO18_IO25_CAPACITANCE_DISTINCTION": bool(capacitance_ratios)
        and min(capacitance_ratios) >= float(settings["capacitance_ratio_all_min"])
        and float(np.median(capacitance_ratios))
        >= float(settings["capacitance_ratio_median_min"]),
        "IO18_IO25_CURRENT_DENSITY_DISTINCTION": bool(current_success)
        and sum(current_success) / len(current_success)
        >= float(settings["current_density_required_majority_fraction"]),
        "IO18_IO25_DESIGN_REALIZATION_DISTINCTION": bool(design_success)
        and sum(design_success) / len(design_success)
        >= float(settings["required_width_ratio_majority_fraction"]),
        "no_forced_unrelated_order": not any(
            bool(settings[name])
            for name in (
                "forced_gm_over_gds_order",
                "forced_noise_order",
                "forced_leakage_order",
                "forced_total_gate_charge_order",
            )
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "claim_classes": {
            name: (
                "ROBUST_ACROSS_ENSEMBLE"
                if value and name == "IO18_IO25_CAPACITANCE_DISTINCTION"
                else "MAJORITY_ACROSS_ENSEMBLE"
                if value
                else "EPISTEMICALLY_UNRESOLVED"
            )
            for name, value in checks.items()
            if name.startswith("IO18_IO25_")
        },
        "metrics": {
            "capacitance_ratio_min": _minimum(capacitance_ratios),
            "capacitance_ratio_median": _median(capacitance_ratios),
            "current_density_ratio_min": _minimum(current_ratios),
            "current_density_ratio_median": _median(current_ratios),
            "current_density_success_fraction": sum(current_success)
            / max(len(current_success), 1),
            "design_width_ratio_success_fraction": sum(design_success)
            / max(len(design_success), 1),
        },
        "comparisons": comparisons,
        "design_realization": design_records,
        "candidate_observations": [
            item for values in observations.values() for item in values
        ],
    }


def _solve_current(curve: Curve, target_a: float) -> dict[str, Any]:
    for index in range(curve.idmag_a.size - 1):
        low = float(curve.idmag_a[index])
        high = float(curve.idmag_a[index + 1])
        if low <= target_a <= high and high > low:
            fraction = (target_a - low) / (high - low)
            return {
                "state": "validated",
                "vctrl_v": float(
                    curve.sweep_v[index]
                    + fraction * (curve.sweep_v[index + 1] - curve.sweep_v[index])
                ),
                "interpolated_current_a": target_a,
                "bracket_indices": [index, index + 1],
            }
    return {
        "state": "target_not_reachable",
        "target_a": target_a,
        "current_min_a": float(np.min(curve.idmag_a)),
        "current_max_a": float(np.max(curve.idmag_a)),
    }


def _circuit_candidate(
    *,
    sweep_evaluator: NgspiceEvaluator,
    terminal: TerminalEvaluator,
    circuit: CircuitEvaluator,
    generation: Mapping[str, Any],
    qualification: Mapping[str, Any],
    n_record: Mapping[str, Any],
    p_record: Mapping[str, Any],
    token: str,
) -> dict[str, Any]:
    family = str(n_record["family"])
    seed = int(n_record["seed"])
    if str(p_record["family"]) != family or int(p_record["seed"]) != seed:
        raise QualificationError("circuit candidate N/P pair identity mismatch")
    geometry = _geometry(generation, family)
    settings = qualification["circuit_holdout"]
    criteria = settings["criteria"]
    n_card = _render_candidate(generation, family, "n", n_record["parameters"])
    p_card = _render_candidate(generation, family, "p", p_record["parameters"])
    n_name = f"apm045_{family}_ncore"
    p_name = f"apm045_{family}_pcore"

    basic: list[dict[str, Any]] = []
    for temperature in settings["temperatures_c"]:
        for length_ratio in settings["length_ratios"]:
            request = BasicCircuitRequest(
                request_id=f"{family}-{seed}-t{int(temperature):+d}-lr{float(length_ratio):.4g}",
                family=family,
                seed=seed,
                temperature_c=int(temperature),
                l_m=geometry.lmin_m * float(length_ratio),
                w_m=float(settings["device_width_um"]) * 1e-6,
                vdd_v=geometry.native_vdd_v,
            )
            basic.append(
                circuit.evaluate_basic(
                    request=request,
                    n_card=n_card,
                    p_card=p_card,
                    n_model_name=n_name,
                    p_model_name=p_name,
                    settings=settings,
                    criteria=criteria,
                    token=f"{token}-basic-t{int(temperature):+d}-lr{float(length_ratio):.4g}",
                )
            )

    scenario_names = [
        name
        for name in settings["pass_scenarios"]
        if str(settings["scenario"][name]["family"]) == family
    ]
    unit_width_m = float(settings["unit_width_um"]) * 1e-6
    pass_requests: list[SweepRequest] = []
    pass_identity: dict[str, dict[str, Any]] = {}
    for temperature in settings["temperatures_c"]:
        for length_ratio in settings["length_ratios"]:
            for scenario_name in scenario_names:
                scenario = settings["scenario"][scenario_name]
                vin = float(scenario["vin_v"])
                vout = float(scenario["vout_v"])
                request_id = (
                    f"{family}-{seed}-{scenario_name}-t{int(temperature):+d}"
                    f"-lr{float(length_ratio):.4g}"
                )
                pass_requests.append(
                    SweepRequest(
                        request_id=request_id,
                        kind="idvg",
                        temperature_c=int(temperature),
                        l_m=geometry.lmin_m * float(length_ratio),
                        w_m=unit_width_m,
                        fixed_bias_v=vin - vout,
                        sweep_stop_v=vin,
                        points=int(settings["pass_sweep_points"]),
                    )
                )
                pass_identity[request_id] = {
                    "scenario": scenario_name,
                    "temperature_c": int(temperature),
                    "length_ratio": float(length_ratio),
                    "vin_v": vin,
                    "vout_v": vout,
                }
    p_source = _source(generation, p_record)
    pass_curves = sweep_evaluator.evaluate_many(
        source=p_source,
        polarity="p",
        requests=pass_requests,
        token=f"{token}-pass-sizing",
    )
    pass_cases: list[PassCase] = []
    sizing_records: list[dict[str, Any]] = []
    margin = float(criteria["pass_required_vsg_margin_fraction_vin"])
    headroom = float(settings["pass_sizing_current_headroom"])
    maximum_units = int(settings["maximum_parallel_units"])
    for request_id, curve in pass_curves.items():
        identity = pass_identity[request_id]
        maximum_vsg = identity["vin_v"] * (1.0 - margin)
        allowed_current = float(
            np.interp(maximum_vsg, curve.sweep_v, curve.idmag_a)
        )
        for load in settings["pass_load_currents_a"]:
            units = math.ceil(float(load) * headroom / allowed_current)
            case_id = f"{request_id}-load{float(load):.12g}"
            solution = _solve_current(curve, float(load) / units) if units <= maximum_units else {
                "state": "target_not_reachable",
                "reason": "maximum_parallel_units_exceeded",
            }
            sizing = {
                "case_id": case_id,
                **identity,
                "load_current_a": float(load),
                "allowed_single_unit_current_a": allowed_current,
                "sizing_current_headroom": headroom,
                "parallel_units": units,
                "maximum_parallel_units": maximum_units,
                "solution": solution,
            }
            sizing_records.append(sizing)
            if solution["state"] == "validated" and units <= maximum_units:
                pass_cases.append(
                    PassCase(
                        case_id=case_id,
                        family=family,
                        seed=seed,
                        temperature_c=int(identity["temperature_c"]),
                        l_m=curve.request.l_m,
                        unit_width_m=unit_width_m,
                        units=units,
                        vin_v=float(identity["vin_v"]),
                        vout_v=float(identity["vout_v"]),
                        required_vsg_v=float(solution["vctrl_v"]),
                        load_current_a=float(load),
                    )
                )

    pass_observations: list[dict[str, Any]] = []
    for temperature in sorted({case.temperature_c for case in pass_cases}):
        group = [case for case in pass_cases if case.temperature_c == temperature]
        pass_observations.extend(
            circuit.evaluate_pass_cases(
                cases=group,
                p_card=p_card,
                p_model_name=p_name,
                maximum_units=maximum_units,
                relative_error_max=float(criteria["pass_current_relative_error_max"]),
                token=f"{token}-pass-confirm-t{temperature:+d}",
            )
        )

    derivative_points = [
        BiasPoint(
            point_id=case.case_id,
            temperature_c=case.temperature_c,
            l_m=case.l_m,
            w_m=case.unit_width_m,
            vctrl_v=case.required_vsg_v,
            vout_v=case.vin_v - case.vout_v,
        )
        for case in pass_cases
    ]
    pass_derivatives = terminal.evaluate_derivatives(
        source=p_source,
        model_name=p_source.model_name,
        polarity="p",
        points=derivative_points,
        vdd_v=geometry.native_vdd_v,
        step_fraction_vdd=float(
            qualification["device_holdout"]["criteria"][
                "finite_difference_step_fraction_vdd"
            ]
        ),
        token=f"{token}-pass-derivatives",
    )
    derivative_by_id = {item["point_id"]: item for item in pass_derivatives}
    trajectory_by_case: dict[str, GateTrajectory] = {}
    for case in pass_cases:
        trajectory_by_case[case.case_id] = GateTrajectory(
            trajectory_id=case.case_id,
            temperature_c=case.temperature_c,
            l_m=case.l_m,
            w_m=case.unit_width_m,
            fixed_vout_v=case.vin_v - case.vout_v,
            vctrl_values_v=tuple(
                float(value) for value in np.linspace(0.0, case.required_vsg_v, 11)
            ),
        )
    charge_observations = terminal.evaluate_gate_trajectories(
        source=p_source,
        model_name=p_source.model_name,
        polarity="p",
        trajectories=list(trajectory_by_case.values()),
        frequencies_hz=[float(settings["pass_charge_frequency_hz"])],
        token=f"{token}-pass-charge",
    )
    charge_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in charge_observations:
        charge_groups[str(item["trajectory_id"])].append(item)
    case_by_id = {case.case_id: case for case in pass_cases}
    enriched: list[dict[str, Any]] = []
    for item in pass_observations:
        case = case_by_id[str(item["case_id"])]
        derivative = derivative_by_id[str(item["case_id"])]
        trajectory = sorted(
            charge_groups[str(item["case_id"])], key=lambda record: float(record["vctrl_v"])
        )
        unit_charge = float(
            np.trapezoid(
                [float(record["cgg_f"]) for record in trajectory],
                [float(record["vctrl_v"]) for record in trajectory],
            )
        )
        total_charge = unit_charge * case.units
        total_width = case.unit_width_m * case.units
        enriched.append(
            {
                **item,
                "gm_over_id_per_v": derivative["gm_over_id_per_v"],
                "gds_over_id_per_v": derivative["gds_over_id_per_v"],
                "ron_times_width_ohm_m": (
                    (case.vin_v - case.vout_v)
                    / float(item["observed_current_a"])
                    * total_width
                ),
                "intrinsic_gate_charge_c": total_charge,
                "intrinsic_gate_charge_per_width_c_per_m": total_charge / total_width,
                "intrinsic_gate_charge_per_current_c_per_a": total_charge
                / float(item["observed_current_a"]),
                "charge_boundary": "intrinsic/model terminal charge including model overlap only",
            }
        )
    checks = {
        "all_basic_fixtures_pass": bool(basic)
        and all(item["status"] == "pass" for item in basic),
        "all_pass_cases_sized": len(pass_cases) == len(sizing_records) and bool(pass_cases),
        "maximum_parallel_units": all(case.units <= maximum_units for case in pass_cases),
        "explicit_parallel_units": all(
            item["explicit_parallel_instances"] for item in enriched
        ),
        "all_pass_confirmations": bool(enriched)
        and all(item["status"] == "pass" for item in enriched),
        "pass_vsg_margin": all(
            item["required_vsg_v"]
            <= item["vin_v"] * (1.0 - margin)
            for item in enriched
        ),
        "pass_metrics_finite": all(
            math.isfinite(float(item[name]))
            for item in enriched
            for name in (
                "required_vsg_v",
                "total_width_m",
                "gm_over_id_per_v",
                "gds_over_id_per_v",
                "ron_times_width_ohm_m",
                "intrinsic_gate_charge_per_width_c_per_m",
                "intrinsic_gate_charge_per_current_c_per_a",
            )
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "fixture_classes": settings["fixture_classes"],
        "basic_fixtures": basic,
        "pass_sizing": sizing_records,
        "pmos_pass_device": enriched,
        "claim_boundary": (
            "Numerical/usefulness fixtures only; not foundry circuit targets, layout area, "
            "shared-diffusion capacitance, extracted gate resistance, or production gate charge."
        ),
    }


def _candidate_metric_vector(domains: Mapping[str, Mapping[str, Any]]) -> dict[str, float]:
    device = domains["sealed_device_holdout"]["metrics"]
    charge = domains["sealed_charge_holdout"]["metrics"]
    body = domains["body_effect"]["metrics"]
    return {
        "vth": float(device["threshold_v_median"]),
        "dibl": float(device["dibl_v_per_v_median"]),
        "id_per_width_vs_gmid": float(device["id_per_width_at_gmid_median_a_per_m"]),
        "gds_over_id": float(device["gds_over_id_median_per_v"]),
        "gm_over_gds": float(device["gm_over_gds_median"]),
        "cgg_per_width_or_area": float(charge["cgg_density_median_f_per_m2"]),
        "cgd_over_cgg": float(charge["cgd_over_cgg_median"]),
        "body_effect": float(body["threshold_shift_median_v"]),
        "temperature": float(device["temperature_endpoint_current_ratio_median"]),
    }


def _select_medoid(
    *,
    family: str,
    seeds: Sequence[int],
    candidate_results: Mapping[tuple[str, int, str], Mapping[str, Any]],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    names = [str(value) for value in settings["metric_names"]]
    vectors: dict[int, dict[str, float]] = {}
    for seed in seeds:
        polarity_vectors = [
            _candidate_metric_vector(candidate_results[(family, int(seed), polarity)]["domains"])
            for polarity in ("n", "p")
        ]
        vectors[int(seed)] = {
            name: float(np.median([item[name] for item in polarity_vectors])) for name in names
        }
    scales: dict[str, float] = {}
    for name in names:
        values = np.asarray([vectors[int(seed)][name] for seed in seeds], dtype=float)
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        scales[name] = max(mad, float(settings["normalization_floor"][name]))
    distances: dict[int, float] = {}
    for seed in seeds:
        distances[int(seed)] = sum(
            sum(
                abs(vectors[int(seed)][name] - vectors[int(other)][name]) / scales[name]
                for name in names
            )
            for other in seeds
            if int(other) != int(seed)
        )
    selected = min((distance, int(seed)) for seed, distance in distances.items())[1]
    return {
        "family": family,
        "method": settings["method"],
        "distance": settings["distance"],
        "normalization": settings["normalization"],
        "normalization_scales": scales,
        "metric_vectors": {str(seed): vector for seed, vector in vectors.items()},
        "summed_pairwise_distance": {
            str(seed): distance for seed, distance in distances.items()
        },
        "tie_break": settings["tie_break"],
        "selected_seed": selected,
        "circuit_results_available_before_selection": True,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def run_preflight(
    *,
    root: Path,
    output: Path,
    qualification_path: Path,
    calibration_report_path: Path,
) -> dict[str, Any]:
    _, _, _, audit = _validate_contracts(
        root=root,
        qualification_path=qualification_path,
        calibration_report_path=calibration_report_path,
    )
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": PREFLIGHT_SCHEMA,
        "created_utc": _utc_now(),
        "status": "pass",
        "holdouts_evaluated": False,
        "safe_to_commit_before_unseal": True,
        "audit": audit,
    }
    _write_json(output / "preflight.json", report)
    return report


def qualify(
    *,
    root: Path,
    output: Path,
    qualification_path: Path,
    calibration_report_path: Path,
) -> dict[str, Any]:
    qualification, generation, calibration, preflight = _validate_contracts(
        root=root,
        qualification_path=qualification_path,
        calibration_report_path=calibration_report_path,
    )
    git = _git_identity(root)
    if not git["worktree_clean"]:
        raise QualificationError(
            "sealed qualification requires a clean committed worktree; "
            + "; ".join(git["status_lines"][:20])
        )
    if output.exists() and any(output.iterdir()):
        raise QualificationError(f"one-shot qualification output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "apm.mixed-voltage-holdout-unseal-receipt.v1",
        "created_utc": _utc_now(),
        "qualification_epoch": int(qualification["qualification_epoch"]),
        "generation_epoch": int(generation["generation_epoch"]),
        "git": git,
        "qualification_input_sha256": sha256_file(qualification_path),
        "generation_contract_sha256": sha256_file(
            root / str(qualification["generation_contract"])
        ),
        "calibration_report_sha256": sha256_file(calibration_report_path),
        "calibration_canonical_content_sha256": _canonical_report_sha256(calibration),
        "definitions_unsealed": [
            "sealed_device_holdout",
            "sealed_charge_holdout",
            "terminal_y.holdout",
            "sealed_circuit_holdout",
        ],
        "candidate_parameter_modification_after_unseal_permitted": False,
        "failed_holdout_reuse_for_repair_permitted": False,
    }
    _write_json(output / "unseal_receipt.json", receipt)

    ngspice = root / ".apm/toolchain/ngspice-47/bin/ngspice"
    sweep_evaluator = NgspiceEvaluator(
        ngspice=ngspice, work_directory=output / "work" / "sweeps"
    )
    terminal = TerminalEvaluator(
        ngspice=ngspice, work_directory=output / "work" / "terminals"
    )
    circuit = CircuitEvaluator(
        ngspice=ngspice, work_directory=output / "work" / "circuits"
    )
    tool_identities = [
        sweep_evaluator.tool_identity(),
        terminal.tool_identity(),
        circuit.tool_identity(),
    ]
    if not all(
        item["major"] == str(qualification["reference_simulator_major"])
        and item["sha256"] == tool_identities[0]["sha256"]
        for item in tool_identities
    ):
        raise QualificationError("qualification evaluator tool identities disagree")

    records = _record_map(calibration)
    candidate_results: dict[tuple[str, int, str], dict[str, Any]] = {}
    for family in ("io18", "io25"):
        for seed in calibration["ensemble"]["retained_seeds"][family]:
            for polarity in ("n", "p"):
                key = (family, int(seed), polarity)
                record = records[key]
                token = f"{family}-{seed}-{polarity}"
                domains = {
                    "sealed_device_holdout": _device_holdout(
                        evaluator=sweep_evaluator,
                        terminal=terminal,
                        generation=generation,
                        qualification=qualification,
                        record=record,
                        token=f"{token}-device",
                    ),
                    "sealed_charge_holdout": _charge_holdout(
                        terminal=terminal,
                        generation=generation,
                        qualification=qualification,
                        record=record,
                        token=f"{token}-charge",
                    ),
                    "terminal_y": _terminal_y_holdout(
                        terminal=terminal,
                        generation=generation,
                        qualification=qualification,
                        record=record,
                        token=f"{token}-y",
                    ),
                    "body_effect": _body_effect(
                        terminal=terminal,
                        generation=generation,
                        qualification=qualification,
                        record=record,
                        token=f"{token}-body",
                    ),
                }
                candidate_results[key] = {
                    "family": family,
                    "seed": int(seed),
                    "polarity": polarity,
                    "parameter_sha256": record["parameter_sha256"],
                    "card_sha256": record["card"]["sha256"],
                    "status": (
                        "pass"
                        if all(item["status"] == "pass" for item in domains.values())
                        else "fail"
                    ),
                    "domains": domains,
                }

    pair_circuits: dict[tuple[str, int], dict[str, Any]] = {}
    for family in ("io18", "io25"):
        for seed in calibration["ensemble"]["retained_seeds"][family]:
            pair_circuits[(family, int(seed))] = _circuit_candidate(
                sweep_evaluator=sweep_evaluator,
                terminal=terminal,
                circuit=circuit,
                generation=generation,
                qualification=qualification,
                n_record=records[(family, int(seed), "n")],
                p_record=records[(family, int(seed), "p")],
                token=f"circuit-{family}-{seed}",
            )

    eligible: dict[str, list[int]] = {}
    eligibility: dict[str, dict[str, Any]] = {}
    minimum = int(qualification["ensemble"]["minimum_retained_candidates_per_family"])
    for family in ("io18", "io25"):
        seeds = [int(value) for value in calibration["ensemble"]["retained_seeds"][family]]
        eligible[family] = [
            seed
            for seed in seeds
            if candidate_results[(family, seed, "n")]["status"] == "pass"
            and candidate_results[(family, seed, "p")]["status"] == "pass"
            and pair_circuits[(family, seed)]["status"] == "pass"
        ]
        eligibility[family] = {
            "calibration_retained_seeds": seeds,
            "individually_qualified_seeds": eligible[family],
            "retained_count": len(eligible[family]),
            "minimum_required": minimum,
            "minimum_count": len(eligible[family]) >= minimum,
        }
    if not all(item["minimum_count"] for item in eligibility.values()):
        if not eligibility["io25"]["minimum_count"]:
            early_failure_state = qualification["failure_states"]["io25"]
        elif not eligibility["io18"]["minimum_count"]:
            early_failure_state = qualification["failure_states"]["io18"]
        else:  # pragma: no cover - defensive completeness
            early_failure_state = qualification["failure_states"]["ensemble"]
        failure_report = {
            "schema": SCHEMA,
            "created_utc": _utc_now(),
            "status": "fail",
            "completion_state": None,
            "failure_state": early_failure_state,
            "unseal_receipt": receipt,
            "preflight": preflight,
            "eligibility": eligibility,
            "candidate_results": list(candidate_results.values()),
            "circuit_results": list(pair_circuits.values()),
            "holdout_reuse_for_repair_permitted": False,
        }
        _write_json(output / "report.json", failure_report)
        return failure_report

    structural = _structural_qualification(
        root=root,
        terminal=terminal,
        generation=generation,
        qualification=qualification,
        records=records,
        eligible=eligible,
    )
    distinctness = _distinctness_qualification(
        evaluator=sweep_evaluator,
        terminal=terminal,
        generation=generation,
        qualification=qualification,
        records=records,
        eligible=eligible,
    )
    global_checks = {
        "minimum_retained_ensemble": all(
            item["minimum_count"] for item in eligibility.values()
        ),
        "hard_structural_contract": structural["status"] == "pass",
        "io18_io25_distinctness": distinctness["status"] == "pass",
        "all_candidate_domains": all(
            candidate_results[(family, seed, polarity)]["status"] == "pass"
            for family in ("io18", "io25")
            for seed in eligible[family]
            for polarity in ("n", "p")
        ),
        "all_circuit_holdouts": all(
            pair_circuits[(family, seed)]["status"] == "pass"
            for family in ("io18", "io25")
            for seed in eligible[family]
        ),
    }
    status = "pass" if all(global_checks.values()) else "fail"
    selections: dict[str, Any] = {}
    canonical_artifacts: dict[str, Any] = {}
    if status == "pass":
        canonical_directory = output / "canonical"
        canonical_directory.mkdir()
        for family in ("io18", "io25"):
            selections[family] = _select_medoid(
                family=family,
                seeds=eligible[family],
                candidate_results=candidate_results,
                settings=qualification["selection"],
            )
            selected = int(selections[family]["selected_seed"])
            canonical_artifacts[family] = {"seed": selected, "devices": {}}
            for polarity in ("n", "p"):
                record = records[(family, selected, polarity)]
                source_path = calibration_report_path.parent / record["card"]["path"]
                target_path = canonical_directory / f"apm045_{family}_{polarity}.inc"
                shutil.copyfile(source_path, target_path)
                canonical_artifacts[family]["devices"][polarity] = {
                    "path": str(target_path.relative_to(output)),
                    "sha256": sha256_file(target_path),
                    "source_calibration_card_sha256": record["card"]["sha256"],
                    "byte_identical_to_frozen_candidate": target_path.read_bytes()
                    == source_path.read_bytes(),
                }

    failure_state = None
    if status == "fail":
        failure_state = (
            qualification["failure_states"]["ensemble"]
            if structural["status"] != "pass"
            else qualification["failure_states"]["distinctness"]
            if distinctness["status"] != "pass"
            else qualification["failure_states"]["circuit"]
        )
    report = {
        "schema": SCHEMA,
        "created_utc": _utc_now(),
        "status": status,
        "completion_state": COMPLETION_STATE if status == "pass" else None,
        "failure_state": failure_state,
        "qualification_epoch": int(qualification["qualification_epoch"]),
        "generation_epoch": int(generation["generation_epoch"]),
        "unseal_receipt": receipt,
        "preflight": preflight,
        "artifact_identity": {
            "git": git,
            "qualification_input": {
                "path": str(qualification_path.relative_to(root)),
                "sha256": sha256_file(qualification_path),
            },
            "qualification_implementation": {
                "path": str(Path(__file__).relative_to(root)),
                "sha256": sha256_file(Path(__file__)),
            },
            "terminal_observables_implementation_sha256": sha256_file(
                Path(__file__).with_name("terminal_observables.py")
            ),
            "circuit_fixtures_implementation_sha256": sha256_file(
                Path(__file__).with_name("circuit_fixtures.py")
            ),
            "calibration_report": {
                "path": str(calibration_report_path),
                "sha256": sha256_file(calibration_report_path),
                "canonical_content_sha256": _canonical_report_sha256(calibration),
            },
            "kernel": f"{KERNEL_ID}@{KERNEL_VERSION}",
            "reference_tool": tool_identities[0],
        },
        "global_checks": global_checks,
        "eligibility": eligibility,
        "epistemic_ensemble": {
            "retained_seeds": eligible,
            "minimum_per_family": minimum,
            "epistemic_not_process_variation": True,
            "claim_classes": qualification["ensemble"]["required_claim_classes"],
            "required_structural_claim_reversal_is_failure": True,
        },
        "candidate_results": list(candidate_results.values()),
        "structural": structural,
        "io18_io25_distinctness": distinctness,
        "sealed_circuit_holdout": list(pair_circuits.values()),
        "canonical_selection": selections,
        "canonical_artifacts": canonical_artifacts,
        "simulator_evaluation_count": {
            "sweep_batches": sweep_evaluator.evaluation_count,
            "terminal_batches": terminal.evaluation_count,
            "circuit_batches": circuit.evaluation_count,
            "total": sweep_evaluator.evaluation_count
            + terminal.evaluation_count
            + circuit.evaluation_count,
        },
        "claim_boundary": qualification["claim_boundary"],
        "holdout_reuse_for_repair_permitted": False,
    }
    _write_json(output / "report.json", report)
    return report


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("qualification_epoch_2.toml"),
    )
    parser.add_argument("--calibration-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--unseal", action="store_true")
    parser.add_argument("--replace-output", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    root = arguments.root.resolve()
    output = arguments.output.resolve()
    if arguments.replace_output:
        if arguments.unseal:
            raise QualificationError("--replace-output is forbidden for one-shot unsealing")
        if output.exists():
            shutil.rmtree(output)
    report = (
        run_preflight(
            root=root,
            output=output,
            qualification_path=arguments.config.resolve(),
            calibration_report_path=arguments.calibration_report.resolve(),
        )
        if arguments.preflight
        else qualify(
            root=root,
            output=output,
            qualification_path=arguments.config.resolve(),
            calibration_report_path=arguments.calibration_report.resolve(),
        )
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
