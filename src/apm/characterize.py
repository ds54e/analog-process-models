# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import csv
import json
import math
import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10 reference environments
    import tomli as tomllib

from .model_build import build_models, sha256_file
from .toolchain import Toolchain, ToolchainError, resolve_toolchain, run_checked

TERMINALS = ("d", "g", "s", "b")


class CharacterizationError(RuntimeError):
    """A terminal characterization run could not be completed or audited."""


@dataclass(frozen=True)
class PlanarKit:
    kit_id: str
    compact_model: str
    vdd_v: float
    lmin_m: float
    width_m: float
    lengths_m: tuple[float, ...]
    temperatures_c: tuple[int, ...]
    public_devices: dict[str, Any]
    model_library: Path
    model_section: str
    wrapper_file: Path
    osdi_artifacts: tuple[str, ...]
    provenance_revision: str
    threshold_coefficient_a: float
    vout_low_v: float
    vout_high_v: float
    idvg_points: int
    idvd_points: int
    y_frequencies_hz: tuple[float, ...]

    def raw_voltage(self, polarity: str, effective_voltage: float) -> float:
        return effective_voltage if polarity == "n" else -effective_voltage

    def native_vector(self, polarity: str, quantity: str) -> str:
        upstream = "nmos" if polarity == "n" else "pmos"
        return f"@n.xdut.xapm130_core.nsg13_lv_{upstream}[{quantity}]"


def _load_apm130(root: Path) -> PlanarKit:
    path = root / "models/apm130/kit.toml"
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    source = root / "models/apm130/vendor/ihp-sg13g2-models"
    provenance_path = root / "models/apm130/provenance.toml"
    with provenance_path.open("rb") as handle:
        provenance = tomllib.load(handle)
    return PlanarKit(
        kit_id=data["id"],
        compact_model=data["compact_model"],
        vdd_v=float(data["nominal_vdd_v"]),
        lmin_m=float(data["model_lmin_m"]),
        width_m=float(data["default_w_m"]),
        lengths_m=tuple(float(value) for value in data["characterization_lengths_m"]),
        temperatures_c=tuple(int(value) for value in data["temperatures_c"]),
        public_devices=dict(data["public_devices"]),
        model_library=source / "cornerMOSlv.lib",
        model_section="mos_tt",
        wrapper_file=root / "models/apm130/ngspice/apm130_wrappers.inc",
        osdi_artifacts=("psp103.osdi", "psp103-nqs.osdi"),
        provenance_revision=provenance["source"]["revision"],
        threshold_coefficient_a=float(data["threshold"]["planar_current_coefficient_a"]),
        vout_low_v=float(data["threshold"]["vout_low_v"]),
        vout_high_v=float(data["threshold"]["vout_high_fraction_vdd"])
        * float(data["nominal_vdd_v"]),
        idvg_points=int(data["characterization"]["idvg_points"]),
        idvd_points=int(data["characterization"]["idvd_points"]),
        y_frequencies_hz=tuple(
            float(value) for value in data["characterization"]["y_frequencies_hz"]
        ),
    )


def load_planar_kit(technology: str, root: Path) -> PlanarKit:
    if technology == "apm130":
        return _load_apm130(root)
    raise CharacterizationError(
        f"{technology} characterization has not reached its implementation milestone"
    )


def _float_token(value: float) -> str:
    return f"{value:.9g}".replace("-", "m").replace(".", "p").replace("+", "p")


def _read_wrdata(path: Path, expected_columns: int) -> list[list[float]]:
    if not path.is_file():
        raise CharacterizationError(f"ngspice did not create expected raw data: {path}")
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        try:
            values = [float(value) for value in line.split()]
        except ValueError as error:
            raise CharacterizationError(f"malformed numeric row in {path}: {line}") from error
        if len(values) != expected_columns:
            raise CharacterizationError(
                f"expected {expected_columns} columns in {path}, found {len(values)}"
            )
        rows.append(values)
    if not rows:
        raise CharacterizationError(f"no numerical rows found in {path}")
    return rows


