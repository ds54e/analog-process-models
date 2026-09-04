# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Real-ngspice circuit fixtures for mixed-voltage qualification.

The fixtures are deliberately small and topology-specific.  They qualify
numerical usefulness; they are not foundry circuit targets and do not infer
layout area or extracted parasitics.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .kernel import FAILURE_TOKENS, ModelgenError, sha256_file


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise ModelgenError("circuit-fixture value is not finite")
    return f"{value:.12g}"


def _read_row(path: Path, vector_count: int) -> list[float]:
    if not path.is_file():
        raise ModelgenError(f"ngspice did not create {path}")
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()[1:] if line]
    if len(rows) != 1 or len(rows[0]) != vector_count + 1:
        raise ModelgenError(
            f"{path}: expected one row and {vector_count + 1} columns"
        )
    values = [float(item) for item in rows[0][1:]]
    if not all(math.isfinite(value) for value in values):
        raise ModelgenError(f"{path}: ngspice emitted NaN/Inf")
    return values


@dataclass(frozen=True)
class BasicCircuitRequest:
    request_id: str
    family: str
    seed: int
    temperature_c: int
    l_m: float
    w_m: float
    vdd_v: float


@dataclass(frozen=True)
class PassCase:
    case_id: str
    family: str
    seed: int
    temperature_c: int
    l_m: float
    unit_width_m: float
    units: int
    vin_v: float
    vout_v: float
    required_vsg_v: float
    load_current_a: float

    def __post_init__(self) -> None:
        finite = (
            self.l_m,
            self.unit_width_m,
            self.vin_v,
            self.vout_v,
            self.required_vsg_v,
            self.load_current_a,
        )
        if not self.case_id or not all(math.isfinite(value) for value in finite):
            raise ModelgenError("invalid PMOS pass-case identity or value")
        if (
            min(self.l_m, self.unit_width_m, self.vin_v, self.load_current_a) <= 0.0
            or not 0.0 < self.vout_v < self.vin_v
            or not 0.0 < self.required_vsg_v < self.vin_v
            or self.units < 1
        ):
            raise ModelgenError(f"{self.case_id}: invalid PMOS pass-case bounds")


