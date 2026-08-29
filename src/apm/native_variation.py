# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import csv
import json
import math
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .characterize import (
    PlanarKit,
    _read_wrdata,
    _run_ngspice,
    _threshold_crossing,
    load_kit,
)
from .model_build import build_models, sha256_file
from .toolchain import Toolchain, resolve_toolchain

NATIVE_CORNER_PROFILES = ("mos_tt", "mos_ss", "mos_ff", "mos_sf", "mos_fs")
NATIVE_PROCESS_PROFILE = "mos_tt_stat"
NATIVE_MISMATCH_PROFILE = "mos_tt_mismatch"
NATIVE_MODES = ("corner", "process", "mismatch")
NATIVE_SAMPLE_COUNT = 128
NATIVE_BASE_SEED = 20260830

CORNER_SPEED_PROFILES = {
    "n": {
        "slow": ("mos_ss", "mos_sf"),
        "fast": ("mos_ff", "mos_fs"),
    },
    "p": {
        "slow": ("mos_ss", "mos_fs"),
        "fast": ("mos_ff", "mos_sf"),
    },
}

CORNER_FIELDS = (
    "kit_id",
    "compact_model",
    "public_device",
    "polarity",
    "temperature_c",
    "w_m",
    "l_m",
    "vout_v",
    "vctrl_on_v",
    "threshold_criterion_a",
    "threshold_magnitude_v",
    "raw_vd_source_current_a",
    "raw_drain_current_entering_device_a",
    "idmag_on_a",
    "variation_origin",
    "variation_mode",
    "native_profile",
    "upstream_library",
    "raw_file",
)

PROCESS_SAMPLE_FIELDS = (
    "kit_id",
    "sample_index",
    "seed",
    "polarity",
    "parameter_name",
    "nominal_value",
    "relative_one_sigma",
    "ngspice_num_sigmas",
    "expected_sigma",
    "resolved_value",
    "normalized_z",
    "empirical_role",
    "variation_origin",
    "variation_mode",
    "native_profile",
    "distribution",
)

PROCESS_OBSERVATION_FIELDS = (
    "kit_id",
    "sample_index",
    "seed",
    "polarity",
    "public_device",
    "temperature_c",
    "w_m",
    "l_m",
    "vctrl_v",
    "vout_v",
    "raw_vd_source_current_1_a",
    "raw_vd_source_current_2_a",
    "idmag_1_a",
    "idmag_2_a",
    "variation_origin",
    "variation_mode",
    "native_profile",
)

MISMATCH_SAMPLE_FIELDS = (
    "kit_id",
    "sample_index",
    "seed",
    "polarity",
    "public_device",
    "geometry_label",
    "instance_index",
    "temperature_c",
    "w_nominal_m",
    "l_nominal_m",
    "area_um2",
    "vctrl_v",
    "vout_v",
    "w_resolved_m",
    "l_resolved_m",
    "delvto_v",
    "factuo",
    "w_expected_sigma_m",
    "l_expected_sigma_m",
    "delvto_expected_sigma_v",
    "factuo_expected_sigma",
    "w_normalized_z",
    "l_normalized_z",
    "delvto_normalized_z",
    "factuo_normalized_z",
    "raw_vd_source_current_a",
    "raw_drain_current_entering_device_a",
    "idmag_a",
    "variation_origin",
    "variation_mode",
    "native_profile",
)


class NativeVariationError(RuntimeError):
    """The selected IHP-native variation flow failed validation."""


@dataclass(frozen=True)
class ProcessParameter:
    name: str
    nominal_name: str
    polarity: str
    nominal_value: float
    relative_one_sigma: float
    num_sigmas: float

    @property
    def expected_sigma(self) -> float:
        return abs(self.nominal_value * self.relative_one_sigma / self.num_sigmas)

    @property
    def empirically_variable(self) -> bool:
        # ngspice 47 serializes evaluated gauss() values into the expanded deck
        # with %g. IHP's sole 1e-9 relative entry is therefore below resolution.
        return self.relative_one_sigma > 1e-8


