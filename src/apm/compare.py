# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Catalog-driven APM v2 family and cross-technology comparisons."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .catalog import Catalog, ComparisonSet, FamilySpec, load_catalog
from .characterize import characterize, characterize_bias_view
from .model_build import sha256_file
from .toolchain import Toolchain, resolve_toolchain, run_checked

REQUIRED_TECHNOLOGIES = ("apm350", "apm130", "apm045", "apm022", "apm016f")
REQUIRED_TEMPERATURES_C = (-40, 27, 85, 125)
COMPARISON_TEMPERATURE_C = 27
COMPARISON_L_OVER_LMIN = 2.0
COMPARISON_VOUT_OVER_VDD = 0.5
COMPARISON_VCTRL_OVER_VDD = 0.5
COMPARISON_GM_OVER_ID_PER_V = 15.0
COMPARISON_NORMALIZED_BIAS_TOLERANCE = 0.005

REQUIRED_RESULT_FILES = (
    "metadata.json",
    "idvg.csv",
    "idvd.csv",
    "derived.csv",
    "dibl.csv",
    "family_metrics.csv",
    "y_matrix.json",
    "capacitance.csv",
    "length_scaling.csv",
)

COMPARISON_FIELDS = (
    "technology_id",
    "family_id",
    "device_id",
    "public_device",
    "polarity",
    "comparison_kind",
    "comparison_set_id",
    "operating_profile_id",
    "operating_profile_origin",
    "operating_profile_evidence",
    "reference_vdd_v",
    "terminal_metric_profile_id",
    "family_metric_profile_id",
    "family_metric_reference_vdd_v",
    "metric_basis_note",
    "architecture",
    "compact_model",
    "model_origin",
    "gate_stack_id",
    "gate_stack_class",
    "threshold_class",
    "temperature_c",
    "w_m",
    "nfin",
    "l_m",
    "l_over_lmin",
    "bias_mode",
    "vctrl_v",
    "vctrl_over_vdd",
    "vout_v",
    "vout_over_vdd",
    "idmag_a",
    "gm_s",
    "gds_s",
    "gm_over_id_per_v",
    "gm_over_gds",
    "normalization_basis",
    "normalized_unit",
    "id_normalized",
    "gm_normalized",
    "vth_high_magnitude_v",
    "dibl_v_per_v",
    "ion_a",
    "ioff_a",
    "ion_normalized",
    "ioff_normalized",
    "log10_ion_over_ioff",
    "ss_v_per_decade",
    "ss_r_squared",
    "capacitance_bias_mode",
    "capacitance_frequency_hz",
    "cgg_f",
    "cgd_f",
    "cgs_f",
    "cgg_normalized",
    "cgd_normalized",
    "cgs_normalized",
    "variation_origin",
    "variation_mode",
    "source_result_directory",
    "source_bias_view_directory",
)


class ComparisonError(RuntimeError):
    """A v2 comparison could not be completed or audited."""


@dataclass
class AuditedResult:
    directory: Path
    family: FamilySpec
    metadata: dict[str, Any]
    tables: dict[str, list[dict[str, str]]]
    y_records: list[dict[str, Any]]
    audit: dict[str, Any]