class CircuitEvaluator:
    """Execute deterministic DC circuit fixtures with external measurements."""

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

    def _directory(self, token: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", token)
        job = self.work_directory / safe
        job.mkdir(parents=True, exist_ok=True)
        return job

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
        if completed.returncode != 0 or any(item in lowered for item in FAILURE_TOKENS):
            detail = completed.stderr.strip() or completed.stdout.strip() or log_text[-2000:]
            raise ModelgenError(f"ngspice failed for {token}: {detail}")
        if "ngspice-47 done" not in log_text:
            raise ModelgenError(f"ngspice did not report reference completion for {token}")

    @staticmethod
    def _write_cards(job: Path, n_card: str, p_card: str) -> list[str]:
        n_path = job / "candidate-n.inc"
        p_path = job / "candidate-p.inc"
        n_path.write_text(n_card, encoding="utf-8")
        p_path.write_text(p_card, encoding="utf-8")
        return [f'.include "{n_path}"', f'.include "{p_path}"']

    def evaluate_basic(
        self,
        *,
        request: BasicCircuitRequest,
        n_card: str,
        p_card: str,
        n_model_name: str,
        p_model_name: str,
        settings: Mapping[str, Any],
        criteria: Mapping[str, Any],
        token: str,
    ) -> dict[str, Any]:
        """Run diode, mirror, follower, and common-source fixtures."""

        job = self._directory(token)
        raw = job / "basic.dat"
        log = job / "ngspice.log"
        netlist = job / "basic.cir"
        includes = self._write_cards(job, n_card, p_card)
        lines = [
            "APM mixed-voltage sealed basic circuit fixtures",
            *includes,
            ".options gmin=1e-15",
            f".temp {request.temperature_c}",
        ]
        vectors: list[str] = []
        diode_biases = [float(value) * request.vdd_v for value in settings["diode_bias_fractions"]]
        for index, bias in enumerate(diode_biases):
            lines.extend(
                [
                    f"Vdn{index} dn{index} 0 {_number(bias)}",
                    (
                        f"Mdn{index} dn{index} dn{index} 0 0 {n_model_name} "
                        f"w={_number(request.w_m)} l={_number(request.l_m)}"
                    ),
                    f"Vdp{index} dp{index} 0 {_number(-bias)}",
                    (
                        f"Mdp{index} dp{index} dp{index} 0 0 {p_model_name} "
                        f"w={_number(request.w_m)} l={_number(request.l_m)}"
                    ),
                ]
            )
            vectors.extend((f"i(Vdn{index})", f"i(Vdp{index})"))

        reference_current = float(settings["mirror_reference_current_a"])
        mirror_vout = float(settings["mirror_output_fraction_vdd"]) * request.vdd_v
        lines.extend(
            [
                f"Vmirror_supply mirror_vdd 0 {_number(request.vdd_v)}",
                f"Imirror_ref mirror_vdd mirror_gate {_number(reference_current)}",
                (
                    f"Mmirror_ref mirror_gate mirror_gate 0 0 {n_model_name} "
                    f"w={_number(request.w_m)} l={_number(request.l_m)}"
                ),
                f"Vmirror_out mirror_out 0 {_number(mirror_vout)}",
                (
                    f"Mmirror_out mirror_out mirror_gate 0 0 {n_model_name} "
                    f"w={_number(request.w_m)} l={_number(request.l_m)}"
                ),
            ]
        )
        vectors.extend(("v(mirror_gate)", "i(Vmirror_out)"))

        follower_gate_fractions = [
            float(value) for value in settings["source_follower_gate_fractions"]
        ]
        follower_load = float(settings["source_follower_load_current_a"])
        for index, fraction in enumerate(follower_gate_fractions):
            lines.extend(
                [
                    f"Vf_supply{index} fvdd{index} 0 {_number(request.vdd_v)}",
                    f"Vf_gate{index} fgate{index} 0 {_number(fraction * request.vdd_v)}",
                    f"If_load{index} fsource{index} 0 {_number(follower_load)}",
                    (
                        f"Mf{index} fvdd{index} fgate{index} fsource{index} 0 "
                        f"{n_model_name} w={_number(request.w_m)} l={_number(request.l_m)}"
                    ),
                ]
            )
            vectors.append(f"v(fsource{index})")

        common_source_gate_fractions = [
            float(value) for value in settings["common_source_gate_fractions"]
        ]
        resistance = float(settings["common_source_resistance_ohm"])
        for index, fraction in enumerate(common_source_gate_fractions):
            lines.extend(
                [
                    f"Vcs_supply{index} csvdd{index} 0 {_number(request.vdd_v)}",
                    f"Vcs_gate{index} csgate{index} 0 {_number(fraction * request.vdd_v)}",
                    f"Rcs{index} csvdd{index} csout{index} {_number(resistance)}",
                    (
                        f"Mcs{index} csout{index} csgate{index} 0 0 {n_model_name} "
                        f"w={_number(request.w_m)} l={_number(request.l_m)}"
                    ),
                ]
            )
            vectors.append(f"v(csout{index})")

        lines.extend(
            [
                ".control",
                "set wr_vecnames",
                "set wr_singlescale",
                "op",
                f"wrdata {raw} " + " ".join(vectors),
                "quit",
                ".endc",
                ".end",
                "",
            ]
        )
        netlist.write_text("\n".join(lines), encoding="utf-8")
        self._run(netlist, log, token)
        values = _read_row(raw, len(vectors))
        cursor = 0
        n_diode: list[float] = []
        p_diode: list[float] = []
        for _bias in diode_biases:
            n_diode.append(abs(values[cursor]))
            p_diode.append(abs(values[cursor + 1]))
            cursor += 2
        mirror_gate = values[cursor]
        mirror_current = abs(values[cursor + 1])
        cursor += 2
        follower_outputs = values[cursor : cursor + len(follower_gate_fractions)]
        cursor += len(follower_gate_fractions)
        common_source_outputs = values[
            cursor : cursor + len(common_source_gate_fractions)
        ]
        cursor += len(common_source_gate_fractions)
        if cursor != len(values):
            raise ModelgenError("basic circuit output vector count mismatch")

        follower_inputs = [fraction * request.vdd_v for fraction in follower_gate_fractions]
        follower_gains = [
            (second_out - first_out) / (second_in - first_in)
            for first_in, second_in, first_out, second_out in zip(
                follower_inputs,
                follower_inputs[1:],
                follower_outputs,
                follower_outputs[1:],
            )
        ]
        cs_inputs = [fraction * request.vdd_v for fraction in common_source_gate_fractions]
        cs_gains = [
            (second_out - first_out) / (second_in - first_in)
            for first_in, second_in, first_out, second_out in zip(
                cs_inputs,
                cs_inputs[1:],
                common_source_outputs,
                common_source_outputs[1:],
            )
        ]
        interior_min = float(criteria["interior_output_fraction_min"]) * request.vdd_v
        interior_max = float(criteria["interior_output_fraction_max"]) * request.vdd_v
        checks = {
            "finite_values": all(math.isfinite(value) for value in values),
            "mos_diode_n_monotonic": all(
                second > first for first, second in zip(n_diode, n_diode[1:])
            ),
            "mos_diode_p_monotonic": all(
                second > first for first, second in zip(p_diode, p_diode[1:])
            ),
            "mirror_gate_in_supply_range": 0.0 < mirror_gate < request.vdd_v,
            "mirror_ratio": float(criteria["mirror_ratio_min"])
            <= mirror_current / reference_current
            <= float(criteria["mirror_ratio_max"]),
            "source_follower_interior": all(
                interior_min < value < interior_max for value in follower_outputs
            ),
            "source_follower_gain": bool(follower_gains)
            and all(
                float(criteria["source_follower_gain_min"])
                <= value
                <= float(criteria["source_follower_gain_max"])
                for value in follower_gains
            ),
            "common_source_interior": all(
                interior_min < value < interior_max for value in common_source_outputs
            ),
            "common_source_gain_negative": bool(cs_gains)
            and all(value < 0.0 for value in cs_gains),
        }
        return {
            "request": {
                "request_id": request.request_id,
                "family": request.family,
                "seed": request.seed,
                "temperature_c": request.temperature_c,
                "l_m": request.l_m,
                "w_m": request.w_m,
                "vdd_v": request.vdd_v,
            },
            "status": "pass" if all(checks.values()) else "fail",
            "checks": checks,
            "mos_diode": {
                "biases_v": diode_biases,
                "n_current_a": n_diode,
                "p_current_a": p_diode,
            },
            "current_mirror_1to1": {
                "reference_current_a": reference_current,
                "output_current_a": mirror_current,
                "ratio": mirror_current / reference_current,
                "gate_voltage_v": mirror_gate,
                "output_voltage_v": mirror_vout,
            },
            "source_follower": {
                "gate_voltage_v": follower_inputs,
                "source_voltage_v": follower_outputs,
                "secant_gain": follower_gains,
                "load_current_a": follower_load,
            },
            "resistive_load_common_source": {
                "gate_voltage_v": cs_inputs,
                "output_voltage_v": common_source_outputs,
                "secant_gain": cs_gains,
                "resistance_ohm": resistance,
            },
        }

    def evaluate_pass_cases(
        self,
        *,
        cases: Sequence[PassCase],
        p_card: str,
        p_model_name: str,
        maximum_units: int,
        relative_error_max: float,
        token: str,
    ) -> list[dict[str, Any]]:
        """Confirm sized PMOS pass banks using explicit parallel unit devices."""

        if not cases:
            raise ModelgenError("PMOS pass-device evaluation requires cases")
        if len({case.temperature_c for case in cases}) != 1:
            raise ModelgenError("one PMOS pass-device batch must use one temperature")
        job = self._directory(token)
        card_path = job / "candidate-p.inc"
        card_path.write_text(p_card, encoding="utf-8")
        raw = job / "pass.dat"
        log = job / "ngspice.log"
        netlist = job / "pass.cir"
        lines = [
            "APM mixed-voltage sealed PMOS pass-device fixtures",
            f'.include "{card_path}"',
            ".options gmin=1e-15",
            f".temp {cases[0].temperature_c}",
        ]
        vectors: list[str] = []
        for index, case in enumerate(cases):
            if case.units > maximum_units:
                raise ModelgenError(f"{case.case_id}: explicit-unit maximum exceeded")
            lines.extend(
                [
                    f"Vpass_s{index} ps{index} 0 {_number(case.vin_v)}",
                    f"Vpass_d{index} pd{index} 0 {_number(case.vout_v)}",
                    (
                        f"Vpass_g{index} pg{index} 0 "
                        f"{_number(case.vin_v - case.required_vsg_v)}"
                    ),
                ]
            )
            for unit in range(case.units):
                lines.append(
                    f"Mpass{index}_{unit} pd{index} pg{index} ps{index} ps{index} "
                    f"{p_model_name} w={_number(case.unit_width_m)} l={_number(case.l_m)}"
                )
            vectors.append(f"i(Vpass_d{index})")
        lines.extend(
            [
                ".control",
                "set wr_vecnames",
                "set wr_singlescale",
                "op",
                f"wrdata {raw} " + " ".join(vectors),
                "quit",
                ".endc",
                ".end",
                "",
            ]
        )
        netlist.write_text("\n".join(lines), encoding="utf-8")
        self._run(netlist, log, token)
        currents = [abs(value) for value in _read_row(raw, len(vectors))]
        result: list[dict[str, Any]] = []
        for case, current in zip(cases, currents):
            relative_error = abs(current / case.load_current_a - 1.0)
            result.append(
                {
                    "case_id": case.case_id,
                    "family": case.family,
                    "seed": case.seed,
                    "temperature_c": case.temperature_c,
                    "l_m": case.l_m,
                    "vin_v": case.vin_v,
                    "vout_v": case.vout_v,
                    "required_vsg_v": case.required_vsg_v,
                    "load_current_a": case.load_current_a,
                    "observed_current_a": current,
                    "relative_error": relative_error,
                    "unit_width_m": case.unit_width_m,
                    "parallel_units": case.units,
                    "total_width_m": case.units * case.unit_width_m,
                    "explicit_parallel_instances": True,
                    "ideal_gate_control": True,
                    "status": "pass" if relative_error <= relative_error_max else "fail",
                }
            )
        return result