def _prepare_output(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise NativeVariationError(
            f"refusing to overwrite non-empty native-variation directory: {output}"
        )
    for child in ("netlists", "logs", "raw"):
        (output / child).mkdir(parents=True, exist_ok=True)


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _scalar(log: Path, name: str) -> float:
    text = log.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        rf"^{re.escape(name)}\s*=\s*([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        raise NativeVariationError(f"missing scalar {name!r} in ngspice log: {log}")
    value = float(match.group(1))
    if not math.isfinite(value):
        raise NativeVariationError(f"non-finite scalar {name!r} in ngspice log: {log}")
    return value


def _library_section(text: str, section: str) -> str:
    lines: list[str] = []
    active = False
    for line in text.splitlines():
        tokens = line.strip().split()
        if len(tokens) == 2 and tokens[0].lower() == ".lib":
            active = tokens[1].lower() == section.lower()
            continue
        if active and len(tokens) == 2 and tokens[0].lower() == ".endl":
            if tokens[1].lower() != section.lower():
                raise NativeVariationError(f"malformed upstream library section {section}")
            return "\n".join(lines)
        if active:
            lines.append(line)
    raise NativeVariationError(f"upstream library lacks section {section}")


def parse_process_parameters(corner_library: Path, stat_file: Path) -> tuple[ProcessParameter, ...]:
    corner_text = corner_library.read_text(encoding="utf-8")
    stat_text = stat_file.read_text(encoding="utf-8")
    section = _library_section(corner_text, NATIVE_PROCESS_PROFILE)
    nominal_values = {
        match.group(1).lower(): float(match.group(2))
        for match in re.finditer(
            r"(?im)^\s*\.param\s+(\w+)\s*=\s*([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)\s*$",
            section,
        )
    }
    num_sigmas_match = re.search(
        r"(?im)^\s*\.param\s+num_sigmas\s*=\s*([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)",
        stat_text,
    )
    if not num_sigmas_match:
        raise NativeVariationError("upstream statistical file lacks num_sigmas")
    num_sigmas = float(num_sigmas_match.group(1))
    if num_sigmas <= 0.0:
        raise NativeVariationError("upstream num_sigmas must be positive")
    pattern = re.compile(
        r"(?im)^\s*\.param\s+(mc_\w+)\s*=\s*'\s*gauss\(\s*(\w+)\s*,"
        r"\s*([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)\s*,\s*num_sigmas\s*\)\s*'\s*$"
    )
    parameters: list[ProcessParameter] = []
    for match in pattern.finditer(stat_text):
        name = match.group(1).lower()
        nominal_name = match.group(2).lower()
        if nominal_name not in nominal_values:
            raise NativeVariationError(f"missing nominal value for upstream parameter {name}")
        if "_nmos_" in name:
            polarity = "n"
        elif "_pmos_" in name:
            polarity = "p"
        else:
            raise NativeVariationError(f"cannot identify polarity of upstream parameter {name}")
        parameters.append(
            ProcessParameter(
                name=name,
                nominal_name=nominal_name,
                polarity=polarity,
                nominal_value=nominal_values[nominal_name],
                relative_one_sigma=float(match.group(3)),
                num_sigmas=num_sigmas,
            )
        )
    if len(parameters) != 34 or len({item.name for item in parameters}) != 34:
        raise NativeVariationError(
            f"expected 34 upstream low-voltage MOS process parameters, found {len(parameters)}"
        )
    if any(item.expected_sigma <= 0.0 for item in parameters):
        raise NativeVariationError("upstream process parameter has non-positive sigma")
    return tuple(parameters)


def parse_mismatch_parameters(mismatch_file: Path) -> dict[str, dict[str, float]]:
    text = mismatch_file.read_text(encoding="utf-8")
    values = {
        match.group(1).lower(): float(match.group(2))
        for match in re.finditer(
            r"(?im)^\s*\.param\s+(sg13g2_lv_[np]mos_(?:delvto|factuo|dw|dl)_mm)"
            r"\s*=\s*([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)\s*$",
            text,
        )
    }
    expected_names = {
        f"sg13g2_lv_{polarity}mos_{field}_mm"
        for polarity in ("n", "p")
        for field in ("delvto", "factuo", "dw", "dl")
    }
    if set(values) != expected_names or any(value <= 0.0 for value in values.values()):
        raise NativeVariationError("upstream mismatch parameter set is incomplete")
    result: dict[str, dict[str, float]] = {}
    for polarity in ("n", "p"):
        prefix = f"sg13g2_lv_{polarity}mos_"
        result[polarity] = {
            field: values[f"{prefix}{field}_mm"]
            for field in ("delvto", "factuo", "dw", "dl")
        }
    return result


def _osdi_lines(toolchain: Toolchain) -> list[str]:
    return [
        f"pre_osdi {toolchain.osdi_directory / 'psp103.osdi'}",
        f"pre_osdi {toolchain.osdi_directory / 'psp103-nqs.osdi'}",
    ]


def _corner_job(
    toolchain: Toolchain,
    output: Path,
    kit: PlanarKit,
    profile: str,
    polarity: str,
) -> tuple[dict[str, Any], bool]:
    sign = 1.0 if polarity == "n" else -1.0
    vout = 0.5 * kit.vdd_v
    step = 0.005
    geometry_w = kit.width_m
    geometry_l = 2.0 * kit.lmin_m
    criterion = kit.threshold_coefficient_a * geometry_w / geometry_l
    job = f"corner_{profile}_{polarity}"
    raw = output / "raw" / f"{job}.dat"
    netlist = output / "netlists" / f"{job}.cir"
    log = output / "logs" / f"{job}.log"
    lines = [
        f"APM130 IHP-native corner {profile} {polarity}",
        f'.lib "{kit.model_library}" {profile}',
        f'.include "{kit.wrapper_file}"',
        ".temp 27",
        f"Vd d 0 {sign * vout:.17g}",
        "Vg g 0 0",
        "Vs s 0 0",
        "Vb b 0 0",
        (
            f"Xdut d g s b {kit.public_devices[polarity]} "
            f"w={geometry_w:.17g} l={geometry_l:.17g}"
        ),
        ".control",
        *_osdi_lines(toolchain),
        "set numdgt=15",
        "set wr_vecnames",
        "set wr_singlescale",
        f"dc Vg 0 {sign * kit.vdd_v:.17g} {sign * step:.17g}",
        f"wrdata {raw} v(g) i(vd)",
        "quit",
        ".endc",
        ".end",
    ]
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)
    curve = [
        {
            "vctrl_v": abs(values[1]),
            "raw_current_a": values[2],
            "idmag_a": abs(values[2]),
        }
        for values in _read_wrdata(raw, 3)
    ]
    threshold = _threshold_crossing(curve, criterion)
    on = curve[-1]
    conduction = [row for row in curve if row["idmag_a"] >= criterion]
    monotonic = all(
        second["idmag_a"] >= first["idmag_a"] * (1.0 - 1e-10)
        for first, second in zip(conduction, conduction[1:])
    )
    row = {
        "kit_id": "apm130",
        "compact_model": "psp103",
        "public_device": kit.public_devices[polarity],
        "polarity": polarity,
        "temperature_c": 27,
        "w_m": geometry_w,
        "l_m": geometry_l,
        "vout_v": vout,
        "vctrl_on_v": kit.vdd_v,
        "threshold_criterion_a": criterion,
        "threshold_magnitude_v": threshold,
        "raw_vd_source_current_a": on["raw_current_a"],
        "raw_drain_current_entering_device_a": -on["raw_current_a"],
        "idmag_on_a": on["idmag_a"],
        "variation_origin": "native",
        "variation_mode": "corner",
        "native_profile": profile,
        "upstream_library": str(kit.model_library.relative_to(toolchain.root)),
        "raw_file": str(raw.relative_to(output)),
    }
    return row, monotonic


