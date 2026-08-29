# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .characterize import FinFETKit, PlanarKit, characterize, load_kit
from .model_build import sha256_file
from .toolchain import Toolchain, resolve_toolchain

REQUIRED_KITS = ("apm350", "apm130", "apm045", "apm022", "apm016f")
REQUIRED_TEMPERATURES_C = (-40, 27, 85, 125)
COMPARISON_L_OVER_LMIN = 2.0
COMPARISON_VOUT_OVER_VDD = 0.5
COMPARISON_GM_OVER_ID_PER_V = 15.0

REQUIRED_RESULT_FILES = (
    "metadata.json",
    "idvg.csv",
    "idvd.csv",
    "derived.csv",
    "dibl.csv",
    "y_matrix.json",
    "capacitance.csv",
    "length_scaling.csv",
)

COMPARISON_FIELDS = (
    "kit_id",
    "public_device",
    "polarity",
    "compact_model",
    "model_revision",
    "architecture",
    "nominal_vdd_v",
    "model_lmin_m",
    "w_m",
    "nfin",
    "l_m",
    "l_over_lmin",
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
    "normalization_count",
    "id_normalized_a_per_unit",
    "gm_normalized_s_per_unit",
    "vth_high_magnitude_v",
    "dibl_v_per_v",
    "capacitance_frequency_hz",
    "cgg_f",
    "cgd_f",
    "cgs_f",
    "cgg_normalized_f_per_unit",
    "cgd_normalized_f_per_unit",
    "cgs_normalized_f_per_unit",
    "variation_origin",
    "variation_mode",
    "source_result_directory",
)


class ComparisonError(RuntimeError):
    """An integrated characterization or normalized comparison failed."""


@dataclass
class AuditedResult:
    directory: Path
    metadata: dict[str, Any]
    tables: dict[str, list[dict[str, str]]]
    y_records: list[dict[str, Any]]
    audit: dict[str, Any]


