# SPDX-FileCopyrightText: 2026 APM preflight contributors
# SPDX-License-Identifier: Apache-2.0

"""Bounded ngspice-47 preflight; not a production variation API or release gate.

Use immutable VTG inputs at W=1um, L=.12um, N/P, 300K, |VDS|=50mV first.
Application, extraction and mapping are reported independently. No measured
beta coefficient is used. Each uncached request uses a fresh -n -b process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import numpy as np
from numerical_core import PreflightError, extract_mg, inverse_mapping, local_jacobian
from scipy.interpolate import CubicSpline
from scipy.signal import find_peaks

BASE_REF = "b09d104759296e6dd59c6f08e6cd30fa716d6461"
MODEL_FILES = {
    "models/apm045/vendor/freepdk45/NMOS_VTG.inc": "d98a9f5103d4248f46fdf4086d19fe64c9e3eded",
    "models/apm045/vendor/freepdk45/PMOS_VTG.inc": "5d3fcca1b06d81685713ec4dd90beadb4051f5e1",
    "models/apm045/families/vtg/ngspice/wrapper.inc": "62cc2ef43146224a2dc0b06398139b2d1ece2ada",
}
LEAF_A = "@m.xtop.xea.xa.mapm045_vtg_core"
LEAF_B = "@m.xtop.xea.xb.mapm045_vtg_core"
BAD_LEAF = "@m.xtop.xea.xmissing.mapm045_vtg_core"
TARGETS = [(0.01, 0.02), (0.01, -0.02), (-0.01, 0.02), (-0.01, -0.02)]
SCALES = np.array([0.01, 0.02])
RAW_STEPS = np.array([0.001, 0.01])
PROBE_RAW = (0.02, math.log(1.05))
ERROR_LINE = re.compile(
    r"^\s*(?:fatal error|error(?:\s|:)|warning:|.*simulation interrupted)", re.IGNORECASE
)


def write_json(path: Path, value: object):
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_hash(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def verify_models(root: Path) -> dict:
    observed = {}
    for relative, expected in MODEL_FILES.items():
        path = root / relative
        if not path.is_file():
            raise PreflightError(f"MODEL_MISSING: {relative}")
        observed[relative] = {
            "git_blob_sha1": git_blob_hash(path.read_bytes()),
            "sha256": sha256(path),
        }
        if observed[relative]["git_blob_sha1"] != expected:
            raise PreflightError(f"MODEL_IDENTITY_MISMATCH: {relative}")
    return observed


def expected_readback(w_um, l_um, raw) -> dict:
    return {
        "a_w": w_um * 1e-6,
        "a_l": l_um * 1e-6,
        "a_delvto": float(raw[0]),
        "a_mulu0": math.exp(float(raw[1])),
        "b_w": w_um * 1e-6,
        "b_l": l_um * 1e-6,
        "b_delvto": 0.0,
        "b_mulu0": 1.0,
    }


def readback_commands(prefix="") -> list[str]:
    commands = []
    for label, leaf in [("a", LEAF_A), ("b", LEAF_B)]:
        for parameter in ("w", "l", "delvto", "mulu0"):
            key = f"{prefix}{label}_{parameter}"
            commands += [f"let {key} = {leaf}[{parameter}]", f"print {key}"]
    return commands


def render_deck(
    root: Path,
    polarity: str,
    w_um: float,
    l_um: float,
    step: float,
    delvto: float,
    ln_mulu0: float,
    temperature_c: float = 26.85,
    vds: float = 0.05,
    invalid_target: bool = False,
    reset_after_apply: bool = False,
) -> str:
    if polarity not in ("n", "p"):
        raise PreflightError("invalid polarity")
    if not all(math.isfinite(x) for x in (w_um, l_um, step, delvto, ln_mulu0, temperature_c, vds)):
        raise PreflightError("nonfinite deck parameter")
    if min(w_um, l_um, step, vds) <= 0 or vds > 1 or step > 0.125:
        raise PreflightError("invalid deck parameter")
    if invalid_target and reset_after_apply:
        raise PreflightError("negative controls must be independent")
    includes = []
    for relative in MODEL_FILES:
        path = str((root / relative).resolve())
        if any(c in path for c in ('"', "\n", "\r")):
            raise PreflightError("unsafe include path")
        includes.append(f'.include "{path}"')
    source, drain, stop, increment = (
        (0.0, vds, 1.0, step) if polarity == "n" else (1.0, 1.0 - vds, -1.0, -step)
    )
    wrapper = f"apm045_vtg_{'nmos' if polarity == 'n' else 'pmos'}"
    target = BAD_LEAF if invalid_target else LEAF_A
    apply = [
        f"alter {LEAF_A}[delvto] = 0",
        f"alter {LEAF_A}[mulu0] = 1",
        f"alter {LEAF_B}[delvto] = 0",
        f"alter {LEAF_B}[mulu0] = 1",
        f"alter {target}[delvto] = {delvto:.17g}",
        f"alter {target}[mulu0] = {math.exp(ln_mulu0):.17g}",
    ]
    if reset_after_apply:
        # Demonstrate successful application BEFORE reset, then its specific loss.
        apply += ["op", *readback_commands("applied_"), "reset"]
    return "\n".join(
        [
            "* APM v5 exploratory hierarchy/MG probe; no statistical calibration claim",
            *includes,
            f".temp {temperature_c:.17g}",
            ".options reltol=1e-7 abstol=1e-15 vntol=1e-9",
            f"Vs s 0 {source:.17g}",
            "Vb b s 0",
            f"Vda da 0 {drain:.17g}",
            f"Vdb db 0 {drain:.17g}",
            "Vctrl g s 0",
            f"Xtop da db g s b stage1 w={w_um:.17g}u l={l_um:.17g}u",
            ".subckt stage1 da db g s b w=1u l=.12u",
            "Xea da db g s b stage2 w='w' l='l'",
            ".ends stage1",
            ".subckt stage2 da db g s b w=1u l=.12u",
            f"Xa da g s b {wrapper} w='w' l='l'",
            f"Xb db g s b {wrapper} w='w' l='l'",
            ".ends stage2",
            ".control",
            "set num_threads=1",
            "set noaskquit",
            "set numdgt=17",
            "set wr_singlescale",
            "set wr_vecnames",
            *apply,
            "op",
            *readback_commands(),
            f"dc Vctrl 0 {stop:.17g} {increment:.17g}",
            "let u = abs(v(g)-v(s))",
            "wrdata sweep.txt u i(Vda) i(Vdb)",
            "quit",
            ".endc",
            ".end",
            "",
        ]
    )


def readback_scalars(log: str, prefix="") -> dict:
    result = {}
    for key in expected_readback(1, 0.12, (0, 0)):
        found = re.findall(r"(?m)^\s*" + prefix + key + r"\s*=\s*([-+0-9.eE]+)\s*$", log)
        if len(found) != 1:
            raise PreflightError(f"READBACK_MISSING_OR_DUPLICATE: {prefix}{key}")
        result[key] = float(found[0])
        if not math.isfinite(result[key]):
            raise PreflightError("READBACK_NONFINITE")
    return result


def mismatches(observed, expected):
    return [
        key
        for key, value in expected.items()
        if key not in observed
        or not math.isclose(observed[key], value, rel_tol=1e-8, abs_tol=1e-16)
    ]


def curve_difference(record, reference, channel="ib") -> dict:
    if (
        channel not in record
        or channel not in reference
        or not np.array_equal(record["u"], reference["u"])
    ):
        return {"status": "FAILED", "error": "CURVE_OR_AXIS_UNAVAILABLE"}
    a, b = record[channel], reference[channel]
    maximum = float(np.max(np.abs(a - b)))
    reference_peak = float(np.max(np.abs(b)))
    return {
        "status": "PASSED" if np.allclose(a, b, rtol=1e-8, atol=1e-15) else "FAILED",
        "max_absolute_difference_a": maximum,
        "max_difference_over_reference_peak": maximum / reference_peak if reference_peak else None,
    }


def negative_control(name: str, record: dict, baseline: dict, positive: dict) -> dict:
    """A failed run alone is never a successful negative control."""
    missing_lines = [
        line
        for line in record["diagnostics"]
        if BAD_LEAF[1:] in line.lower()
        and re.search(r"no such|not found|does not exist|unknown", line, re.IGNORECASE)
    ]
    checks = {
        "positive_application_proven": positive["status"] == "PASSED",
        "process_completed": record["returncode"] == 0 and not record["timed_out"],
        "readback_failed_only_for_requested_a_knobs": set(record["readback_mismatches"])
        == {"a_delvto", "a_mulu0"},
        "observed_reset_or_rejected_values_nominal": not mismatches(
            record.get("readback", {}), baseline.get("readback", {})
        )
        and bool(baseline.get("readback")),
        "a_curve_nominal": curve_difference(record, baseline, "ia")["status"] == "PASSED",
        "b_curve_nominal": curve_difference(record, baseline)["status"] == "PASSED",
        "no_unrelated_data_failure": not record["data_errors"],
    }
    if name == "bad_path":
        checks["explicit_missing_leaf_diagnostic"] = len(missing_lines) == 2
        checks["no_unrelated_diagnostic"] = record["diagnostics"] == missing_lines
    elif name == "reset_loses_perturbation":
        checks["nonzero_application_read_back_before_reset"] = not mismatches(
            record.get("readback_before_reset", {}), record["expected_readback"]
        )
        checks["no_simulator_error"] = not record["diagnostics"]
        checks["explicit_reset_message"] = "Reset re-loads circuit" in record["log"]
    else:
        raise PreflightError("unknown negative control")
    return {
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "intended_failure": "MISSING_HIERARCHY_LEAF"
        if name == "bad_path"
        else "RESET_DISCARDS_APPLIED_INSTANCE_PARAMETERS",
        "run": compact_run(record),
    }


def compact_run(record):
    return {key: value for key, value in record.items() if key not in ("u", "ia", "ib", "log")}


class SpiceProbe:
    def __init__(
        self, root: Path, binary: str, output: Path, polarity: str, w_um: float, l_um: float
    ):
        self.root, self.binary, self.output = root, binary, output
        self.polarity, self.w_um, self.l_um = polarity, w_um, l_um
        self.counter = 0
        self.cache = {}
        self.cache_hits = 0

    def run(
        self,
        raw=(0.0, 0.0),
        step=0.001,
        temperature_c=26.85,
        vds=0.05,
        invalid_target=False,
        reset_after_apply=False,
    ):
        key = tuple(map(float, raw)) + (step, temperature_c, vds, invalid_target, reset_after_apply)
        if key in self.cache:
            self.cache_hits += 1
            return self.cache[key]
        path = self.output / f"{self.counter:05d}"
        self.counter += 1
        path.mkdir(parents=True, exist_ok=False)
        deck = render_deck(
            self.root,
            self.polarity,
            self.w_um,
            self.l_um,
            step,
            *raw,
            temperature_c,
            vds,
            invalid_target,
            reset_after_apply,
        )
        (path / "input.cir").write_text(deck, encoding="utf-8")
        command = [self.binary, "-n", "-b", "input.cir"]
        requested = {
            "command": command,
            "raw": list(map(float, raw)),
            "step_v": step,
            "temperature_c": temperature_c,
            "vds_magnitude_v": vds,
            "invalid_target": invalid_target,
            "reset_after_apply": reset_after_apply,
            "source_calibration": False,
            "w_um": self.w_um,
            "l_um": self.l_um,
            "polarity": self.polarity,
            "timeout_seconds": 60,
            "environment_overrides": {"OMP_NUM_THREADS": "1", "LC_ALL": "C"},
        }
        write_json(path / "request.json", requested)
        started = time.monotonic()
        timed_out, returncode = False, None
        try:
            proc = subprocess.run(
                command,
                cwd=path,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
                env={**os.environ, **requested["environment_overrides"]},
            )
            stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout, stderr = error.stdout or "", error.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
        except OSError as error:
            stdout, stderr = "", str(error)
        (path / "stdout.txt").write_text(stdout, encoding="utf-8")
        (path / "stderr.txt").write_text(stderr, encoding="utf-8")
        log = stdout + "\n" + stderr
        record = {
            "run_directory": str(path),
            "returncode": returncode,
            "timed_out": timed_out,
            "duration_seconds": time.monotonic() - started,
            "log": log,
            "expected_readback": expected_readback(self.w_um, self.l_um, raw),
            "data_errors": [],
            "diagnostics": [s for s in log.splitlines() if ERROR_LINE.match(s)],
        }
        try:
            record["readback"] = readback_scalars(log)
            if reset_after_apply:
                record["readback_before_reset"] = readback_scalars(log, "applied_")
        except PreflightError as error:
            record["data_errors"].append(str(error))
        record["readback_mismatches"] = mismatches(
            record.get("readback", {}), record["expected_readback"]
        )
        try:
            data = np.loadtxt(path / "sweep.txt", skiprows=1)
            if data.ndim != 2 or data.shape[1] != 4 or not np.all(np.isfinite(data)):
                raise PreflightError("OUTPUT_SHAPE_INVALID")
            u, ia, ib = data[:, 1], data[:, 2], data[:, 3]
            expected_u = np.arange(round(1 / step) + 1) * step
            if (
                u.shape != expected_u.shape
                or not np.all(np.diff(u) > 0)
                or not np.allclose(u, expected_u, rtol=0, atol=1e-11)
            ):
                raise PreflightError("OUTPUT_AXIS_INVALID")
            record.update(u=u, ia=ia, ib=ib)
            record["points"] = len(u)
            record["current_convention"] = "signed ideal drain-voltage-source branch currents"
            record["sparse_solver_observed"] = "Using SPARSE 1.3" in log
        except (OSError, ValueError) as error:
            record["data_errors"].append(str(error))
        record["status"] = (
            "PASSED"
            if returncode == 0
            and not timed_out
            and not record["diagnostics"]
            and not record["data_errors"]
            and not record["readback_mismatches"]
            and record.get("sparse_solver_observed")
            else "FAILED"
        )
        record["artifacts_sha256"] = {
            p.name: sha256(p) for p in sorted(path.iterdir()) if p.is_file()
        }
        write_json(path / "run.json", compact_run(record))
        self.cache[key] = record
        return record


def extract_record(record, vds=0.05):
    path = Path(record["run_directory"]) / "extraction.json"
    if path.exists():
        return json.loads(path.read_text())
    result = {"status": "BLOCKED", "run_directory": record["run_directory"]}
    if record["status"] != "PASSED":
        result["error"] = "APPLICATION_OR_ACQUISITION_FAILED"
    else:
        result["status"] = "PASSED"
        for label, channel in [("a", "ia"), ("b", "ib")]:
            u, current = record["u"], np.abs(record[channel])
            derivative = CubicSpline(u, current).derivative()
            gm = derivative(u)
            peaks, _ = find_peaks(gm)
            k = int(np.argmax(gm))
            diagnostics = {
                "sampled_max_u_v": float(u[k]),
                "endpoint_gm_over_sampled_max": [float(gm[0] / gm[k]), float(gm[-1] / gm[k])],
                "sampled_peaks": [
                    {"u_v": float(u[p]), "gm_over_max": float(gm[p] / gm[k])} for p in peaks
                ],
            }
            try:
                result[label] = {
                    "status": "PASSED",
                    **asdict(extract_mg(u, current, vds)),
                    "diagnostics": diagnostics,
                }
            except PreflightError as error:
                result[label] = {
                    "status": "FAILED",
                    "error": str(error),
                    "diagnostics": diagnostics,
                }
                result["status"] = "FAILED"
    write_json(path, result)
    return result


def require_measurement(record):
    if record["status"] != "PASSED":
        raise PreflightError(f"APPLICATION_OR_ACQUISITION_FAILED: {record['run_directory']}")
    result = extract_record(record)
    if result["status"] != "PASSED":
        raise PreflightError(f"MG_EXTRACTION_FAILED: {record['run_directory']}: {result}")
    return result["a"]


def observables(result, base):
    return np.array(
        [
            result["vth_mg_v"] - base["vth_mg_v"],
            result["beta_mg_a_per_v2"] / base["beta_mg_a_per_v2"] - 1,
        ]
    )


def experiment_application(probe):
    base = probe.run()
    changed = probe.run(PROBE_RAW)
    twin = curve_difference(changed, base)
    active = curve_difference(changed, base, "ia")
    checks = {
        "baseline_readback_and_acquisition": base["status"] == "PASSED",
        "nonzero_readback_and_acquisition": changed["status"] == "PASSED",
        "untouched_twin_curve_unchanged": twin["status"] == "PASSED",
        "perturbed_a_curve_changed": active.get("max_absolute_difference_a", 0) > 1e-12
        and active["status"] == "FAILED",
    }
    positive = {
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "nominal": compact_run(base),
        "nonzero": compact_run(changed),
        "twin_isolation": twin,
        "a_curve_difference": active,
    }
    controls = {}
    for name, options in [
        ("bad_path", {"invalid_target": True}),
        ("reset_loses_perturbation", {"reset_after_apply": True}),
    ]:
        controls[name] = negative_control(name, probe.run(PROBE_RAW, **options), base, positive)
    return {
        "status": "PASSED"
        if positive["status"] == "PASSED"
        and all(item["status"] == "PASSED" for item in controls.values())
        else "FAILED",
        "positive": positive,
        "negative_controls": controls,
    }


def experiment_extraction(probe):
    grids = []
    for step in (0.005, 0.002, 0.001):
        record = probe.run(step=step)
        grids.append({"step_v": step, **extract_record(record)})
    result = {
        "status": "FAILED",
        "grids": grids,
        "method": "supplied cubic-interpolant terminal-current maximum-gm; unchanged",
        "tolerances": {"vth_range_v": 5e-5, "beta_relative_range": 0.001},
    }
    if all(row["status"] == "PASSED" for row in grids):
        convergence = {}
        for label in ("a", "b"):
            vth = [row[label]["vth_mg_v"] for row in grids]
            beta = [row[label]["beta_mg_a_per_v2"] for row in grids]
            convergence[label] = {
                "vth_range_v": max(vth) - min(vth),
                "beta_relative_range": (max(beta) - min(beta)) / beta[-1],
            }
        result["convergence"] = convergence
        if all(
            c["vth_range_v"] <= 5e-5 and c["beta_relative_range"] <= 0.001
            for c in convergence.values()
        ):
            result["status"] = "PASSED"
        else:
            result["error"] = "EXTRACTION_NOT_CONVERGED"
    else:
        result["error"] = "ONE_OR_MORE_GRIDS_UNAVAILABLE_OR_REJECTED"
    return result


def experiment_mapping(probe, extraction):
    result = {
        "status": "BLOCKED",
        "output_scales": SCALES.tolist(),
        "raw_difference_steps": RAW_STEPS.tolist(),
        "solver_difference_steps": [0.0001, 0.001],
        "raw_bounds": {"delvto_v": [-0.1, 0.1], "mulu0": [0.5, 1.5]},
        "scaled_condition_limit": 100,
        "max_component_scaled_residual": 0.01,
        "targets": [{"target": list(t), "status": "BLOCKED"} for t in TARGETS],
    }
    if extraction["status"] != "PASSED":
        result["error"] = "NOMINAL_MG_EXTRACTION_NOT_PROVEN"
        return result
    base_record = probe.run()
    base = require_measurement(base_record)

    def function(raw):
        record = probe.run(raw)
        if curve_difference(record, base_record)["status"] != "PASSED":
            raise PreflightError(f"UNTOUCHED_TWIN_CHANGED: {record['run_directory']}")
        return observables(require_measurement(record), base)

    try:
        jac, condition = local_jacobian(function, RAW_STEPS, SCALES)
        half_jac, half_condition = local_jacobian(function, RAW_STEPS / 2, SCALES)
        scaled = np.diag(1 / SCALES) @ jac @ np.diag(RAW_STEPS)
        result.update(
            raw_jacobian=jac.tolist(),
            scaled_jacobian=scaled.tolist(),
            scaled_singular_values=np.linalg.svd(scaled, compute_uv=False).tolist(),
            scaled_condition_number=condition,
            half_step_jacobian=half_jac.tolist(),
            half_step_condition_number=half_condition,
            half_step_relative_frobenius_change=float(
                np.linalg.norm(np.diag(1 / SCALES) @ (half_jac - jac) @ np.diag(RAW_STEPS))
                / np.linalg.norm(scaled)
            ),
        )
        if not math.isfinite(condition) or condition > 100:
            raise PreflightError("MAPPING_ILL_CONDITIONED")
    except (PreflightError, OSError, ValueError) as error:
        result.update(status="FAILED", error=str(error))
        return result
    result["targets"] = []
    for target in TARGETS:
        first = probe.counter
        mapped = {"target": list(target), "status": "FAILED"}
        try:
            raw = inverse_mapping(
                function,
                np.array(target),
                SCALES,
                (np.array([-0.1, math.log(0.5)]), np.array([0.1, math.log(1.5)])),
            )
            coarse = function(raw)
            fine0_record, fine_record = probe.run(step=0.0005), probe.run(raw, step=0.0005)
            fine0, fine = require_measurement(fine0_record), require_measurement(fine_record)
            recovered = observables(fine, fine0)
            residual = recovered - target
            isolation = curve_difference(fine_record, fine0_record)
            mapped.update(
                raw=raw.tolist(),
                mulu0=math.exp(float(raw[1])),
                coarse_recovered=coarse.tolist(),
                coarse_residual=(coarse - target).tolist(),
                fine_recovered=recovered.tolist(),
                fine_residual=residual.tolist(),
                fine_scaled_residual=(residual / SCALES).tolist(),
                fine_run=fine_record["run_directory"],
                fine_baseline_run=fine0_record["run_directory"],
                fine_twin_isolation=isolation,
            )
            if np.max(np.abs(residual / SCALES)) > 0.01 or isolation["status"] != "PASSED":
                raise PreflightError("MAPPING_REFINEMENT_OR_ISOLATION_CHECK_FAILED")
            mapped["status"] = "PASSED"
        except (PreflightError, OSError, ValueError) as error:
            mapped["error"] = str(error)
        mapped["new_run_index_interval_half_open"] = [first, probe.counter]
        result["targets"].append(mapped)
    result["status"] = (
        "PASSED" if all(t["status"] == "PASSED" for t in result["targets"]) else "FAILED"
    )
    return result


def source_identity(root):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

    paths = [
        "tools/v5_preflight/run_spike.py",
        "tools/v5_preflight/numerical_core.py",
        "tools/v5_preflight/V5_MINIMUM_EXPERIMENT.md",
        "V5_PREFLIGHT.md",
    ]
    return {
        "head": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "worktree_status": git("status", "--porcelain=v1"),
        "experiment_input_sha256": {p: sha256(root / p) for p in paths},
        "python": sys.version,
        "python_executable": sys.executable,
        "packages": {p: metadata.version(p) for p in ("numpy", "scipy", "analog-process-models")},
        "platform": platform.uname()._asdict(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--ngspice", default="ngspice")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--w-um", type=float, default=1.0)
    parser.add_argument("--l-um", type=float, default=0.12)
    args = parser.parse_args()
    root, out = args.repo.resolve(), args.output.resolve()
    if not out.is_relative_to(root / ".apm/v5-preflight"):
        parser.error("raw output must be below repository .apm/v5-preflight/")
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {
        "kind": "exploratory_preflight",
        "comparison_base_ref": BASE_REF,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_beta_approved": False,
        "release_qualification": False,
        "geometry": {"w_um": args.w_um, "l_um": args.l_um},
        "bias": {"temperature_k": 300, "vds_magnitude_v": 0.05, "u_range_v": [0, 1]},
        "records": {},
        "status": "NOT_RUN",
    }
    try:
        binary = shutil.which(args.ngspice)
        if not binary:
            raise PreflightError("TOOL_UNAVAILABLE")
        version = subprocess.run(
            [binary, "--version"], text=True, capture_output=True, timeout=10, check=False
        )
        text = version.stdout + "\n" + version.stderr
        (out / "ngspice-version.txt").write_text(text, encoding="utf-8")
        if version.returncode or not re.search(r"ngspice\s*-?\s*47\b", text, re.IGNORECASE):
            raise PreflightError("WRONG_TOOL_VERSION")
        report.update(
            source=source_identity(root),
            models=verify_models(root),
            simulator_path=str(Path(binary).resolve()),
            simulator_sha256=sha256(Path(binary)),
            simulator_version=text.strip(),
        )
    except (PreflightError, OSError, ValueError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    else:
        for polarity in ("n", "p"):
            probe = SpiceProbe(root, binary, out / polarity, polarity, args.w_um, args.l_um)
            record = report["records"][polarity] = {}
            for name, experiment in [
                ("application", experiment_application),
                ("extraction", experiment_extraction),
                ("mapping", lambda p, r=record: experiment_mapping(p, r["extraction"])),
            ]:
                stage_start, first = time.monotonic(), probe.counter
                try:
                    record[name] = experiment(probe)
                except (PreflightError, OSError, ValueError, subprocess.SubprocessError) as error:
                    record[name] = {"status": "FAILED", "error": str(error)}
                record[name].update(
                    ngspice_processes=probe.counter - first,
                    duration_seconds=time.monotonic() - stage_start,
                )
                write_json(out / "report.json", report)
            record.update(ngspice_processes=probe.counter, cache_hits=probe.cache_hits)
        report["status"] = (
            "PASSED"
            if all(
                r[e]["status"] == "PASSED"
                for r in report["records"].values()
                for e in ("application", "extraction", "mapping")
            )
            else "FAILED"
        )
        report["models_after"] = verify_models(root)
    report["duration_seconds"] = time.monotonic() - started
    # The inventory binds every request, deck, signed curve, log, readback and extraction.
    inventory = {
        str(p.relative_to(out)): sha256(p)
        for p in sorted(out.rglob("*"))
        if p.is_file() and p != out / "report.json"
    }
    write_json(out / "artifact-inventory.json", inventory)
    report["artifact_inventory_sha256"] = sha256(out / "artifact-inventory.json")
    report["ngspice_processes"] = sum(r["ngspice_processes"] for r in report["records"].values())
    write_json(out / "report.json", report)
    print(json.dumps({"status": report["status"], "report": str(out / "report.json")}, indent=2))
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