def _run_ngspice(toolchain: Toolchain, netlist: Path, log: Path) -> None:
    result = run_checked(
        [toolchain.ngspice, "-n", "-b", "-o", log, netlist],
        environment=toolchain.environment(),
        cwd=netlist.parent.parent,
    )
    text = log.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    failure_tokens = (
        "fatal error",
        "simulation interrupted",
        "timestep too small",
        "no convergence in dc analysis",
        "no such file or directory",
    )
    if any(token in lowered for token in failure_tokens):
        raise ToolchainError(f"ngspice reported a failed analysis in {log}")
    if "ngspice-47 done" not in text:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ToolchainError(f"ngspice did not complete {netlist}: {detail}")


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _dc_job(
    kit: PlanarKit,
    toolchain: Toolchain,
    output: Path,
    temperature_c: int,
    polarity: str,
    length_m: float,
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, float], list[dict[str, Any]]]
]:
    raw_dir = output / "raw"
    netlist_dir = output / "netlists"
    log_dir = output / "logs"
    job = f"dc_{polarity}_{temperature_c}_{_float_token(length_m)}"
    netlist = netlist_dir / f"{job}.cir"
    log = log_dir / f"{job}.log"
    sign = 1.0 if polarity == "n" else -1.0
    idvg_step = kit.vdd_v / (kit.idvg_points - 1)
    idvd_step = kit.vdd_v / (kit.idvd_points - 1)
    nominal_vout = 0.5 * kit.vdd_v
    gds_h1 = 0.01 * kit.vdd_v
    gds_h2 = 0.02 * kit.vdd_v
    idvg_vouts = sorted(
        {
            kit.vout_low_v,
            kit.vout_high_v,
            nominal_vout,
            nominal_vout - gds_h1,
            nominal_vout + gds_h1,
            nominal_vout - gds_h2,
            nominal_vout + gds_h2,
        }
    )
    idvd_vctrls = (0.25 * kit.vdd_v, 0.5 * kit.vdd_v, 0.75 * kit.vdd_v, kit.vdd_v)
    device = kit.public_devices[polarity]
    native_gm = kit.native_vector(polarity, "gm")
    native_gds = kit.native_vector(polarity, "gds")
    lines = [
        "APM DC characterization",
        f'.lib "{kit.model_library}" {kit.model_section}',
        f'.include "{kit.wrapper_file}"',
        f".temp {temperature_c}",
        f"Vd d 0 {sign * nominal_vout:.12g}",
        "Vg g 0 0",
        "Vs s 0 0",
        "Vb b 0 0",
        f"Xdut d g s b {device} w={kit.width_m:.12g} l={length_m:.12g}",
        ".control",
        *[f"pre_osdi {toolchain.osdi_directory / item}" for item in kit.osdi_artifacts],
        "set wr_vecnames",
        "set wr_singlescale",
        f"save all {native_gm} {native_gds}",
    ]
    raw_paths: dict[tuple[str, float], Path] = {}
    for vout in idvg_vouts:
        path = raw_dir / f"{job}_idvg_vout_{_float_token(vout)}.dat"
        raw_paths[("idvg", vout)] = path
        lines.extend(
            [
                f"alter Vd = {sign * vout:.12g}",
                f"dc Vg 0 {sign * kit.vdd_v:.12g} {sign * idvg_step:.12g}",
                f"wrdata {path} v(g) i(vd) {native_gm} {native_gds}",
            ]
        )
    for vctrl in idvd_vctrls:
        path = raw_dir / f"{job}_idvd_vctrl_{_float_token(vctrl)}.dat"
        raw_paths[("idvd", vctrl)] = path
        lines.extend(
            [
                f"alter Vg = {sign * vctrl:.12g}",
                f"dc Vd 0 {sign * kit.vdd_v:.12g} {sign * idvd_step:.12g}",
                f"wrdata {path} v(d) i(vd) {native_gm} {native_gds}",
            ]
        )
    lines.extend(["quit", ".endc", ".end"])
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)

    idvg_rows: list[dict[str, Any]] = []
    idvd_rows: list[dict[str, Any]] = []
    curves: dict[tuple[str, float], list[dict[str, Any]]] = {}
    common = {
        "kit_id": kit.kit_id,
        "public_device": device,
        "polarity": polarity,
        "compact_model": kit.compact_model,
        "temperature_c": temperature_c,
        "w_m": kit.width_m,
        "l_m": length_m,
        "l_over_lmin": length_m / kit.lmin_m,
        "variation_origin": "none",
        "variation_mode": "nominal",
    }
    for (kind, fixed_bias), path in raw_paths.items():
        parsed: list[dict[str, Any]] = []
        for values in _read_wrdata(path, 5):
            raw_sweep_v = values[1]
            raw_source_current_a = values[2]
            vctrl_v = abs(raw_sweep_v) if kind == "idvg" else fixed_bias
            vout_v = fixed_bias if kind == "idvg" else abs(raw_sweep_v)
            raw_vgs_v = kit.raw_voltage(polarity, vctrl_v)
            raw_vds_v = kit.raw_voltage(polarity, vout_v)
            row = {
                **common,
                "vctrl_v": vctrl_v,
                "vout_v": vout_v,
                "raw_vgs_v": raw_vgs_v,
                "raw_vds_v": raw_vds_v,
                "raw_vd_source_current_a": raw_source_current_a,
                "raw_drain_current_entering_device_a": -raw_source_current_a,
                "idmag_a": abs(raw_source_current_a),
                "native_gm_s": abs(values[3]),
                "native_gds_s": abs(values[4]),
                "raw_file": str(path.relative_to(output)),
            }
            parsed.append(row)
        curves[(kind, fixed_bias)] = parsed
        if kind == "idvg":
            idvg_rows.extend(parsed)
        else:
            idvd_rows.extend(parsed)
    return idvg_rows, idvd_rows, curves


