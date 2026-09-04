# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Versioned real-ngspice APM045 mixed-voltage comparison views."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib

from .catalog import FamilySpec, load_catalog
from .characterize import (
    NGSPICE_GMIN_S,
    PlanarGeometry,
    PlanarKit,
    _capacitance_rows,
    _dc_job,
    _derive_operating_metrics,
    _read_wrdata,
    _run_ngspice,
    _y_job,
    load_family,
)
from .model_build import build_models, sha256_file
from .paths import repository_root
from .toolchain import Toolchain, resolve_toolchain, run_checked

COMPARISON_SCHEMA = "apm.mixed-voltage-comparison.v1"
CONFIGURATION_PATH = Path("validation/mixed_voltage_comparison_v1.toml")
RELEASE_CONTRACT_PATH = Path("validation/release_gates_v4.toml")
ALLOWED_TARGET_STATES = {"validated", "target_not_reachable", "simulation_failed"}

OBSERVATION_FIELDS = (
    "point_id",
    "view_id",
    "coordinate_kind",
    "technology_id",
    "family_id",
    "device_id",
    "public_device",
    "polarity",
    "operating_profile_id",
    "reference_vdd_v",
    "metric_basis",
    "temperature_c",
    "w_m",
    "l_m",
    "l_over_lmin",
    "target_solver_state",
    "target_solver_method",
    "target_solver_reason",
    "qualified_gmid_min_per_v",
    "qualified_gmid_max_per_v",
    "gmid_target_per_v",
    "gmid_target_relative_error",
    "vctrl_v",
    "vctrl_over_vdd",
    "vout_v",
    "vout_over_vdd",
    "raw_vd_source_current_a",
    "raw_drain_current_entering_device_a",
    "idmag_a",
    "id_per_width_a_per_m",
    "gm_s",
    "gds_s",
    "gm_over_id_per_v",
    "gds_over_id_per_v",
    "gm_over_gds",
    "gm_convergence_relative",
    "gds_convergence_relative",
    "native_gm_relative_error",
    "native_gds_relative_error",
    "terminal_y_frequency_hz",
    "y_kcl_normalized_residual",
    "cgg_f",
    "cgd_f",
    "cgs_f",
    "cgg_per_width_f_per_m",
    "cgd_per_width_f_per_m",
    "cgg_density_f_per_m2",
    "cgd_over_cgg",
    "qg_intrinsic_c",
    "qg_intrinsic_per_width_c_per_m",
    "qg_intrinsic_per_current_c_per_a",
    "normalization_basis",
    "variation_origin",
    "variation_mode",
    "source_identity_id",
    "raw_dc_file",
    "raw_y_file",
    "raw_charge_file",
)


