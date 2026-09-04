# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""External-terminal observables for sealed mixed-voltage qualification.

This offline-only module deliberately measures voltage-source branch currents.
Native BSIM operating-point quantities are retained only as diagnostic oracles.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .kernel import FAILURE_TOKENS, ModelgenError, ModelSource, sha256_file

TERMINALS = ("d", "g", "s", "b")


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise ModelgenError("terminal-observable value is not finite")
    return f"{value:.12g}"


def _relative(first: float, second: float, floor: float = 1e-30) -> float:
    return abs(first - second) / max(abs(first), abs(second), floor)


def _read_wrdata(path: Path, expected_columns: int) -> list[list[float]]:
    if not path.is_file():
        raise ModelgenError(f"ngspice did not create {path}")
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        values = [float(item) for item in line.split()]
        if len(values) != expected_columns:
            raise ModelgenError(
                f"{path}: expected {expected_columns} columns, found {len(values)}"
            )
        if not all(math.isfinite(value) for value in values):
            raise ModelgenError(f"{path}: ngspice emitted NaN/Inf")
        rows.append(values)
    if not rows:
        raise ModelgenError(f"ngspice produced no samples in {path}")
    return rows


@dataclass(frozen=True)
class BiasPoint:
    point_id: str
    temperature_c: int
    l_m: float
    w_m: float
    vctrl_v: float
    vout_v: float

    def __post_init__(self) -> None:
        if not self.point_id or self.temperature_c < -273:
            raise ModelgenError("invalid terminal-observable bias identity")
        for name, value in (
            ("l_m", self.l_m),
            ("w_m", self.w_m),
            ("vctrl_v", self.vctrl_v),
            ("vout_v", self.vout_v),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ModelgenError(f"{self.point_id}: {name} must be positive and finite")


@dataclass(frozen=True)
class GateTrajectory:
    trajectory_id: str
    temperature_c: int
    l_m: float
    w_m: float
    fixed_vout_v: float
    vctrl_values_v: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.trajectory_id or self.temperature_c < -273:
            raise ModelgenError("invalid gate-trajectory identity")
        if len(self.vctrl_values_v) < 5 or tuple(sorted(self.vctrl_values_v)) != self.vctrl_values_v:
            raise ModelgenError(
                f"{self.trajectory_id}: gate trajectory must be sorted with at least five points"
            )
        values = (
            self.l_m,
            self.w_m,
            self.fixed_vout_v,
            *self.vctrl_values_v,
        )
        if not all(math.isfinite(value) for value in values):
            raise ModelgenError(f"{self.trajectory_id}: non-finite trajectory value")
        if self.l_m <= 0.0 or self.w_m <= 0.0 or self.fixed_vout_v <= 0.0:
            raise ModelgenError(f"{self.trajectory_id}: geometry and output bias must be positive")
        if self.vctrl_values_v[0] < 0.0 or len(set(self.vctrl_values_v)) != len(
            self.vctrl_values_v
        ):
            raise ModelgenError(
                f"{self.trajectory_id}: gate biases must be unique and non-negative"
            )


@dataclass(frozen=True)
class BodySweep:
    sweep_id: str
    temperature_c: int
    l_m: float
    w_m: float
    fixed_vout_v: float
    reverse_body_bias_v: float
    sweep_stop_v: float
    points: int

    def __post_init__(self) -> None:
        if not self.sweep_id or self.temperature_c < -273:
            raise ModelgenError("invalid body-sweep identity")
        values = (
            self.l_m,
            self.w_m,
            self.fixed_vout_v,
            self.reverse_body_bias_v,
            self.sweep_stop_v,
        )
        if not all(math.isfinite(value) for value in values):
            raise ModelgenError(f"{self.sweep_id}: non-finite body-sweep value")
        if min(self.l_m, self.w_m, self.fixed_vout_v, self.sweep_stop_v) <= 0.0:
            raise ModelgenError(f"{self.sweep_id}: geometry and sweep biases must be positive")
        if self.reverse_body_bias_v < 0.0 or self.points < 5:
            raise ModelgenError(f"{self.sweep_id}: invalid reverse body bias or point count")


class TerminalEvaluator:
    """Run deterministic DC derivative, body, and complex-Y observations."""

    def __init__(self, *, ngspice: Path, work_directory: Path) -> None:
        self.ngspice = ngspice.resolve()
        self.work_directory = work_directory.resolve()
        self.work_directory.mkdir(parents=True, exist_ok=True)
        if not self.ngspice.is_file():
            raise ModelgenError(f"ngspice executable is missing: {self.ngspice}")
        self.evaluation_count = 0

    def tool_identity(self) -> dict[str, str]:
        completed = subprocess.run(
            [str(self.ngspice), "--version"],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
        )
        output = completed.stdout + completed.stderr
        match = re.search(r"ngspice-(\d+)", output)
        if not match:
            raise ModelgenError("cannot determine ngspice major version")
        return {
            "path": str(self.ngspice),
            "sha256": sha256_file(self.ngspice),
            "major": match.group(1),
            "version_output": output.strip(),
        }

    def _run(self, netlist: Path, log: Path, token: str) -> None:
        completed = subprocess.run(
            [str(self.ngspice), "-n", "-b", "-o", str(log), str(netlist)],
            cwd=netlist.parent,
            env={**os.environ, "LC_ALL": "C"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.evaluation_count += 1
        log_text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        lowered = log_text.lower()
        if completed.returncode != 0 or any(token_ in lowered for token_ in FAILURE_TOKENS):
            detail = completed.stderr.strip() or completed.stdout.strip() or log_text[-2000:]
            raise ModelgenError(f"ngspice failed for {token}: {detail}")
        if "ngspice-47 done" not in log_text:
            raise ModelgenError(f"ngspice did not report reference completion for {token}")

    def _job_directory(self, token: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", token)
        result = self.work_directory / safe
        result.mkdir(parents=True, exist_ok=True)
        return result

    @staticmethod
    def _source_lines(source: ModelSource, job: Path) -> tuple[list[str], Path | None]:
        if source.rendered_card is not None:
            card_path = job / "candidate.inc"
            card_path.write_text(source.rendered_card, encoding="utf-8")
            return [f'.include "{card_path}"'], card_path
        return [f'.include "{path.resolve()}"' for path in source.include_paths], None

    def evaluate_derivatives(
        self,
        *,
        source: ModelSource,
        model_name: str,
        polarity: str,
        points: Sequence[BiasPoint],
        vdd_v: float,
        step_fraction_vdd: float,
        token: str,
    ) -> list[dict[str, Any]]:
        """Measure gm/gds with two central steps and native diagnostic oracles."""

        if polarity not in {"n", "p"} or not points:
            raise ModelgenError("derivative evaluation requires points and N/P polarity")
        step = float(vdd_v) * float(step_fraction_vdd)
        if step <= 0.0:
            raise ModelgenError("finite-difference step must be positive")
        grouped: dict[int, list[BiasPoint]] = defaultdict(list)
        point_ids: set[str] = set()
        for point in points:
            if point.point_id in point_ids:
                raise ModelgenError(f"duplicate derivative point id: {point.point_id}")
            point_ids.add(point.point_id)
            if point.vctrl_v <= 2.0 * step or point.vctrl_v + 2.0 * step >= vdd_v:
                raise ModelgenError(f"{point.point_id}: gm finite-difference step clips endpoint")
            if point.vout_v <= 2.0 * step or point.vout_v + 2.0 * step >= vdd_v:
                raise ModelgenError(f"{point.point_id}: gds finite-difference step clips endpoint")
            grouped[point.temperature_c].append(point)
        sign = 1.0 if polarity == "n" else -1.0
        records: list[dict[str, Any]] = []
        variants = (
            ("center", 0.0, 0.0),
            ("gm_m2", -2.0 * step, 0.0),
            ("gm_m1", -step, 0.0),
            ("gm_p1", step, 0.0),
            ("gm_p2", 2.0 * step, 0.0),
            ("gds_m2", 0.0, -2.0 * step),
            ("gds_m1", 0.0, -step),
            ("gds_p1", 0.0, step),
            ("gds_p2", 0.0, 2.0 * step),
        )
        for temperature, group in sorted(grouped.items()):
            job = self._job_directory(f"{token}-t{temperature:+d}")
            includes, _ = self._source_lines(source, job)
            netlist = job / "derivatives.cir"
            log = job / "ngspice.log"
            lines = [
                "APM mixed-voltage external-terminal derivative observations",
                *includes,
                ".options gmin=1e-15",
                f".temp {temperature}",
            ]
            currents: dict[str, list[str]] = {}
            center_instances: dict[str, str] = {}
            serial = 0
            for point in group:
                currents[point.point_id] = []
                for variant, gate_delta, drain_delta in variants:
                    suffix = f"{serial}"
                    instance = f"Mobs{suffix}"
                    lines.extend(
                        [
                            f"Vd{suffix} d{suffix} 0 {_number(sign * (point.vout_v + drain_delta))}",
                            f"Vg{suffix} g{suffix} 0 {_number(sign * (point.vctrl_v + gate_delta))}",
                            f"Vs{suffix} s{suffix} 0 0",
                            f"Vb{suffix} b{suffix} 0 0",
                            (
                                f"{instance} d{suffix} g{suffix} s{suffix} b{suffix} "
                                f"{model_name} w={_number(point.w_m)} l={_number(point.l_m)}"
                            ),
                        ]
                    )
                    currents[point.point_id].append(f"i(Vd{suffix})")
                    if variant == "center":
                        center_instances[point.point_id] = instance.lower()
                    serial += 1
            vector_names = [
                vector for point in group for vector in currents[point.point_id]
            ]
            vector_names.extend(
                vector
                for point in group
                for vector in (
                    f"@{center_instances[point.point_id]}[gm]",
                    f"@{center_instances[point.point_id]}[gds]",
                )
            )
            raw = job / "derivatives.dat"
            lines.extend(
                [
                    ".control",
                    "set wr_vecnames",
                    "set wr_singlescale",
                    "save all "
                    + " ".join(
                        vector
                        for point in group
                        for vector in (
                            f"@{center_instances[point.point_id]}[gm]",
                            f"@{center_instances[point.point_id]}[gds]",
                        )
                    ),
                    "op",
                    f"wrdata {raw} " + " ".join(vector_names),
                    "quit",
                    ".endc",
                    ".end",
                    "",
                ]
            )
            netlist.write_text("\n".join(lines), encoding="utf-8")
            self._run(netlist, log, f"{token}-derivatives-t{temperature:+d}")
            rows = _read_wrdata(raw, 1 + len(vector_names))
            if len(rows) != 1:
                raise ModelgenError("operating-point derivative job emitted multiple rows")
            values = rows[0][1:]
            cursor = 0
            current_values: dict[str, list[float]] = {}
            for point in group:
                current_values[point.point_id] = [
                    abs(value) for value in values[cursor : cursor + len(variants)]
                ]
                cursor += len(variants)
            raw_current_cursor = 0
            for point in group:
                observed = current_values[point.point_id]
                native_gm = abs(values[cursor])
                native_gds = abs(values[cursor + 1])
                cursor += 2
                gm_first = (observed[3] - observed[2]) / (2.0 * step)
                gm_second = (observed[4] - observed[1]) / (4.0 * step)
                gds_first = (observed[7] - observed[6]) / (2.0 * step)
                gds_second = (observed[8] - observed[5]) / (4.0 * step)
                current = observed[0]
                records.append(
                    {
                        "point_id": point.point_id,
                        "temperature_c": point.temperature_c,
                        "l_m": point.l_m,
                        "w_m": point.w_m,
                        "vctrl_v": point.vctrl_v,
                        "vout_v": point.vout_v,
                        "raw_drain_source_current_a": values[raw_current_cursor],
                        "idmag_a": current,
                        "gm_s": gm_first,
                        "gm_second_step_s": gm_second,
                        "gm_step_v": step,
                        "gm_second_step_v": 2.0 * step,
                        "gm_convergence_relative": _relative(gm_first, gm_second),
                        "gds_s": gds_first,
                        "gds_second_step_s": gds_second,
                        "gds_step_v": step,
                        "gds_second_step_v": 2.0 * step,
                        "gds_convergence_relative": _relative(gds_first, gds_second),
                        "gm_over_id_per_v": gm_first / current if current > 0.0 else math.inf,
                        "gds_over_id_per_v": gds_first / current if current > 0.0 else math.inf,
                        "gm_over_gds": gm_first / gds_first if gds_first > 0.0 else math.inf,
                        "native_gm_s": native_gm,
                        "native_gds_s": native_gds,
                        "native_gm_relative_error": _relative(gm_first, native_gm),
                        "native_gds_relative_error": _relative(gds_first, native_gds),
                    }
                )
                raw_current_cursor += len(variants)
            if cursor != len(values):
                raise ModelgenError("derivative output vector count mismatch")
        return records

    def evaluate_y(
        self,
        *,
        source: ModelSource,
        model_name: str,
        polarity: str,
        points: Sequence[BiasPoint],
        frequencies_hz: Sequence[float],
        token: str,
    ) -> list[dict[str, Any]]:
        """Measure ordered complex 4x4 terminal Y matrices."""

        if polarity not in {"n", "p"} or not points or not frequencies_hz:
            raise ModelgenError("terminal-Y evaluation requires points, frequencies, and polarity")
        sign = 1.0 if polarity == "n" else -1.0
        grouped: dict[int, list[BiasPoint]] = defaultdict(list)
        for point in points:
            grouped[point.temperature_c].append(point)
        records: list[dict[str, Any]] = []
        point_ids: set[str] = set()
        for temperature, group in sorted(grouped.items()):
            for point in group:
                if point.point_id in point_ids:
                    raise ModelgenError(f"duplicate terminal-Y point id: {point.point_id}")
                point_ids.add(point.point_id)
            job = self._job_directory(f"{token}-t{temperature:+d}")
            includes, _ = self._source_lines(source, job)
            netlist = job / "terminal-y.cir"
            log = job / "ngspice.log"
            lines = [
                "APM mixed-voltage ordered complex terminal-Y observations",
                *includes,
                ".options gmin=1e-15",
                f".temp {temperature}",
            ]
            vector_names: list[str] = []
            serial = 0
            for point in group:
                for excitation in TERMINALS:
                    nodes = {terminal: f"{terminal}{serial}" for terminal in TERMINALS}
                    biases = {
                        "d": sign * point.vout_v,
                        "g": sign * point.vctrl_v,
                        "s": 0.0,
                        "b": 0.0,
                    }
                    for terminal in TERMINALS:
                        source_name = f"V{terminal}{serial}"
                        ac = 1 if terminal == excitation else 0
                        lines.append(
                            f"{source_name} {nodes[terminal]} 0 {_number(biases[terminal])} AC {ac}"
                        )
                        vector_names.append(f"i({source_name})")
                    lines.append(
                        f"My{serial} {nodes['d']} {nodes['g']} {nodes['s']} {nodes['b']} "
                        f"{model_name} w={_number(point.w_m)} l={_number(point.l_m)}"
                    )
                    serial += 1
            lines.extend([".control", "set wr_vecnames", "set wr_singlescale"])
            raw_paths: dict[float, Path] = {}
            for index, frequency in enumerate(frequencies_hz):
                if not math.isfinite(float(frequency)) or float(frequency) <= 0.0:
                    raise ModelgenError("terminal-Y frequency must be positive and finite")
                raw = job / f"terminal-y-{index:03d}.dat"
                raw_paths[float(frequency)] = raw
                lines.extend(
                    [
                        f"ac lin 1 {_number(float(frequency))} {_number(float(frequency))}",
                        f"wrdata {raw} " + " ".join(vector_names),
                    ]
                )
            lines.extend(["quit", ".endc", ".end", ""])
            netlist.write_text("\n".join(lines), encoding="utf-8")
            self._run(netlist, log, f"{token}-terminal-y-t{temperature:+d}")
            for frequency, raw in raw_paths.items():
                rows = _read_wrdata(raw, 1 + 2 * len(vector_names))
                if len(rows) != 1 or not math.isclose(rows[0][0], frequency, rel_tol=1e-12):
                    raise ModelgenError("terminal-Y job emitted an unexpected frequency")
                values = rows[0]
                cursor = 1
                for point in group:
                    matrix = [[0j for _ in TERMINALS] for _ in TERMINALS]
                    for column, _excitation in enumerate(TERMINALS):
                        for row, _response in enumerate(TERMINALS):
                            matrix[row][column] = -complex(values[cursor], values[cursor + 1])
                            cursor += 2
                    column_sums = [
                        abs(sum(matrix[row][column] for row in range(4)))
                        for column in range(4)
                    ]
                    matrix_scale = max(abs(value) for row in matrix for value in row)
                    records.append(
                        {
                            "point_id": point.point_id,
                            "temperature_c": point.temperature_c,
                            "l_m": point.l_m,
                            "w_m": point.w_m,
                            "vctrl_v": point.vctrl_v,
                            "vout_v": point.vout_v,
                            "frequency_hz": frequency,
                            "terminal_order": list(TERMINALS),
                            "excitation_convention": (
                                "1 V small-signal excitation at column terminal; "
                                "other terminal sources at AC ground"
                            ),
                            "current_convention": (
                                "Y[i,j] is current entering device terminal i; "
                                "ngspice voltage-source currents are negated"
                            ),
                            "y_real_s": [[value.real for value in row] for row in matrix],
                            "y_imag_s": [[value.imag for value in row] for row in matrix],
                            "kcl_column_sum_abs_s": column_sums,
                            "kcl_max_normalized_residual": max(column_sums)
                            / max(matrix_scale, 1e-30),
                        }
                    )
                if cursor != len(values):
                    raise ModelgenError("terminal-Y output vector count mismatch")
        return records

    def evaluate_gate_trajectories(
        self,
        *,
        source: ModelSource,
        model_name: str,
        polarity: str,
        trajectories: Sequence[GateTrajectory],
        frequencies_hz: Sequence[float],
        token: str,
    ) -> list[dict[str, Any]]:
        """Measure the gate-excitation Y column along intrinsic charge trajectories."""

        if polarity not in {"n", "p"} or not trajectories or not frequencies_hz:
            raise ModelgenError("gate-trajectory evaluation requires inputs")
        sign = 1.0 if polarity == "n" else -1.0
        grouped: dict[int, list[GateTrajectory]] = defaultdict(list)
        for trajectory in trajectories:
            grouped[trajectory.temperature_c].append(trajectory)
        records: list[dict[str, Any]] = []
        trajectory_ids: set[str] = set()
        for temperature, group in sorted(grouped.items()):
            for trajectory in group:
                if trajectory.trajectory_id in trajectory_ids:
                    raise ModelgenError(
                        f"duplicate gate-trajectory id: {trajectory.trajectory_id}"
                    )
                trajectory_ids.add(trajectory.trajectory_id)
            job = self._job_directory(f"{token}-t{temperature:+d}")
            includes, _ = self._source_lines(source, job)
            netlist = job / "gate-trajectories.cir"
            log = job / "ngspice.log"
            lines = [
                "APM mixed-voltage gate-terminal charge trajectories",
                *includes,
                ".options gmin=1e-15",
                f".temp {temperature}",
            ]
            vector_names: list[str] = []
            point_map: list[tuple[GateTrajectory, float]] = []
            serial = 0
            for trajectory in group:
                for vctrl in trajectory.vctrl_values_v:
                    biases = {
                        "d": sign * trajectory.fixed_vout_v,
                        "g": sign * vctrl,
                        "s": 0.0,
                        "b": 0.0,
                    }
                    for terminal in TERMINALS:
                        ac = 1 if terminal == "g" else 0
                        lines.append(
                            f"V{terminal}{serial} {terminal}{serial} 0 "
                            f"{_number(biases[terminal])} AC {ac}"
                        )
                        vector_names.append(f"i(V{terminal}{serial})")
                    lines.append(
                        f"Mq{serial} d{serial} g{serial} s{serial} b{serial} "
                        f"{model_name} w={_number(trajectory.w_m)} l={_number(trajectory.l_m)}"
                    )
                    point_map.append((trajectory, float(vctrl)))
                    serial += 1
            lines.extend([".control", "set wr_vecnames", "set wr_singlescale"])
            raw_paths: dict[float, Path] = {}
            for index, frequency in enumerate(frequencies_hz):
                if not math.isfinite(float(frequency)) or float(frequency) <= 0.0:
                    raise ModelgenError(
                        "gate-trajectory frequency must be positive and finite"
                    )
                raw = job / f"gate-y-{index:03d}.dat"
                raw_paths[float(frequency)] = raw
                lines.extend(
                    [
                        f"ac lin 1 {_number(float(frequency))} {_number(float(frequency))}",
                        f"wrdata {raw} " + " ".join(vector_names),
                    ]
                )
            lines.extend(["quit", ".endc", ".end", ""])
            netlist.write_text("\n".join(lines), encoding="utf-8")
            self._run(netlist, log, f"{token}-gate-trajectories-t{temperature:+d}")
            for frequency, raw in raw_paths.items():
                rows = _read_wrdata(raw, 1 + 2 * len(vector_names))
                if len(rows) != 1:
                    raise ModelgenError("gate-trajectory job emitted multiple rows")
                cursor = 1
                omega = 2.0 * math.pi * frequency
                for trajectory, vctrl in point_map:
                    y_column: list[complex] = []
                    for _terminal in TERMINALS:
                        y_column.append(-complex(rows[0][cursor], rows[0][cursor + 1]))
                        cursor += 2
                    kcl = abs(sum(y_column))
                    scale = max(abs(value) for value in y_column)
                    records.append(
                        {
                            "trajectory_id": trajectory.trajectory_id,
                            "temperature_c": trajectory.temperature_c,
                            "l_m": trajectory.l_m,
                            "w_m": trajectory.w_m,
                            "vctrl_v": vctrl,
                            "vout_v": trajectory.fixed_vout_v,
                            "frequency_hz": frequency,
                            "terminal_order": list(TERMINALS),
                            "excited_terminal": "g",
                            "y_gate_column_real_s": [value.real for value in y_column],
                            "y_gate_column_imag_s": [value.imag for value in y_column],
                            "cgg_f": y_column[1].imag / omega,
                            "cgd_f": -y_column[0].imag / omega,
                            "cgs_f": -y_column[2].imag / omega,
                            "cgb_f": -y_column[3].imag / omega,
                            "kcl_abs_s": kcl,
                            "kcl_normalized_residual": kcl / max(scale, 1e-30),
                        }
                    )
                if cursor != len(rows[0]):
                    raise ModelgenError("gate-trajectory output vector count mismatch")
        return records

    def evaluate_body_sweeps(
        self,
        *,
        source: ModelSource,
        model_name: str,
        polarity: str,
        sweeps: Sequence[BodySweep],
        token: str,
    ) -> dict[str, dict[str, Any]]:
        if polarity not in {"n", "p"} or not sweeps:
            raise ModelgenError("body-effect evaluation requires sweeps and polarity")
        temperatures = {sweep.temperature_c for sweep in sweeps}
        if len(temperatures) != 1:
            raise ModelgenError("one body-effect batch must use one temperature")
        sign = 1.0 if polarity == "n" else -1.0
        temperature = next(iter(temperatures))
        job = self._job_directory(token)
        includes, _ = self._source_lines(source, job)
        netlist = job / "body-sweeps.cir"
        log = job / "ngspice.log"
        lines = [
            "APM mixed-voltage body-effect terminal sweeps",
            *includes,
            ".options gmin=1e-15",
            f".temp {temperature}",
        ]
        raw_paths: list[Path] = []
        for index, sweep in enumerate(sweeps):
            lines.extend(
                [
                    f"Vd{index} d{index} 0 {_number(sign * sweep.fixed_vout_v)}",
                    f"Vg{index} g{index} 0 0",
                    f"Vs{index} s{index} 0 0",
                    f"Vb{index} b{index} 0 {_number(-sign * sweep.reverse_body_bias_v)}",
                    (
                        f"Mb{index} d{index} g{index} s{index} b{index} {model_name} "
                        f"w={_number(sweep.w_m)} l={_number(sweep.l_m)}"
                    ),
                ]
            )
        lines.extend([".control", "set wr_vecnames", "set wr_singlescale", "save all"])
        for index, sweep in enumerate(sweeps):
            raw = job / f"body-{index:03d}.dat"
            raw_paths.append(raw)
            step = sign * sweep.sweep_stop_v / (sweep.points - 1)
            lines.extend(
                [
                    f"dc Vg{index} 0 {_number(sign * sweep.sweep_stop_v)} {_number(step)}",
                    f"wrdata {raw} v(g{index}) i(Vd{index})",
                ]
            )
        lines.extend(["quit", ".endc", ".end", ""])
        netlist.write_text("\n".join(lines), encoding="utf-8")
        self._run(netlist, log, token)
        result: dict[str, dict[str, Any]] = {}
        for sweep, raw in zip(sweeps, raw_paths):
            rows = _read_wrdata(raw, 3)
            result[sweep.sweep_id] = {
                "request": sweep,
                "vctrl_v": np.asarray([abs(row[1]) for row in rows]),
                "raw_drain_source_current_a": np.asarray([row[2] for row in rows]),
                "idmag_a": np.asarray([abs(row[2]) for row in rows]),
            }
        return result