def _relative_difference(first: float, second: float, floor: float = 1e-30) -> float:
    return abs(first - second) / max(abs(first), abs(second), floor)


def _derive_operating_metrics(
    kit: PlanarKit,
    temperature_c: int,
    polarity: str,
    length_m: float,
    curves: dict[tuple[str, float], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    nominal_vout = 0.5 * kit.vdd_v
    gds_h1 = 0.01 * kit.vdd_v
    gds_h2 = 0.02 * kit.vdd_v
    nominal = curves[("idvg", nominal_vout)]
    minus_h1 = curves[("idvg", nominal_vout - gds_h1)]
    plus_h1 = curves[("idvg", nominal_vout + gds_h1)]
    minus_h2 = curves[("idvg", nominal_vout - gds_h2)]
    plus_h2 = curves[("idvg", nominal_vout + gds_h2)]
    vctrl_step = kit.vdd_v / (kit.idvg_points - 1)
    result: list[dict[str, Any]] = []
    for index in range(2, len(nominal) - 2):
        center = nominal[index]
        gm_h1 = (nominal[index + 1]["idmag_a"] - nominal[index - 1]["idmag_a"]) / (2.0 * vctrl_step)
        gm_h2 = (nominal[index + 2]["idmag_a"] - nominal[index - 2]["idmag_a"]) / (4.0 * vctrl_step)
        gds_first = (plus_h1[index]["idmag_a"] - minus_h1[index]["idmag_a"]) / (2.0 * gds_h1)
        gds_second = (plus_h2[index]["idmag_a"] - minus_h2[index]["idmag_a"]) / (2.0 * gds_h2)
        current = center["idmag_a"]
        native_gm = center["native_gm_s"]
        native_gds = center["native_gds_s"]
        result.append(
            {
                "kit_id": kit.kit_id,
                "public_device": kit.public_devices[polarity],
                "polarity": polarity,
                "compact_model": kit.compact_model,
                "temperature_c": temperature_c,
                "w_m": kit.width_m,
                "l_m": length_m,
                "l_over_lmin": length_m / kit.lmin_m,
                "vctrl_v": center["vctrl_v"],
                "vout_v": nominal_vout,
                "idmag_a": current,
                "gm_s": gm_h1,
                "gm_second_step_s": gm_h2,
                "gm_step_v": vctrl_step,
                "gm_second_step_v": 2.0 * vctrl_step,
                "gm_convergence_relative": _relative_difference(gm_h1, gm_h2),
                "gds_s": gds_first,
                "gds_second_step_s": gds_second,
                "gds_step_v": gds_h1,
                "gds_second_step_v": gds_h2,
                "gds_convergence_relative": _relative_difference(gds_first, gds_second),
                "gm_over_id_per_v": gm_h1 / current if current > 0.0 else math.nan,
                "gm_over_gds": gm_h1 / gds_first if gds_first > 0.0 else math.nan,
                "native_gm_s": native_gm,
                "native_gds_s": native_gds,
                "native_gm_relative_error": _relative_difference(gm_h1, native_gm),
                "native_gds_relative_error": _relative_difference(gds_first, native_gds),
                "variation_origin": "none",
                "variation_mode": "nominal",
            }
        )
    return result


def _threshold_crossing(curve: list[dict[str, Any]], target_a: float) -> float:
    for lower, upper in zip(curve, curve[1:]):
        low_i = lower["idmag_a"]
        high_i = upper["idmag_a"]
        if low_i <= target_a <= high_i and high_i > low_i:
            fraction = (target_a - low_i) / (high_i - low_i)
            return lower["vctrl_v"] + fraction * (upper["vctrl_v"] - lower["vctrl_v"])
    raise CharacterizationError(
        f"constant-current threshold target {target_a:.6g} A is outside the Id-Vg sweep"
    )


def _derive_dibl(
    kit: PlanarKit,
    temperature_c: int,
    polarity: str,
    length_m: float,
    curves: dict[tuple[str, float], list[dict[str, Any]]],
) -> dict[str, Any]:
    criterion = kit.threshold_coefficient_a * kit.width_m / length_m
    low_threshold = _threshold_crossing(curves[("idvg", kit.vout_low_v)], criterion)
    high_threshold = _threshold_crossing(curves[("idvg", kit.vout_high_v)], criterion)
    dibl = (low_threshold - high_threshold) / (kit.vout_high_v - kit.vout_low_v)
    return {
        "kit_id": kit.kit_id,
        "public_device": kit.public_devices[polarity],
        "polarity": polarity,
        "temperature_c": temperature_c,
        "w_m": kit.width_m,
        "l_m": length_m,
        "l_over_lmin": length_m / kit.lmin_m,
        "criterion_a": criterion,
        "criterion_coefficient_a": kit.threshold_coefficient_a,
        "criterion_normalization": "coefficient * W/L",
        "vout_low_v": kit.vout_low_v,
        "vout_high_v": kit.vout_high_v,
        "vth_low_magnitude_v": low_threshold,
        "vth_high_magnitude_v": high_threshold,
        "dibl_v_per_v": dibl,
        "variation_origin": "none",
        "variation_mode": "nominal",
    }


def _y_job(
    kit: PlanarKit,
    toolchain: Toolchain,
    output: Path,
    temperature_c: int,
    polarity: str,
    length_m: float,
) -> list[dict[str, Any]]:
    job = f"y_{polarity}_{temperature_c}_{_float_token(length_m)}"
    netlist = output / "netlists" / f"{job}.cir"
    log = output / "logs" / f"{job}.log"
    raw_paths = {
        frequency: output / "raw" / f"{job}_{_float_token(frequency)}hz.dat"
        for frequency in kit.y_frequencies_hz
    }
    vctrl = 0.5 * kit.vdd_v
    vout = 0.5 * kit.vdd_v
    raw_bias = {
        "d": kit.raw_voltage(polarity, vout),
        "g": kit.raw_voltage(polarity, vctrl),
        "s": 0.0,
        "b": 0.0,
    }
    lines = [
        "APM four-terminal Y characterization",
        f'.lib "{kit.model_library}" {kit.model_section}',
        f'.include "{kit.wrapper_file}"',
        f".temp {temperature_c}",
    ]
    vector_names: list[str] = []
    for excitation in TERMINALS:
        nodes = {terminal: f"{terminal}_{excitation}" for terminal in TERMINALS}
        for terminal in TERMINALS:
            source_name = f"V{terminal}{excitation}"
            ac_magnitude = 1 if terminal == excitation else 0
            lines.append(
                f"{source_name} {nodes[terminal]} 0 {raw_bias[terminal]:.12g} AC {ac_magnitude}"
            )
            vector_names.append(f"i({source_name})")
        lines.append(
            f"X{excitation} {nodes['d']} {nodes['g']} {nodes['s']} {nodes['b']} "
            f"{kit.public_devices[polarity]} w={kit.width_m:.12g} l={length_m:.12g}"
        )
    lines.extend(
        [
            ".control",
            *[f"pre_osdi {toolchain.osdi_directory / item}" for item in kit.osdi_artifacts],
            "set wr_vecnames",
            "set wr_singlescale",
        ]
    )
    for frequency, raw_path in raw_paths.items():
        lines.extend(
            [
                f"ac lin 1 {frequency:.12g} {frequency:.12g}",
                f"wrdata {raw_path} " + " ".join(vector_names),
            ]
        )
    lines.extend(["quit", ".endc", ".end"])
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)
    records: list[dict[str, Any]] = []
    for requested_frequency, raw_path in raw_paths.items():
        parsed = _read_wrdata(raw_path, 1 + 2 * len(vector_names))
        if len(parsed) != 1:
            raise CharacterizationError(
                f"expected one AC row at {requested_frequency:g} Hz in {raw_path}"
            )
        for values in parsed:
            frequency = values[0]
            if not math.isclose(frequency, requested_frequency, rel_tol=1e-12):
                raise CharacterizationError(
                    f"ngspice AC frequency {frequency:g} does not match {requested_frequency:g}"
                )
            y = [[0j for _ in TERMINALS] for _ in TERMINALS]
            cursor = 1
            for column, _excitation in enumerate(TERMINALS):
                for row, _response in enumerate(TERMINALS):
                    source_current = complex(values[cursor], values[cursor + 1])
                    cursor += 2
                    y[row][column] = -source_current
            column_sums = [abs(sum(y[row][column] for row in range(4))) for column in range(4)]
            records.append(
                {
                    "kit_id": kit.kit_id,
                    "public_device": kit.public_devices[polarity],
                    "polarity": polarity,
                    "compact_model": kit.compact_model,
                    "temperature_c": temperature_c,
                    "w_m": kit.width_m,
                    "l_m": length_m,
                    "l_over_lmin": length_m / kit.lmin_m,
                    "raw_dc_vgs_v": raw_bias["g"],
                    "raw_dc_vds_v": raw_bias["d"],
                    "vctrl_v": vctrl,
                    "vout_v": vout,
                    "frequency_hz": frequency,
                    "terminal_order": list(TERMINALS),
                    "excitation_convention": "1 V small-signal excitation at column terminal; other terminal sources at AC ground",
                    "current_convention": "Y[i,j] is current entering APM device terminal i divided by excitation at j; ngspice voltage-source currents are negated",
                    "reference_node": "independent ground node 0",
                    "y_real_s": [[value.real for value in row] for row in y],
                    "y_imag_s": [[value.imag for value in row] for row in y],
                    "kcl_column_sum_abs_s": column_sums,
                    "raw_file": str(raw_path.relative_to(output)),
                    "variation_origin": "none",
                    "variation_mode": "nominal",
                }
            )
    return records


def _capacitance_rows(y_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in y_records:
        omega = 2.0 * math.pi * record["frequency_hz"]
        imag = record["y_imag_s"]
        rows.append(
            {
                "kit_id": record["kit_id"],
                "public_device": record["public_device"],
                "polarity": record["polarity"],
                "temperature_c": record["temperature_c"],
                "w_m": record["w_m"],
                "l_m": record["l_m"],
                "l_over_lmin": record["l_over_lmin"],
                "vctrl_v": record["vctrl_v"],
                "vout_v": record["vout_v"],
                "frequency_hz": record["frequency_hz"],
                "cgg_f": imag[1][1] / omega,
                "cgd_f": -imag[1][0] / omega,
                "cgs_f": -imag[1][2] / omega,
                "variation_origin": "none",
                "variation_mode": "nominal",
            }
        )
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["polarity"], row["temperature_c"], row["l_m"])
        grouped.setdefault(key, []).append(row)
    for group in grouped.values():
        group.sort(key=lambda row: row["frequency_hz"])
        low, high = group[0], group[-1]
        changes = [
            _relative_difference(low[field], high[field]) for field in ("cgg_f", "cgd_f", "cgs_f")
        ]
        for row in group:
            row["low_frequency_max_relative_change"] = max(changes)
    return rows


def _median(values: Iterable[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return statistics.median(finite) if finite else math.nan


def _percentile(values: Iterable[float], fraction: float) -> float:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return math.nan
    position = fraction * (len(finite) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return finite[lower]
    weight = position - lower
    return finite[lower] * (1.0 - weight) + finite[upper] * weight


def _build_checks(
    kit: PlanarKit,
    idvg: list[dict[str, Any]],
    idvd: list[dict[str, Any]],
    derived: list[dict[str, Any]],
    dibl: list[dict[str, Any]],
    y_records: list[dict[str, Any]],
    capacitance: list[dict[str, Any]],
) -> dict[str, Any]:
    moderate = [
        row
        for row in derived
        if row["idmag_a"] > kit.threshold_coefficient_a * kit.width_m / row["l_m"]
        and 0.25 * kit.vdd_v <= row["vctrl_v"] <= 0.9 * kit.vdd_v
    ]

    def monotonic_violations(
        rows: list[dict[str, Any]], coordinate: str, fixed_coordinate: str
    ) -> int:
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in rows:
            key = (
                row["polarity"],
                row["temperature_c"],
                row["l_m"],
                row[fixed_coordinate],
            )
            groups.setdefault(key, []).append(row)
        violations = 0
        for group in groups.values():
            ordered = sorted(group, key=lambda row: row[coordinate])
            if any(
                upper["idmag_a"] < lower["idmag_a"] - 1e-12
                for lower, upper in zip(ordered, ordered[1:])
            ):
                violations += 1
        return violations

    checks: dict[str, Any] = {
        "moderate_operating_points": len(moderate),
        "gm_finite_difference_median_relative_change": _median(
            row["gm_convergence_relative"] for row in moderate
        ),
        "gds_finite_difference_median_relative_change": _median(
            row["gds_convergence_relative"] for row in moderate
        ),
        "gm_finite_difference_p95_relative_change": _percentile(
            (row["gm_convergence_relative"] for row in moderate), 0.95
        ),
        "gds_finite_difference_p95_relative_change": _percentile(
            (row["gds_convergence_relative"] for row in moderate), 0.95
        ),
        "psp_native_gm_median_relative_error": _median(
            row["native_gm_relative_error"] for row in moderate
        ),
        "psp_native_gds_median_relative_error": _median(
            row["native_gds_relative_error"] for row in moderate
        ),
        "psp_native_gm_p95_relative_error": _percentile(
            (row["native_gm_relative_error"] for row in moderate), 0.95
        ),
        "psp_native_gds_p95_relative_error": _percentile(
            (row["native_gds_relative_error"] for row in moderate), 0.95
        ),
        "dibl_min_v_per_v": min(row["dibl_v_per_v"] for row in dibl),
        "dibl_max_v_per_v": max(row["dibl_v_per_v"] for row in dibl),
        "y_kcl_max_column_sum_abs_s": max(
            max(record["kcl_column_sum_abs_s"]) for record in y_records
        ),
        "capacitance_frequency_max_relative_change": max(
            row["low_frequency_max_relative_change"] for row in capacitance
        ),
        "idvg_nonmonotonic_group_count": monotonic_violations(idvg, "vctrl_v", "vout_v"),
        "idvd_nonmonotonic_group_count": monotonic_violations(idvd, "vout_v", "vctrl_v"),
        "n_raw_source_current_sign_violation_count": sum(
            row["raw_vd_source_current_a"] > 1e-12 for row in idvg if row["polarity"] == "n"
        ),
        "p_raw_source_current_sign_violation_count": sum(
            row["raw_vd_source_current_a"] < -1e-12 for row in idvg if row["polarity"] == "p"
        ),
        "minimum_cgg_f": min(row["cgg_f"] for row in capacitance),
        "minimum_cgd_f": min(row["cgd_f"] for row in capacitance),
        "minimum_cgs_f": min(row["cgs_f"] for row in capacitance),
    }
    checks["criteria"] = {
        "gm_finite_difference_p95_relative_change_max": 0.02,
        "gds_finite_difference_p95_relative_change_max": 0.02,
        "psp_native_gm_p95_relative_error_max": 0.02,
        "psp_native_gds_p95_relative_error_max": 0.02,
        "dibl_range_v_per_v": [0.0, 0.5],
        "y_kcl_max_column_sum_abs_s_max": 1e-9,
        "capacitance_frequency_max_relative_change_max": 0.01,
        "monotonic_group_violations_max": 0,
        "raw_current_sign_violations_max": 0,
        "minimum_reported_capacitance_f_exclusive": 0.0,
    }
    checks["requirements"] = {
        "finite_difference_convergence": checks["gm_finite_difference_p95_relative_change"] < 0.02
        and checks["gds_finite_difference_p95_relative_change"] < 0.02,
        "psp_native_oracle_agreement": checks["psp_native_gm_p95_relative_error"] < 0.02
        and checks["psp_native_gds_p95_relative_error"] < 0.02,
        "positive_sensible_dibl": 0.0
        < checks["dibl_min_v_per_v"]
        <= checks["dibl_max_v_per_v"]
        < 0.5,
        "y_matrix_kcl": checks["y_kcl_max_column_sum_abs_s"] < 1e-9,
        "quasi_static_frequency_sensitivity": checks["capacitance_frequency_max_relative_change"]
        < 0.01,
        "monotonic_dc_curves": checks["idvg_nonmonotonic_group_count"] == 0
        and checks["idvd_nonmonotonic_group_count"] == 0,
        "raw_current_sign_convention": checks["n_raw_source_current_sign_violation_count"] == 0
        and checks["p_raw_source_current_sign_violation_count"] == 0,
        "positive_reported_capacitances": min(
            checks["minimum_cgg_f"], checks["minimum_cgd_f"], checks["minimum_cgs_f"]
        )
        > 0.0,
    }
    checks["overall_pass"] = all(checks["requirements"].values())
    return checks


def _length_scaling_rows(kit: PlanarKit, derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for temperature in kit.temperatures_c:
        for polarity in ("n", "p"):
            for length in kit.lengths_m:
                candidates = [
                    row
                    for row in derived
                    if row["temperature_c"] == temperature
                    and row["polarity"] == polarity
                    and row["l_m"] == length
                ]
                fixed = min(candidates, key=lambda row: abs(row["vctrl_v"] - 0.8 * kit.vdd_v))
                moderate = min(
                    candidates,
                    key=lambda row: (
                        abs(row["gm_over_id_per_v"] - 15.0)
                        if math.isfinite(row["gm_over_id_per_v"])
                        else math.inf
                    ),
                )
                rows.append(
                    {
                        "kit_id": kit.kit_id,
                        "public_device": kit.public_devices[polarity],
                        "polarity": polarity,
                        "temperature_c": temperature,
                        "w_m": kit.width_m,
                        "l_m": length,
                        "l_over_lmin": length / kit.lmin_m,
                        "fixed_vctrl_v": fixed["vctrl_v"],
                        "fixed_vout_v": fixed["vout_v"],
                        "fixed_idmag_a": fixed["idmag_a"],
                        "fixed_gm_s": fixed["gm_s"],
                        "fixed_gds_s": fixed["gds_s"],
                        "moderate_vctrl_v": moderate["vctrl_v"],
                        "moderate_gm_over_id_per_v": moderate["gm_over_id_per_v"],
                        "moderate_gm_over_gds": moderate["gm_over_gds"],
                        "variation_origin": "none",
                        "variation_mode": "nominal",
                    }
                )
    return rows


def characterize(
    technology: str,
    output_directory: Path | None = None,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    selected = toolchain or resolve_toolchain()
    kit = load_planar_kit(technology, selected.root)
    build_metadata = build_models(selected, force=False)
    if output_directory is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = selected.root / "results" / technology / stamp
    else:
        output = output_directory.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise CharacterizationError(f"refusing to overwrite non-empty result directory: {output}")
    for child in ("raw", "netlists", "logs"):
        (output / child).mkdir(parents=True, exist_ok=True)

    version = run_checked([selected.ngspice, "--version"])
    idvg_rows: list[dict[str, Any]] = []
    idvd_rows: list[dict[str, Any]] = []
    derived_rows: list[dict[str, Any]] = []
    dibl_rows: list[dict[str, Any]] = []
    y_records: list[dict[str, Any]] = []
    for temperature in kit.temperatures_c:
        for polarity in ("n", "p"):
            for length in kit.lengths_m:
                idvg, idvd, curves = _dc_job(kit, selected, output, temperature, polarity, length)
                idvg_rows.extend(idvg)
                idvd_rows.extend(idvd)
                derived_rows.extend(
                    _derive_operating_metrics(kit, temperature, polarity, length, curves)
                )
                dibl_rows.append(_derive_dibl(kit, temperature, polarity, length, curves))
                y_records.extend(_y_job(kit, selected, output, temperature, polarity, length))

    capacitance_rows = _capacitance_rows(y_records)
    length_rows = _length_scaling_rows(kit, derived_rows)
    checks = _build_checks(
        kit, idvg_rows, idvd_rows, derived_rows, dibl_rows, y_records, capacitance_rows
    )
    _write_csv(output / "idvg.csv", list(idvg_rows[0]), idvg_rows)
    _write_csv(output / "idvd.csv", list(idvd_rows[0]), idvd_rows)
    _write_csv(output / "derived.csv", list(derived_rows[0]), derived_rows)
    _write_csv(output / "dibl.csv", list(dibl_rows[0]), dibl_rows)
    _write_csv(output / "capacitance.csv", list(capacitance_rows[0]), capacitance_rows)
    _write_csv(output / "length_scaling.csv", list(length_rows[0]), length_rows)
    (output / "y_matrix.json").write_text(
        json.dumps(y_records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    metadata: dict[str, Any] = {
        "schema": "apm.characterization.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "validated" if checks["overall_pass"] else "real_tool_completed_checks_failed",
        "kit_id": kit.kit_id,
        "public_devices": kit.public_devices,
        "polarities": ["n", "p"],
        "compact_model": kit.compact_model,
        "model_revision": kit.provenance_revision,
        "model_library_sha256": sha256_file(kit.model_library),
        "simulator_backend": "ngspice",
        "simulator_version": (version.stdout + version.stderr).strip(),
        "nominal_vdd_v": kit.vdd_v,
        "temperatures_c": list(kit.temperatures_c),
        "geometry": {
            "architecture": "planar_bulk",
            "w_m": kit.width_m,
            "lengths_m": list(kit.lengths_m),
            "model_lmin_m": kit.lmin_m,
        },
        "variation_origin": "none",
        "variation_mode": "nominal",
        "raw_current_convention": "ngspice voltage-source branch current is retained; current entering the device drain is its negative",
        "canonical_polarity_convention": {
            "n": "VCTRL=VGS, VOUT=VDS, IDMAG=abs(ID)",
            "p": "VCTRL=VSG, VOUT=VSD, IDMAG=abs(ID)",
        },
        "finite_difference": {
            "method": "central terminal finite differences",
            "gm_steps_v": [
                kit.vdd_v / (kit.idvg_points - 1),
                2 * kit.vdd_v / (kit.idvg_points - 1),
            ],
            "gds_steps_v": [0.01 * kit.vdd_v, 0.02 * kit.vdd_v],
            "native_psp_values_are_validation_oracles_only": True,
        },
        "dibl": {
            "method": "constant-current threshold magnitude",
            "coefficient_a": kit.threshold_coefficient_a,
            "normalization": "coefficient * W/L",
            "vout_low_v": kit.vout_low_v,
            "vout_high_v": kit.vout_high_v,
        },
        "y_matrix": {
            "terminal_order": list(TERMINALS),
            "frequencies_hz": list(kit.y_frequencies_hz),
            "definition": "Y[i,j]=terminal current entering i / 1 V excitation at j",
            "self_capacitance": "Cii=imag(Yii)/(2*pi*f)",
            "transfer_capacitance": "Cij=-imag(Yij)/(2*pi*f), i!=j",
        },
        "row_counts": {
            "idvg": len(idvg_rows),
            "idvd": len(idvd_rows),
            "derived": len(derived_rows),
            "dibl": len(dibl_rows),
            "y_matrix": len(y_records),
            "capacitance": len(capacitance_rows),
            "length_scaling": len(length_rows),
        },
        "checks": checks,
        "model_build_metadata": build_metadata["metadata_path"],
    }
    metadata_path = output / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    metadata["output_directory"] = str(output)
    metadata["metadata_path"] = str(metadata_path)
    return metadata