class MixedVoltageComparisonError(RuntimeError):
    """A mixed-voltage comparison input, execution, or check failed."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _hash_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise MixedVoltageComparisonError(f"cannot load {path}: {error}") from error


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MixedVoltageComparisonError(message)


def _load_configuration(root: Path) -> dict[str, Any]:
    path = root / CONFIGURATION_PATH
    configuration = _load_toml(path)
    contract = _load_toml(root / RELEASE_CONTRACT_PATH)
    _require(
        configuration.get("schema") == "apm.mixed-voltage-comparison-input.v1",
        "mixed-voltage comparison input schema mismatch",
    )
    _require(
        configuration.get("state") == "FROZEN_AFTER_GRID_REFINEMENT",
        "mixed-voltage comparison input is not frozen after grid refinement",
    )
    _require(
        configuration.get("technology_id") == "apm045"
        and configuration.get("comparison_set_id") == "mixed_voltage",
        "mixed-voltage comparison identity mismatch",
    )
    required_views = set(contract["mixed_voltage_comparison"]["required_views"])
    configured_views = {item["id"] for item in configuration.get("view", [])}
    _require(
        configured_views | {"equal_inversion"} == required_views,
        "mixed-voltage comparison view coverage differs from the v4 release contract",
    )
    _require(
        tuple(float(item) for item in configuration["gmid_targets_per_v"])
        == tuple(
            float(item)
            for item in contract["mixed_voltage_comparison"][
                "required_equal_inversion_targets_per_v"
            ]
        ),
        "mixed-voltage gm/Id targets differ from the v4 release contract",
    )
    _require(
        int(configuration["sweep_points"]) >= 101
        and int(configuration["sweep_points"]) % 2 == 1,
        "comparison sweep_points must be an odd integer of at least 101",
    )
    _require(
        int(configuration["charge_trajectory_points"]) >= 21,
        "charge trajectory requires at least 21 points",
    )
    refinement = configuration.get("development_refinement", {})
    _require(
        refinement.get("initial_sweep_points") == 201
        and refinement.get("selected_sweep_points") == configuration["sweep_points"]
        and refinement.get("acceptance_threshold_changed") is False
        and float(refinement.get("fixed_acceptance_maximum", math.nan))
        == float(configuration["finite_difference_relative_max"]),
        "mixed-voltage comparison grid-refinement record is incomplete",
    )
    boundary = configuration.get("claim_boundary", {})
    for field, expected in (
        ("device_level_only", True),
        ("foundry_correlated", False),
        ("silicon_calibrated", False),
        ("reliability_qualified", False),
        ("layout_dependent_charge", False),
        ("process_noise_calibrated", False),
        ("real_spectre_qualified", False),
        ("forced_gm_over_gds_order", False),
        ("forced_noise_order", False),
        ("forced_leakage_order", False),
        ("forced_total_gate_charge_order", False),
    ):
        _require(boundary.get(field) is expected, f"claim-boundary field {field} drifted")
    evidence_path = (root / configuration["qualification_evidence"]).resolve()
    _require(evidence_path.is_file(), "mixed-voltage qualification evidence is missing")
    _require(
        sha256_file(evidence_path) == configuration["qualification_evidence_sha256"],
        "mixed-voltage qualification evidence hash mismatch",
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    _require(
        evidence.get("status") == "validated",
        "mixed-voltage qualification did not pass",
    )
    configuration["identity"] = {
        "path": str(CONFIGURATION_PATH),
        "sha256": sha256_file(path),
        "release_contract_path": str(RELEASE_CONTRACT_PATH),
        "release_contract_sha256": sha256_file(root / RELEASE_CONTRACT_PATH),
        "qualification_evidence_path": configuration["qualification_evidence"],
        "qualification_evidence_sha256": configuration[
            "qualification_evidence_sha256"
        ],
    }
    configuration["qualification"] = evidence
    return configuration


def _source_identities(
    root: Path, families: list[FamilySpec], configuration: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    selected_cards = configuration["qualification"]["canonical_selection"]
    identities: dict[str, dict[str, Any]] = {}
    for family in families:
        binding = family.backend("ngspice")
        files = [
            family.manifest_path,
            family.provenance_path,
            binding.manifest_path,
            binding.wrapper_path,
            *binding.model_source_files(),
        ]
        artifacts = [
            {
                "path": str(path.relative_to(root)),
                "sha256": sha256_file(path),
            }
            for path in files
        ]
        payload = {
            "selector": family.selector,
            "origin": family.origin,
            "compact_model": family.compact_model,
            "artifacts": artifacts,
        }
        if family.family_id in {"io18", "io25"}:
            selection = selected_cards[family.family_id]
            expected = {
                selection["n_card_sha256"],
                selection["p_card_sha256"],
            }
            actual = {sha256_file(path) for path in binding.model_source_files()}
            _require(
                actual == expected,
                f"{family.selector}: shipped card bytes differ from sealed canonical selection",
            )
            payload["sealed_canonical_selection"] = {
                "selected_seed": selection["selected_seed"],
                "n_card_sha256": selection["n_card_sha256"],
                "p_card_sha256": selection["p_card_sha256"],
            }
        identity_id = _hash_value(payload)
        identities[family.selector] = {"source_identity_id": identity_id, **payload}
    return identities


def _geometry_for_view(
    family: FamilySpec,
    polarity: str,
    view: dict[str, Any],
    width_m: float,
) -> PlanarGeometry:
    device = family.device_for_polarity(polarity)
    _require(device.geometry_kind == "planar", f"{device.selector}: expected planar geometry")
    if view["geometry"] == "equal_physical_l":
        length = float(view["l_m"])
    elif view["geometry"] == "equal_relative_l":
        length = float(view["l_over_lmin"]) * device.lmin_m
    else:
        raise MixedVoltageComparisonError(
            f"{view['id']}: unsupported geometry contract {view['geometry']!r}"
        )
    _require(length >= device.lmin_m, f"{device.selector}: comparison length is below Lfloor")
    if device.lmax_m is not None:
        _require(length <= device.lmax_m, f"{device.selector}: comparison length exceeds Lmax")
    if device.wmin_m is not None:
        _require(width_m >= device.wmin_m, f"{device.selector}: comparison width is below Wfloor")
    if device.wmax_m is not None:
        _require(width_m <= device.wmax_m, f"{device.selector}: comparison width exceeds Wmax")
    return PlanarGeometry(l_m=length, w_m=width_m)


def _finite_positive_metric(row: dict[str, Any]) -> bool:
    fields = (
        "idmag_a",
        "gm_s",
        "gds_s",
        "gm_over_id_per_v",
        "gm_over_gds",
    )
    return all(math.isfinite(float(row[field])) and float(row[field]) > 0.0 for field in fields)


def _solve_target(
    metrics: list[dict[str, Any]],
    target: float,
    *,
    kit: PlanarKit,
    geometry: PlanarGeometry,
    configuration: dict[str, Any],
) -> dict[str, Any]:
    criterion = kit.threshold_coefficient_a * geometry.w_m / geometry.l_m
    current_floor = max(
        float(configuration["absolute_current_floor_a"]),
        float(configuration["threshold_relative_current_floor"]) * criterion,
    )
    lower = float(configuration["qualified_vctrl_fraction_min"])
    upper = float(configuration["qualified_vctrl_fraction_max"])
    qualified = [
        row
        for row in metrics
        if _finite_positive_metric(row)
        and float(row["idmag_a"]) >= current_floor
        and lower <= float(row["vctrl_v"]) / kit.vdd_v <= upper
    ]
    if not qualified:
        return {
            "state": "target_not_reachable",
            "target_per_v": target,
            "reason": "no_qualified_control_region",
        }
    nearest = min(qualified, key=lambda row: abs(float(row["gm_over_id_per_v"]) - target))
    relative_error = abs(float(nearest["gm_over_id_per_v"]) / target - 1.0)
    if relative_error > float(configuration["gmid_target_relative_tolerance_max"]):
        return {
            "state": "target_not_reachable",
            "target_per_v": target,
            "reason": "target_outside_qualified_grid_tolerance",
            "qualified_gmid_min_per_v": min(float(row["gm_over_id_per_v"]) for row in qualified),
            "qualified_gmid_max_per_v": max(float(row["gm_over_id_per_v"]) for row in qualified),
            "nearest_relative_error": relative_error,
        }
    return {
        "state": "validated",
        "target_per_v": target,
        "relative_error": relative_error,
        "metric": nearest,
        "solver": "nearest_qualified_characterization_grid_point",
        "current_floor_a": current_floor,
    }


def _normalized_y_residual(record: dict[str, Any]) -> float:
    real = record["y_real_s"]
    imag = record["y_imag_s"]
    scale = max(
        math.hypot(float(real[row][column]), float(imag[row][column]))
        for row in range(4)
        for column in range(4)
    )
    return max(float(value) for value in record["kcl_column_sum_abs_s"]) / max(
        scale, 1.0e-30
    )


def _gate_charge_job(
    kit: PlanarKit,
    toolchain: Toolchain,
    output: Path,
    polarity: str,
    geometry: PlanarGeometry,
    points: list[dict[str, Any]],
    *,
    frequency_hz: float,
    trajectory_points: int,
    token: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not points:
        return {}, {}
    sign = 1.0 if polarity == "n" else -1.0
    netlist = output / "netlists" / f"charge_{token}.cir"
    log = output / "logs" / f"charge_{token}.log"
    raw = output / "raw" / f"charge_{token}.dat"
    lines = [
        "APM v4 mixed-voltage intrinsic terminal gate-charge trajectories",
        *kit.model_directives(),
        f'.include "{kit.wrapper_file}"',
        f".options gmin={NGSPICE_GMIN_S:.12g}",
        f".temp {int(points[0]['temperature_c'])}",
    ]
    vectors: list[str] = []
    trajectories: list[tuple[str, list[float]]] = []
    serial = 0
    for point in points:
        values = [
            float(point["vctrl_v"]) * index / (trajectory_points - 1)
            for index in range(trajectory_points)
        ]
        trajectories.append((str(point["point_id"]), values))
        for vctrl in values:
            lines.extend(
                [
                    f"Vd{serial} d{serial} 0 {sign * float(point['vout_v']):.12g} AC 0",
                    f"Vg{serial} g{serial} 0 {sign * vctrl:.12g} AC 1",
                    f"Vs{serial} s{serial} 0 0 AC 0",
                    f"Vb{serial} b{serial} 0 0 AC 0",
                    (
                        f"Xq{serial} d{serial} g{serial} s{serial} b{serial} "
                        f"{kit.public_devices[polarity]} {geometry.netlist_parameters()}"
                    ),
                ]
            )
            vectors.append(f"i(Vg{serial})")
            serial += 1
    lines.extend(
        [
            ".control",
            *[f"pre_osdi {toolchain.osdi_directory / item}" for item in kit.osdi_artifacts],
            "set wr_vecnames",
            "set wr_singlescale",
            f"ac lin 1 {frequency_hz:.12g} {frequency_hz:.12g}",
            f"wrdata {raw} " + " ".join(vectors),
            "quit",
            ".endc",
            ".end",
        ]
    )
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)
    parsed = _read_wrdata(raw, 1 + 2 * len(vectors))
    _require(len(parsed) == 1, "gate-charge trajectory emitted more than one AC row")
    _require(
        math.isclose(parsed[0][0], frequency_hz, rel_tol=1.0e-12),
        "gate-charge trajectory frequency mismatch",
    )
    omega = 2.0 * math.pi * frequency_hz
    cursor = 1
    results: dict[str, dict[str, Any]] = {}
    trajectory_records: list[dict[str, Any]] = []
    for point_id, voltages in trajectories:
        cgg_values: list[float] = []
        for _voltage in voltages:
            ygg = -complex(parsed[0][cursor], parsed[0][cursor + 1])
            cursor += 2
            cgg_values.append(ygg.imag / omega)
        charge = sum(
            0.5
            * (cgg_values[index - 1] + cgg_values[index])
            * (voltages[index] - voltages[index - 1])
            for index in range(1, len(voltages))
        )
        results[point_id] = {
            "qg_intrinsic_c": charge,
            "raw_charge_file": str(raw.relative_to(output)),
        }
        trajectory_records.append(
            {
                "point_id": point_id,
                "frequency_hz": frequency_hz,
                "integration_path": "terminal Cgg integrated from VCTRL=0 at constant VOUT",
                "vctrl_values_v": voltages,
                "cgg_values_f": cgg_values,
                "qg_intrinsic_c": charge,
            }
        )
    _require(cursor == len(parsed[0]), "gate-charge trajectory vector count mismatch")
    return results, {
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "raw": str(raw.relative_to(output)),
        "records": trajectory_records,
    }


def _validated_observation(
    *,
    point_id: str,
    view: dict[str, Any],
    family: FamilySpec,
    kit: PlanarKit,
    geometry: PlanarGeometry,
    polarity: str,
    metric: dict[str, Any],
    raw_point: dict[str, Any],
    target: float | None,
    target_relative_error: float | None,
    y_record: dict[str, Any],
    capacitance: dict[str, Any],
    source_identity_id: str,
) -> dict[str, Any]:
    cgg = float(capacitance["cgg_f"])
    cgd = float(capacitance["cgd_f"])
    return {
        "point_id": point_id,
        "view_id": view["id"],
        "coordinate_kind": "fixed_bias" if target is None else "equal_inversion",
        "technology_id": family.technology_id,
        "family_id": family.family_id,
        "device_id": family.device_for_polarity(polarity).device_id,
        "public_device": family.device_for_polarity(polarity).public_name,
        "polarity": polarity,
        "operating_profile_id": kit.operating_profile_id,
        "reference_vdd_v": kit.vdd_v,
        "metric_basis": view["metric_basis"],
        "temperature_c": int(metric["temperature_c"]),
        "w_m": geometry.w_m,
        "l_m": geometry.l_m,
        "l_over_lmin": float(metric["l_over_lmin"]),
        "target_solver_state": None if target is None else "validated",
        "target_solver_method": (
            None if target is None else "nearest_qualified_characterization_grid_point"
        ),
        "target_solver_reason": None,
        "qualified_gmid_min_per_v": None,
        "qualified_gmid_max_per_v": None,
        "gmid_target_per_v": target,
        "gmid_target_relative_error": target_relative_error,
        "vctrl_v": float(metric["vctrl_v"]),
        "vctrl_over_vdd": float(metric["vctrl_v"]) / kit.vdd_v,
        "vout_v": float(metric["vout_v"]),
        "vout_over_vdd": float(metric["vout_v"]) / kit.vdd_v,
        "raw_vd_source_current_a": float(raw_point["raw_vd_source_current_a"]),
        "raw_drain_current_entering_device_a": float(
            raw_point["raw_drain_current_entering_device_a"]
        ),
        "idmag_a": float(metric["idmag_a"]),
        "id_per_width_a_per_m": float(metric["idmag_a"]) / geometry.w_m,
        "gm_s": float(metric["gm_s"]),
        "gds_s": float(metric["gds_s"]),
        "gm_over_id_per_v": float(metric["gm_over_id_per_v"]),
        "gds_over_id_per_v": float(metric["gds_s"]) / float(metric["idmag_a"]),
        "gm_over_gds": float(metric["gm_over_gds"]),
        "gm_convergence_relative": float(metric["gm_convergence_relative"]),
        "gds_convergence_relative": float(metric["gds_convergence_relative"]),
        "native_gm_relative_error": float(metric["native_gm_relative_error"]),
        "native_gds_relative_error": float(metric["native_gds_relative_error"]),
        "terminal_y_frequency_hz": float(y_record["frequency_hz"]),
        "y_kcl_normalized_residual": _normalized_y_residual(y_record),
        "cgg_f": cgg,
        "cgd_f": cgd,
        "cgs_f": float(capacitance["cgs_f"]),
        "cgg_per_width_f_per_m": cgg / geometry.w_m,
        "cgd_per_width_f_per_m": cgd / geometry.w_m,
        "cgg_density_f_per_m2": cgg / (geometry.w_m * geometry.l_m),
        "cgd_over_cgg": cgd / cgg,
        "qg_intrinsic_c": None,
        "qg_intrinsic_per_width_c_per_m": None,
        "qg_intrinsic_per_current_c_per_a": None,
        "normalization_basis": "planar_drawn_width_and_model_supported_length",
        "variation_origin": "none",
        "variation_mode": "nominal",
        "source_identity_id": source_identity_id,
        "raw_dc_file": raw_point["raw_file"],
        "raw_y_file": y_record["raw_file"],
        "raw_charge_file": None,
    }


def _unreachable_observation(
    *,
    point_id: str,
    view: dict[str, Any],
    family: FamilySpec,
    kit: PlanarKit,
    geometry: PlanarGeometry,
    polarity: str,
    solution: dict[str, Any],
    source_identity_id: str,
) -> dict[str, Any]:
    record = {field: None for field in OBSERVATION_FIELDS}
    record.update(
        {
            "point_id": point_id,
            "view_id": view["id"],
            "coordinate_kind": "equal_inversion",
            "technology_id": family.technology_id,
            "family_id": family.family_id,
            "device_id": family.device_for_polarity(polarity).device_id,
            "public_device": family.device_for_polarity(polarity).public_name,
            "polarity": polarity,
            "operating_profile_id": kit.operating_profile_id,
            "reference_vdd_v": kit.vdd_v,
            "metric_basis": view["metric_basis"],
            "temperature_c": int(solution.get("temperature_c", 27)),
            "w_m": geometry.w_m,
            "l_m": geometry.l_m,
            "l_over_lmin": geometry.l_m / family.device_for_polarity(polarity).lmin_m,
            "target_solver_state": "target_not_reachable",
            "target_solver_method": "nearest_qualified_characterization_grid_point",
            "target_solver_reason": solution.get("reason"),
            "qualified_gmid_min_per_v": solution.get("qualified_gmid_min_per_v"),
            "qualified_gmid_max_per_v": solution.get("qualified_gmid_max_per_v"),
            "gmid_target_per_v": float(solution["target_per_v"]),
            "normalization_basis": "planar_drawn_width_and_model_supported_length",
            "variation_origin": "none",
            "variation_mode": "nominal",
            "source_identity_id": source_identity_id,
        }
    )
    return record


def _relations(observations: list[dict[str, Any]], views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    for view in views:
        family_order = list(view["families"])
        view_rows = [row for row in observations if row["view_id"] == view["id"]]
        coordinates = sorted(
            {
                (row["coordinate_kind"], row["gmid_target_per_v"], row["polarity"])
                for row in view_rows
                if row["target_solver_state"] in {None, "validated"}
            },
            key=lambda item: (item[0], -1.0 if item[1] is None else item[1], item[2]),
        )
        for coordinate_kind, target, polarity in coordinates:
            group = [
                row
                for row in view_rows
                if row["coordinate_kind"] == coordinate_kind
                and row["gmid_target_per_v"] == target
                and row["polarity"] == polarity
                and row["target_solver_state"] in {None, "validated"}
            ]
            by_family = {row["family_id"]: row for row in group}
            for first_id, second_id in zip(family_order, family_order[1:]):
                if first_id not in by_family or second_id not in by_family:
                    continue
                first = by_family[first_id]
                second = by_family[second_id]
                relations.append(
                    {
                        "view_id": view["id"],
                        "coordinate_kind": coordinate_kind,
                        "gmid_target_per_v": target,
                        "polarity": polarity,
                        "first_family": first_id,
                        "second_family": second_id,
                        "current_density_ratio_second_over_first": second[
                            "id_per_width_a_per_m"
                        ]
                        / first["id_per_width_a_per_m"],
                        "cgg_density_ratio_second_over_first": second[
                            "cgg_density_f_per_m2"
                        ]
                        / first["cgg_density_f_per_m2"],
                        "gm_over_gds_ratio_second_over_first": second["gm_over_gds"]
                        / first["gm_over_gds"],
                        "qg_per_current_ratio_second_over_first": second[
                            "qg_intrinsic_per_current_c_per_a"
                        ]
                        / first["qg_intrinsic_per_current_c_per_a"],
                        "ordering_claim": None,
                    }
                )
    return relations


def _artifact_inventory(output: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(output)),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "report.json"
    ]


def _write_observations(path: Path, observations: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OBSERVATION_FIELDS))
        writer.writeheader()
        writer.writerows(observations)


def compare_mixed_voltage(
    output_directory: Path,
    toolchain: Toolchain | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Execute all frozen v4 APM045 mixed-voltage comparison views."""

    selected = toolchain or resolve_toolchain(root or repository_root())
    resolved_root = selected.root.resolve()
    output = output_directory.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise MixedVoltageComparisonError(f"refusing to overwrite non-empty directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    configuration = _load_configuration(resolved_root)
    catalog = load_catalog(resolved_root)
    technology = catalog.technology("apm045")
    comparison_set = technology.comparison_set("mixed_voltage")
    _require(comparison_set.kind == "mixed_voltage", "catalog comparison-set kind mismatch")
    _require(
        comparison_set.members == ("vtg", "io18", "io25"),
        "catalog mixed-voltage membership mismatch",
    )
    families = [technology.family(item) for item in comparison_set.members]
    sources = _source_identities(resolved_root, families, configuration)
    views = list(configuration["view"])
    observations: list[dict[str, Any]] = []
    y_records: list[dict[str, Any]] = []
    charge_batches: list[dict[str, Any]] = []

    for view in views:
        for family_id in view["families"]:
            family = technology.family(family_id)
            profile_id = view["profiles"][family_id]
            family.operating_profile(profile_id)
            base_kit = load_family(family.selector, resolved_root, profile_id)
            _require(isinstance(base_kit, PlanarKit), f"{family.selector}: expected planar kit")
            kit = replace(
                base_kit,
                idvg_points=int(configuration["sweep_points"]),
                y_frequencies_hz=(float(configuration["terminal_y_frequency_hz"]),),
            )
            if kit.osdi_artifacts:
                build_models(selected, force=False)
            for polarity in kit.polarities:
                geometry = _geometry_for_view(
                    family, polarity, view, float(configuration["width_m"])
                )
                run_root = output / "raw_views" / view["id"] / family_id / polarity
                for child in ("raw", "netlists", "logs"):
                    (run_root / child).mkdir(parents=True, exist_ok=True)
                _idvg, _idvd, curves = _dc_job(
                    kit,
                    selected,
                    run_root,
                    int(configuration["temperature_c"]),
                    polarity,
                    geometry,
                )
                metrics = _derive_operating_metrics(
                    kit,
                    int(configuration["temperature_c"]),
                    polarity,
                    geometry,
                    curves,
                )
                fixed_target = float(configuration["fixed_vctrl_fraction_vdd"]) * kit.vdd_v
                selected_points: list[tuple[str, dict[str, Any], float | None, float | None]] = []
                fixed = min(metrics, key=lambda row: abs(float(row["vctrl_v"]) - fixed_target))
                selected_points.append(("fixed", fixed, None, None))
                solutions: list[tuple[float, dict[str, Any]]] = []
                for target in configuration["gmid_targets_per_v"]:
                    target_value = float(target)
                    solution = _solve_target(
                        metrics,
                        target_value,
                        kit=kit,
                        geometry=geometry,
                        configuration=configuration,
                    )
                    solution["temperature_c"] = int(configuration["temperature_c"])
                    solutions.append((target_value, solution))
                    if solution["state"] == "validated":
                        selected_points.append(
                            (
                                f"gmid_{target_value:g}",
                                solution["metric"],
                                target_value,
                                float(solution["relative_error"]),
                            )
                        )

                validated_for_charge: list[dict[str, Any]] = []
                by_target: dict[float, dict[str, Any]] = {}
                for point_tag, metric, target, target_error in selected_points:
                    point_id = f"{view['id']}:{family_id}:{polarity}:{point_tag}"
                    bias_mode = (
                        f"mixed_{view['id']}_{polarity}_{point_tag}".replace(".", "p")
                    )
                    current_curve = curves[("idvg", 0.5 * kit.vdd_v)]
                    raw_point = min(
                        current_curve,
                        key=lambda row: abs(float(row["vctrl_v"]) - float(metric["vctrl_v"])),
                    )
                    raw_point = {
                        **raw_point,
                        "raw_file": str(
                            (run_root / raw_point["raw_file"]).relative_to(output)
                        ),
                    }
                    y = _y_job(
                        kit,
                        selected,
                        run_root,
                        int(configuration["temperature_c"]),
                        polarity,
                        geometry,
                        bias_mode=bias_mode,
                        vctrl=float(metric["vctrl_v"]),
                        vout=float(metric["vout_v"]),
                    )
                    for item in y:
                        item["raw_file"] = str(
                            (run_root / item["raw_file"]).relative_to(output)
                        )
                    y_records.extend(y)
                    capacitance = _capacitance_rows(y)[0]
                    record = _validated_observation(
                        point_id=point_id,
                        view=view,
                        family=family,
                        kit=kit,
                        geometry=geometry,
                        polarity=polarity,
                        metric=metric,
                        raw_point=raw_point,
                        target=target,
                        target_relative_error=target_error,
                        y_record=y[0],
                        capacitance=capacitance,
                        source_identity_id=sources[family.selector]["source_identity_id"],
                    )
                    observations.append(record)
                    validated_for_charge.append(record)
                    if target is not None:
                        by_target[target] = record

                for target, solution in solutions:
                    if solution["state"] == "target_not_reachable":
                        point_id = f"{view['id']}:{family_id}:{polarity}:gmid_{target:g}"
                        observations.append(
                            _unreachable_observation(
                                point_id=point_id,
                                view=view,
                                family=family,
                                kit=kit,
                                geometry=geometry,
                                polarity=polarity,
                                solution=solution,
                                source_identity_id=sources[family.selector][
                                    "source_identity_id"
                                ],
                            )
                        )
                    elif target not in by_target:
                        raise MixedVoltageComparisonError(
                            f"{view['id']}/{family_id}/{polarity}: validated target was lost"
                        )

                charge, charge_batch = _gate_charge_job(
                    kit,
                    selected,
                    run_root,
                    polarity,
                    geometry,
                    validated_for_charge,
                    frequency_hz=float(configuration["terminal_y_frequency_hz"]),
                    trajectory_points=int(configuration["charge_trajectory_points"]),
                    token=f"{view['id']}_{family_id}_{polarity}",
                )
                for measured in charge.values():
                    measured["raw_charge_file"] = str(
                        (run_root / measured["raw_charge_file"]).relative_to(output)
                    )
                for field in ("netlist", "log", "raw"):
                    charge_batch[field] = str(
                        (run_root / charge_batch[field]).relative_to(output)
                    )
                charge_batch.update(
                    {
                        "view_id": view["id"],
                        "family_id": family_id,
                        "polarity": polarity,
                    }
                )
                charge_batches.append(charge_batch)
                for record in validated_for_charge:
                    measured = charge[record["point_id"]]
                    qg = float(measured["qg_intrinsic_c"])
                    record["qg_intrinsic_c"] = qg
                    record["qg_intrinsic_per_width_c_per_m"] = qg / float(record["w_m"])
                    record["qg_intrinsic_per_current_c_per_a"] = qg / float(record["idmag_a"])
                    record["raw_charge_file"] = measured["raw_charge_file"]

    required_views = set(
        _load_toml(resolved_root / RELEASE_CONTRACT_PATH)["mixed_voltage_comparison"][
            "required_views"
        ]
    )
    observed_views = {row["view_id"] for row in observations}
    target_rows = [row for row in observations if row["coordinate_kind"] == "equal_inversion"]
    validated = [
        row
        for row in observations
        if row["target_solver_state"] in {None, "validated"}
    ]
    target_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in target_rows:
        target_groups.setdefault(
            (row["view_id"], row["family_id"], row["polarity"]), []
        ).append(row)
    numerical_fields = (
        "idmag_a",
        "gm_s",
        "gds_s",
        "gm_over_id_per_v",
        "gds_over_id_per_v",
        "gm_over_gds",
        "cgg_f",
        "cgd_f",
        "cgs_f",
        "cgg_per_width_f_per_m",
        "cgd_per_width_f_per_m",
        "cgg_density_f_per_m2",
        "cgd_over_cgg",
        "qg_intrinsic_c",
        "qg_intrinsic_per_width_c_per_m",
        "qg_intrinsic_per_current_c_per_a",
    )
    common_physical = [
        row
        for row in validated
        if row["view_id"] == "common_1v0_equal_physical_l"
        and row["coordinate_kind"] == "fixed_bias"
    ]
    structural_order = []
    for polarity in ("n", "p"):
        by_family = {
            row["family_id"]: row
            for row in common_physical
            if row["polarity"] == polarity
        }
        structural_order.append(
            set(by_family) == {"vtg", "io18", "io25"}
            and by_family["vtg"]["cgg_density_f_per_m2"]
            > by_family["io18"]["cgg_density_f_per_m2"]
            > by_family["io25"]["cgg_density_f_per_m2"]
        )
    requirements = {
        "all_required_views": observed_views | {"equal_inversion"} == required_views,
        "fixed_bias_coverage": sum(
            row["coordinate_kind"] == "fixed_bias" for row in observations
        )
        == sum(len(view["families"]) * 2 for view in views),
        "target_solver_states_explicit": bool(target_rows)
        and all(row["target_solver_state"] in ALLOWED_TARGET_STATES for row in target_rows),
        "equal_inversion_target_coverage": len(target_groups)
        == sum(len(view["families"]) * 2 for view in views)
        and all(
            {float(row["gmid_target_per_v"]) for row in group}
            == {float(value) for value in configuration["gmid_targets_per_v"]}
            for group in target_groups.values()
        ),
        "minimum_reachable_equal_inversion_targets": bool(target_groups)
        and all(
            sum(row["target_solver_state"] == "validated" for row in group)
            >= int(configuration["minimum_reachable_targets_per_family_polarity_view"])
            for group in target_groups.values()
        ),
        "equal_inversion_target_accuracy": all(
            float(row["gmid_target_relative_error"])
            <= float(configuration["gmid_target_relative_tolerance_max"])
            for row in target_rows
            if row["target_solver_state"] == "validated"
        ),
        "finite_positive_terminal_and_charge_metrics": bool(validated)
        and all(
            row[field] is not None
            and math.isfinite(float(row[field]))
            and float(row[field]) > 0.0
            for row in validated
            for field in numerical_fields
        ),
        "finite_difference_convergence": all(
            float(row["gm_convergence_relative"])
            <= float(configuration["finite_difference_relative_max"])
            and float(row["gds_convergence_relative"])
            <= float(configuration["finite_difference_relative_max"])
            for row in validated
        ),
        "native_oracle_diagnostic_agreement": all(
            float(row["native_gm_relative_error"])
            <= float(configuration["native_oracle_relative_max"])
            and float(row["native_gds_relative_error"])
            <= float(configuration["native_oracle_relative_max"])
            for row in validated
        ),
        "raw_signed_current_convention": all(
            math.isclose(
                float(row["raw_vd_source_current_a"]),
                -float(row["raw_drain_current_entering_device_a"]),
                rel_tol=1.0e-12,
                abs_tol=1.0e-18,
            )
            for row in validated
        ),
        "terminal_y_kcl": all(
            float(row["y_kcl_normalized_residual"])
            <= float(configuration["y_kcl_normalized_residual_max"])
            for row in validated
        ),
        "common_1v0_capacitance_density_order": bool(structural_order)
        and all(structural_order),
        "source_identity_and_raw_artifacts": all(
            row["source_identity_id"]
            == sources[f"apm045/{row['family_id']}"]["source_identity_id"]
            and all(
                (output / str(row[field])).is_file()
                for field in ("raw_dc_file", "raw_y_file", "raw_charge_file")
            )
            for row in validated
        ),
        "metric_basis_and_normalization_explicit": all(
            bool(row["metric_basis"])
            and row["normalization_basis"]
            == "planar_drawn_width_and_model_supported_length"
            for row in observations
        ),
        "nominal_not_process_variation": all(
            row["variation_origin"] == "none" and row["variation_mode"] == "nominal"
            for row in observations
        ),
        "claim_boundary_preserved": configuration["claim_boundary"]
        == {
            "device_level_only": True,
            "foundry_correlated": False,
            "silicon_calibrated": False,
            "reliability_qualified": False,
            "layout_dependent_charge": False,
            "process_noise_calibrated": False,
            "real_spectre_qualified": False,
            "forced_gm_over_gds_order": False,
            "forced_noise_order": False,
            "forced_leakage_order": False,
            "forced_total_gate_charge_order": False,
        },
    }
    checks = {
        "criteria": {
            key: configuration[key]
            for key in (
                "gmid_target_relative_tolerance_max",
                "finite_difference_relative_max",
                "native_oracle_relative_max",
                "y_kcl_normalized_residual_max",
                "minimum_reachable_targets_per_family_polarity_view",
            )
        },
        "summary": {
            "observation_count": len(observations),
            "validated_observation_count": len(validated),
            "target_state_counts": {
                state: sum(row["target_solver_state"] == state for row in target_rows)
                for state in sorted(ALLOWED_TARGET_STATES)
            },
            "maximum_gm_convergence_relative": max(
                float(row["gm_convergence_relative"]) for row in validated
            ),
            "maximum_gds_convergence_relative": max(
                float(row["gds_convergence_relative"]) for row in validated
            ),
            "maximum_native_gm_relative_error": max(
                float(row["native_gm_relative_error"]) for row in validated
            ),
            "maximum_native_gds_relative_error": max(
                float(row["native_gds_relative_error"]) for row in validated
            ),
            "maximum_y_kcl_normalized_residual": max(
                float(row["y_kcl_normalized_residual"]) for row in validated
            ),
        },
        "requirements": requirements,
        "overall_pass": all(requirements.values()),
    }
    relations = _relations(observations, views)
    observations_path = output / "observations.csv"
    y_path = output / "terminal_y.json"
    charge_path = output / "charge_trajectories.json"
    _write_observations(observations_path, observations)
    y_path.write_text(json.dumps(y_records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    charge_path.write_text(
        json.dumps(charge_batches, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    version = run_checked([selected.ngspice, "--version"])
    tool_identity = {
        "path": str(selected.ngspice),
        "sha256": sha256_file(selected.ngspice),
        "version_output": (version.stdout + version.stderr).strip(),
        "required_major": 47,
    }
    report = {
        "schema": COMPARISON_SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if checks["overall_pass"] else "fail",
        "completion_state": (
            "MIXED_VOLTAGE_COMPARISON_QUALIFIED"
            if checks["overall_pass"]
            else "MIXED_VOLTAGE_COMPARISON_FAILED"
        ),
        "technology_id": "apm045",
        "comparison_set": {
            "id": comparison_set.set_id,
            "kind": comparison_set.kind,
            "members": list(comparison_set.members),
            "anchor": comparison_set.anchor,
        },
        "configuration": configuration["identity"],
        "tool_identity": tool_identity,
        "source_identities": sources,
        "views": views,
        "metric_scope": {
            "terminal_metrics_only": True,
            "native_profile_family_metrics_mixed_into_common_views": False,
            "intrinsic_charge_path": (
                "terminal Cgg integrated from VCTRL=0 at constant VOUT; "
                "no layout-dependent parasitics"
            ),
        },
        "claim_boundary": configuration["claim_boundary"],
        "observations": {
            "path": str(observations_path.relative_to(output)),
            "sha256": sha256_file(observations_path),
            "row_count": len(observations),
        },
        "terminal_y": {
            "path": str(y_path.relative_to(output)),
            "sha256": sha256_file(y_path),
            "record_count": len(y_records),
        },
        "charge_trajectories": {
            "path": str(charge_path.relative_to(output)),
            "sha256": sha256_file(charge_path),
            "batch_count": len(charge_batches),
        },
        "relations": relations,
        "checks": checks,
        "artifact_inventory": _artifact_inventory(output),
    }
    report_path = output / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    report["output_directory"] = str(output)
    report["report_path"] = str(report_path)
    if not checks["overall_pass"]:
        failed = [name for name, passed in requirements.items() if not passed]
        raise MixedVoltageComparisonError(
            f"mixed-voltage comparison checks failed: {failed}; see {report_path}"
        )
    return report