def _prepare_output(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ComparisonError(f"refusing to overwrite non-empty comparison directory: {output}")
    output.mkdir(parents=True, exist_ok=True)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ComparisonError(f"missing CSV header: {path}")
        rows = list(reader)
    if not rows:
        raise ComparisonError(f"empty result table: {path}")
    return rows


def _float(row: dict[str, Any], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ComparisonError(f"missing or malformed numeric field {field!r}") from error
    if not math.isfinite(value):
        raise ComparisonError(f"non-finite numeric field {field!r}")
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COMPARISON_FIELDS), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _audit_result(directory: Path, family: FamilySpec) -> AuditedResult:
    issues: list[str] = []
    for name in REQUIRED_RESULT_FILES:
        if not (directory / name).is_file():
            issues.append(f"missing required result file {name}")
    if issues:
        return AuditedResult(
            directory, family, {}, {}, [], {"overall_pass": False, "issues": issues}
        )

    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    binding = family.backend("ngspice")
    if metadata.get("schema") != "apm.characterization.v2":
        issues.append("metadata schema is not apm.characterization.v2")
    if metadata.get("status") != "validated":
        issues.append("characterization status is not validated")
    if metadata.get("technology_id") != family.technology_id:
        issues.append("technology identity mismatch")
    if metadata.get("family_id") != family.family_id:
        issues.append("family identity mismatch")
    expected_devices = {device.device_id for device in family.devices}
    if set(metadata.get("device_ids", [])) != expected_devices:
        issues.append("device identity set mismatch")
    if tuple(metadata.get("temperatures_c", ())) != REQUIRED_TEMPERATURES_C:
        issues.append("temperature coverage mismatch")
    if metadata.get("simulator_backend") != "ngspice":
        issues.append("simulator backend is not ngspice")
    semantic = metadata.get("semantic_binding", {})
    expected_semantic = {
        "family_manifest_sha256": family.manifest_sha256,
        "backend_binding_sha256": binding.manifest_sha256,
        "provenance_sha256": family.provenance_sha256,
        "model_origin": family.origin,
        "base_family": family.base_family,
        "variant_method": family.variant_method,
    }
    for key, expected in expected_semantic.items():
        if semantic.get(key) != expected:
            issues.append(f"semantic binding mismatch for {key}")
    if (
        family.variant_generation_sha256 is not None
        and semantic.get("variant_generation_sha256") != family.variant_generation_sha256
    ):
        issues.append("variant-generation binding mismatch")
    requirements = metadata.get("checks", {}).get("requirements", {})
    if not requirements or not all(requirements.values()):
        issues.append("one or more characterization requirements failed")

    tables = {
        name: _read_csv(directory / f"{name}.csv")
        for name in (
            "idvg",
            "idvd",
            "derived",
            "dibl",
            "family_metrics",
            "capacitance",
            "length_scaling",
        )
    }
    required_identity = {
        "technology_id",
        "family_id",
        "device_id",
        "public_device",
        "polarity",
        "operating_profile_id",
        "temperature_c",
        "l_m",
        "l_over_lmin",
        "variation_origin",
        "variation_mode",
    }
    for name, rows in tables.items():
        missing = required_identity - set(rows[0])
        if missing:
            issues.append(f"{name}.csv lacks identity fields {sorted(missing)}")
        for row in rows:
            if (
                row.get("technology_id") != family.technology_id
                or row.get("family_id") != family.family_id
            ):
                issues.append(f"{name}.csv family identity mismatch")
                break
            if row.get("device_id") not in expected_devices:
                issues.append(f"{name}.csv device identity mismatch")
                break
            if row.get("variation_origin") != "none" or row.get("variation_mode") != "nominal":
                issues.append(f"{name}.csv variation identity mismatch")
                break
        if {int(float(row["temperature_c"])) for row in rows} != set(REQUIRED_TEMPERATURES_C):
            issues.append(f"{name}.csv temperature coverage mismatch")

    if {row.get("bias_mode") for row in tables["capacitance"]} != {
        "equal_bias",
        "equal_inversion_gm_over_id_15",
    }:
        issues.append("capacitance table lacks required equal-bias/equal-inversion Y views")
    for name in ("idvg", "idvd"):
        for row in tables[name]:
            raw_source = _float(row, "raw_vd_source_current_a")
            raw_entering = _float(row, "raw_drain_current_entering_device_a")
            if not math.isclose(raw_source, -raw_entering, rel_tol=1e-12, abs_tol=1e-18):
                issues.append(f"{name}.csv signed-current convention mismatch")
                break

    y_records = json.loads((directory / "y_matrix.json").read_text(encoding="utf-8"))
    if not isinstance(y_records, list) or not y_records:
        issues.append("y_matrix.json is not a non-empty record list")
        y_records = []
    else:
        if {record.get("bias_mode") for record in y_records} != {
            "equal_bias",
            "equal_inversion_gm_over_id_15",
        }:
            issues.append("raw Y data lacks required bias modes")
        for record in y_records:
            real = record.get("y_real_s")
            imag = record.get("y_imag_s")
            if record.get("terminal_order") != ["d", "g", "s", "b"] or not (
                isinstance(real, list)
                and isinstance(imag, list)
                and len(real) == len(imag) == 4
                and all(isinstance(row, list) and len(row) == 4 for row in real)
                and all(isinstance(row, list) and len(row) == 4 for row in imag)
            ):
                issues.append("raw Y record is not a full ordered 4x4 complex matrix")
                break

    counts = metadata.get("row_counts", {})
    for name, rows in tables.items():
        if counts.get(name) != len(rows):
            issues.append(f"metadata row-count mismatch for {name}")
    if counts.get("y_matrix") != len(y_records):
        issues.append("metadata row-count mismatch for y_matrix")

    critical = (
        "fatal error",
        "simulation interrupted",
        "no convergence",
        "timestep too small",
        "singular matrix",
        "unknown parameter",
        "unsupported parameter",
    )
    hits: list[dict[str, str]] = []
    logs = sorted((directory / "logs").glob("*.log"))
    for log in logs:
        text = log.read_text(encoding="utf-8", errors="replace").lower()
        for token in critical:
            if token in text:
                hits.append({"log": log.name, "token": token})
    if hits:
        issues.append("simulator logs contain critical diagnostic text")
    hashes = {
        name: sha256_file(directory / name)
        for name in REQUIRED_RESULT_FILES
        if (directory / name).is_file()
    }
    audit = {
        "overall_pass": not issues,
        "issues": issues,
        "selector": family.selector,
        "artifact_sha256": hashes,
        "row_counts": counts,
        "simulator_log_count": len(logs),
        "critical_log_hits": hits,
    }
    return AuditedResult(directory, family, metadata, tables, y_records, audit)


def _geometry_matches(row: dict[str, str], device_id: str) -> bool:
    if row.get("device_id") != device_id:
        return False
    if not math.isclose(
        _float(row, "l_over_lmin"), COMPARISON_L_OVER_LMIN, rel_tol=0.0, abs_tol=1e-12
    ):
        return False
    return "nfin" not in row or int(float(row["nfin"])) == 1


def _same_geometry(first: dict[str, str], second: dict[str, str]) -> bool:
    if first.get("device_id") != second.get("device_id"):
        return False
    if not math.isclose(_float(first, "l_m"), _float(second, "l_m"), abs_tol=1e-18):
        return False
    if "nfin" in first:
        return int(float(first["nfin"])) == int(float(second.get("nfin", "0")))
    return math.isclose(_float(first, "w_m"), _float(second, "w_m"), abs_tol=1e-18)


def _select_one(rows: Iterable[dict[str, str]], description: str) -> dict[str, str]:
    selected = list(rows)
    if len(selected) != 1:
        raise ComparisonError(f"expected one {description} row, found {len(selected)}")
    return selected[0]


def _comparison_rows(
    result: AuditedResult,
    comparison_kind: str,
    comparison_set_id: str | None,
) -> list[dict[str, Any]]:
    family = result.family
    vdd = float(result.metadata["operating_profile"]["reference_vdd_v"])
    profile_id = str(result.metadata["operating_profile"]["id"])
    profile = family.operating_profile(profile_id)
    bias_mode = (
        "equal_inversion_gm_over_id_15"
        if comparison_kind in {"threshold_equal_inversion", "cross_process_anchor"}
        else "equal_bias"
    )
    rows: list[dict[str, Any]] = []
    for device in family.devices:
        derived_candidates = [
            row
            for row in result.tables["derived"]
            if int(float(row["temperature_c"])) == COMPARISON_TEMPERATURE_C
            and _geometry_matches(row, device.device_id)
        ]
        if bias_mode == "equal_inversion_gm_over_id_15":
            derived = min(
                derived_candidates,
                key=lambda row: abs(_float(row, "gm_over_id_per_v") - COMPARISON_GM_OVER_ID_PER_V),
            )
        else:
            derived = min(
                derived_candidates,
                key=lambda row: abs(_float(row, "vctrl_v") / vdd - COMPARISON_VCTRL_OVER_VDD),
            )
        dibl = _select_one(
            (
                row
                for row in result.tables["dibl"]
                if int(float(row["temperature_c"])) == COMPARISON_TEMPERATURE_C
                and _same_geometry(row, derived)
            ),
            f"{family.selector}/{device.device_id} DIBL",
        )
        metrics = _select_one(
            (
                row
                for row in result.tables["family_metrics"]
                if int(float(row["temperature_c"])) == COMPARISON_TEMPERATURE_C
                and _same_geometry(row, derived)
            ),
            f"{family.selector}/{device.device_id} family-metric",
        )
        capacitance_candidates = [
            row
            for row in result.tables["capacitance"]
            if int(float(row["temperature_c"])) == COMPARISON_TEMPERATURE_C
            and row.get("bias_mode") == bias_mode
            and _same_geometry(row, derived)
        ]
        if not capacitance_candidates:
            raise ComparisonError(
                f"{family.selector}/{device.device_id} lacks {bias_mode} capacitance"
            )
        capacitance = min(capacitance_candidates, key=lambda row: _float(row, "frequency_hz"))
        if device.geometry_kind == "planar":
            count = _float(derived, "w_m")
            geometry: dict[str, Any] = {"w_m": count}
            normalization_basis = "planar_drawn_width"
            normalized_unit = "A/m and F/m"
        else:
            count = int(float(derived["nfin"]))
            geometry = {"nfin": count}
            normalization_basis = "fin_count"
            normalized_unit = "A/fin and F/fin"
        rows.append(
            {
                "technology_id": family.technology_id,
                "family_id": family.family_id,
                "device_id": device.device_id,
                "public_device": device.public_name,
                "polarity": device.polarity,
                "comparison_kind": comparison_kind,
                "comparison_set_id": comparison_set_id,
                "operating_profile_id": profile_id,
                "operating_profile_origin": profile.origin,
                "operating_profile_evidence": profile.evidence,
                "reference_vdd_v": vdd,
                "terminal_metric_profile_id": profile_id,
                "family_metric_profile_id": profile_id,
                "family_metric_reference_vdd_v": vdd,
                "metric_basis_note": "all metrics use the native release characterization profile",
                "architecture": family.architecture,
                "compact_model": family.compact_model,
                "model_origin": family.origin,
                "gate_stack_id": family.gate_stack_id,
                "gate_stack_class": family.gate_stack_class,
                "threshold_class": family.threshold_class,
                "temperature_c": COMPARISON_TEMPERATURE_C,
                **geometry,
                "l_m": _float(derived, "l_m"),
                "l_over_lmin": _float(derived, "l_over_lmin"),
                "bias_mode": bias_mode,
                "vctrl_v": _float(derived, "vctrl_v"),
                "vctrl_over_vdd": _float(derived, "vctrl_v") / vdd,
                "vout_v": _float(derived, "vout_v"),
                "vout_over_vdd": _float(derived, "vout_v") / vdd,
                "idmag_a": _float(derived, "idmag_a"),
                "gm_s": _float(derived, "gm_s"),
                "gds_s": _float(derived, "gds_s"),
                "gm_over_id_per_v": _float(derived, "gm_over_id_per_v"),
                "gm_over_gds": _float(derived, "gm_over_gds"),
                "normalization_basis": normalization_basis,
                "normalized_unit": normalized_unit,
                "id_normalized": _float(derived, "idmag_a") / count,
                "gm_normalized": _float(derived, "gm_s") / count,
                "vth_high_magnitude_v": _float(dibl, "vth_high_magnitude_v"),
                "dibl_v_per_v": _float(dibl, "dibl_v_per_v"),
                "ion_a": _float(metrics, "ion_a"),
                "ioff_a": _float(metrics, "ioff_a"),
                "ion_normalized": _float(metrics, "ion_normalized"),
                "ioff_normalized": _float(metrics, "ioff_normalized"),
                "log10_ion_over_ioff": _float(metrics, "log10_ion_over_ioff"),
                "ss_v_per_decade": _float(metrics, "ss_v_per_decade"),
                "ss_r_squared": _float(metrics, "ss_r_squared"),
                "capacitance_bias_mode": bias_mode,
                "capacitance_frequency_hz": _float(capacitance, "frequency_hz"),
                "cgg_f": _float(capacitance, "cgg_f"),
                "cgd_f": _float(capacitance, "cgd_f"),
                "cgs_f": _float(capacitance, "cgs_f"),
                "cgg_normalized": _float(capacitance, "cgg_f") / count,
                "cgd_normalized": _float(capacitance, "cgd_f") / count,
                "cgs_normalized": _float(capacitance, "cgs_f") / count,
                "variation_origin": "none",
                "variation_mode": "nominal",
                "source_result_directory": str(result.directory),
                "source_bias_view_directory": None,
            }
        )
    return rows


def _common_overlap_rows(
    native: AuditedResult,
    bias_view: dict[str, Any],
    comparison_set_id: str,
) -> list[dict[str, Any]]:
    """Join shared-bias terminal metrics to explicitly labelled native family metrics."""

    family = native.family
    if bias_view.get("schema") != "apm.bias-view.v2" or bias_view.get("status") != "validated":
        raise ComparisonError(f"{family.selector}: common-overlap bias view is not validated")
    if (
        bias_view.get("technology_id") != family.technology_id
        or bias_view.get("family_id") != family.family_id
    ):
        raise ComparisonError(f"{family.selector}: common-overlap bias-view identity mismatch")
    semantic = bias_view.get("semantic_binding", {})
    if (
        semantic.get("family_manifest_sha256") != family.manifest_sha256
        or semantic.get("provenance_sha256") != family.provenance_sha256
        or semantic.get("backend_binding_sha256") != family.backend("ngspice").manifest_sha256
    ):
        raise ComparisonError(f"{family.selector}: common-overlap semantic binding mismatch")
    common_profile = bias_view["operating_profile"]
    common_profile_id = str(common_profile["id"])
    common_vdd = float(common_profile["reference_vdd_v"])
    native_profile_id = str(native.metadata["operating_profile"]["id"])
    native_vdd = float(native.metadata["operating_profile"]["reference_vdd_v"])
    rows: list[dict[str, Any]] = []
    for device in family.devices:
        point = _select_one(
            (row for row in bias_view["operating_points"] if row["device_id"] == device.device_id),
            f"{family.selector}/{device.device_id} common-overlap operating point",
        )
        dibl = _select_one(
            (
                row
                for row in native.tables["dibl"]
                if int(float(row["temperature_c"])) == COMPARISON_TEMPERATURE_C
                and _same_geometry(row, point)
            ),
            f"{family.selector}/{device.device_id} native DIBL",
        )
        metrics = _select_one(
            (
                row
                for row in native.tables["family_metrics"]
                if int(float(row["temperature_c"])) == COMPARISON_TEMPERATURE_C
                and _same_geometry(row, point)
            ),
            f"{family.selector}/{device.device_id} native family-metric",
        )
        capacitance = min(
            (
                row
                for row in bias_view["capacitance_rows"]
                if row["device_id"] == device.device_id and _same_geometry(row, point)
            ),
            key=lambda row: float(row["frequency_hz"]),
        )
        if device.geometry_kind == "planar":
            count = float(point["w_m"])
            geometry: dict[str, Any] = {"w_m": count}
            normalization_basis = "planar_drawn_width"
            normalized_unit = "A/m and F/m"
        else:
            count = int(point["nfin"])
            geometry = {"nfin": count}
            normalization_basis = "fin_count"
            normalized_unit = "A/fin and F/fin"
        rows.append(
            {
                "technology_id": family.technology_id,
                "family_id": family.family_id,
                "device_id": device.device_id,
                "public_device": device.public_name,
                "polarity": device.polarity,
                "comparison_kind": "gate_stack_common_overlap",
                "comparison_set_id": comparison_set_id,
                "operating_profile_id": common_profile_id,
                "operating_profile_origin": common_profile["origin"],
                "operating_profile_evidence": common_profile["evidence"],
                "reference_vdd_v": common_vdd,
                "terminal_metric_profile_id": common_profile_id,
                "family_metric_profile_id": native_profile_id,
                "family_metric_reference_vdd_v": native_vdd,
                "metric_basis_note": (
                    "Id/gm/gds/Y/capacitance use the common-overlap bias; "
                    "Vth/DIBL/Ion/Ioff/SS retain the explicitly identified native release profile"
                ),
                "architecture": family.architecture,
                "compact_model": family.compact_model,
                "model_origin": family.origin,
                "gate_stack_id": family.gate_stack_id,
                "gate_stack_class": family.gate_stack_class,
                "threshold_class": family.threshold_class,
                "temperature_c": int(point["temperature_c"]),
                **geometry,
                "l_m": float(point["l_m"]),
                "l_over_lmin": float(point["l_over_lmin"]),
                "bias_mode": "gate_stack_common_overlap",
                "vctrl_v": float(point["vctrl_v"]),
                "vctrl_over_vdd": float(point["resolved_vctrl_over_vdd"]),
                "vout_v": float(point["vout_v"]),
                "vout_over_vdd": float(point["resolved_vout_over_vdd"]),
                "idmag_a": float(point["idmag_a"]),
                "gm_s": float(point["gm_s"]),
                "gds_s": float(point["gds_s"]),
                "gm_over_id_per_v": float(point["gm_over_id_per_v"]),
                "gm_over_gds": float(point["gm_over_gds"]),
                "normalization_basis": normalization_basis,
                "normalized_unit": normalized_unit,
                "id_normalized": float(point["idmag_a"]) / count,
                "gm_normalized": float(point["gm_s"]) / count,
                "vth_high_magnitude_v": _float(dibl, "vth_high_magnitude_v"),
                "dibl_v_per_v": _float(dibl, "dibl_v_per_v"),
                "ion_a": _float(metrics, "ion_a"),
                "ioff_a": _float(metrics, "ioff_a"),
                "ion_normalized": _float(metrics, "ion_normalized"),
                "ioff_normalized": _float(metrics, "ioff_normalized"),
                "log10_ion_over_ioff": _float(metrics, "log10_ion_over_ioff"),
                "ss_v_per_decade": _float(metrics, "ss_v_per_decade"),
                "ss_r_squared": _float(metrics, "ss_r_squared"),
                "capacitance_bias_mode": "gate_stack_common_overlap",
                "capacitance_frequency_hz": float(capacitance["frequency_hz"]),
                "cgg_f": float(capacitance["cgg_f"]),
                "cgd_f": float(capacitance["cgd_f"]),
                "cgs_f": float(capacitance["cgs_f"]),
                "cgg_normalized": float(capacitance["cgg_f"]) / count,
                "cgd_normalized": float(capacitance["cgd_f"]) / count,
                "cgs_normalized": float(capacitance["cgs_f"]) / count,
                "variation_origin": "none",
                "variation_mode": "nominal",
                "source_result_directory": str(native.directory),
                "source_bias_view_directory": str(bias_view["output_directory"]),
            }
        )
    return rows


def _comparison_checks(
    rows: list[dict[str, Any]],
    expected_families: tuple[str, ...],
    comparison_kind: str,
) -> dict[str, Any]:
    positive = (
        "idmag_a",
        "gm_s",
        "gds_s",
        "gm_over_id_per_v",
        "gm_over_gds",
        "id_normalized",
        "gm_normalized",
        "vth_high_magnitude_v",
        "dibl_v_per_v",
        "ion_a",
        "ioff_a",
        "ion_normalized",
        "ioff_normalized",
        "ss_v_per_decade",
        "ss_r_squared",
        "cgg_f",
        "cgd_f",
        "cgs_f",
    )
    actual_families = {f"{row['technology_id']}/{row['family_id']}" for row in rows}
    requirements = {
        "family_coverage": actual_families == set(expected_families),
        "normalized_length": all(
            math.isclose(row["l_over_lmin"], COMPARISON_L_OVER_LMIN, abs_tol=1e-12) for row in rows
        ),
        "normalized_output": all(
            math.isclose(
                row["vout_over_vdd"],
                COMPARISON_VOUT_OVER_VDD,
                abs_tol=COMPARISON_NORMALIZED_BIAS_TOLERANCE,
            )
            for row in rows
        ),
        "finite_positive_metrics": all(
            math.isfinite(row[field]) and row[field] > 0.0 for row in rows for field in positive
        ),
        "basis_is_explicit": all(
            (
                row["architecture"] == "planar_bulk"
                and row["normalization_basis"] == "planar_drawn_width"
            )
            or (row["architecture"] == "finfet" and row["normalization_basis"] == "fin_count")
            for row in rows
        ),
        "nominal_identity": all(
            row["variation_origin"] == "none" and row["variation_mode"] == "nominal" for row in rows
        ),
        "metric_profile_basis_is_explicit": all(
            bool(row["terminal_metric_profile_id"])
            and bool(row["family_metric_profile_id"])
            and bool(row["metric_basis_note"])
            for row in rows
        ),
    }
    if comparison_kind in {"threshold_equal_inversion", "cross_process_anchor"}:
        requirements["equal_inversion_coordinate"] = all(
            abs(row["gm_over_id_per_v"] - COMPARISON_GM_OVER_ID_PER_V) <= 2.0 for row in rows
        )
    else:
        requirements["equal_bias_coordinate"] = all(
            math.isclose(
                row["vctrl_over_vdd"],
                COMPARISON_VCTRL_OVER_VDD,
                abs_tol=COMPARISON_NORMALIZED_BIAS_TOLERANCE,
            )
            for row in rows
        )
    if comparison_kind == "gate_stack_common_overlap":
        requirements["common_terminal_and_native_family_metric_profiles"] = all(
            row["terminal_metric_profile_id"] == row["operating_profile_id"]
            and row["family_metric_profile_id"]
            and row["operating_profile_origin"] == "apm_selected"
            and bool(row["operating_profile_evidence"])
            and bool(row["source_bias_view_directory"])
            for row in rows
        )
    return {
        "criteria": {
            "temperature_c": COMPARISON_TEMPERATURE_C,
            "l_over_lmin": COMPARISON_L_OVER_LMIN,
            "vout_over_vdd": COMPARISON_VOUT_OVER_VDD,
            "equal_bias_vctrl_over_vdd": COMPARISON_VCTRL_OVER_VDD,
            "normalized_bias_absolute_tolerance": COMPARISON_NORMALIZED_BIAS_TOLERANCE,
            "equal_inversion_gm_over_id_per_v": COMPARISON_GM_OVER_ID_PER_V,
            "equal_inversion_absolute_tolerance_per_v": 2.0,
        },
        "requirements": requirements,
        "overall_pass": all(requirements.values()),
    }


def _relations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    kinds = sorted({row["comparison_kind"] for row in rows})
    for kind in kinds:
        kind_rows = [row for row in rows if row["comparison_kind"] == kind]
        selectors = sorted({f"{row['technology_id']}/{row['family_id']}" for row in kind_rows})
        for first_selector, second_selector in zip(selectors, selectors[1:]):
            for polarity in sorted({row["polarity"] for row in kind_rows}):
                first = next(
                    (
                        row
                        for row in kind_rows
                        if f"{row['technology_id']}/{row['family_id']}" == first_selector
                        and row["polarity"] == polarity
                    ),
                    None,
                )
                second = next(
                    (
                        row
                        for row in kind_rows
                        if f"{row['technology_id']}/{row['family_id']}" == second_selector
                        and row["polarity"] == polarity
                    ),
                    None,
                )
                if first is None or second is None:
                    continue
                same_basis = first["normalization_basis"] == second["normalization_basis"]
                relations.append(
                    {
                        "comparison_kind": kind,
                        "polarity": polarity,
                        "first": first_selector,
                        "second": second_selector,
                        "gm_over_gds_ratio_second_over_first": second["gm_over_gds"]
                        / first["gm_over_gds"],
                        "dibl_ratio_second_over_first": second["dibl_v_per_v"]
                        / first["dibl_v_per_v"],
                        "vth_ratio_second_over_first": second["vth_high_magnitude_v"]
                        / first["vth_high_magnitude_v"],
                        "normalized_current_ratio_second_over_first": (
                            second["id_normalized"] / first["id_normalized"] if same_basis else None
                        ),
                        "normalized_capacitance_ratio_second_over_first": (
                            second["cgg_normalized"] / first["cgg_normalized"]
                            if same_basis
                            else None
                        ),
                        "normalization_ratio_status": (
                            "comparable_same_basis"
                            if same_basis
                            else "not_reported_across_per_width_and_per_fin_bases"
                        ),
                    }
                )
    return relations


def _generic_multivt_ordering(
    rows: list[dict[str, Any]], technology_id: str
) -> dict[str, Any] | None:
    if technology_id not in {"apm022", "apm016f"}:
        return None
    failures: list[dict[str, Any]] = []
    for polarity in sorted({row["polarity"] for row in rows}):
        by_family = {
            row["family_id"]: row
            for row in rows
            if row["technology_id"] == technology_id and row["polarity"] == polarity
        }
        if set(by_family) != {"lvt", "svt", "hvt"}:
            failures.append({"polarity": polarity, "reason": "family coverage"})
            continue
        lvt, svt, hvt = (by_family[item] for item in ("lvt", "svt", "hvt"))
        if not (
            lvt["vth_high_magnitude_v"] < svt["vth_high_magnitude_v"] < hvt["vth_high_magnitude_v"]
            and lvt["ion_normalized"] > svt["ion_normalized"] > hvt["ion_normalized"]
            and lvt["ioff_normalized"] > svt["ioff_normalized"] > hvt["ioff_normalized"]
        ):
            failures.append({"polarity": polarity, "reason": "Vth/Ion/Ioff ordering"})
    return {"overall_pass": not failures, "failures": failures}


def _run_results(
    catalog: Catalog,
    selectors: tuple[str, ...],
    output: Path,
    toolchain: Toolchain,
    profile_id: str | None = None,
    label: str = "native",
) -> list[AuditedResult]:
    result_root = output / "characterizations" / label
    audited: list[AuditedResult] = []
    for selector in selectors:
        technology_id, family_id = selector.split("/")
        family = catalog.family(technology_id, family_id)
        directory = result_root / technology_id / family_id
        characterize(
            selector,
            directory,
            toolchain,
            operating_profile_id=profile_id,
        )
        audited.append(_audit_result(directory, family))
    return audited


def _write_report(
    output: Path,
    mode: str,
    rows: list[dict[str, Any]],
    audited: list[AuditedResult],
    checks: dict[str, Any],
    toolchain: Toolchain,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    csv_path = output / "comparison.csv"
    _write_csv(csv_path, rows)
    version = run_checked([toolchain.ngspice, "--version"])
    report: dict[str, Any] = {
        "schema": "apm.comparison.v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "validated" if checks["overall_pass"] else "checks_failed",
        "mode": mode,
        "simulator_backend": "ngspice",
        "simulator_version": (version.stdout + version.stderr).strip(),
        "comparison_path": str(csv_path.relative_to(output)),
        "comparison_sha256": sha256_file(csv_path),
        "comparison_rows": rows,
        "relations": _relations(rows),
        "result_audits": {result.family.selector: result.audit for result in audited},
        "checks": checks,
    }
    if extra:
        report.update(extra)
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["output_directory"] = str(output)
    report["report_path"] = str(report_path)
    if not checks["overall_pass"]:
        raise ComparisonError(f"comparison checks failed; see {report_path}")
    return report


def compare_set(
    technology_id: str,
    set_id: str,
    output_directory: Path,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    selected = toolchain or resolve_toolchain()
    catalog = load_catalog(selected.root)
    technology = catalog.technology(technology_id)
    comparison_set: ComparisonSet = technology.comparison_set(set_id)
    if comparison_set.kind == "mixed_voltage":
        from .mixed_voltage_compare import compare_mixed_voltage

        return compare_mixed_voltage(output_directory, selected)
    selectors = tuple(f"{technology_id}/{family}" for family in comparison_set.members)
    output = output_directory.expanduser().resolve()
    _prepare_output(output)
    audited = _run_results(catalog, selectors, output, selected)
    audits_pass = all(item.audit["overall_pass"] for item in audited)
    rows: list[dict[str, Any]] = []
    view_checks: dict[str, Any] = {}
    if audits_pass and comparison_set.kind == "threshold_family":
        for kind in ("threshold_equal_bias", "threshold_equal_inversion"):
            view_rows = [
                row for result in audited for row in _comparison_rows(result, kind, set_id)
            ]
            rows.extend(view_rows)
            view_checks[kind] = _comparison_checks(view_rows, selectors, kind)
        ordering = _generic_multivt_ordering(
            [row for row in rows if row["comparison_kind"] == "threshold_equal_bias"],
            technology_id,
        )
    elif audits_pass and comparison_set.kind == "gate_stack":
        native_rows = [
            row
            for result in audited
            for row in _comparison_rows(result, "gate_stack_native_profile", set_id)
        ]
        rows.extend(native_rows)
        view_checks["gate_stack_native_profile"] = _comparison_checks(
            native_rows, selectors, "gate_stack_native_profile"
        )
        common_profile = comparison_set.common_overlap_profile
        if not common_profile:
            raise ComparisonError(f"{technology_id}/{set_id} lacks a common-overlap profile")
        bias_views: list[dict[str, Any]] = []
        common_rows: list[dict[str, Any]] = []
        for result in audited:
            bias_view = characterize_bias_view(
                result.family.selector,
                common_profile,
                output
                / "bias_views"
                / common_profile
                / result.family.technology_id
                / result.family.family_id,
                selected,
                temperature_c=COMPARISON_TEMPERATURE_C,
                l_over_lmin=COMPARISON_L_OVER_LMIN,
                vctrl_over_vdd=COMPARISON_VCTRL_OVER_VDD,
                vout_over_vdd=COMPARISON_VOUT_OVER_VDD,
            )
            bias_views.append(bias_view)
            common_rows.extend(_common_overlap_rows(result, bias_view, set_id))
        rows.extend(common_rows)
        common_check = _comparison_checks(common_rows, selectors, "gate_stack_common_overlap")
        common_vdds = {row["reference_vdd_v"] for row in common_rows}
        common_check["requirements"]["explicit_common_profile"] = (
            {row["operating_profile_id"] for row in common_rows} == {common_profile}
            and len(common_vdds) == 1
            and all(view["checks"]["overall_pass"] for view in bias_views)
        )
        common_check["overall_pass"] = all(common_check["requirements"].values())
        view_checks["gate_stack_common_overlap"] = common_check
        ordering = None
    else:
        if comparison_set.kind not in {"threshold_family", "gate_stack"}:
            raise ComparisonError(f"unsupported comparison-set kind {comparison_set.kind!r}")
        ordering = None
    requirements = {
        "all_characterization_audits": audits_pass,
        "all_required_views": bool(view_checks)
        and all(check["overall_pass"] for check in view_checks.values()),
    }
    if ordering is not None:
        requirements["generic_multivt_nominal_ordering"] = ordering["overall_pass"]
    checks = {
        "views": view_checks,
        "generic_multivt_ordering": ordering,
        "requirements": requirements,
        "overall_pass": all(requirements.values()),
    }
    extra: dict[str, Any] = {
        "technology_id": technology_id,
        "comparison_set": {
            "id": comparison_set.set_id,
            "kind": comparison_set.kind,
            "members": list(comparison_set.members),
            "anchor": comparison_set.anchor,
            "common_overlap_profile": comparison_set.common_overlap_profile,
        },
    }
    if comparison_set.kind == "gate_stack" and audits_pass:
        extra["bias_view_audits"] = {
            f"{view['technology_id']}/{view['family_id']}": {
                "schema": view["schema"],
                "status": view["status"],
                "output_directory": view["output_directory"],
                "metadata_sha256": sha256_file(Path(view["metadata_path"])),
                "checks": view["checks"],
            }
            for view in bias_views
        }
    return _write_report(
        output,
        "comparison_set",
        rows,
        audited,
        checks,
        selected,
        extra,
    )


def compare_anchors(
    output_directory: Path,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    selected = toolchain or resolve_toolchain()
    catalog = load_catalog(selected.root)
    selectors = tuple(
        f"{technology.technology_id}/{technology.cross_process_anchor}"
        for technology in catalog.technologies
    )
    output = output_directory.expanduser().resolve()
    _prepare_output(output)
    audited = _run_results(catalog, selectors, output, selected)
    audits_pass = all(item.audit["overall_pass"] for item in audited)
    rows = (
        [
            row
            for result in audited
            for row in _comparison_rows(result, "cross_process_anchor", "anchors")
        ]
        if audits_pass
        else []
    )
    view = _comparison_checks(rows, selectors, "cross_process_anchor")
    requirements = {
        "all_characterization_audits": audits_pass,
        "cross_process_anchor_view": view["overall_pass"],
        "no_cross_basis_ratios": all(
            relation["normalization_ratio_status"] == "comparable_same_basis"
            or (
                relation["normalized_current_ratio_second_over_first"] is None
                and relation["normalized_capacitance_ratio_second_over_first"] is None
            )
            for relation in _relations(rows)
        ),
    }
    checks = {
        "view": view,
        "requirements": requirements,
        "overall_pass": all(requirements.values()),
    }
    return _write_report(
        output,
        "cross_process_anchors",
        rows,
        audited,
        checks,
        selected,
        {"selectors": list(selectors)},
    )


def compare_families(
    selector_a: str,
    selector_b: str,
    output_directory: Path | None = None,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    if selector_a == selector_b:
        raise ComparisonError("comparison requires two distinct family selectors")
    selected = toolchain or resolve_toolchain()
    catalog = load_catalog(selected.root)
    resolved: list[str] = []
    for selector in (selector_a, selector_b):
        parts = selector.strip("/").split("/")
        if len(parts) == 1:
            technology = catalog.technology(parts[0])
            resolved.append(f"{parts[0]}/{technology.cross_process_anchor}")
        elif len(parts) == 2:
            catalog.family(parts[0], parts[1])
            resolved.append(selector)
        else:
            raise ComparisonError("compare selectors must identify a technology or family")
    if resolved[0] == resolved[1]:
        raise ComparisonError("comparison selectors resolve to the same family")
    output = (
        output_directory.expanduser().resolve()
        if output_directory is not None
        else selected.root
        / ".apm"
        / "results"
        / "comparisons"
        / f"{resolved[0].replace('/', '-')}-vs-{resolved[1].replace('/', '-')}"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    _prepare_output(output)
    selectors = tuple(resolved)
    audited = _run_results(catalog, selectors, output, selected)
    audits_pass = all(item.audit["overall_pass"] for item in audited)
    rows: list[dict[str, Any]] = []
    view_checks: dict[str, Any] = {}
    if audits_pass:
        for kind in ("threshold_equal_bias", "threshold_equal_inversion"):
            view_rows = [row for result in audited for row in _comparison_rows(result, kind, None)]
            rows.extend(view_rows)
            view_checks[kind] = _comparison_checks(view_rows, selectors, kind)
    requirements = {
        "all_characterization_audits": audits_pass,
        "equal_bias_and_equal_inversion": len(view_checks) == 2
        and all(item["overall_pass"] for item in view_checks.values()),
    }
    checks = {
        "views": view_checks,
        "requirements": requirements,
        "overall_pass": all(requirements.values()),
    }
    return _write_report(
        output,
        "pairwise",
        rows,
        audited,
        checks,
        selected,
        {"selectors": list(selectors)},
    )


def validate_all_characterizations(
    output_directory: Path,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    selected = toolchain or resolve_toolchain()
    catalog = load_catalog(selected.root)
    selectors = tuple(
        family.selector for technology in catalog.technologies for family in technology.families
    )
    output = output_directory.expanduser().resolve()
    _prepare_output(output)
    audited = _run_results(catalog, selectors, output, selected)
    requirements = {
        "five_technologies": len(catalog.technologies) == 5,
        "fifteen_families": len(selectors) == 15,
        "all_characterization_audits": all(item.audit["overall_pass"] for item in audited),
    }
    checks = {"requirements": requirements, "overall_pass": all(requirements.values())}
    return _write_report(
        output,
        "all_family_characterization",
        [],
        audited,
        checks,
        selected,
        {"selectors": list(selectors)},
    )
