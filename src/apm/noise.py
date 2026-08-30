# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Stationary small-signal MOS-noise characterization for the V3-N0 spike."""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

from .catalog import DeviceSpec, FamilySpec, load_catalog
from .characterize import (
    NGSPICE_GMIN_S,
    CharacterizationKit,
    FinFETGeometry,
    PlanarGeometry,
    load_family,
)
from .model_build import build_models, sha256_file
from .noise_fit import fit_noise_spectrum, integrate_psd
from .noise_provenance import (
    SHOWMOD_BEGIN,
    SHOWMOD_END,
    build_noise_model_snapshot,
    showmod_control_line,
)
from .paths import repository_root, state_directory
from .toolchain import Toolchain, ToolchainError, resolve_toolchain, run_checked

NOISE_SCHEMA = "apm.noise-characterization.v1"
NOISE_METHOD_ID = "apm.stationary-short-circuit-drain-noise"
NOISE_METHOD_VERSION = "1.0.0"
PROBE_METHOD_ID = "apm.ccvs-current-probe-1ohm"
PROBE_METHOD_VERSION = "1.0.0"
BIAS_METHOD_ID = "apm.gm-id-bounded-secant-finite-difference"
BIAS_METHOD_VERSION = "1.0.0"
FREQUENCY_PROFILE_ID = "v3-n0-provisional-1hz-100mhz-20ppd"
DEFAULT_TEMPERATURE_C = 27
DEFAULT_GM_OVER_ID_TARGET = 15.0
DEFAULT_GM_OVER_ID_RELATIVE_TOLERANCE = 0.01
DEFAULT_VOUT_FRACTION = 0.5
DEFAULT_L_OVER_LMIN = 2.0
DEFAULT_FREQUENCY_START_HZ = 1.0
DEFAULT_FREQUENCY_STOP_HZ = 1.0e8
DEFAULT_POINTS_PER_DECADE = 20
MAX_BIAS_ITERATIONS = 20
FINITE_DIFFERENCE_RELATIVE_TOLERANCE = 0.02
NATIVE_ORACLE_RELATIVE_TOLERANCE = 0.02


class NoiseCharacterizationError(RuntimeError):
    """A noise result cannot satisfy the fail-closed V3-N0 contract."""


NoiseGeometry = Union[PlanarGeometry, FinFETGeometry]