def _device_lines(
    label: str,
    polarity: str,
    public_device: str,
    w_m: float,
    l_m: float,
    vctrl_v: float,
    vout_v: float,
) -> list[str]:
    sign = 1.0 if polarity == "n" else -1.0
    return [
        f"Vd{label} d{label} 0 {sign * vout_v:.17g}",
        f"Vg{label} g{label} 0 {sign * vctrl_v:.17g}",
        f"Vs{label} s{label} 0 0",
        f"Vb{label} b{label} 0 0",
        (
            f"X{label} d{label} g{label} s{label} b{label} {public_device} "
            f"w={w_m:.17g} l={l_m:.17g}"
        ),
    ]


def _process_job(
    toolchain: Toolchain,
    output: Path,
    kit: PlanarKit,
    parameters: tuple[ProcessParameter, ...],
    sample_index: int,
    seed: int,
    *,
    replay: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    suffix = "_replay" if replay else ""
    job = f"process_{sample_index:03d}_seed_{seed}{suffix}"
    netlist = output / "netlists" / f"{job}.cir"
    log = output / "logs" / f"{job}.log"
    w_m = kit.width_m
    l_m = 2.0 * kit.lmin_m
    biases = {"n": 0.4, "p": 0.46}
    lines = [
        f"APM130 IHP-native process sample {sample_index} seed {seed}",
        f".option seed={seed} seedinfo",
        f'.lib "{kit.model_library}" {NATIVE_PROCESS_PROFILE}',
        f'.include "{kit.wrapper_file}"',
        ".temp 27",
    ]
    for polarity in ("n", "p"):
        for instance_index in (1, 2):
            label = f"{polarity}{instance_index}"
            lines.extend(
                _device_lines(
                    label,
                    polarity,
                    kit.public_devices[polarity],
                    w_m,
                    l_m,
                    biases[polarity],
                    0.5 * kit.vdd_v,
                )
            )
    for index, parameter in enumerate(parameters):
        lines.append(f"Bproc{index:02d} proc{index:02d} 0 v='{parameter.name}'")
    lines.extend([".control", *_osdi_lines(toolchain), "set numdgt=15", "op"])
    for polarity in ("n", "p"):
        for instance_index in (1, 2):
            lines.append(f"print i(vd{polarity}{instance_index})")
    for index in range(len(parameters)):
        lines.append(f"print v(proc{index:02d})")
    lines.extend(["quit", ".endc", ".end"])
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)

    sample_rows: list[dict[str, Any]] = []
    for index, parameter in enumerate(parameters):
        resolved = _scalar(log, f"v(proc{index:02d})")
        sample_rows.append(
            {
                "kit_id": "apm130",
                "sample_index": sample_index,
                "seed": seed,
                "polarity": parameter.polarity,
                "parameter_name": parameter.name,
                "nominal_value": parameter.nominal_value,
                "relative_one_sigma": parameter.relative_one_sigma,
                "ngspice_num_sigmas": parameter.num_sigmas,
                "expected_sigma": parameter.expected_sigma,
                "resolved_value": resolved,
                "normalized_z": (resolved - parameter.nominal_value)
                / parameter.expected_sigma,
                "empirical_role": (
                    "sampled_variable"
                    if parameter.empirically_variable
                    else "upstream_negligible_effectively_fixed_in_ngspice47"
                ),
                "variation_origin": "native",
                "variation_mode": "process",
                "native_profile": NATIVE_PROCESS_PROFILE,
                "distribution": "upstream ngspice gauss(nominal, relative, num_sigmas)",
            }
        )
    observations: list[dict[str, Any]] = []
    for polarity in ("n", "p"):
        currents = [
            _scalar(log, f"i(vd{polarity}{instance_index})")
            for instance_index in (1, 2)
        ]
        observations.append(
            {
                "kit_id": "apm130",
                "sample_index": sample_index,
                "seed": seed,
                "polarity": polarity,
                "public_device": kit.public_devices[polarity],
                "temperature_c": 27,
                "w_m": w_m,
                "l_m": l_m,
                "vctrl_v": biases[polarity],
                "vout_v": 0.5 * kit.vdd_v,
                "raw_vd_source_current_1_a": currents[0],
                "raw_vd_source_current_2_a": currents[1],
                "idmag_1_a": abs(currents[0]),
                "idmag_2_a": abs(currents[1]),
                "variation_origin": "native",
                "variation_mode": "process",
                "native_profile": NATIVE_PROCESS_PROFILE,
            }
        )
    return sample_rows, observations