def _prepare_output(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ComparisonError(f"refusing to overwrite non-empty comparison directory: {output}")
    output.mkdir(parents=True, exist_ok=True)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ComparisonError(f"missing CSV header: {path}")
        rows = list(reader)
    if not rows:
        raise ComparisonError(f"empty result table: {path}")
    return list(reader.fieldnames), rows


def _write_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(COMPARISON_FIELDS),
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def _float(row: dict[str, str], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, ValueError) as error:
        raise ComparisonError(f"missing or malformed numeric field {field!r}") from error
    if not math.isfinite(value):
        raise ComparisonError(f"non-finite numeric field {field!r}")
    return value


def _required_fields() -> dict[str, set[str]]:
    common = {
        "kit_id",
        "public_device",
        "polarity",
        "temperature_c",
        "l_m",
        "l_over_lmin",
        "variation_origin",
        "variation_mode",
    }
    return {
        "idvg": common
        | {
            "compact_model",
            "vctrl_v",
            "vout_v",
            "raw_vgs_v",
            "raw_vds_v",
            "raw_vd_source_current_a",
            "raw_drain_current_entering_device_a",
            "idmag_a",
        },
        "idvd": common
        | {
            "compact_model",
            "vctrl_v",
            "vout_v",
            "raw_vgs_v",
            "raw_vds_v",
            "raw_vd_source_current_a",
            "raw_drain_current_entering_device_a",
            "idmag_a",
        },
        "derived": common
        | {
            "compact_model",
            "vctrl_v",
            "vout_v",
            "idmag_a",
            "gm_s",
            "gm_second_step_s",
            "gm_step_v",
            "gm_second_step_v",
            "gm_convergence_relative",
            "gds_s",
            "gds_second_step_s",
            "gds_step_v",
            "gds_second_step_v",
            "gds_convergence_relative",
            "gm_over_id_per_v",
            "gm_over_gds",
            "native_gm_s",
            "native_gds_s",
        },
        "dibl": common
        | {
            "criterion_a",
            "criterion_coefficient_a",
            "criterion_normalization",
            "vout_low_v",
            "vout_high_v",
            "vth_low_magnitude_v",
            "vth_high_magnitude_v",
            "dibl_v_per_v",
        },
        "capacitance": common
        | {
            "vctrl_v",
            "vout_v",
            "frequency_hz",
            "cgg_f",
            "cgd_f",
            "cgs_f",
            "low_frequency_max_relative_change",
        },
        "length_scaling": common
        | {
            "fixed_vctrl_v",
            "fixed_vout_v",
            "fixed_idmag_a",
            "fixed_gm_s",
            "fixed_gds_s",
            "moderate_vctrl_v",
            "moderate_gm_over_id_per_v",
            "moderate_gm_over_gds",
        },
    }


def _audit_result(
    result_directory: Path,
    expected_kit_id: str,
    toolchain: Toolchain,
) -> AuditedResult:
    issues: list[str] = []
    for name in REQUIRED_RESULT_FILES:
        if not (result_directory / name).is_file():
            issues.append(f"missing required result file {name}")
    if issues:
        return AuditedResult(result_directory, {}, {}, [], {"issues": issues, "overall_pass": False})

    metadata = json.loads((result_directory / "metadata.json").read_text(encoding="utf-8"))
    kit = load_kit(expected_kit_id, toolchain.root)
    if metadata.get("schema") != "apm.characterization.v1":
        issues.append("metadata schema is not apm.characterization.v1")
    if metadata.get("status") != "validated":
        issues.append("real-tool characterization status is not validated")
    if metadata.get("kit_id") != expected_kit_id:
        issues.append("metadata kit identity mismatch")
    if metadata.get("compact_model") != kit.compact_model:
        issues.append("metadata compact-model identity mismatch")
    if metadata.get("public_devices") != kit.public_devices:
        issues.append("metadata public-device contract mismatch")
    if not metadata.get("model_revision"):
        issues.append("metadata lacks a model revision")
    if not metadata.get("model_source_sha256"):
        issues.append("metadata lacks model-source hashes")
    if metadata.get("simulator_backend") != "ngspice":
        issues.append("metadata simulator backend is not ngspice")
    if "ngspice-47" not in metadata.get("simulator_version", ""):
        issues.append("metadata does not identify ngspice 47")
    if tuple(metadata.get("temperatures_c", ())) != REQUIRED_TEMPERATURES_C:
        issues.append("metadata required temperature set mismatch")
    if metadata.get("variation_origin") != "none" or metadata.get("variation_mode") != "nominal":
        issues.append("nominal result variation identity mismatch")
    if metadata.get("polarities") != ["n", "p"]:
        issues.append("metadata polarity set mismatch")
    if metadata.get("finite_difference", {}).get("method") != (
        "central terminal finite differences"
    ):
        issues.append("finite-difference method metadata mismatch")
    if metadata.get("dibl", {}).get("method") != (
        "constant-current threshold magnitude"
    ):
        issues.append("DIBL method metadata mismatch")
    if metadata.get("y_matrix", {}).get("terminal_order") != ["d", "g", "s", "b"]:
        issues.append("terminal Y order mismatch")
    requirement_values = metadata.get("checks", {}).get("requirements", {})
    if not requirement_values or not all(requirement_values.values()):
        issues.append("one or more per-kit characterization requirements failed")

    tables: dict[str, list[dict[str, str]]] = {}
    field_sets = _required_fields()
    for table_name, required in field_sets.items():
        fields, rows = _read_csv(result_directory / f"{table_name}.csv")
        missing = required - set(fields)
        if missing:
            issues.append(f"{table_name}.csv lacks fields {sorted(missing)}")
        tables[table_name] = rows

    is_finfet = isinstance(kit, FinFETKit)
    geometry_field = "nfin" if is_finfet else "w_m"
    forbidden_geometry_field = "w_m" if is_finfet else "nfin"
    for table_name, rows in tables.items():
        fields = set(rows[0])
        if geometry_field not in fields:
            issues.append(f"{table_name}.csv lacks {geometry_field} geometry")
        if forbidden_geometry_field in fields:
            issues.append(f"{table_name}.csv exposes invalid {forbidden_geometry_field} geometry")
        temperatures = {int(float(row["temperature_c"])) for row in rows}
        if temperatures != set(REQUIRED_TEMPERATURES_C):
            issues.append(f"{table_name}.csv temperature coverage mismatch")
        if any(row.get("kit_id") != expected_kit_id for row in rows):
            issues.append(f"{table_name}.csv kit identity mismatch")
        if any(row.get("polarity") not in ("n", "p") for row in rows):
            issues.append(f"{table_name}.csv polarity mismatch")
        if any(
            row.get("public_device") != kit.public_devices[row["polarity"]]
            for row in rows
            if row.get("polarity") in ("n", "p")
        ):
            issues.append(f"{table_name}.csv public-device identity mismatch")
        if any(
            row.get("variation_origin") != "none" or row.get("variation_mode") != "nominal"
            for row in rows
        ):
            issues.append(f"{table_name}.csv variation identity mismatch")

    for table_name in ("idvg", "idvd"):
        for row in tables[table_name]:
            raw_source = _float(row, "raw_vd_source_current_a")
            raw_entering = _float(row, "raw_drain_current_entering_device_a")
            tolerance = max(1e-18, 1e-12 * max(abs(raw_source), abs(raw_entering), 1.0))
            if abs(raw_source + raw_entering) > tolerance:
                issues.append(f"{table_name}.csv raw current conventions are inconsistent")
                break
            if _float(row, "idmag_a") < 0.0:
                issues.append(f"{table_name}.csv has negative canonical current magnitude")
                break

    y_records = json.loads((result_directory / "y_matrix.json").read_text(encoding="utf-8"))
    if not isinstance(y_records, list) or not y_records:
        issues.append("y_matrix.json is not a non-empty record list")
        y_records = []
    else:
        y_temperatures = {int(record["temperature_c"]) for record in y_records}
        if y_temperatures != set(REQUIRED_TEMPERATURES_C):
            issues.append("y_matrix.json temperature coverage mismatch")
        for record in y_records:
            if record.get("terminal_order") != ["d", "g", "s", "b"]:
                issues.append("y_matrix.json terminal order mismatch")
                break
            real = record.get("y_real_s")
            imag = record.get("y_imag_s")
            if not (
                isinstance(real, list)
                and isinstance(imag, list)
                and len(real) == len(imag) == 4
                and all(isinstance(row, list) and len(row) == 4 for row in real)
                and all(isinstance(row, list) and len(row) == 4 for row in imag)
            ):
                issues.append("y_matrix.json does not preserve full 4x4 complex matrices")
                break
            if geometry_field not in record or forbidden_geometry_field in record:
                issues.append("y_matrix.json geometry semantics mismatch")
                break
            if record.get("variation_origin") != "none" or record.get("variation_mode") != (
                "nominal"
            ):
                issues.append("y_matrix.json variation identity mismatch")
                break

    expected_counts = metadata.get("row_counts", {})
    for table_name, rows in tables.items():
        if expected_counts.get(table_name) != len(rows):
            issues.append(f"metadata row count mismatch for {table_name}")
    if expected_counts.get("y_matrix") != len(y_records):
        issues.append("metadata row count mismatch for y_matrix")
    nfin_path = result_directory / "nfin_scaling.csv"
    if is_finfet:
        if not nfin_path.is_file():
            issues.append("FinFET result lacks nfin_scaling.csv")
        else:
            _, nfin_rows = _read_csv(nfin_path)
            if expected_counts.get("nfin_scaling") != len(nfin_rows):
                issues.append("metadata row count mismatch for nfin_scaling")
    elif nfin_path.exists():
        issues.append("planar result unexpectedly contains nfin_scaling.csv")

    log_files = sorted((result_directory / "logs").glob("*.log"))
    critical_tokens = (
        "fatal error",
        "simulation interrupted",
        "no convergence",
        "timestep too small",
        "singular matrix",
        "unknown parameter",
        "unsupported parameter",
    )
    critical_log_hits: list[dict[str, str]] = []
    warning_count = 0
    for log in log_files:
        text = log.read_text(encoding="utf-8", errors="replace").lower()
        warning_count += text.count("warning")
        for token in critical_tokens:
            if token in text:
                critical_log_hits.append({"log": log.name, "token": token})
    if critical_log_hits:
        issues.append("one or more simulator logs contain critical diagnostic text")

    artifact_names = list(REQUIRED_RESULT_FILES)
    if nfin_path.is_file():
        artifact_names.append("nfin_scaling.csv")
    artifact_hashes = {
        name: sha256_file(result_directory / name) for name in sorted(artifact_names)
    }
    audit = {
        "overall_pass": not issues,
        "issues": issues,
        "result_directory": str(result_directory.relative_to(result_directory.parent.parent)),
        "artifact_sha256": artifact_hashes,
        "row_counts": expected_counts,
        "simulator_log_count": len(log_files),
        "simulator_warning_token_count": warning_count,
        "critical_log_hits": critical_log_hits,
        "model_revision": metadata.get("model_revision"),
        "model_source_sha256": metadata.get("model_source_sha256"),
    }
    return AuditedResult(result_directory, metadata, tables, y_records, audit)


def _matches_comparison_geometry(row: dict[str, str], is_finfet: bool) -> bool:
    if not math.isclose(
        _float(row, "l_over_lmin"),
        COMPARISON_L_OVER_LMIN,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        return False
    return not is_finfet or int(float(row["nfin"])) == 1


def _same_geometry(
    candidate: dict[str, str],
    selected: dict[str, str],
    is_finfet: bool,
) -> bool:
    if not math.isclose(
        _float(candidate, "l_m"), _float(selected, "l_m"), rel_tol=0.0, abs_tol=1e-18
    ):
        return False
    if is_finfet:
        return int(float(candidate["nfin"])) == int(float(selected["nfin"]))
    return math.isclose(
        _float(candidate, "w_m"), _float(selected, "w_m"), rel_tol=0.0, abs_tol=1e-18
    )


def _normalized_rows(results: list[AuditedResult], toolchain: Toolchain) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        kit = load_kit(result.metadata["kit_id"], toolchain.root)
        is_finfet = isinstance(kit, FinFETKit)
        for polarity in ("n", "p"):
            candidates = [
                row
                for row in result.tables["derived"]
                if int(float(row["temperature_c"])) == 27
                and row["polarity"] == polarity
                and _matches_comparison_geometry(row, is_finfet)
            ]
            if not candidates:
                raise ComparisonError(
                    f"{kit.kit_id} {polarity} lacks the normalized comparison geometry"
                )
            selected = min(
                candidates,
                key=lambda row: abs(
                    _float(row, "gm_over_id_per_v") - COMPARISON_GM_OVER_ID_PER_V
                ),
            )
            dibl_candidates = [
                row
                for row in result.tables["dibl"]
                if int(float(row["temperature_c"])) == 27
                and row["polarity"] == polarity
                and _same_geometry(row, selected, is_finfet)
            ]
            capacitance_candidates = [
                row
                for row in result.tables["capacitance"]
                if int(float(row["temperature_c"])) == 27
                and row["polarity"] == polarity
                and _same_geometry(row, selected, is_finfet)
            ]
            if len(dibl_candidates) != 1 or not capacitance_candidates:
                raise ComparisonError(
                    f"{kit.kit_id} {polarity} lacks matching DIBL/capacitance records"
                )
            dibl = dibl_candidates[0]
            capacitance = min(capacitance_candidates, key=lambda row: _float(row, "frequency_hz"))

            if isinstance(kit, PlanarKit):
                normalization_count = _float(selected, "w_m") / 1e-6
                normalization_basis = "per_um_drawn_width"
                geometry: dict[str, Any] = {"w_m": _float(selected, "w_m")}
            else:
                normalization_count = int(float(selected["nfin"]))
                normalization_basis = "per_fin"
                geometry = {"nfin": normalization_count}
            row = {
                "kit_id": kit.kit_id,
                "public_device": kit.public_devices[polarity],
                "polarity": polarity,
                "compact_model": kit.compact_model,
                "model_revision": result.metadata["model_revision"],
                "architecture": result.metadata["geometry"]["architecture"],
                "nominal_vdd_v": kit.vdd_v,
                "model_lmin_m": kit.lmin_m,
                **geometry,
                "l_m": _float(selected, "l_m"),
                "l_over_lmin": _float(selected, "l_over_lmin"),
                "vctrl_v": _float(selected, "vctrl_v"),
                "vctrl_over_vdd": _float(selected, "vctrl_v") / kit.vdd_v,
                "vout_v": _float(selected, "vout_v"),
                "vout_over_vdd": _float(selected, "vout_v") / kit.vdd_v,
                "idmag_a": _float(selected, "idmag_a"),
                "gm_s": _float(selected, "gm_s"),
                "gds_s": _float(selected, "gds_s"),
                "gm_over_id_per_v": _float(selected, "gm_over_id_per_v"),
                "gm_over_gds": _float(selected, "gm_over_gds"),
                "normalization_basis": normalization_basis,
                "normalization_count": normalization_count,
                "id_normalized_a_per_unit": _float(selected, "idmag_a")
                / normalization_count,
                "gm_normalized_s_per_unit": _float(selected, "gm_s")
                / normalization_count,
                "vth_high_magnitude_v": _float(dibl, "vth_high_magnitude_v"),
                "dibl_v_per_v": _float(dibl, "dibl_v_per_v"),
                "capacitance_frequency_hz": _float(capacitance, "frequency_hz"),
                "cgg_f": _float(capacitance, "cgg_f"),
                "cgd_f": _float(capacitance, "cgd_f"),
                "cgs_f": _float(capacitance, "cgs_f"),
                "cgg_normalized_f_per_unit": _float(capacitance, "cgg_f")
                / normalization_count,
                "cgd_normalized_f_per_unit": _float(capacitance, "cgd_f")
                / normalization_count,
                "cgs_normalized_f_per_unit": _float(capacitance, "cgs_f")
                / normalization_count,
                "variation_origin": "none",
                "variation_mode": "nominal",
                "source_result_directory": str(
                    result.directory.relative_to(result.directory.parent.parent)
                ),
            }
            rows.append(row)
    return rows


def _comparison_checks(
    rows: list[dict[str, Any]], required_kits: tuple[str, ...]
) -> dict[str, Any]:
    expected_pairs = {(kit, polarity) for kit in required_kits for polarity in ("n", "p")}
    actual_pairs = {(row["kit_id"], row["polarity"]) for row in rows}
    positive_fields = (
        "idmag_a",
        "gm_s",
        "gds_s",
        "gm_over_id_per_v",
        "gm_over_gds",
        "id_normalized_a_per_unit",
        "gm_normalized_s_per_unit",
        "vth_high_magnitude_v",
        "dibl_v_per_v",
        "cgg_f",
        "cgd_f",
        "cgs_f",
    )
    requirements = {
        "all_required_kit_polarity_rows": actual_pairs == expected_pairs
        and len(rows) == len(expected_pairs),
        "normalized_length_coordinate": all(
            math.isclose(
                row["l_over_lmin"], COMPARISON_L_OVER_LMIN, rel_tol=0.0, abs_tol=1e-12
            )
            for row in rows
        ),
        "normalized_output_coordinate": all(
            math.isclose(
                row["vout_over_vdd"],
                COMPARISON_VOUT_OVER_VDD,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            for row in rows
        ),
        "moderate_inversion_coordinate": all(
            abs(row["gm_over_id_per_v"] - COMPARISON_GM_OVER_ID_PER_V) <= 2.0
            for row in rows
        ),
        "finite_positive_terminal_metrics": all(
            math.isfinite(row[field]) and row[field] > 0.0
            for row in rows
            for field in positive_fields
        ),
        "geometry_semantics": all(
            (
                row["architecture"] == "planar_bulk"
                and row["normalization_basis"] == "per_um_drawn_width"
                and "w_m" in row
                and "nfin" not in row
            )
            or (
                row["architecture"] == "finfet"
                and row["normalization_basis"] == "per_fin"
                and row.get("nfin") == 1
                and "w_m" not in row
            )
            for row in rows
        ),
        "nominal_variation_identity": all(
            row["variation_origin"] == "none" and row["variation_mode"] == "nominal"
            for row in rows
        ),
    }
    return {
        "criteria": {
            "l_over_lmin": COMPARISON_L_OVER_LMIN,
            "vout_over_vdd": COMPARISON_VOUT_OVER_VDD,
            "gm_over_id_target_per_v": COMPARISON_GM_OVER_ID_PER_V,
            "gm_over_id_absolute_tolerance_per_v": 2.0,
        },
        "requirements": requirements,
        "overall_pass": all(requirements.values()),
    }


def _pairwise_relations(
    rows: list[dict[str, Any]], technology_a: str, technology_b: str
) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    for polarity in ("n", "p"):
        first = next(
            row for row in rows if row["kit_id"] == technology_a and row["polarity"] == polarity
        )
        second = next(
            row for row in rows if row["kit_id"] == technology_b and row["polarity"] == polarity
        )
        same_normalization = first["normalization_basis"] == second["normalization_basis"]
        relations.append(
            {
                "polarity": polarity,
                "technology_a": technology_a,
                "technology_b": technology_b,
                "gm_over_gds_ratio_b_over_a": second["gm_over_gds"]
                / first["gm_over_gds"],
                "dibl_ratio_b_over_a": second["dibl_v_per_v"] / first["dibl_v_per_v"],
                "vth_ratio_b_over_a": second["vth_high_magnitude_v"]
                / first["vth_high_magnitude_v"],
                "normalized_current_ratio_b_over_a": (
                    second["id_normalized_a_per_unit"]
                    / first["id_normalized_a_per_unit"]
                    if same_normalization
                    else None
                ),
                "normalized_capacitance_ratio_b_over_a": (
                    second["cgg_normalized_f_per_unit"]
                    / first["cgg_normalized_f_per_unit"]
                    if same_normalization
                    else None
                ),
                "normalization_ratio_status": (
                    "comparable_same_basis"
                    if same_normalization
                    else "not_reported_across_per_width_and_per_fin_bases"
                ),
            }
        )
    return relations


def _run_comparison(
    technologies: tuple[str, ...],
    output_directory: Path,
    mode: str,
    toolchain: Toolchain,
) -> dict[str, Any]:
    output = output_directory.expanduser().resolve()
    _prepare_output(output)
    kit_root = output / "kits"
    generated_metadata = {
        technology: characterize(technology, kit_root / technology, toolchain)
        for technology in technologies
    }
    audited = [
        _audit_result(kit_root / technology, technology, toolchain)
        for technology in technologies
    ]
    all_audits_pass = all(result.audit["overall_pass"] for result in audited)
    normalized_rows = _normalized_rows(audited, toolchain) if all_audits_pass else []
    normalized_checks = _comparison_checks(normalized_rows, technologies)
    checks = {
        "all_result_contract_audits": all_audits_pass,
        "normalized_comparison": normalized_checks["overall_pass"],
    }
    checks["overall_pass"] = all(checks.values())
    comparison_path = output / "normalized_comparison.csv"
    _write_comparison_csv(comparison_path, normalized_rows)
    report: dict[str, Any] = {
        "schema": "apm.characterization-validation.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "validated" if checks["overall_pass"] else "checks_failed",
        "mode": mode,
        "technologies": list(technologies),
        "comparison_coordinate": {
            "temperature_c": 27,
            "l_over_lmin": COMPARISON_L_OVER_LMIN,
            "vout_over_vdd": COMPARISON_VOUT_OVER_VDD,
            "gm_over_id_target_per_v": COMPARISON_GM_OVER_ID_PER_V,
            "finfet_nfin": 1,
            "planar_current_capacitance_normalization": "per um of drawn width",
            "finfet_current_capacitance_normalization": "per fin",
            "cross_basis_width_to_fin_ratios_reported": False,
        },
        "generated_characterizations": {
            technology: {
                "status": generated_metadata[technology]["status"],
                "directory": str((kit_root / technology).relative_to(output)),
            }
            for technology in technologies
        },
        "result_contract_audits": {
            result.metadata.get("kit_id", technologies[index]): result.audit
            for index, result in enumerate(audited)
        },
        "normalized_comparison_path": str(comparison_path.relative_to(output)),
        "normalized_comparison_sha256": sha256_file(comparison_path),
        "normalized_comparison_rows": normalized_rows,
        "normalized_comparison_checks": normalized_checks,
        "pairwise_relations": (
            _pairwise_relations(normalized_rows, technologies[0], technologies[1])
            if mode == "pairwise" and normalized_checks["overall_pass"]
            else []
        ),
        "checks": checks,
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["output_directory"] = str(output)
    report["report_path"] = str(report_path)
    if not checks["overall_pass"]:
        raise ComparisonError(f"integrated characterization checks failed; see {report_path}")
    return report


def validate_all_characterizations(
    output_directory: Path,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    selected = toolchain or resolve_toolchain()
    return _run_comparison(REQUIRED_KITS, output_directory, "all_kits", selected)


def compare_technologies(
    technology_a: str,
    technology_b: str,
    output_directory: Path | None = None,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    if technology_a == technology_b:
        raise ComparisonError("comparison requires two distinct technology kits")
    if technology_a not in REQUIRED_KITS or technology_b not in REQUIRED_KITS:
        raise ComparisonError("comparison technology is not a required APM v1 kit")
    selected = toolchain or resolve_toolchain()
    if output_directory is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_directory = (
            selected.root / "results" / "comparisons" / f"{technology_a}-vs-{technology_b}" / stamp
        )
    return _run_comparison(
        (technology_a, technology_b), output_directory, "pairwise", selected
    )