@dataclass(frozen=True)
class ResolvedNoiseDevice:
    selector: str
    family: FamilySpec
    device: DeviceSpec
    kit: CharacterizationKit
    polarity: str
    geometry: NoiseGeometry
    temperature_c: int
    vout_v: float


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv_write(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _prepare_output(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.exists() and any(resolved.iterdir()):
        raise NoiseCharacterizationError(f"refusing to overwrite non-empty output: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    for name in ("netlists", "logs", "raw"):
        (resolved / name).mkdir(exist_ok=True)
    return resolved


def _default_output(selector: str, root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    token = selector.replace("/", "-")
    return state_directory(root) / "results" / f"noise-{token}-{timestamp}"


def _float_token(value: float) -> str:
    return f"{value:.9g}".replace("-", "m").replace(".", "p").replace("+", "p")


def _read_wrdata(path: Path, expected_columns: int | None = None) -> tuple[list[str], list[list[float]]]:
    if not path.is_file():
        raise NoiseCharacterizationError(f"ngspice did not create expected data file: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        raise NoiseCharacterizationError(f"ngspice data file is empty: {path}")
    header = lines[0].split()
    rows: list[list[float]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        try:
            values = [float(token) for token in line.split()]
        except ValueError as error:
            raise NoiseCharacterizationError(f"malformed numeric row in {path}: {line}") from error
        if expected_columns is not None and len(values) != expected_columns:
            raise NoiseCharacterizationError(
                f"expected {expected_columns} columns in {path}, found {len(values)}"
            )
        if len(values) != len(header):
            raise NoiseCharacterizationError(
                f"header/data column mismatch in {path}: {len(header)} versus {len(values)}"
            )
        rows.append(values)
    if not rows:
        raise NoiseCharacterizationError(f"ngspice produced no numeric rows in {path}")
    return header, rows


def _run_ngspice(toolchain: Toolchain, netlist: Path, log: Path) -> list[str]:
    command = [toolchain.ngspice, "-n", "-b", "-o", log, netlist]
    result = run_checked(command, environment=toolchain.environment(), cwd=netlist.parent.parent)
    text = log.read_text(encoding="utf-8", errors="replace")
    if "ngspice-47 done" not in text:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ToolchainError(f"ngspice did not complete {netlist}: {detail}")
    audit_ngspice_log(text, require_sparse=True)
    return [str(item) for item in command]


def audit_ngspice_log(log_text: str, *, require_sparse: bool) -> dict[str, Any]:
    lowered = log_text.lower()
    critical_patterns = (
        r"fatal(?: error)?:",
        r"error:",
        r"simulation interrupted",
        r"no convergence",
        r"timestep too small",
        r"singular matrix",
        r"not supported",
        r"unsupported",
        r"unknown parameter",
        r"no such model",
    )
    critical = [
        line.strip()
        for line in log_text.splitlines()
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in critical_patterns)
    ]
    if critical:
        raise NoiseCharacterizationError(
            "ngspice log contains critical/unsupported diagnostics: " + "; ".join(critical[:8])
        )
    sparse_lines = [line.strip() for line in log_text.splitlines() if "using sparse" in line.lower()]
    klu_lines = [
        line.strip()
        for line in log_text.splitlines()
        if "using klu" in line.lower() or "klu as direct linear solver" in line.lower()
    ]
    if klu_lines:
        raise NoiseCharacterizationError("KLU was used by a required noise job")
    if require_sparse and not sparse_lines:
        raise NoiseCharacterizationError("required ngspice job did not attest the Sparse solver")
    warnings = [line.strip() for line in log_text.splitlines() if "warning" in line.lower()]
    return {
        "status": "pass",
        "required_solver": "Sparse",
        "sparse_attestations": sparse_lines,
        "klu_attestations": klu_lines,
        "warnings": warnings,
        "critical_diagnostics": critical,
        "nan_token_present": bool(re.search(r"(?<![A-Za-z])nan(?![A-Za-z])", lowered)),
    }


def resolve_noise_device(
    selector: str,
    root: Path,
    *,
    operating_profile_id: str | None = None,
    temperature_c: int = DEFAULT_TEMPERATURE_C,
) -> ResolvedNoiseDevice:
    catalog = load_catalog(root)
    resolved = catalog.resolve(selector)
    if not isinstance(resolved, DeviceSpec):
        raise NoiseCharacterizationError("noise selector must resolve to one public device")
    family = catalog.family(resolved.technology_id, resolved.family_id)
    kit = load_family(family.selector, root, operating_profile_id)
    if resolved.polarity not in kit.polarities:
        raise NoiseCharacterizationError(f"{selector}: device polarity is not bound for ngspice")
    l_m = DEFAULT_L_OVER_LMIN * resolved.lmin_m
    if resolved.lmax_m is not None and l_m > resolved.lmax_m:
        raise NoiseCharacterizationError(f"{selector}: L/Lmin=2 exceeds the recorded model range")
    if resolved.geometry_kind == "planar":
        if resolved.default_w_m is None:
            raise NoiseCharacterizationError(f"{selector}: planar default width is missing")
        geometry: NoiseGeometry = PlanarGeometry(l_m=l_m, w_m=resolved.default_w_m)
    elif resolved.geometry_kind == "finfet":
        geometry = FinFETGeometry(l_m=l_m, nfin=1)
    else:
        raise NoiseCharacterizationError(
            f"{selector}: unsupported geometry kind {resolved.geometry_kind!r}"
        )
    return ResolvedNoiseDevice(
        selector=selector,
        family=family,
        device=resolved,
        kit=kit,
        polarity=resolved.polarity,
        geometry=geometry,
        temperature_c=temperature_c,
        vout_v=DEFAULT_VOUT_FRACTION * kit.vdd_v,
    )


def _netlist_prefix(resolved: ResolvedNoiseDevice) -> list[str]:
    return [
        *resolved.kit.model_directives(),
        f'.include "{resolved.kit.wrapper_file}"',
        f".options gmin={NGSPICE_GMIN_S:.12g} klu=0",
        f".temp {resolved.temperature_c}",
    ]


def _control_osdi(resolved: ResolvedNoiseDevice, toolchain: Toolchain) -> list[str]:
    return [
        f"pre_osdi {toolchain.osdi_directory / artifact}"
        for artifact in resolved.kit.osdi_artifacts
    ]


def _coarse_bias_sweep(
    resolved: ResolvedNoiseDevice, toolchain: Toolchain, output: Path
) -> dict[str, Any]:
    kit = resolved.kit
    sign = 1.0 if resolved.polarity == "n" else -1.0
    points = max(kit.idvg_points, 101)
    step = kit.vdd_v / (points - 1)
    job = "bias_coarse"
    netlist = output / "netlists" / f"{job}.cir"
    log = output / "logs" / f"{job}.log"
    raw = output / "raw" / f"{job}.dat"
    native_gm = kit.native_vector(resolved.polarity, "gm")
    native_gds = kit.native_vector(resolved.polarity, "gds")
    lines = [
        "APM V3-N0 coarse gm/Id bracket",
        *_netlist_prefix(resolved),
        f"Vd d 0 {kit.raw_voltage(resolved.polarity, resolved.vout_v):.12g}",
        "Vg g 0 0",
        "Vs s 0 0",
        "Vb b 0 0",
        (
            f"Xdut d g s b {resolved.device.public_name} "
            f"{resolved.geometry.netlist_parameters()}"
        ),
        ".control",
        *_control_osdi(resolved, toolchain),
        "set wr_vecnames",
        "set wr_singlescale",
        f"save all {native_gm} {native_gds}",
        f"dc Vg 0 {sign * kit.vdd_v:.12g} {sign * step:.12g}",
        f"wrdata {raw} v(g) i(vd) {native_gm} {native_gds}",
        "quit",
        ".endc",
        ".end",
    ]
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    command = _run_ngspice(toolchain, netlist, log)
    _header, values = _read_wrdata(raw, 5)
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(values):
        rows.append(
            {
                "index": index,
                "vctrl_v": abs(row[1]),
                "raw_vgs_v": row[1],
                "raw_vd_source_current_a": row[2],
                "idmag_a": abs(row[2]),
                "native_gm_s": abs(row[3]),
                "native_gds_s": abs(row[4]),
            }
        )
    metrics: list[dict[str, Any]] = []
    for index in range(1, len(rows) - 1):
        gm = (rows[index + 1]["idmag_a"] - rows[index - 1]["idmag_a"]) / (2.0 * step)
        current = rows[index]["idmag_a"]
        gm_over_id = gm / current if current > 1e-30 and gm > 0.0 else math.nan
        metrics.append({**rows[index], "coarse_gm_s": gm, "coarse_gm_over_id_per_v": gm_over_id})
    return {
        "method": "manifest-profile DC sweep used only to bracket/refine, never as final row",
        "point_count": points,
        "step_v": step,
        "rows": metrics,
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "raw_file": str(raw.relative_to(output)),
        "command": command,
    }


def _precise_bias_evaluation(
    resolved: ResolvedNoiseDevice,
    toolchain: Toolchain,
    output: Path,
    vctrl_v: float,
    evaluation_id: int,
) -> dict[str, Any]:
    kit = resolved.kit
    sign = 1.0 if resolved.polarity == "n" else -1.0
    gm_step = min(
        max(kit.vdd_v * 2.0e-4, 1.0e-6),
        vctrl_v / 4.0,
        (kit.vdd_v - vctrl_v) / 4.0,
    )
    if gm_step <= 1.0e-9:
        raise NoiseCharacterizationError("gm/Id candidate is too close to a legal bias endpoint")
    gds_step = min(kit.vdd_v * 1.0e-3, resolved.vout_v / 4.0)
    token = f"bias_refine_{evaluation_id:02d}_{_float_token(vctrl_v)}"
    netlist = output / "netlists" / f"{token}.cir"
    log = output / "logs" / f"{token}.log"
    gm_raw = output / "raw" / f"{token}_gm.dat"
    gds_raw = output / "raw" / f"{token}_gds.dat"
    native_gm = kit.native_vector(resolved.polarity, "gm")
    native_gds = kit.native_vector(resolved.polarity, "gds")
    raw_vout = kit.raw_voltage(resolved.polarity, resolved.vout_v)
    lines = [
        "APM V3-N0 precise gm/gds finite differences",
        *_netlist_prefix(resolved),
        f"Vd d 0 {raw_vout:.12g}",
        f"Vg g 0 {kit.raw_voltage(resolved.polarity, vctrl_v):.12g}",
        "Vs s 0 0",
        "Vb b 0 0",
        (
            f"Xdut d g s b {resolved.device.public_name} "
            f"{resolved.geometry.netlist_parameters()}"
        ),
        ".control",
        *_control_osdi(resolved, toolchain),
        "set wr_vecnames",
        "set wr_singlescale",
        f"save all {native_gm} {native_gds}",
        (
            f"dc Vg {sign * (vctrl_v - 2.0 * gm_step):.12g} "
            f"{sign * (vctrl_v + 2.0 * gm_step):.12g} {sign * gm_step:.12g}"
        ),
        f"wrdata {gm_raw} v(g) i(vd) {native_gm} {native_gds}",
        f"alter Vg = {sign * vctrl_v:.12g}",
        (
            f"dc Vd {sign * (resolved.vout_v - 2.0 * gds_step):.12g} "
            f"{sign * (resolved.vout_v + 2.0 * gds_step):.12g} {sign * gds_step:.12g}"
        ),
        f"wrdata {gds_raw} v(d) i(vd) {native_gm} {native_gds}",
        "quit",
        ".endc",
        ".end",
    ]
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    command = _run_ngspice(toolchain, netlist, log)
    _gm_header, gm_values = _read_wrdata(gm_raw, 5)
    _gds_header, gds_values = _read_wrdata(gds_raw, 5)
    if len(gm_values) != 5 or len(gds_values) != 5:
        raise NoiseCharacterizationError("precise finite-difference sweeps must each have five rows")
    gm_currents = [abs(row[2]) for row in gm_values]
    gds_currents = [abs(row[2]) for row in gds_values]
    gm_first = (gm_currents[3] - gm_currents[1]) / (2.0 * gm_step)
    gm_second = (gm_currents[4] - gm_currents[0]) / (4.0 * gm_step)
    gds_first = (gds_currents[3] - gds_currents[1]) / (2.0 * gds_step)
    gds_second = (gds_currents[4] - gds_currents[0]) / (4.0 * gds_step)
    current = gm_currents[2]
    if current <= 0.0 or gm_first <= 0.0:
        gm_over_id = math.nan
    else:
        gm_over_id = gm_first / current
    relative = lambda first, second: abs(first - second) / max(abs(first), abs(second), 1e-30)
    return {
        "evaluation_id": evaluation_id,
        "vctrl_v": vctrl_v,
        "vout_v": resolved.vout_v,
        "raw_vgs_v": gm_values[2][1],
        "raw_vds_v": gds_values[2][1],
        "raw_vd_source_current_a": gm_values[2][2],
        "raw_drain_current_entering_device_a": -gm_values[2][2],
        "idmag_a": current,
        "gm_s": gm_first,
        "gm_second_step_s": gm_second,
        "gm_step_v": gm_step,
        "gm_second_step_v": 2.0 * gm_step,
        "gm_convergence_relative": relative(gm_first, gm_second),
        "gds_s": gds_first,
        "gds_second_step_s": gds_second,
        "gds_step_v": gds_step,
        "gds_second_step_v": 2.0 * gds_step,
        "gds_convergence_relative": relative(gds_first, gds_second),
        "gm_over_id_per_v": gm_over_id,
        "gm_over_gds": gm_first / gds_first if gds_first > 0.0 else None,
        "native_gm_s": abs(gm_values[2][3]),
        "native_gds_s": abs(gm_values[2][4]),
        "native_gm_relative_error": relative(gm_first, abs(gm_values[2][3])),
        "native_gds_relative_error": relative(gds_first, abs(gm_values[2][4])),
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "raw_gm_file": str(gm_raw.relative_to(output)),
        "raw_gds_file": str(gds_raw.relative_to(output)),
        "command": command,
    }


def resolve_gm_over_id_bias(
    resolved: ResolvedNoiseDevice,
    toolchain: Toolchain,
    output: Path,
    *,
    target_per_v: float = DEFAULT_GM_OVER_ID_TARGET,
    relative_tolerance: float = DEFAULT_GM_OVER_ID_RELATIVE_TOLERANCE,
) -> dict[str, Any]:
    coarse = _coarse_bias_sweep(resolved, toolchain, output)
    usable = [
        row
        for row in coarse["rows"]
        if math.isfinite(row["coarse_gm_over_id_per_v"])
        and row["coarse_gm_over_id_per_v"] > 0.0
    ]
    pairs = [
        (first, second)
        for first, second in zip(usable, usable[1:])
        if (first["coarse_gm_over_id_per_v"] - target_per_v)
        * (second["coarse_gm_over_id_per_v"] - target_per_v)
        <= 0.0
    ]
    if not pairs:
        failure = {
            "schema": "apm.noise-bias-resolution.v1",
            "method_id": BIAS_METHOD_ID,
            "method_version": BIAS_METHOD_VERSION,
            "status": "target_not_reachable",
            "reason": "coarse_sweep_did_not_bracket_target",
            "target_per_v": target_per_v,
            "relative_tolerance": relative_tolerance,
            "coarse_sweep": coarse,
            "evaluations": [],
            "final": None,
        }
        _json_write(output / "bias_resolution.json", failure)
        raise NoiseCharacterizationError(
            f"{resolved.selector}: gm/Id target {target_per_v:g} 1/V is not bracketed"
        )
    pairs.sort(
        key=lambda pair: abs(
            0.5
            * (pair[0]["coarse_gm_over_id_per_v"] + pair[1]["coarse_gm_over_id_per_v"])
            - target_per_v
        )
    )
    evaluations: list[dict[str, Any]] = []
    cache: dict[float, dict[str, Any]] = {}

    def evaluate(vctrl: float) -> dict[str, Any]:
        key = round(vctrl, 15)
        if key not in cache:
            item = _precise_bias_evaluation(
                resolved, toolchain, output, vctrl, len(evaluations) + 1
            )
            item["target_per_v"] = target_per_v
            item["relative_target_error"] = abs(item["gm_over_id_per_v"] - target_per_v) / target_per_v
            evaluations.append(item)
            cache[key] = item
        return cache[key]

    bracket: tuple[dict[str, Any], dict[str, Any]] | None = None
    coarse_pair: tuple[dict[str, Any], dict[str, Any]] | None = None
    for first, second in pairs:
        left = evaluate(first["vctrl_v"])
        right = evaluate(second["vctrl_v"])
        if not math.isfinite(left["gm_over_id_per_v"]) or not math.isfinite(
            right["gm_over_id_per_v"]
        ):
            continue
        if (left["gm_over_id_per_v"] - target_per_v) * (
            right["gm_over_id_per_v"] - target_per_v
        ) <= 0.0:
            bracket = (left, right)
            coarse_pair = (first, second)
            break
    if bracket is None or coarse_pair is None:
        failure = {
            "schema": "apm.noise-bias-resolution.v1",
            "method_id": BIAS_METHOD_ID,
            "method_version": BIAS_METHOD_VERSION,
            "status": "target_not_reachable",
            "reason": "precise_finite_differences_invalidated_coarse_bracket",
            "target_per_v": target_per_v,
            "relative_tolerance": relative_tolerance,
            "coarse_sweep": coarse,
            "evaluations": evaluations,
            "final": None,
        }
        _json_write(output / "bias_resolution.json", failure)
        raise NoiseCharacterizationError(
            f"{resolved.selector}: precise finite differences invalidated the coarse gm/Id bracket"
        )
    best = min(bracket, key=lambda item: item["relative_target_error"])
    refinement_goal = min(relative_tolerance, 0.001)
    for _iteration in range(MAX_BIAS_ITERATIONS):
        if best["relative_target_error"] <= refinement_goal:
            break
        left, right = bracket
        left_f = left["gm_over_id_per_v"] - target_per_v
        right_f = right["gm_over_id_per_v"] - target_per_v
        if right_f == left_f:
            candidate = 0.5 * (left["vctrl_v"] + right["vctrl_v"])
        else:
            candidate = right["vctrl_v"] - right_f * (
                right["vctrl_v"] - left["vctrl_v"]
            ) / (right_f - left_f)
        lower = min(left["vctrl_v"], right["vctrl_v"])
        upper = max(left["vctrl_v"], right["vctrl_v"])
        margin = 0.05 * (upper - lower)
        if not lower + margin < candidate < upper - margin:
            candidate = 0.5 * (lower + upper)
        item = evaluate(candidate)
        item_f = item["gm_over_id_per_v"] - target_per_v
        if left_f * item_f <= 0.0:
            bracket = (left, item)
        else:
            bracket = (item, right)
        if item["relative_target_error"] < best["relative_target_error"]:
            best = item
    finite_difference_pass = (
        best["gm_convergence_relative"] < FINITE_DIFFERENCE_RELATIVE_TOLERANCE
        and best["gds_convergence_relative"] < FINITE_DIFFERENCE_RELATIVE_TOLERANCE
    )
    native_oracle_pass = (
        best["native_gm_relative_error"] < NATIVE_ORACLE_RELATIVE_TOLERANCE
        and best["native_gds_relative_error"] < NATIVE_ORACLE_RELATIVE_TOLERANCE
    )
    if best["relative_target_error"] > relative_tolerance:
        status = "failed_tolerance"
    elif not finite_difference_pass:
        status = "failed_finite_difference_convergence"
    elif not native_oracle_pass:
        status = "failed_native_oracle_agreement"
    else:
        status = "resolved"
    result = {
        "schema": "apm.noise-bias-resolution.v1",
        "method_id": BIAS_METHOD_ID,
        "method_version": BIAS_METHOD_VERSION,
        "status": status,
        "target_per_v": target_per_v,
        "relative_tolerance": relative_tolerance,
        "achieved_per_v": best["gm_over_id_per_v"],
        "relative_target_error": best["relative_target_error"],
        "iteration_count": len(evaluations),
        "finite_difference_validation": {
            "status": "pass" if finite_difference_pass else "fail",
            "relative_tolerance": FINITE_DIFFERENCE_RELATIVE_TOLERANCE,
            "gm_relative_change": best["gm_convergence_relative"],
            "gds_relative_change": best["gds_convergence_relative"],
        },
        "native_oracle_validation": {
            "status": "pass" if native_oracle_pass else "fail",
            "relative_tolerance": NATIVE_ORACLE_RELATIVE_TOLERANCE,
            "gm_relative_error": best["native_gm_relative_error"],
            "gds_relative_error": best["native_gds_relative_error"],
        },
        "coarse_bracket": {
            "vctrl_v": [coarse_pair[0]["vctrl_v"], coarse_pair[1]["vctrl_v"]],
            "coarse_gm_over_id_per_v": [
                coarse_pair[0]["coarse_gm_over_id_per_v"],
                coarse_pair[1]["coarse_gm_over_id_per_v"],
            ],
        },
        "coarse_sweep": coarse,
        "evaluations": evaluations,
        "final": best,
    }
    _json_write(output / "bias_resolution.json", result)
    if status != "resolved":
        raise NoiseCharacterizationError(
            f"{resolved.selector}: bias resolution failed with status {status}; "
            f"gm/Id target error={best['relative_target_error']:.3%}"
        )
    return result


def _noise_wrdata(path: Path) -> tuple[list[dict[str, float]], dict[str, list[float]]]:
    header, rows = _read_wrdata(path)
    indexed_names: list[str] = []
    counts: dict[str, int] = {}
    for name in header:
        count = counts.get(name, 0)
        indexed_names.append(name if count == 0 else f"{name}#{count + 1}")
        counts[name] = count + 1
    records = [dict(zip(indexed_names, row)) for row in rows]
    if "onoise_spectrum" not in records[0] or "inoise_spectrum" not in records[0]:
        raise NoiseCharacterizationError("ngspice noise plot omitted canonical total vectors")
    source_names = [
        name
        for name in indexed_names
        if name.startswith("onoise") and name != "onoise_spectrum"
    ]
    breakdown = {name: [record[name] for record in records] for name in source_names}
    return records, breakdown


def canonical_noise_observables(
    output_psd_v2_per_hz: float, ccvs_output_real_v: float, ccvs_output_imag_v: float
) -> dict[str, float]:
    """Convert the validated 1 ohm CCVS output to canonical external quantities."""

    if not math.isfinite(output_psd_v2_per_hz) or output_psd_v2_per_hz < 0.0:
        raise NoiseCharacterizationError("drain-terminal PSD is not finite/non-negative")
    # Hnoise is exactly 1 ohm and produces I(Vd)*1 ohm.  Current entering the
    # external device drain is -I(Vd), hence the explicit negative sign.
    y_dg = -complex(ccvs_output_real_v, ccvs_output_imag_v)
    transfer_squared = abs(y_dg) ** 2
    if not math.isfinite(transfer_squared) or transfer_squared <= 0.0:
        raise NoiseCharacterizationError("gate-to-drain transfer is zero/non-finite")
    return {
        "s_idrain_terminal_a2_per_hz": output_psd_v2_per_hz,
        "s_vgate_equivalent_v2_per_hz": output_psd_v2_per_hz / transfer_squared,
        "y_dg_real_s": y_dg.real,
        "y_dg_imag_s": y_dg.imag,
    }


def _parse_native_oracles(log_text: str, vectors: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for semantic_name, vector in vectors.items():
        match = re.search(
            rf"^\s*{re.escape(vector)}\s*=\s*([-+0-9.eE]+)\s*$",
            log_text,
            re.MULTILINE | re.IGNORECASE,
        )
        result[semantic_name] = float(match.group(1)) if match else None
    return result


def _run_mos_noise(
    resolved: ResolvedNoiseDevice,
    toolchain: Toolchain,
    output: Path,
    bias: dict[str, Any],
    *,
    frequency_start_hz: float,
    frequency_stop_hz: float,
    points_per_decade: int,
) -> dict[str, Any]:
    final = bias["final"]
    netlist = output / "netlists" / "noise_spectrum.cir"
    log = output / "logs" / "noise_spectrum.log"
    raw_noise = output / "raw" / "noise_all_vectors.dat"
    raw_ac = output / "raw" / "gate_to_drain_transfer.dat"
    raw_vd = resolved.kit.raw_voltage(resolved.polarity, resolved.vout_v)
    raw_vg = resolved.kit.raw_voltage(resolved.polarity, final["vctrl_v"])
    native_oracle_vectors: dict[str, str] = {}
    if resolved.kit.compact_model == "psp103":
        native_oracle_vectors = {
            "psp_sid_a2_per_hz": resolved.kit.native_vector(resolved.polarity, "sid"),
            "psp_sfl_at_1hz_a2_per_hz": resolved.kit.native_vector(resolved.polarity, "sfl"),
            "psp_cigid_imaginary_correlation": resolved.kit.native_vector(
                resolved.polarity, "cigid"
            ),
        }
    lines = [
        "APM V3-N0 stationary MOS noise",
        *_netlist_prefix(resolved),
        f"Vd d 0 DC {raw_vd:.12g}",
        f"Vg g 0 DC {raw_vg:.12g} AC 1",
        "Vs s 0 DC 0",
        "Vb b 0 DC 0",
        (
            f"Xdut d g s b {resolved.device.public_name} "
            f"{resolved.geometry.netlist_parameters()}"
        ),
        "Hnoise nout 0 Vd 1",
        ".control",
        *_control_osdi(resolved, toolchain),
        "set wr_vecnames",
        "set wr_singlescale",
        "set sqrnoise",
        ("save all " + " ".join(native_oracle_vectors.values()))
        if native_oracle_vectors
        else "save all",
        "op",
        *[f"print {vector}" for vector in native_oracle_vectors.values()],
        f"echo {SHOWMOD_BEGIN}",
        showmod_control_line(resolved.kit.compact_model),
        f"echo {SHOWMOD_END}",
        (
            f"noise v(nout) Vg dec {points_per_decade} {frequency_start_hz:.12g} "
            f"{frequency_stop_hz:.12g} 1"
        ),
        "setplot noise1",
        f"wrdata {raw_noise} all",
        (
            f"ac dec {points_per_decade} {frequency_start_hz:.12g} "
            f"{frequency_stop_hz:.12g}"
        ),
        f"wrdata {raw_ac} v(nout)",
        "quit",
        ".endc",
        ".end",
    ]
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    command = _run_ngspice(toolchain, netlist, log)
    log_text = log.read_text(encoding="utf-8", errors="replace")
    log_audit = audit_ngspice_log(log_text, require_sparse=True)
    noise_records, source_vectors = _noise_wrdata(raw_noise)
    _ac_header, ac_rows = _read_wrdata(raw_ac, 3)
    if len(noise_records) != len(ac_rows):
        raise NoiseCharacterizationError("noise and AC transfer grids have different lengths")
    spectrum: list[dict[str, Any]] = []
    input_ref_relative_errors: list[float] = []
    for noise_row, ac_row in zip(noise_records, ac_rows):
        frequency = noise_row["frequency"]
        if not math.isclose(frequency, ac_row[0], rel_tol=1e-10):
            raise NoiseCharacterizationError("noise and AC transfer frequencies do not align")
        canonical = canonical_noise_observables(
            noise_row["onoise_spectrum"], ac_row[1], ac_row[2]
        )
        s_vgate = canonical["s_vgate_equivalent_v2_per_hz"]
        backend_input = noise_row["inoise_spectrum"]
        relative_error = abs(s_vgate - backend_input) / max(
            abs(s_vgate), abs(backend_input), 1e-300
        )
        input_ref_relative_errors.append(relative_error)
        spectrum.append(
            {
                "operating_point_id": "gm-id-15",
                "frequency_hz": frequency,
                **canonical,
                "backend_inoise_spectrum_v2_per_hz": backend_input,
                "backend_input_ref_relative_error": relative_error,
            }
        )
    if max(input_ref_relative_errors) > 1e-5:
        raise NoiseCharacterizationError(
            "calculated gate-referred PSD disagrees with ngspice input-referred PSD"
        )
    low_frequency_gm_error = abs(abs(complex(spectrum[0]["y_dg_real_s"], spectrum[0]["y_dg_imag_s"])) - final["gm_s"]) / final["gm_s"]
    if low_frequency_gm_error > 0.05:
        raise NoiseCharacterizationError(
            f"low-frequency gate-to-drain transfer differs from canonical gm by {low_frequency_gm_error:.3%}"
        )
    snapshot = build_noise_model_snapshot(
        kit=resolved.kit,
        log_text=log_text,
        ngspice_version=run_checked([toolchain.ngspice, "--version"]).stdout.strip(),
    )
    if not snapshot["effective_parameter_snapshot_available"]:
        raise NoiseCharacterizationError("effective noise parameter snapshot is incomplete")
    source_breakdown = {
        "schema": "apm.noise-source-breakdown.v1",
        "status": "available" if source_vectors else "not_available",
        "backend": "ngspice",
        "compact_model": resolved.kit.compact_model,
        "namespace": "raw_backend_model_specific",
        "cross_engine_semantic_mapping": "none",
        "frequency_hz": [record["frequency"] for record in noise_records],
        "sources": [
            {"raw_vector_name": name, "output_referred_psd": values}
            for name, values in sorted(source_vectors.items())
        ],
    }
    native_oracles = _parse_native_oracles(log_text, native_oracle_vectors)
    if native_oracles:
        native_oracles.update(
            {
                "status": "validation_oracle_only",
                "semantic_source": (
                    "Pinned PSP103 source declares sid as white current PSD, sfl as 1 Hz "
                    "flicker current PSD, and cigid as the imaginary correlation coefficient."
                ),
                "not_equal_by_contract": "external drain-terminal total PSD",
            }
        )
    _json_write(output / "source_breakdown.json", source_breakdown)
    _json_write(output / "noise_model_snapshot.json", snapshot)
    _csv_write(
        output / "noise_spectrum.csv",
        [
            "operating_point_id",
            "frequency_hz",
            "s_idrain_terminal_a2_per_hz",
            "s_vgate_equivalent_v2_per_hz",
            "y_dg_real_s",
            "y_dg_imag_s",
            "backend_inoise_spectrum_v2_per_hz",
            "backend_input_ref_relative_error",
        ],
        spectrum,
    )
    return {
        "spectrum": spectrum,
        "source_breakdown": source_breakdown,
        "snapshot": snapshot,
        "native_oracles": native_oracles,
        "low_frequency_gm_relative_error": low_frequency_gm_error,
        "max_backend_input_ref_relative_error": max(input_ref_relative_errors),
        "log_audit": log_audit,
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "raw_noise": str(raw_noise.relative_to(output)),
        "raw_ac": str(raw_ac.relative_to(output)),
        "command": command,
    }


def _operating_point_row(
    resolved: ResolvedNoiseDevice, bias: dict[str, Any]
) -> dict[str, Any]:
    final = bias["final"]
    return {
        "operating_point_id": "gm-id-15",
        "technology_id": resolved.device.technology_id,
        "family_id": resolved.device.family_id,
        "device_id": resolved.device.device_id,
        "public_device": resolved.device.public_name,
        "polarity": resolved.device.polarity,
        "temperature_c": resolved.temperature_c,
        **resolved.geometry.result_fields(resolved.device.lmin_m),
        "vctrl_v": final["vctrl_v"],
        "vout_v": final["vout_v"],
        "raw_vgs_v": final["raw_vgs_v"],
        "raw_vds_v": final["raw_vds_v"],
        "raw_vd_source_current_a": final["raw_vd_source_current_a"],
        "raw_drain_current_entering_device_a": final[
            "raw_drain_current_entering_device_a"
        ],
        "idmag_a": final["idmag_a"],
        "gm_s": final["gm_s"],
        "gds_s": final["gds_s"],
        "gm_over_id_per_v": final["gm_over_id_per_v"],
        "gm_over_gds": final["gm_over_gds"],
        "gm_over_id_target_per_v": bias["target_per_v"],
        "gm_over_id_relative_error": bias["relative_target_error"],
        "gm_over_id_resolution_status": bias["status"],
        "gm_step_v": final["gm_step_v"],
        "gm_second_step_v": final["gm_second_step_v"],
        "gm_convergence_relative": final["gm_convergence_relative"],
        "gds_step_v": final["gds_step_v"],
        "gds_second_step_v": final["gds_second_step_v"],
        "gds_convergence_relative": final["gds_convergence_relative"],
        "native_gm_s": final["native_gm_s"],
        "native_gds_s": final["native_gds_s"],
        "variation_origin": "none",
        "variation_mode": "nominal",
    }


def _metrics_row(
    metrics: dict[str, Any], gate_integral: float, frequency_start: float, frequency_stop: float
) -> dict[str, Any]:
    flicker = metrics["flicker_fit"]
    white = metrics["white_fit"]
    corner = metrics["flicker_corner"]
    gamma = metrics["gamma_eff_total"]
    return {
        "operating_point_id": "gm-id-15",
        "fit_method_id": metrics["method_id"],
        "fit_method_version": metrics["method_version"],
        "fit_method_status": metrics["method_status"],
        "flicker_fit_status": flicker["status"],
        "flicker_fit_reason": flicker["reason"],
        "flicker_window_min_hz": flicker["window_min_hz"],
        "flicker_window_max_hz": flicker["window_max_hz"],
        "flicker_point_count": flicker["point_count"],
        "flicker_alpha": flicker["alpha"],
        "flicker_coefficient_a2_per_hz_at_1hz": flicker[
            "coefficient_a2_per_hz_at_1hz"
        ],
        "flicker_r_squared": flicker["r_squared"],
        "white_fit_status": white["status"],
        "white_fit_reason": white["reason"],
        "white_window_min_hz": white["window_min_hz"],
        "white_window_max_hz": white["window_max_hz"],
        "white_point_count": white["point_count"],
        "white_floor_a2_per_hz": white["floor_a2_per_hz"],
        "white_log_slope": white["log_slope"],
        "white_max_to_min_ratio": white["max_to_min_ratio"],
        "flicker_corner_status": corner["status"],
        "flicker_corner_hz": corner["frequency_hz"],
        "gamma_eff_total_status": gamma["status"],
        "gamma_eff_total": gamma["value"],
        "integration_band_min_hz": frequency_start,
        "integration_band_max_hz": frequency_stop,
        "integrated_drain_noise_a2": metrics["integrated_drain_noise_a2"],
        "integrated_gate_referred_noise_v2": gate_integral,
    }


def characterize_noise_selector(
    selector: str,
    output: Path | None = None,
    *,
    operating_profile_id: str | None = None,
    temperature_c: int = DEFAULT_TEMPERATURE_C,
    gm_over_id_target: float = DEFAULT_GM_OVER_ID_TARGET,
    frequency_start_hz: float = DEFAULT_FREQUENCY_START_HZ,
    frequency_stop_hz: float = DEFAULT_FREQUENCY_STOP_HZ,
    points_per_decade: int = DEFAULT_POINTS_PER_DECADE,
    root: Path | None = None,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    resolved_root = (root or repository_root()).resolve()
    result_directory = _prepare_output(output or _default_output(selector, resolved_root))
    selected_toolchain = toolchain or resolve_toolchain(resolved_root)
    resolved = resolve_noise_device(
        selector,
        resolved_root,
        operating_profile_id=operating_profile_id,
        temperature_c=temperature_c,
    )
    if resolved.kit.osdi_artifacts:
        build_models(selected_toolchain, force=False)
        missing = [
            artifact
            for artifact in resolved.kit.osdi_artifacts
            if not (selected_toolchain.osdi_directory / artifact).is_file()
        ]
        if missing:
            raise NoiseCharacterizationError(f"missing required OSDI artifacts: {missing}")
    bias = resolve_gm_over_id_bias(
        resolved,
        selected_toolchain,
        result_directory,
        target_per_v=gm_over_id_target,
    )
    noise = _run_mos_noise(
        resolved,
        selected_toolchain,
        result_directory,
        bias,
        frequency_start_hz=frequency_start_hz,
        frequency_stop_hz=frequency_stop_hz,
        points_per_decade=points_per_decade,
    )
    operating_point = _operating_point_row(resolved, bias)
    _csv_write(result_directory / "operating_points.csv", list(operating_point), [operating_point])
    frequencies = [row["frequency_hz"] for row in noise["spectrum"]]
    drain_psd = [row["s_idrain_terminal_a2_per_hz"] for row in noise["spectrum"]]
    gate_psd = [row["s_vgate_equivalent_v2_per_hz"] for row in noise["spectrum"]]
    metrics = fit_noise_spectrum(
        frequencies,
        drain_psd,
        gm_s=operating_point["gm_s"],
        temperature_c=temperature_c,
    )
    gate_integral = integrate_psd(frequencies, gate_psd)
    metrics_row = _metrics_row(metrics, gate_integral, frequency_start_hz, frequency_stop_hz)
    _csv_write(result_directory / "noise_metrics.csv", list(metrics_row), [metrics_row])
    ngspice_version = run_checked([selected_toolchain.ngspice, "--version"]).stdout.strip()
    openvaf_version = run_checked(
        [selected_toolchain.openvaf, "--version"], environment=selected_toolchain.environment()
    ).stdout.strip()
    git_commit = run_checked(["git", "rev-parse", "HEAD"], cwd=resolved_root).stdout.strip()
    metadata = {
        "schema": NOISE_SCHEMA,
        "schema_version": "1.0.0",
        "status": "pass",
        "created_utc": _utc_now(),
        "repository_commit": git_commit,
        "technology_id": resolved.device.technology_id,
        "family_id": resolved.device.family_id,
        "device_id": resolved.device.device_id,
        "selector": resolved.selector,
        "public_device": resolved.device.public_name,
        "polarity": resolved.device.polarity,
        "compact_model": resolved.kit.compact_model,
        "model_origin": resolved.kit.model_origin,
        "operating_profile": {
            "id": resolved.kit.operating_profile_id,
            "reference_vdd_v": resolved.kit.vdd_v,
            "resolved_vout_fraction": DEFAULT_VOUT_FRACTION,
            "resolved_vout_v": resolved.vout_v,
        },
        "geometry": resolved.geometry.result_fields(resolved.device.lmin_m),
        "temperature_c": temperature_c,
        "bias_resolution": {
            "method_id": bias["method_id"],
            "method_version": bias["method_version"],
            "status": bias["status"],
            "target_per_v": bias["target_per_v"],
            "achieved_per_v": bias["achieved_per_v"],
            "relative_target_error": bias["relative_target_error"],
            "relative_tolerance": bias["relative_tolerance"],
            "iteration_count": bias["iteration_count"],
            "finite_difference_validation": bias["finite_difference_validation"],
            "native_oracle_validation": bias["native_oracle_validation"],
            "diagnostic_path": "bias_resolution.json",
        },
        "noise_method": {
            "id": NOISE_METHOD_ID,
            "version": NOISE_METHOD_VERSION,
            "canonical_quantity": "s_idrain_terminal_a2_per_hz",
            "output_definition": (
                "total stationary short-circuit noise-current PSD at the external drain "
                "with external terminal voltages held by ideal noiseless sources"
            ),
            "psd_not_asd": True,
            "ngspice_setting": "set sqrnoise",
        },
        "probe": {
            "id": PROBE_METHOD_ID,
            "version": PROBE_METHOD_VERSION,
            "transresistance_ohm": 1.0,
            "control_branch": "Vd",
            "canonical_current_sign": "negative of ngspice I(Vd)",
            "qualification_required": "apm noise-check analytic fixtures",
        },
        "frequency_profile": {
            "id": FREQUENCY_PROFILE_ID,
            "status": "provisional",
            "start_hz": frequency_start_hz,
            "stop_hz": frequency_stop_hz,
            "points_per_decade": points_per_decade,
            "retained_point_count": len(noise["spectrum"]),
        },
        "solver": {
            "required": "Sparse",
            "netlist_option": "klu=0",
            "validated": bool(noise["log_audit"]["sparse_attestations"]),
            "klu_used": False,
        },
        "log_audit": noise["log_audit"],
        "backend_capability": {
            "noise_backend_validation": "real_tool",
            "noise_correlation_path": (
                "model_internal_network"
                if resolved.kit.compact_model in {"psp103", "bsim_cmg"}
                else "native_backend"
            ),
            "source_breakdown_available": bool(noise["source_breakdown"]["sources"]),
            "effective_parameter_snapshot_available": noise["snapshot"][
                "effective_parameter_snapshot_available"
            ],
        },
        "simulator": {
            "backend": "ngspice",
            "path": str(selected_toolchain.ngspice),
            "sha256": sha256_file(selected_toolchain.ngspice),
            "version_output": ngspice_version,
        },
        "openvaf": {
            "path": str(selected_toolchain.openvaf),
            "sha256": sha256_file(selected_toolchain.openvaf),
            "version_output": openvaf_version,
        },
        "osdi_artifacts": [
            {
                "name": artifact,
                "sha256": sha256_file(selected_toolchain.osdi_directory / artifact),
            }
            for artifact in resolved.kit.osdi_artifacts
        ],
        "manifest_binding": {
            "family_manifest": str(resolved.kit.family_manifest.relative_to(resolved_root)),
            "family_manifest_sha256": resolved.kit.family_manifest_sha256,
            "backend_binding": str(
                resolved.kit.backend_binding_manifest.relative_to(resolved_root)
            ),
            "backend_binding_sha256": resolved.kit.backend_binding_sha256,
            "provenance": str(resolved.kit.provenance_path.relative_to(resolved_root)),
            "provenance_sha256": resolved.kit.provenance_sha256,
        },
        "model_snapshot": {
            "path": "noise_model_snapshot.json",
            "sha256": sha256_file(result_directory / "noise_model_snapshot.json"),
        },
        "source_breakdown": {
            "path": "source_breakdown.json",
            "sha256": sha256_file(result_directory / "source_breakdown.json"),
            "cross_engine_mapping": "none",
        },
        "execution": {
            "noise_command": noise["command"],
            "noise_netlist": noise["netlist"],
            "noise_log": noise["log"],
            "raw_noise": noise["raw_noise"],
            "raw_ac_transfer": noise["raw_ac"],
        },
        "native_noise_oracles": noise["native_oracles"],
        "transfer_validation": {
            "low_frequency_gm_relative_error": noise["low_frequency_gm_relative_error"],
            "max_backend_input_ref_relative_error": noise[
                "max_backend_input_ref_relative_error"
            ],
        },
        "variation_origin": "none",
        "variation_mode": "nominal",
        "claims": {
            "simulator_execution_validated": True,
            "silicon_calibrated_noise_claim": False,
            "process_noise_coefficients_tuned_for_spike": False,
        },
        "artifacts": {
            "operating_points": "operating_points.csv",
            "noise_spectrum": "noise_spectrum.csv",
            "noise_metrics": "noise_metrics.csv",
            "source_breakdown": "source_breakdown.json",
            "noise_model_snapshot": "noise_model_snapshot.json",
            "bias_resolution": "bias_resolution.json",
        },
    }
    _json_write(result_directory / "metadata.json", metadata)
    return {
        "status": "pass",
        "schema": NOISE_SCHEMA,
        "selector": selector,
        "output_directory": str(result_directory),
        "metadata_path": str(result_directory / "metadata.json"),
        "achieved_gm_over_id_per_v": bias["achieved_per_v"],
        "gm_over_id_relative_error": bias["relative_target_error"],
        "gm_convergence_relative": bias["final"]["gm_convergence_relative"],
        "gds_convergence_relative": bias["final"]["gds_convergence_relative"],
        "native_gm_relative_error": bias["final"]["native_gm_relative_error"],
        "native_gds_relative_error": bias["final"]["native_gds_relative_error"],
        "frequency_point_count": len(noise["spectrum"]),
        "minimum_drain_psd_a2_per_hz": min(drain_psd),
        "maximum_drain_psd_a2_per_hz": max(drain_psd),
        "fit_status": {
            "flicker": metrics["flicker_fit"]["status"],
            "white": metrics["white_fit"]["status"],
            "corner": metrics["flicker_corner"]["status"],
        },
    }