def _mismatch_job(
    toolchain: Toolchain,
    output: Path,
    kit: PlanarKit,
    mismatch_parameters: dict[str, dict[str, float]],
    wrapper: Path,
    sample_index: int,
    seed: int,
    *,
    replay: bool = False,
) -> list[dict[str, Any]]:
    suffix = "_replay" if replay else ""
    job = f"mismatch_{sample_index:03d}_seed_{seed}{suffix}"
    netlist = output / "netlists" / f"{job}.cir"
    log = output / "logs" / f"{job}.log"
    geometries = {
        "small": (kit.width_m, 2.0 * kit.lmin_m),
        "large_4x_area": (2.0 * kit.width_m, 4.0 * kit.lmin_m),
    }
    biases = {"n": 0.4, "p": 0.46}
    devices: list[tuple[str, str, str, int, float, float]] = []
    lines = [
        f"APM130 IHP-native mismatch sample {sample_index} seed {seed}",
        f".option seed={seed} seedinfo",
        f'.lib "{kit.model_library}" {NATIVE_MISMATCH_PROFILE}',
        f'.include "{wrapper}"',
        ".temp 27",
    ]
    for polarity in ("n", "p"):
        for geometry_label, (w_m, l_m) in geometries.items():
            geometry_token = "s" if geometry_label == "small" else "l"
            for instance_index in (1, 2):
                label = f"{polarity}{geometry_token}{instance_index}"
                devices.append(
                    (label, polarity, geometry_label, instance_index, w_m, l_m)
                )
                lines.extend(
                    _device_lines(
                        label,
                        polarity,
                        kit.public_devices[polarity],
                        w_m,
                        l_m,
                        biases[polarity],
                        0.5 * kit.vdd_v,
                    )
                )
    lines.extend([".control", *_osdi_lines(toolchain), "set numdgt=15", "op"])
    for label, polarity, _geometry_label, _instance_index, _w_m, _l_m in devices:
        core = f"@n.x{label}.xapm130_core.nsg13_lv_{polarity}mos"
        lines.append(f"print i(vd{label})")
        for field in ("w", "l", "delvto", "factuo"):
            lines.append(f"print {core}[{field}]")
    lines.extend(["quit", ".endc", ".end"])
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)

    rows: list[dict[str, Any]] = []
    for label, polarity, geometry_label, instance_index, w_m, l_m in devices:
        core = f"@n.x{label}.xapm130_core.nsg13_lv_{polarity}mos"
        raw_current = _scalar(log, f"i(vd{label})")
        resolved = {
            field: _scalar(log, f"{core}[{field}]")
            for field in ("w", "l", "delvto", "factuo")
        }
        coefficients = mismatch_parameters[polarity]
        area_um2 = w_m * l_m * 1e12
        delvto_sigma = coefficients["delvto"] / math.sqrt(area_um2)
        factuo_sigma = coefficients["factuo"] / math.sqrt(area_um2)
        rows.append(
            {
                "kit_id": "apm130",
                "sample_index": sample_index,
                "seed": seed,
                "polarity": polarity,
                "public_device": kit.public_devices[polarity],
                "geometry_label": geometry_label,
                "instance_index": instance_index,
                "temperature_c": 27,
                "w_nominal_m": w_m,
                "l_nominal_m": l_m,
                "area_um2": area_um2,
                "vctrl_v": biases[polarity],
                "vout_v": 0.5 * kit.vdd_v,
                "w_resolved_m": resolved["w"],
                "l_resolved_m": resolved["l"],
                "delvto_v": resolved["delvto"],
                "factuo": resolved["factuo"],
                "w_expected_sigma_m": coefficients["dw"],
                "l_expected_sigma_m": coefficients["dl"],
                "delvto_expected_sigma_v": delvto_sigma,
                "factuo_expected_sigma": factuo_sigma,
                "w_normalized_z": (resolved["w"] - w_m) / coefficients["dw"],
                "l_normalized_z": (resolved["l"] - l_m) / coefficients["dl"],
                "delvto_normalized_z": resolved["delvto"] / delvto_sigma,
                "factuo_normalized_z": (resolved["factuo"] - 1.0) / factuo_sigma,
                "raw_vd_source_current_a": raw_current,
                "raw_drain_current_entering_device_a": -raw_current,
                "idmag_a": abs(raw_current),
                "variation_origin": "native",
                "variation_mode": "mismatch",
                "native_profile": NATIVE_MISMATCH_PROFILE,
            }
        )
    return rows


