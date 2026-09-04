# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Deterministic, real-ngspice BSIM4 observable-space fitting kernel.

This module is deliberately below ``tools/``.  The installed APM runtime does
not import it.  It fits terminal observations and never parses a reference
model card for parameter values.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import least_squares, minimize

KERNEL_ID = "apm.modelgen.observable-kernel"
KERNEL_VERSION = "1.0.0"
MODEL_DIALECT = "4.8.2"
TERMINAL_AC_FREQUENCY_HZ = 1.0e6
STAGE_ORDER = ("electrostatics", "transport", "output", "charge", "temperature")
FAILURE_TOKENS = (
    "fatal error",
    "simulation interrupted",
    "timestep too small",
    "no convergence in dc analysis",
    "no such file or directory",
)


class ModelgenError(RuntimeError):
    """The offline model-generation operation failed closed."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _float_text(value: float) -> str:
    if not math.isfinite(value):
        raise ModelgenError("model parameter is not finite")
    return f"{value:.12g}"


@dataclass(frozen=True)
class ParameterBound:
    name: str
    stage: str
    lower: float
    initial: float
    upper: float
    transform: str = "linear"

    def __post_init__(self) -> None:
        if self.stage not in STAGE_ORDER:
            raise ModelgenError(f"unknown model-generation stage {self.stage!r}")
        if self.transform not in {"linear", "log"}:
            raise ModelgenError(f"unsupported transform {self.transform!r}")
        if not all(math.isfinite(value) for value in (self.lower, self.initial, self.upper)):
            raise ModelgenError(f"{self.name}: parameter bounds must be finite")
        if not self.lower < self.initial < self.upper:
            raise ModelgenError(f"{self.name}: expected lower < initial < upper")
        if self.transform == "log" and self.lower <= 0.0:
            raise ModelgenError(f"{self.name}: logarithmic lower bound must be positive")

    def decode(self, normalized: float) -> float:
        unit = min(max(float(normalized), 0.0), 1.0)
        if self.transform == "linear":
            return self.lower + unit * (self.upper - self.lower)
        low = math.log(self.lower)
        high = math.log(self.upper)
        return math.exp(low + unit * (high - low))

    def encode(self, value: float) -> float:
        if self.transform == "linear":
            return (float(value) - self.lower) / (self.upper - self.lower)
        return (math.log(float(value)) - math.log(self.lower)) / (
            math.log(self.upper) - math.log(self.lower)
        )


@dataclass(frozen=True)
class SweepRequest:
    request_id: str
    kind: str
    temperature_c: int
    l_m: float
    w_m: float
    fixed_bias_v: float
    sweep_stop_v: float
    points: int

    def __post_init__(self) -> None:
        if self.kind not in {"idvg", "idvd"}:
            raise ModelgenError(f"{self.request_id}: unsupported sweep kind {self.kind!r}")
        if self.points < 5:
            raise ModelgenError(f"{self.request_id}: at least five sweep points are required")
        for field, value in (
            ("l_m", self.l_m),
            ("w_m", self.w_m),
            ("fixed_bias_v", self.fixed_bias_v),
            ("sweep_stop_v", self.sweep_stop_v),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ModelgenError(f"{self.request_id}: {field} must be positive and finite")


@dataclass(frozen=True)
class Curve:
    request: SweepRequest
    sweep_v: np.ndarray
    idmag_a: np.ndarray
    terminal_cgg_f: np.ndarray | None

    def as_hash_payload(self) -> dict[str, Any]:
        return {
            "request": self.request.__dict__,
            "sweep_v": [float(value) for value in self.sweep_v],
            "idmag_a": [float(value) for value in self.idmag_a],
            "terminal_cgg_f": (
                [float(value) for value in self.terminal_cgg_f]
                if self.terminal_cgg_f is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ModelSource:
    model_name: str
    include_paths: tuple[Path, ...] = ()
    rendered_card: str | None = None

    def __post_init__(self) -> None:
        if bool(self.include_paths) == bool(self.rendered_card):
            raise ModelgenError("model source requires exactly one of include_paths/rendered_card")


@dataclass(frozen=True)
class FitSettings:
    seeds: tuple[int, ...]
    starts_per_stage: int
    local_max_nfev: int
    sensitivity_fraction: float
    current_floor_a: float
    current_log_tolerance_dec: float
    gmid_log_tolerance: float
    gdsid_log_tolerance: float
    cgg_log_tolerance: float


@dataclass(frozen=True)
class FitResult:
    parameters: dict[str, float]
    stage_records: tuple[dict[str, Any], ...]
    objective_rms: float
    evaluation_count: int
    rendered_card: str


@dataclass(frozen=True)
class CandidateEvaluation:
    normalized_parameters: np.ndarray
    residual: np.ndarray
    curves: dict[str, Curve] | None
    feasible: bool


def render_bsim4_card(
    *,
    model_name: str,
    polarity: str,
    parameters: Mapping[str, float],
    lmin_m: float,
    lmax_m: float,
    wmin_m: float,
    wmax_m: float,
) -> str:
    """Render a canonical APM-owned BSIM4 4.8.2 card byte-for-byte."""

    if polarity not in {"n", "p"}:
        raise ModelgenError(f"unsupported polarity {polarity!r}")
    required = {
        "toxe",
        "xj",
        "ndep",
        "nsd",
        "vth0_magnitude",
        "k1",
        "k2",
        "nfactor",
        "voff",
        "dvt0",
        "dvt1",
        "dvt2",
        "eta0",
        "etab",
        "dsub",
        "u0",
        "ua",
        "ub",
        "vsat",
        "rdsw",
        "rdswmin",
        "pclm",
        "pdiblc1",
        "pdiblc2",
        "drout",
        "delta",
        "fprout",
        "pdits",
        "pscbe1",
        "pscbe2",
        "cgso",
        "cgdo",
        "cgbo",
        "xpart",
        "ckappas",
        "ckappad",
        "acde",
        "moin",
        "noff",
        "voffcv",
        "kt1",
        "kt1l",
        "kt2",
        "ute",
        "at",
    }
    missing = sorted(required - parameters.keys())
    extras = sorted(parameters.keys() - required)
    if missing or extras:
        raise ModelgenError(f"card parameter mismatch: missing={missing}, extras={extras}")
    values = {name: _float_text(float(value)) for name, value in sorted(parameters.items())}
    signed_vth = float(parameters["vth0_magnitude"]) * (1.0 if polarity == "n" else -1.0)
    device_type = "nmos" if polarity == "n" else "pmos"
    lines = [
        "* SPDX-FileCopyrightText: APM contributors",
        "* SPDX-License-Identifier: Apache-2.0",
        "* Deterministically generated by apm.modelgen.observable-kernel@1.0.0",
        f".model {model_name} {device_type} level=54 version=4.8.2",
        "+ binunit=1 paramchk=1 tnom=27",
        "+ mobmod=1 capmod=2 rdsmod=0 igcmod=0 igbmod=0 gidlmod=0",
        "+ rbodymod=0 rgatemod=0 acnqsmod=0 trnqsmod=0",
        "+ geomod=0 diomod=1 permod=1 fnoimod=1 tnoimod=0",
        (
            f"+ lmin={_float_text(lmin_m)} lmax={_float_text(lmax_m)} "
            f"wmin={_float_text(wmin_m)} wmax={_float_text(wmax_m)}"
        ),
        (
            f"+ toxe={values['toxe']} toxp={values['toxe']} toxm={values['toxe']} "
            "+ dtox=0 epsrox=3.9"
        ),
        f"+ xj={values['xj']} ndep={values['ndep']} nsd={values['nsd']} ngate=0",
        (f"+ vth0={_float_text(signed_vth)} k1={values['k1']} k2={values['k2']} + lpe0=0 lpeb=0"),
        (
            f"+ nfactor={values['nfactor']} voff={values['voff']} dvt0={values['dvt0']} "
            f"dvt1={values['dvt1']} dvt2={values['dvt2']}"
        ),
        f"+ eta0={values['eta0']} etab={values['etab']} dsub={values['dsub']}",
        f"+ u0={values['u0']} ua={values['ua']} ub={values['ub']} uc=0 ute={values['ute']}",
        f"+ vsat={values['vsat']} a0=1 ags=0 keta=0",
        f"+ rdsw={values['rdsw']} rdswmin={values['rdswmin']} prwg=0 prwb=0 wr=1",
        (
            f"+ pclm={values['pclm']} pdiblc1={values['pdiblc1']} "
            f"pdiblc2={values['pdiblc2']} pdiblcb=0 drout={values['drout']} pvag=0"
        ),
        (
            f"+ delta={values['delta']} fprout={values['fprout']} "
            f"pdits={values['pdits']} pditsd=0 pscbe1={values['pscbe1']} "
            f"pscbe2={values['pscbe2']}"
        ),
        (
            f"+ cgso={values['cgso']} cgdo={values['cgdo']} cgbo={values['cgbo']} "
            f"xpart={values['xpart']}"
        ),
        (
            f"+ ckappas={values['ckappas']} ckappad={values['ckappad']} "
            f"acde={values['acde']} moin={values['moin']} noff={values['noff']} "
            f"voffcv={values['voffcv']}"
        ),
        (f"+ kt1={values['kt1']} kt1l={values['kt1l']} kt2={values['kt2']} at={values['at']}"),
        "",
    ]
    return "\n".join(lines)


def _read_wrdata(path: Path, expected_columns: int) -> tuple[np.ndarray, ...]:
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
        rows.append(values)
    if not rows:
        raise ModelgenError(f"ngspice produced no samples in {path}")
    columns = tuple(np.asarray(column, dtype=float) for column in zip(*rows))
    return columns


class NgspiceEvaluator:
    """Run deterministic terminal DC and AC observations against a BSIM4 card."""

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

    def _run_batch(self, *, netlist: Path, log: Path, token: str) -> None:
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
            raise ModelgenError(f"ngspice did not report reference-version completion for {token}")

    def _terminal_cgg(
        self,
        *,
        source: ModelSource,
        polarity: str,
        requests: Sequence[SweepRequest],
        include_paths: Sequence[Path],
        job_dir: Path,
        token: str,
    ) -> dict[str, np.ndarray]:
        """Measure Cgg from terminal Ygg, never from simulator-internal state."""

        idvg_requests = [request for request in requests if request.kind == "idvg"]
        if not idvg_requests:
            return {}
        sign = 1.0 if polarity == "n" else -1.0
        netlist = job_dir / "terminal-cgg.cir"
        log = job_dir / "terminal-cgg.log"
        lines = [
            "APM offline model-generation terminal Cgg observations",
            *(f'.include "{path.resolve()}"' for path in include_paths),
            ".options gmin=1e-15",
            f".temp {idvg_requests[0].temperature_c}",
        ]
        raw_by_request: dict[str, tuple[Path, list[str]]] = {}
        serial = 0
        for request_index, request in enumerate(idvg_requests):
            vector_names: list[str] = []
            for sweep_v in np.linspace(0.0, request.sweep_stop_v, request.points):
                lines.extend(
                    [
                        f"Vcd{serial} cd{serial} 0 {_float_text(sign * request.fixed_bias_v)} AC 0",
                        f"Vcg{serial} cg{serial} 0 {_float_text(sign * sweep_v)} AC 1",
                        f"Vcs{serial} cs{serial} 0 0 AC 0",
                        f"Vcb{serial} cb{serial} 0 0 AC 0",
                        (
                            f"Mc{serial} cd{serial} cg{serial} cs{serial} cb{serial} "
                            f"{source.model_name} w={_float_text(request.w_m)} "
                            f"l={_float_text(request.l_m)}"
                        ),
                    ]
                )
                vector_names.append(f"i(Vcg{serial})")
                serial += 1
            raw_path = job_dir / f"cgg-{request_index:03d}-{request.request_id}.dat"
            raw_by_request[request.request_id] = (raw_path, vector_names)
        lines.extend(
            [
                ".control",
                "set wr_vecnames",
                "set wr_singlescale",
                (
                    f"ac lin 1 {_float_text(TERMINAL_AC_FREQUENCY_HZ)} "
                    f"{_float_text(TERMINAL_AC_FREQUENCY_HZ)}"
                ),
            ]
        )
        for raw_path, vector_names in raw_by_request.values():
            lines.append(f"wrdata {raw_path} " + " ".join(vector_names))
        lines.extend(["quit", ".endc", ".end", ""])
        netlist.write_text("\n".join(lines), encoding="utf-8")
        self._run_batch(netlist=netlist, log=log, token=f"{token}-terminal-cgg")

        omega = 2.0 * math.pi * TERMINAL_AC_FREQUENCY_HZ
        result: dict[str, np.ndarray] = {}
        for request in idvg_requests:
            raw_path, vector_names = raw_by_request[request.request_id]
            columns = _read_wrdata(raw_path, 1 + 2 * len(vector_names))
            if columns[0].size != 1 or not math.isclose(
                float(columns[0][0]), TERMINAL_AC_FREQUENCY_HZ, rel_tol=1e-12
            ):
                raise ModelgenError(f"{request.request_id}: unexpected terminal AC frequency")
            # Voltage-source current is positive out of the device terminal. Negating
            # it gives Ygg's current-entering-device convention.
            cgg = np.asarray(
                [-float(columns[2 * index + 2][0]) / omega for index in range(len(vector_names))]
            )
            if cgg.shape != (request.points,) or not np.all(np.isfinite(cgg)):
                raise ModelgenError(f"{request.request_id}: invalid terminal Cgg samples")
            if not np.all(cgg > 0.0):
                raise ModelgenError(f"{request.request_id}: non-positive terminal Cgg")
            result[request.request_id] = cgg
        return result

    def evaluate(
        self,
        *,
        source: ModelSource,
        polarity: str,
        requests: Sequence[SweepRequest],
        token: str,
        measure_terminal_cgg: bool = False,
    ) -> dict[str, Curve]:
        if not requests:
            raise ModelgenError("at least one sweep request is required")
        if polarity not in {"n", "p"}:
            raise ModelgenError(f"unsupported polarity {polarity!r}")
        temperatures = {request.temperature_c for request in requests}
        if len(temperatures) != 1:
            raise ModelgenError("one evaluator invocation may contain only one temperature")
        safe_token = re.sub(r"[^a-zA-Z0-9_.-]", "_", token)
        job_dir = self.work_directory / safe_token
        job_dir.mkdir(parents=True, exist_ok=True)
        card_path = job_dir / "candidate.inc"
        if source.rendered_card is not None:
            card_path.write_text(source.rendered_card, encoding="utf-8")
            include_paths = (card_path,)
        else:
            include_paths = source.include_paths
        netlist = job_dir / "sweeps.cir"
        log = job_dir / "ngspice.log"
        sign = 1.0 if polarity == "n" else -1.0
        lines = [
            "APM offline model-generation terminal sweeps",
            *(f'.include "{path.resolve()}"' for path in include_paths),
            ".options gmin=1e-15",
            f".temp {next(iter(temperatures))}",
        ]
        for index, request in enumerate(requests):
            if request.kind == "idvg":
                vd = sign * request.fixed_bias_v
                vg = 0.0
            else:
                vd = 0.0
                vg = sign * request.fixed_bias_v
            lines.extend(
                [
                    f"Vd{index} d{index} 0 {_float_text(vd)}",
                    f"Vg{index} g{index} 0 {_float_text(vg)}",
                    f"Vs{index} s{index} 0 0",
                    f"Vb{index} b{index} 0 0",
                    (
                        f"Mq{index} d{index} g{index} s{index} b{index} "
                        f"{source.model_name} w={_float_text(request.w_m)} "
                        f"l={_float_text(request.l_m)}"
                    ),
                ]
            )
        lines.extend([".control", "set wr_vecnames", "set wr_singlescale", "save all"])
        raw_paths: list[Path] = []
        for index, request in enumerate(requests):
            raw_path = job_dir / f"{index:03d}-{request.request_id}.dat"
            raw_paths.append(raw_path)
            source_name = f"Vg{index}" if request.kind == "idvg" else f"Vd{index}"
            step = sign * request.sweep_stop_v / (request.points - 1)
            lines.extend(
                [
                    (
                        f"dc {source_name} 0 {_float_text(sign * request.sweep_stop_v)} "
                        f"{_float_text(step)}"
                    ),
                    (
                        f"wrdata {raw_path} "
                        f"v({'g' if request.kind == 'idvg' else 'd'}{index}) i(vd{index})"
                    ),
                ]
            )
        lines.extend(["quit", ".endc", ".end", ""])
        netlist.write_text("\n".join(lines), encoding="utf-8")
        self._run_batch(netlist=netlist, log=log, token=token)
        cgg_by_request = (
            self._terminal_cgg(
                source=source,
                polarity=polarity,
                requests=requests,
                include_paths=include_paths,
                job_dir=job_dir,
                token=token,
            )
            if measure_terminal_cgg
            else {}
        )
        curves: dict[str, Curve] = {}
        for request, raw_path in zip(requests, raw_paths):
            _, raw_sweep, raw_current = _read_wrdata(raw_path, 3)
            curve = Curve(
                request=request,
                sweep_v=np.abs(raw_sweep),
                idmag_a=np.abs(raw_current),
                terminal_cgg_f=cgg_by_request.get(request.request_id),
            )
            arrays = (curve.sweep_v, curve.idmag_a)
            if not all(np.all(np.isfinite(array)) for array in arrays):
                raise ModelgenError(f"{request.request_id}: ngspice emitted NaN/Inf")
            curves[request.request_id] = curve
        return curves

    def evaluate_many(
        self,
        *,
        source: ModelSource,
        polarity: str,
        requests: Sequence[SweepRequest],
        token: str,
        measure_terminal_cgg: bool = False,
    ) -> dict[str, Curve]:
        """Evaluate a possibly multi-temperature request set deterministically."""

        grouped: dict[int, list[SweepRequest]] = {}
        for request in requests:
            grouped.setdefault(request.temperature_c, []).append(request)
        result: dict[str, Curve] = {}
        for temperature in sorted(grouped):
            result.update(
                self.evaluate(
                    source=source,
                    polarity=polarity,
                    requests=grouped[temperature],
                    token=f"{token}-t{temperature:+d}",
                    measure_terminal_cgg=measure_terminal_cgg,
                )
            )
        return result


def curves_sha256(curves: Mapping[str, Curve]) -> str:
    payload = [curves[key].as_hash_payload() for key in sorted(curves)]
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def _safe_log_ratio(candidate: np.ndarray, target: np.ndarray, floor: float) -> np.ndarray:
    return np.log(np.maximum(candidate, floor) / np.maximum(target, floor))


def terminal_derivative(curve: Curve) -> np.ndarray:
    """Return the canonical terminal derivative on the effective sweep axis."""

    return np.gradient(curve.idmag_a, curve.sweep_v, edge_order=2)


def qualified_current_floor(request: SweepRequest, absolute_floor_a: float) -> float:
    """Return the threshold-relative lower edge of the conduction region."""

    threshold_criterion_a = 1e-7 * request.w_m / request.l_m
    return max(float(absolute_floor_a), 0.003 * threshold_criterion_a)


def residual_vector(
    candidate: Mapping[str, Curve],
    target: Mapping[str, Curve],
    *,
    domains: Iterable[str],
    settings: FitSettings,
) -> np.ndarray:
    """Return a fixed-shape observable residual vector for least squares."""

    selected = set(domains)
    residuals: list[float] = []
    for request_id in sorted(target):
        reference = target[request_id]
        observed = candidate.get(request_id)
        if observed is None or observed.idmag_a.shape != reference.idmag_a.shape:
            residuals.extend([100.0] * (reference.idmag_a.size * 2))
            continue
        current_floor_a = qualified_current_floor(reference.request, settings.current_floor_a)
        mask = reference.idmag_a >= current_floor_a
        # Retain deterministic coverage while avoiding overweighting dense curves.
        indices = np.flatnonzero(mask)[:: max(1, int(np.count_nonzero(mask) / 12))]
        if indices.size == 0:
            indices = np.asarray([reference.idmag_a.size - 1])
        if "electrostatics" in selected or "transport" in selected or "output" in selected:
            residuals.extend(
                (
                    _safe_log_ratio(
                        observed.idmag_a[indices],
                        reference.idmag_a[indices],
                        current_floor_a,
                    )
                    / (settings.current_log_tolerance_dec * math.log(10.0))
                ).tolist()
            )
        if reference.request.kind == "idvg" and "transport" in selected:
            target_gmid = terminal_derivative(reference)[indices] / np.maximum(
                reference.idmag_a[indices], current_floor_a
            )
            candidate_gmid = terminal_derivative(observed)[indices] / np.maximum(
                observed.idmag_a[indices], current_floor_a
            )
            residuals.extend(
                (
                    _safe_log_ratio(candidate_gmid, target_gmid, 1e-12)
                    / settings.gmid_log_tolerance
                ).tolist()
            )
        if reference.request.kind == "idvd" and "output" in selected:
            target_gdsid = terminal_derivative(reference)[indices] / np.maximum(
                reference.idmag_a[indices], current_floor_a
            )
            candidate_gdsid = terminal_derivative(observed)[indices] / np.maximum(
                observed.idmag_a[indices], current_floor_a
            )
            residuals.extend(
                (
                    _safe_log_ratio(candidate_gdsid, target_gdsid, 1e-12)
                    / settings.gdsid_log_tolerance
                ).tolist()
            )
        if reference.request.kind == "idvg" and "charge" in selected:
            if reference.terminal_cgg_f is None or observed.terminal_cgg_f is None:
                raise ModelgenError(f"{request_id}: terminal Cgg observation is missing")
            residuals.extend(
                (
                    _safe_log_ratio(
                        observed.terminal_cgg_f[indices],
                        reference.terminal_cgg_f[indices],
                        1e-24,
                    )
                    / settings.cgg_log_tolerance
                ).tolist()
            )
    if not residuals:
        raise ModelgenError("objective selected no observable residuals")
    result = np.asarray(residuals, dtype=float)
    result[~np.isfinite(result)] = 100.0
    return np.clip(result, -100.0, 100.0)


def hard_constraint_observations(
    curves: Mapping[str, Curve], current_floor_a: float
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    for request_id, curve in sorted(curves.items()):
        qualified_floor_a = qualified_current_floor(curve.request, current_floor_a)
        mask = curve.idmag_a >= qualified_floor_a
        values = curve.idmag_a[mask]
        derivative = terminal_derivative(curve)
        arrays = [curve.sweep_v, curve.idmag_a]
        if curve.terminal_cgg_f is not None:
            arrays.append(curve.terminal_cgg_f)
        checks[f"{request_id}.finite"] = all(np.all(np.isfinite(array)) for array in arrays)
        if curve.terminal_cgg_f is not None:
            checks[f"{request_id}.positive_terminal_cgg"] = bool(
                np.all(curve.terminal_cgg_f > 0.0)
            )
        checks[f"{request_id}.positive_current"] = bool(values.size and np.all(values > 0.0))
        if curve.request.kind == "idvg":
            tolerance = (
                max(float(np.max(values)) * 1e-7, qualified_floor_a)
                if values.size
                else qualified_floor_a
            )
            checks[f"{request_id}.monotonic"] = bool(
                values.size > 1 and np.all(np.diff(values) >= -tolerance)
            )
            checks[f"{request_id}.positive_gm"] = bool(np.all(derivative[mask] > 0.0))
        else:
            positive_region = mask & (curve.sweep_v > 0.0)
            output_values = curve.idmag_a[positive_region]
            tolerance = (
                max(float(np.max(output_values)) * 1e-7, qualified_floor_a)
                if output_values.size
                else qualified_floor_a
            )
            checks[f"{request_id}.monotonic"] = bool(
                output_values.size > 1 and np.all(np.diff(output_values) >= -tolerance)
            )
            checks[f"{request_id}.positive_gds"] = bool(np.all(derivative[positive_region] > 0.0))
    return {"status": "pass" if all(checks.values()) else "fail", "checks": checks}


def fit_staged(
    *,
    evaluator: NgspiceEvaluator,
    target: Mapping[str, Curve],
    requests: Sequence[SweepRequest],
    polarity: str,
    model_name: str,
    fixed_parameters: Mapping[str, float],
    bounds: Sequence[ParameterBound],
    geometry_bounds: Mapping[str, float],
    settings: FitSettings,
) -> FitResult:
    """Fit cumulative parameter stages with deterministic starts and refinement."""

    by_name = {bound.name: bound for bound in bounds}
    if len(by_name) != len(bounds):
        raise ModelgenError("parameter bound names must be unique")
    current = {**fixed_parameters, **{bound.name: bound.initial for bound in bounds}}
    stage_records: list[dict[str, Any]] = []
    active_names: list[str] = []
    domains: list[str] = []
    evaluation_start = evaluator.evaluation_count

    def render(parameters: Mapping[str, float]) -> str:
        return render_bsim4_card(
            model_name=model_name,
            polarity=polarity,
            parameters=parameters,
            lmin_m=float(geometry_bounds["lmin_m"]),
            lmax_m=float(geometry_bounds["lmax_m"]),
            wmin_m=float(geometry_bounds["wmin_m"]),
            wmax_m=float(geometry_bounds["wmax_m"]),
        )

    for stage_index, stage in enumerate(STAGE_ORDER):
        released = [bound.name for bound in bounds if bound.stage == stage]
        if not released:
            continue
        active_names.extend(released)
        domains.append(stage)
        active_bounds = [by_name[name] for name in active_names]
        x_initial = np.asarray([bound.encode(current[bound.name]) for bound in active_bounds])
        cache: dict[str, CandidateEvaluation] = {}
        if stage == "temperature":
            stage_requests = tuple(requests)
        else:
            stage_requests = tuple(request for request in requests if request.temperature_c == 27)
        stage_target = {
            request.request_id: target[request.request_id] for request in stage_requests
        }
        if not stage_requests:
            raise ModelgenError(f"stage {stage!r} has no calibration requests")

        base_parameters = dict(current)
        stage_bounds = tuple(active_bounds)
        stage_domains = tuple(domains)

        def parameters_for(
            x: np.ndarray,
            *,
            parameters_at_stage_start: dict[str, float] = base_parameters,
            parameter_bounds_at_stage: tuple[ParameterBound, ...] = stage_bounds,
        ) -> dict[str, float]:
            values = dict(parameters_at_stage_start)
            for bound, normalized in zip(parameter_bounds_at_stage, x):
                values[bound.name] = bound.decode(float(normalized))
            return values

        def objective(
            x: np.ndarray,
            *,
            stage_cache: dict[str, CandidateEvaluation] = cache,
            stage_number: int = stage_index,
            stage_name: str = stage,
            objective_domains: tuple[str, ...] = stage_domains,
            requests_for_stage: tuple[SweepRequest, ...] = stage_requests,
            target_for_stage: dict[str, Curve] = stage_target,
        ) -> np.ndarray:
            key = sha256_bytes(np.asarray(x, dtype=np.float64).tobytes())
            if key in stage_cache:
                return stage_cache[key].residual
            try:
                curves = evaluator.evaluate_many(
                    source=ModelSource(
                        model_name=model_name, rendered_card=render(parameters_for(x))
                    ),
                    polarity=polarity,
                    requests=requests_for_stage,
                    token=f"stage-{stage_number}-{stage_name}-working",
                    measure_terminal_cgg="charge" in objective_domains,
                )
                hard = hard_constraint_observations(curves, settings.current_floor_a)
                residual = residual_vector(
                    curves, target_for_stage, domains=objective_domains, settings=settings
                )
                feasible = hard["status"] == "pass"
            except (ModelgenError, OSError, subprocess.SubprocessError):
                curves = None
                template = residual_vector(
                    target_for_stage,
                    target_for_stage,
                    domains=objective_domains,
                    settings=settings,
                )
                residual = np.full(template.shape, 100.0)
                feasible = False
            stage_cache[key] = CandidateEvaluation(
                normalized_parameters=np.asarray(x, dtype=float).copy(),
                residual=residual,
                curves=curves,
                feasible=feasible,
            )
            return residual

        def feasible_cost(
            x: np.ndarray, *, stage_cache: dict[str, CandidateEvaluation] = cache
        ) -> float:
            residual = objective(x)
            key = sha256_bytes(np.asarray(x, dtype=np.float64).tobytes())
            return float(np.mean(np.square(residual))) if stage_cache[key].feasible else math.inf

        baseline = objective(x_initial)
        baseline_cost = float(np.sqrt(np.mean(np.square(baseline))))
        sensitivity: list[dict[str, Any]] = []
        for index, bound in enumerate(active_bounds):
            delta = settings.sensitivity_fraction
            lower = x_initial.copy()
            upper = x_initial.copy()
            lower[index] = max(0.0, lower[index] - delta)
            upper[index] = min(1.0, upper[index] + delta)
            lower_cost = float(np.sqrt(np.mean(np.square(objective(lower)))))
            upper_cost = float(np.sqrt(np.mean(np.square(objective(upper)))))
            span = max(upper[index] - lower[index], 1e-12)
            sensitivity.append(
                {
                    "parameter": bound.name,
                    "normalized_local_cost_slope": (upper_cost - lower_cost) / span,
                    "lower_cost_rms": lower_cost,
                    "upper_cost_rms": upper_cost,
                }
            )

        starts: list[np.ndarray] = [x_initial]
        for seed in settings.seeds:
            rng = np.random.default_rng(seed + stage_index)
            for _ in range(settings.starts_per_stage):
                perturbation = rng.normal(0.0, 0.12, size=x_initial.size)
                starts.append(np.clip(x_initial + perturbation, 0.0, 1.0))
        start_costs = [feasible_cost(start) for start in starts]
        if not any(math.isfinite(cost) for cost in start_costs):
            raise ModelgenError(f"stage {stage!r} found no feasible deterministic start")
        chosen_start_index = int(np.argmin(start_costs))
        chosen_start = starts[chosen_start_index]
        refined = least_squares(
            objective,
            chosen_start,
            bounds=(np.zeros_like(chosen_start), np.ones_like(chosen_start)),
            max_nfev=settings.local_max_nfev,
            xtol=1e-6,
            ftol=1e-6,
            gtol=1e-6,
            diff_step=1e-3,
            verbose=0,
        )
        refined_x = np.asarray(refined.x, dtype=float)
        cross_stage_refinement = {
            "transport": ("vth0_magnitude", "nfactor", "voff"),
            "output": ("eta0", "dsub"),
            "charge": ("toxe",),
        }
        derivative_free_names = list(
            dict.fromkeys((*cross_stage_refinement.get(stage, ()), *released))
        )
        derivative_free_indices = [active_names.index(name) for name in derivative_free_names]
        derivative_free_start = refined_x[derivative_free_indices]

        def scalar_released(
            released_x: np.ndarray,
            *,
            full_start: np.ndarray = refined_x,
            selected_indices: list[int] = derivative_free_indices,
        ) -> float:
            full_x = full_start.copy()
            full_x[selected_indices] = released_x
            residual = objective(full_x)
            return float(np.mean(np.square(residual)))

        derivative_free = minimize(
            scalar_released,
            derivative_free_start,
            method="Powell",
            bounds=[(0.0, 1.0)] * len(derivative_free_indices),
            options={"maxfev": 200, "xtol": 1e-4, "ftol": 1e-5},
        )
        if derivative_free.fun < scalar_released(derivative_free_start):
            refined_x[derivative_free_indices] = derivative_free.x
        objective(refined_x)
        feasible_records = [record for record in cache.values() if record.feasible]
        if not feasible_records:
            raise ModelgenError(f"stage {stage!r} retained no feasible candidate")
        selected_record = min(
            feasible_records, key=lambda item: float(np.mean(np.square(item.residual)))
        )
        selected_x = selected_record.normalized_parameters
        current = parameters_for(selected_x)
        final_residual = selected_record.residual
        stage_records.append(
            {
                "stage": stage,
                "released_parameters": released,
                "active_parameters": list(active_names),
                "objective_domains": list(domains),
                "baseline_rms": baseline_cost,
                "bounded_start_count": len(starts),
                "chosen_start_index": chosen_start_index,
                "local_refinement": {
                    "method": "scipy.optimize.least_squares/trf",
                    "success": bool(refined.success),
                    "status": int(refined.status),
                    "message": str(refined.message),
                    "nfev": int(refined.nfev),
                    "final_rms": float(np.sqrt(np.mean(np.square(final_residual)))),
                },
                "bounded_derivative_free_refinement": {
                    "method": "scipy.optimize.minimize/Powell",
                    "success": bool(derivative_free.success),
                    "message": str(derivative_free.message),
                    "nfev": int(derivative_free.nfev),
                    "parameters": derivative_free_names,
                    "reopened_prior_stage_parameters": [
                        name for name in derivative_free_names if name not in released
                    ],
                    "final_rms": float(np.sqrt(np.mean(np.square(final_residual)))),
                },
                "local_sensitivity": sensitivity,
                "resolved_parameters": {name: current[name] for name in active_names},
            }
        )
    final_card = render(current)
    final_curves = evaluator.evaluate_many(
        source=ModelSource(model_name=model_name, rendered_card=final_card),
        polarity=polarity,
        requests=requests,
        token=f"final-{polarity}",
        measure_terminal_cgg=True,
    )
    final_residual = residual_vector(
        final_curves,
        target,
        domains=[record["stage"] for record in stage_records],
        settings=settings,
    )
    hard = hard_constraint_observations(final_curves, settings.current_floor_a)
    if hard["status"] != "pass":
        raise ModelgenError("final fitted candidate violates a numerical hard constraint")
    return FitResult(
        parameters=current,
        stage_records=tuple(stage_records),
        objective_rms=float(np.sqrt(np.mean(np.square(final_residual)))),
        evaluation_count=evaluator.evaluation_count - evaluation_start,
        rendered_card=final_card,
    )
