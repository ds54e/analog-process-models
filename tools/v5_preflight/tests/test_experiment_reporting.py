# SPDX-FileCopyrightText: 2026 APM preflight contributors
# SPDX-License-Identifier: Apache-2.0

"""Focused failure-mechanism regressions; synthetic fixtures, no SPICE claim."""

import copy
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
import run_spike as spike


def control_fixture(name):
    baseline = {
        "status": "PASSED",
        "u": np.linspace(0, 1, 11),
        "ia": np.arange(11) * 1e-6,
        "ib": np.arange(11) * 1e-6,
        "readback": spike.expected_readback(1, 0.12, (0, 0)),
    }
    record = {
        **baseline,
        "status": "FAILED",
        "returncode": 0,
        "timed_out": False,
        "expected_readback": spike.expected_readback(1, 0.12, spike.PROBE_RAW),
        "readback_mismatches": ["a_delvto", "a_mulu0"],
        "data_errors": [],
        "diagnostics": [],
        "log": "",
    }
    if name == "bad_path":
        record["diagnostics"] = [f"Error: no such device {spike.BAD_LEAF[1:]}"] * 2
    else:
        record["readback_before_reset"] = record["expected_readback"].copy()
        record["log"] = "Reset re-loads circuit"
    return baseline, record, {"status": "PASSED"}


@pytest.mark.parametrize("name", ["bad_path", "reset_loses_perturbation"])
def test_negative_requires_complete_mechanism(name):
    baseline, record, positive = control_fixture(name)
    assert spike.negative_control(name, record, baseline, positive)["status"] == "PASSED"
    for field, value in [
        ("returncode", 1),
        ("timed_out", True),
        ("readback_mismatches", ["b_w"]),
        ("data_errors", ["missing sweep"]),
    ]:
        broken = {**record, field: value}
        assert spike.negative_control(name, broken, baseline, positive)["status"] == "FAILED"
    assert (
        spike.negative_control(name, record, baseline, {"status": "FAILED"})["status"] == "FAILED"
    )
    broken = copy.deepcopy(record)
    broken["ib"] *= 1.1
    assert spike.negative_control(name, broken, baseline, positive)["status"] == "FAILED"


def test_bad_path_readback_mismatch_alone_or_solver_error_is_inconclusive():
    baseline, record, positive = control_fixture("bad_path")
    record["diagnostics"] = []
    assert spike.negative_control("bad_path", record, baseline, positive)["status"] == "FAILED"
    baseline, record, positive = control_fixture("bad_path")
    record["diagnostics"].append("Error: singular matrix")
    assert spike.negative_control("bad_path", record, baseline, positive)["status"] == "FAILED"


def test_reset_must_prove_application_before_loss():
    baseline, record, positive = control_fixture("reset_loses_perturbation")
    record["readback_before_reset"] = baseline["readback"]
    assert (
        spike.negative_control("reset_loses_perturbation", record, baseline, positive)["status"]
        == "FAILED"
    )
    text = spike.render_deck(Path("/apm"), "p", 1, 0.12, 0.001, 0.02, 0.03, reset_after_apply=True)
    assert (
        text.index("print applied_a_delvto")
        < text.index("\nreset\n")
        < text.index("print a_delvto")
    )


def test_timeout_preserves_request_and_partial_logs(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0], 60, output=b"partial stdout", stderr=b"partial stderr"
        )

    monkeypatch.setattr(spike.subprocess, "run", timeout)
    probe = spike.SpiceProbe(tmp_path, "ngspice", tmp_path / "runs", "n", 1, 0.12)
    result = probe.run()
    assert result["status"] == "FAILED" and result["timed_out"]
    directory = Path(result["run_directory"])
    assert (directory / "stdout.txt").read_text() == "partial stdout"
    assert (directory / "stderr.txt").read_text() == "partial stderr"
    assert json.loads((directory / "request.json").read_text())["timeout_seconds"] == 60
    assert (directory / "run.json").is_file()


def test_application_does_not_invoke_mg(tmp_path, monkeypatch):
    def forbidden(*args):
        raise AssertionError("application must not depend on extraction")

    monkeypatch.setattr(spike, "extract_mg", forbidden)
    baseline, _, _ = control_fixture("bad_path")
    baseline.update(
        returncode=0,
        timed_out=False,
        data_errors=[],
        diagnostics=[],
        readback_mismatches=[],
        expected_readback=baseline["readback"],
        log="",
    )

    class Probe:
        def run(self, raw=(0, 0), **options):
            if options:
                name = "bad_path" if options.get("invalid_target") else "reset_loses_perturbation"
                return control_fixture(name)[1]
            result = copy.deepcopy(baseline)
            if raw != (0, 0):
                result["ia"] *= 1.1
                result["readback"] = spike.expected_readback(1, 0.12, raw)
            return result

    assert spike.experiment_application(Probe())["status"] == "PASSED"


def test_endpoint_failure_retains_all_grids_and_blocks_all_targets(tmp_path):
    class Probe:
        def run(self, step):
            path = tmp_path / str(step)
            path.mkdir()
            u = np.linspace(0, 1, round(1 / step) + 1)
            return {
                "status": "PASSED",
                "run_directory": str(path),
                "u": u,
                "ia": np.exp(u) * 1e-6,
                "ib": np.exp(u) * 1e-6,
            }

    extraction = spike.experiment_extraction(Probe())
    assert extraction["status"] == "FAILED" and len(extraction["grids"]) == 3
    assert all(row["a"]["error"] == "EXTRACTION_ENDPOINT_LIMITED" for row in extraction["grids"])
    mapping = spike.experiment_mapping(None, extraction)
    assert mapping["status"] == "BLOCKED"
    assert len(mapping["targets"]) == 4
    assert all(t["status"] == "BLOCKED" for t in mapping["targets"])


def test_main_continues_both_polarities_after_stage_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(spike, "source_identity", lambda r: {})
    monkeypatch.setattr(spike, "verify_models", lambda r: {})
    monkeypatch.setattr(spike.shutil, "which", lambda r: __file__)
    monkeypatch.setattr(
        spike.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "ngspice-47", ""),
    )
    seen = []

    def fail(probe):
        seen.append(probe.polarity)
        raise spike.PreflightError("deliberate application failure")

    monkeypatch.setattr(spike, "experiment_application", fail)
    monkeypatch.setattr(spike, "experiment_extraction", lambda p: {"status": "FAILED"})
    out = tmp_path / ".apm/v5-preflight/run"
    monkeypatch.setattr(
        spike.sys, "argv", ["run_spike", "--repo", str(tmp_path), "--output", str(out)]
    )
    assert spike.main() == 1
    report = json.loads((out / "report.json").read_text())
    assert seen == ["n", "p"]
    for polarity in seen:
        assert report["records"][polarity]["application"]["status"] == "FAILED"
        assert report["records"][polarity]["extraction"]["status"] == "FAILED"
        assert report["records"][polarity]["mapping"]["status"] == "BLOCKED"