def _relative_difference(first: float, second: float) -> float:
    return abs(first - second) / max(abs(first), abs(second), 1e-30)


def _correlation(first: list[float], second: list[float]) -> float:
    if len(first) != len(second) or len(first) < 2:
        raise NativeVariationError("correlation requires equal nontrivial cohorts")
    first_mean = statistics.mean(first)
    second_mean = statistics.mean(second)
    numerator = sum(
        (left - first_mean) * (right - second_mean)
        for left, right in zip(first, second)
    )
    first_power = sum((value - first_mean) ** 2 for value in first)
    second_power = sum((value - second_mean) ** 2 for value in second)
    denominator = math.sqrt(first_power * second_power)
    if denominator == 0.0:
        raise NativeVariationError("correlation cohort has zero variance")
    return numerator / denominator


def _process_summary(
    parameters: tuple[ProcessParameter, ...],
    rows: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    parameter_statistics = []
    for parameter in parameters:
        values = [
            row["normalized_z"]
            for row in rows
            if row["parameter_name"] == parameter.name
        ]
        parameter_statistics.append(
            {
                "parameter_name": parameter.name,
                "polarity": parameter.polarity,
                "sample_count": len(values),
                "normalized_mean": statistics.mean(values),
                "normalized_sample_stddev": statistics.stdev(values),
                "empirically_variable": parameter.empirically_variable,
            }
        )
    variable_statistics = [
        item for item in parameter_statistics if item["empirically_variable"]
    ]
    current_statistics = []
    for polarity in ("n", "p"):
        values = [
            row["idmag_1_a"] for row in observations if row["polarity"] == polarity
        ]
        current_statistics.append(
            {
                "polarity": polarity,
                "sample_count": len(values),
                "mean_idmag_a": statistics.mean(values),
                "sample_stddev_idmag_a": statistics.stdev(values),
                "coefficient_of_variation": statistics.stdev(values)
                / statistics.mean(values),
            }
        )
    return {
        "parameter_statistics": parameter_statistics,
        "maximum_absolute_normalized_mean": max(
            abs(item["normalized_mean"]) for item in parameter_statistics
        ),
        "minimum_normalized_sample_stddev": min(
            item["normalized_sample_stddev"] for item in variable_statistics
        ),
        "maximum_normalized_sample_stddev": max(
            item["normalized_sample_stddev"] for item in variable_statistics
        ),
        "empirically_variable_parameter_count": len(variable_statistics),
        "effectively_fixed_parameters": [
            item["parameter_name"]
            for item in parameter_statistics
            if not item["empirically_variable"]
        ],
        "maximum_identical_device_relative_difference": max(
            _relative_difference(
                row["raw_vd_source_current_1_a"],
                row["raw_vd_source_current_2_a"],
            )
            for row in observations
        ),
        "current_statistics": current_statistics,
    }


def _mismatch_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_fields = {
        "w": "w_normalized_z",
        "l": "l_normalized_z",
        "delvto": "delvto_normalized_z",
        "factuo": "factuo_normalized_z",
    }
    group_statistics = []
    for polarity in ("n", "p"):
        for geometry_label in ("small", "large_4x_area"):
            selected = [
                row
                for row in rows
                if row["polarity"] == polarity
                and row["geometry_label"] == geometry_label
            ]
            for variable, field in normalized_fields.items():
                values = [row[field] for row in selected]
                group_statistics.append(
                    {
                        "polarity": polarity,
                        "geometry_label": geometry_label,
                        "variable": variable,
                        "sample_count": len(values),
                        "normalized_mean": statistics.mean(values),
                        "normalized_sample_stddev": statistics.stdev(values),
                    }
                )
    local_correlations = []
    for polarity in ("n", "p"):
        for variable in ("w", "l", "delvto", "factuo"):
            field = normalized_fields[variable]
            cohorts = {
                instance_index: [
                    row[field]
                    for row in rows
                    if row["polarity"] == polarity
                    and row["geometry_label"] == "small"
                    and row["instance_index"] == instance_index
                ]
                for instance_index in (1, 2)
            }
            local_correlations.append(
                {
                    "polarity": polarity,
                    "variable": variable,
                    "pearson_correlation_instance_1_2": _correlation(
                        cohorts[1], cohorts[2]
                    ),
                }
            )
    geometry_scaling = []
    for polarity in ("n", "p"):
        for variable, raw_field in (("delvto", "delvto_v"), ("factuo", "factuo")):
            cohorts = {
                geometry_label: [
                    row[raw_field]
                    for row in rows
                    if row["polarity"] == polarity
                    and row["geometry_label"] == geometry_label
                ]
                for geometry_label in ("small", "large_4x_area")
            }
            geometry_scaling.append(
                {
                    "polarity": polarity,
                    "variable": variable,
                    "small_sample_stddev": statistics.stdev(cohorts["small"]),
                    "large_4x_area_sample_stddev": statistics.stdev(
                        cohorts["large_4x_area"]
                    ),
                    "observed_large_over_small_sigma_ratio": statistics.stdev(
                        cohorts["large_4x_area"]
                    )
                    / statistics.stdev(cohorts["small"]),
                    "upstream_expected_ratio": 0.5,
                }
            )
    return {
        "group_statistics": group_statistics,
        "maximum_absolute_normalized_mean": max(
            abs(item["normalized_mean"]) for item in group_statistics
        ),
        "minimum_normalized_sample_stddev": min(
            item["normalized_sample_stddev"] for item in group_statistics
        ),
        "maximum_normalized_sample_stddev": max(
            item["normalized_sample_stddev"] for item in group_statistics
        ),
        "local_correlations": local_correlations,
        "maximum_absolute_local_correlation": max(
            abs(item["pearson_correlation_instance_1_2"])
            for item in local_correlations
        ),
        "geometry_scaling": geometry_scaling,
    }


def validate_apm130_native(
    output_directory: Path,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    selected = toolchain or resolve_toolchain()
    output = output_directory.expanduser().resolve()
    _prepare_output(output)
    build_models(selected, force=False)
    kit = load_kit("apm130", selected.root)
    if not isinstance(kit, PlanarKit) or kit.model_library is None:
        raise NativeVariationError("APM130 is not configured as the IHP planar PSP kit")
    vendor = selected.root / "models/apm130/vendor/ihp-sg13g2-models"
    stat_file = vendor / "sg13g2_moslv_stat.lib"
    mismatch_file = vendor / "sg13g2_moslv_mismatch.lib"
    mismatch_wrapper = (
        selected.root
        / "models/apm130/ngspice/apm130_native_mismatch_wrappers.inc"
    )
    parameters = parse_process_parameters(kit.model_library, stat_file)
    mismatch_parameters = parse_mismatch_parameters(mismatch_file)

    corner_rows: list[dict[str, Any]] = []
    corner_monotonicity: list[bool] = []
    for profile in NATIVE_CORNER_PROFILES:
        for polarity in ("n", "p"):
            row, monotonic = _corner_job(selected, output, kit, profile, polarity)
            corner_rows.append(row)
            corner_monotonicity.append(monotonic)

    process_rows: list[dict[str, Any]] = []
    process_observations: list[dict[str, Any]] = []
    seeds = tuple(NATIVE_BASE_SEED + index for index in range(NATIVE_SAMPLE_COUNT))
    for sample_index, seed in enumerate(seeds):
        rows, observations = _process_job(
            selected, output, kit, parameters, sample_index, seed
        )
        process_rows.extend(rows)
        process_observations.extend(observations)
    process_replay_rows, process_replay_observations = _process_job(
        selected,
        output,
        kit,
        parameters,
        0,
        seeds[0],
        replay=True,
    )

    mismatch_rows: list[dict[str, Any]] = []
    for sample_index, seed in enumerate(seeds):
        mismatch_rows.extend(
            _mismatch_job(
                selected,
                output,
                kit,
                mismatch_parameters,
                mismatch_wrapper,
                sample_index,
                seed,
            )
        )
    mismatch_replay_rows = _mismatch_job(
        selected,
        output,
        kit,
        mismatch_parameters,
        mismatch_wrapper,
        0,
        seeds[0],
        replay=True,
    )

    corner_path = output / "native_corners.csv"
    process_path = output / "native_process_samples.csv"
    process_observation_path = output / "native_process_observations.csv"
    mismatch_path = output / "native_mismatch_samples.csv"
    _write_csv(corner_path, CORNER_FIELDS, corner_rows)
    _write_csv(process_path, PROCESS_SAMPLE_FIELDS, process_rows)
    _write_csv(
        process_observation_path,
        PROCESS_OBSERVATION_FIELDS,
        process_observations,
    )
    _write_csv(mismatch_path, MISMATCH_SAMPLE_FIELDS, mismatch_rows)

    process_summary = _process_summary(parameters, process_rows, process_observations)
    mismatch_summary = _mismatch_summary(mismatch_rows)
    corners_by_key = {
        (row["native_profile"], row["polarity"]): row for row in corner_rows
    }
    corner_direction_checks: dict[str, bool] = {}
    for polarity in ("n", "p"):
        typical = corners_by_key[("mos_tt", polarity)]["idmag_on_a"]
        speed = CORNER_SPEED_PROFILES[polarity]
        corner_direction_checks[f"{polarity}_slow_below_typical"] = all(
            corners_by_key[(profile, polarity)]["idmag_on_a"] < typical
            for profile in speed["slow"]
        )
        corner_direction_checks[f"{polarity}_fast_above_typical"] = all(
            corners_by_key[(profile, polarity)]["idmag_on_a"] > typical
            for profile in speed["fast"]
        )

    process_first = [row for row in process_rows if row["sample_index"] == 0]
    process_second = [row for row in process_rows if row["sample_index"] == 1]
    process_observation_first = [
        row for row in process_observations if row["sample_index"] == 0
    ]
    mismatch_first = [row for row in mismatch_rows if row["sample_index"] == 0]
    mismatch_second = [row for row in mismatch_rows if row["sample_index"] == 1]
    process_signs = all(
        (row["polarity"] == "n" and row["raw_vd_source_current_1_a"] < 0.0)
        or (row["polarity"] == "p" and row["raw_vd_source_current_1_a"] > 0.0)
        for row in process_observations
    )
    mismatch_signs = all(
        (row["polarity"] == "n" and row["raw_vd_source_current_a"] < 0.0)
        or (row["polarity"] == "p" and row["raw_vd_source_current_a"] > 0.0)
        for row in mismatch_rows
    )
    corner_signs = all(
        (row["polarity"] == "n" and row["raw_vd_source_current_a"] < 0.0)
        or (row["polarity"] == "p" and row["raw_vd_source_current_a"] > 0.0)
        for row in corner_rows
    )
    mismatch_pair_difference_fraction = statistics.mean(
        [
            any(
                not math.isclose(
                    first["idmag_a"],
                    second["idmag_a"],
                    rel_tol=1e-12,
                    abs_tol=0.0,
                )
                for first, second in zip(
                    [
                        row
                        for row in mismatch_rows
                        if row["seed"] == seed and row["instance_index"] == 1
                    ],
                    [
                        row
                        for row in mismatch_rows
                        if row["seed"] == seed and row["instance_index"] == 2
                    ],
                )
            )
            for seed in seeds
        ]
    )

    log_files = sorted((output / "logs").glob("*.log"))
    critical_tokens = (
        "fatal error",
        "error:",
        "warning",
        "convergence",
        "timestep too small",
        "singular matrix",
        "unknown parameter",
        "unsupported parameter",
    )
    log_hits = []
    incomplete_logs = []
    for log in log_files:
        text = log.read_text(encoding="utf-8", errors="replace").lower()
        if "ngspice-47 done" not in text:
            incomplete_logs.append(log.name)
        for token in critical_tokens:
            if token in text:
                log_hits.append({"log": log.name, "token": token})

    requirements = {
        "five_native_corner_profiles_executed": {
            (row["native_profile"], row["polarity"]) for row in corner_rows
        }
        == {
            (profile, polarity)
            for profile in NATIVE_CORNER_PROFILES
            for polarity in ("n", "p")
        },
        "corner_curves_finite_monotonic_and_thresholded": all(corner_monotonicity)
        and all(
            0.0 < row["threshold_magnitude_v"] < kit.vdd_v
            and row["idmag_on_a"] > 0.0
            for row in corner_rows
        ),
        "upstream_corner_speed_directions": all(corner_direction_checks.values()),
        "corner_raw_current_signs": corner_signs,
        "process_profile_and_parameter_count": len(parameters) == 34
        and len(process_rows) == NATIVE_SAMPLE_COUNT * len(parameters)
        and process_summary["empirically_variable_parameter_count"] == 33
        and process_summary["effectively_fixed_parameters"]
        == ["mc_sg13g2_lv_pmos_dphiblw"],
        "process_parameter_normalized_means": process_summary[
            "maximum_absolute_normalized_mean"
        ]
        < 0.4,
        "process_parameter_normalized_spread": process_summary[
            "minimum_normalized_sample_stddev"
        ]
        > 0.7
        and process_summary["maximum_normalized_sample_stddev"] < 1.3,
        "process_model_global_sharing": process_summary[
            "maximum_identical_device_relative_difference"
        ]
        < 1e-12,
        "process_current_nonzero_spread": all(
            item["coefficient_of_variation"] > 1e-4
            for item in process_summary["current_statistics"]
        ),
        "process_same_seed_replay": process_first == process_replay_rows
        and process_observation_first == process_replay_observations,
        "process_different_seeds_differ": process_first != process_second,
        "process_raw_current_signs": process_signs,
        "mismatch_sample_count": len(mismatch_rows) == NATIVE_SAMPLE_COUNT * 8,
        "mismatch_normalized_means": mismatch_summary[
            "maximum_absolute_normalized_mean"
        ]
        < 0.4,
        "mismatch_normalized_spread": mismatch_summary[
            "minimum_normalized_sample_stddev"
        ]
        > 0.7
        and mismatch_summary["maximum_normalized_sample_stddev"] < 1.3,
        "mismatch_local_independence": mismatch_summary[
            "maximum_absolute_local_correlation"
        ]
        < 0.3,
        "mismatch_fourfold_area_sigma_scaling": all(
            0.35 < item["observed_large_over_small_sigma_ratio"] < 0.7
            for item in mismatch_summary["geometry_scaling"]
        ),
        "mismatch_same_seed_replay": mismatch_first == mismatch_replay_rows,
        "mismatch_different_seeds_differ": mismatch_first != mismatch_second,
        "mismatch_local_terminal_difference": mismatch_pair_difference_fraction > 0.99,
        "mismatch_raw_current_signs": mismatch_signs,
        "native_identity_separate_from_benchmark": all(
            row["variation_origin"] == "native"
            for row in [*corner_rows, *process_rows, *mismatch_rows]
        ),
        "native_combined_all_not_invented": "all" not in NATIVE_MODES,
        "all_real_ngspice_logs_clean": len(log_files)
        == 2 * len(NATIVE_CORNER_PROFILES) + 2 * NATIVE_SAMPLE_COUNT + 2
        and not log_hits
        and not incomplete_logs,
    }
    checks = {
        "requirements": requirements,
        "overall_pass": all(requirements.values()),
    }
    artifacts = {
        path.name: sha256_file(path)
        for path in (
            corner_path,
            process_path,
            process_observation_path,
            mismatch_path,
        )
    }
    source_files = (
        kit.model_library,
        stat_file,
        mismatch_file,
        vendor / "sg13g2_moslv_parm.lib",
        vendor / "sg13g2_moslv_mod.lib",
        vendor / "sg13g2_moslv_mod_mismatch.lib",
        kit.wrapper_file,
        mismatch_wrapper,
    )
    report = {
        "schema": "apm.native-variation-validation.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "validated" if checks["overall_pass"] else "checks_failed",
        "kit_id": "apm130",
        "compact_model": "psp103",
        "model_revision": kit.provenance_revision,
        "simulator_backend": "ngspice",
        "simulator_version": "ngspice-47",
        "variation_origin": "native",
        "selected_upstream_profiles": {
            "corners": list(NATIVE_CORNER_PROFILES),
            "process": NATIVE_PROCESS_PROFILE,
            "mismatch": NATIVE_MISMATCH_PROFILE,
            "combined_all": None,
            "combined_all_status": (
                "not exposed by the selected upstream statistical deck and intentionally not invented"
            ),
        },
        "native_random_sampling": {
            "owner": "ngspice evaluation of upstream gauss/agauss expressions",
            "seed_control": ".option seed=<integer>",
            "python_sampling": False,
            "sample_count_per_random_mode": NATIVE_SAMPLE_COUNT,
            "base_seed": NATIVE_BASE_SEED,
            "seeds": list(seeds),
            "same_seed_replay_seed": seeds[0],
        },
        "upstream_semantics": {
            "process": (
                "34 independent model-global low-voltage N/P parameter gauss expressions; "
                "num_sigmas=1 in sg13g2_moslv_stat.lib. The sole 1e-9 relative "
                "PMOS dphiblw entry is retained but resolves nominal at ngspice 47's "
                "expanded-deck numeric precision; 33 parameters are empirically variable"
            ),
            "mismatch": (
                "instance-local agauss draws for w, l, delvto, and factuo with mm_ok=1; "
                "delvto/factuo sigma scales as 1/sqrt(W*L in um^2)"
            ),
            "public_geometry": "APM wrapper remains d,g,s,b with only w,l; upstream controls fixed",
        },
        "corner_direction_checks": corner_direction_checks,
        "process_summary": process_summary,
        "mismatch_summary": mismatch_summary,
        "mismatch_pair_difference_fraction": mismatch_pair_difference_fraction,
        "artifact_sha256": artifacts,
        "source_sha256": {
            str(path.relative_to(selected.root)): sha256_file(path) for path in source_files
        },
        "simulator_logs": {
            "count": len(log_files),
            "critical_hits": log_hits,
            "incomplete": incomplete_logs,
        },
        "checks": checks,
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["output_directory"] = str(output)
    report["report_path"] = str(report_path)
    if not checks["overall_pass"]:
        failed = [name for name, passed in requirements.items() if not passed]
        raise NativeVariationError(
            f"IHP-native variation checks failed ({', '.join(failed)}); see {report_path}"
        )
    return report
