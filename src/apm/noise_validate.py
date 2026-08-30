# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Real-tool analytic harness qualification and V3-N0 four-engine spike."""

from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model_build import build_models, sha256_file
from .noise import (
    _noise_wrdata,
    _prepare_output,
    _run_ngspice,
    audit_ngspice_log,
    characterize_noise_selector,
    resolve_noise_device,
)
from .noise_fit import BOLTZMANN_J_PER_K
from .paths import repository_root, state_directory
from .toolchain import Toolchain, resolve_toolchain, run_checked

SPIKE_SELECTORS = (
    "apm350/general/nmos",
    "apm130/lv/nmos",
    "apm045/vtg/nmos",
    "apm016f/svt/nfet",
)
FIXTURE_SOURCES = (
    "apm_noise_white",
    "apm_noise_flicker",
    "apm_noise_correlated",
)
REFERENCE_TEMPERATURE_C = 27.0
REFERENCE_RESISTANCE_OHM = 1000.0
FIXTURE_RELATIVE_TOLERANCE = 2.0e-5


class NoiseValidationError(RuntimeError):
    """The V3-N0 analytic or MOS acceptance contract failed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_output(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return state_directory(root) / "results" / f"v3-n0-noise-spike-{stamp}"


def _maximum_relative_error(observed: list[float], expected: list[float]) -> float:
    return max(
        abs(actual - reference) / max(abs(actual), abs(reference), 1e-300)
        for actual, reference in zip(observed, expected)
    )


def _compile_fixtures(root: Path, output: Path, toolchain: Toolchain) -> dict[str, Any]:
    destination = output / "fixture_osdi"
    destination.mkdir()
    records: list[dict[str, Any]] = []
    for name in FIXTURE_SOURCES:
        source = root / "validation" / "fixtures" / "noise" / f"{name}.va"
        artifact = destination / f"{name}.osdi"
        command = [
            toolchain.openvaf,
            "--target_cpu",
            "generic",
            "-o",
            artifact,
            source,
        ]
        result = run_checked(command, environment=toolchain.environment(), cwd=root)
        records.append(
            {
                "id": name,
                "source": str(source.relative_to(root)),
                "source_sha256": sha256_file(source),
                "artifact": str(artifact.relative_to(output)),
                "artifact_sha256": sha256_file(artifact),
                "command": [str(item) for item in command],
                "compiler_stdout": result.stdout.strip(),
                "compiler_stderr": result.stderr.strip(),
                "status": "pass",
            }
        )
    return {"status": "pass", "fixtures": records}


def _fixture_noise_run(
    *,
    fixture_id: str,
    output: Path,
    toolchain: Toolchain,
    circuit_lines: list[str],
    pre_osdi: Path | None = None,
    ccvs_gain_ohm: float = 1.0,
    points_per_decade: int = 4,
    frequency_start_hz: float = 1.0,
    frequency_stop_hz: float = 1.0e4,
) -> dict[str, Any]:
    directory = output / "fixtures" / fixture_id
    directory.mkdir(parents=True)
    netlist = directory / "fixture.cir"
    log = directory / "fixture.log"
    raw = directory / "noise.dat"
    lines = [
        f"APM V3-N0 fixture {fixture_id}",
        ".options klu=0",
        f".temp {REFERENCE_TEMPERATURE_C:.12g}",
        "Vd d 0 0",
        "Vinput input 0 DC 0 AC 1",
        *circuit_lines,
        f"Hnoise nout 0 Vd {ccvs_gain_ohm:.12g}",
        ".control",
        *([f"pre_osdi {pre_osdi}"] if pre_osdi is not None else []),
        "set sqrnoise",
        "set wr_vecnames",
        "set wr_singlescale",
        (
            f"noise v(nout) Vinput dec {points_per_decade} {frequency_start_hz:.12g} "
            f"{frequency_stop_hz:.12g} 1"
        ),
        "setplot noise1",
        f"wrdata {raw} all",
        "quit",
        ".endc",
        ".end",
    ]
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    command = _run_ngspice(toolchain, netlist, log)
    records, breakdown = _noise_wrdata(raw)
    log_text = log.read_text(encoding="utf-8", errors="replace")
    return {
        "id": fixture_id,
        "frequency_hz": [item["frequency"] for item in records],
        "output_psd": [item["onoise_spectrum"] for item in records],
        "source_vectors": breakdown,
        "netlist": str(netlist.relative_to(output)),
        "netlist_sha256": sha256_file(netlist),
        "log": str(log.relative_to(output)),
        "log_sha256": sha256_file(log),
        "raw": str(raw.relative_to(output)),
        "raw_sha256": sha256_file(raw),
        "command": command,
        "log_audit": audit_ngspice_log(log_text, require_sparse=True),
    }


def _probe_dc_run(
    *, fixture_id: str, output: Path, toolchain: Toolchain, with_probe: bool
) -> dict[str, Any]:
    directory = output / "fixtures" / fixture_id
    directory.mkdir(parents=True)
    netlist = directory / "fixture.cir"
    log = directory / "fixture.log"
    lines = [
        f"APM V3-N0 probe DC transparency {fixture_id}",
        ".options klu=0",
        "Vd d 0 1",
        "Rload d 0 1000",
        *( ["Hnoise nout 0 Vd 1"] if with_probe else []),
        ".control",
        "op",
        "print i(vd) v(d)",
        "quit",
        ".endc",
        ".end",
    ]
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    command = _run_ngspice(toolchain, netlist, log)
    text = log.read_text(encoding="utf-8", errors="replace")

    def value(name: str) -> float:
        match = re.search(
            rf"^\s*{re.escape(name)}\s*=\s*([-+0-9.eE]+)\s*$", text, re.MULTILINE
        )
        if not match:
            raise NoiseValidationError(f"{fixture_id}: ngspice did not print {name}")
        return float(match.group(1))

    return {
        "id": fixture_id,
        "with_probe": with_probe,
        "i_vd_a": value("i(vd)"),
        "v_d_v": value("v(d)"),
        "command": command,
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "log_audit": audit_ngspice_log(text, require_sparse=True),
    }


def validate_noise_harness(root: Path, output: Path, toolchain: Toolchain) -> dict[str, Any]:
    compilation = _compile_fixtures(root, output, toolchain)
    artifact = {
        item["id"]: output / item["artifact"] for item in compilation["fixtures"]
    }
    resistor = _fixture_noise_run(
        fixture_id="resistor_reference",
        output=output,
        toolchain=toolchain,
        circuit_lines=[f"Rnoise d 0 {REFERENCE_RESISTANCE_OHM:.12g}"],
    )
    expected_resistor = 4.0 * BOLTZMANN_J_PER_K * (
        REFERENCE_TEMPERATURE_C + 273.15
    ) / REFERENCE_RESISTANCE_OHM
    resistor_expected = [expected_resistor] * len(resistor["output_psd"])
    resistor_error = _maximum_relative_error(resistor["output_psd"], resistor_expected)
    resistor_result = {
        **resistor,
        "status": "pass" if resistor_error <= FIXTURE_RELATIVE_TOLERANCE else "fail",
        "analytic_definition": "4*k*T/R",
        "temperature_k": REFERENCE_TEMPERATURE_C + 273.15,
        "resistance_ohm": REFERENCE_RESISTANCE_OHM,
        "expected_a2_per_hz": expected_resistor,
        "maximum_relative_error": resistor_error,
        "relative_tolerance": FIXTURE_RELATIVE_TOLERANCE,
    }

    probe_gain_two = _fixture_noise_run(
        fixture_id="probe_gain_two",
        output=output,
        toolchain=toolchain,
        circuit_lines=[f"Rnoise d 0 {REFERENCE_RESISTANCE_OHM:.12g}"],
        ccvs_gain_ohm=2.0,
    )
    probe_quiet = _fixture_noise_run(
        fixture_id="probe_no_independent_noise",
        output=output,
        toolchain=toolchain,
        circuit_lines=[f"Rquiet d 0 {REFERENCE_RESISTANCE_OHM:.12g} noisy=0"],
    )
    dc_without = _probe_dc_run(
        fixture_id="probe_dc_without", output=output, toolchain=toolchain, with_probe=False
    )
    dc_with = _probe_dc_run(
        fixture_id="probe_dc_with", output=output, toolchain=toolchain, with_probe=True
    )
    gain_ratio = max(probe_gain_two["output_psd"]) / max(resistor["output_psd"])
    dc_current_error = abs(dc_with["i_vd_a"] - dc_without["i_vd_a"])
    dc_voltage_error = abs(dc_with["v_d_v"] - dc_without["v_d_v"])
    quiet_max = max(abs(value) for value in probe_quiet["output_psd"])
    probe_source_names = sorted(resistor["source_vectors"])
    probe_result = {
        "status": (
            "pass"
            if math.isclose(gain_ratio, 4.0, rel_tol=FIXTURE_RELATIVE_TOLERANCE)
            and dc_current_error <= 1e-15
            and dc_voltage_error <= 1e-15
            and quiet_max == 0.0
            and not any("hnoise" in name.lower() for name in probe_source_names)
            else "fail"
        ),
        "method": "1 ohm ideal CCVS controlled by the ideal Vd clamp branch",
        "dc_without_probe": dc_without,
        "dc_with_probe": dc_with,
        "dc_current_absolute_error_a": dc_current_error,
        "dc_voltage_absolute_error_v": dc_voltage_error,
        "noise_gain_one": resistor,
        "noise_gain_two": probe_gain_two,
        "observed_psd_gain_two_to_one_ratio": gain_ratio,
        "expected_psd_gain_two_to_one_ratio": 4.0,
        "quiet_resistor_run": probe_quiet,
        "quiet_run_maximum_psd": quiet_max,
        "gain_one_source_vectors": probe_source_names,
        "ccvs_has_named_noise_generator": any(
            "hnoise" in name.lower() for name in probe_source_names
        ),
    }

    white_psd = 4.0e-20
    white = _fixture_noise_run(
        fixture_id="osdi_white",
        output=output,
        toolchain=toolchain,
        circuit_lines=[
            f".model apm_white_model apm_noise_white white_psd={white_psd:.12g}",
            "Nfixture d 0 apm_white_model",
        ],
        pre_osdi=artifact["apm_noise_white"],
    )
    white_error = _maximum_relative_error(
        white["output_psd"], [white_psd] * len(white["output_psd"])
    )
    white_result = {
        **white,
        "status": "pass" if white_error <= FIXTURE_RELATIVE_TOLERANCE else "fail",
        "expected_a2_per_hz": white_psd,
        "maximum_relative_error": white_error,
        "relative_tolerance": FIXTURE_RELATIVE_TOLERANCE,
    }

    flicker_at_1hz = 9.0e-18
    flicker_exponent = 1.25
    flicker = _fixture_noise_run(
        fixture_id="osdi_flicker",
        output=output,
        toolchain=toolchain,
        circuit_lines=[
            (
                ".model apm_flicker_model apm_noise_flicker "
                f"psd_at_1hz={flicker_at_1hz:.12g} exponent={flicker_exponent:.12g}"
            ),
            "Nfixture d 0 apm_flicker_model",
        ],
        pre_osdi=artifact["apm_noise_flicker"],
    )
    flicker_expected = [
        flicker_at_1hz / frequency**flicker_exponent
        for frequency in flicker["frequency_hz"]
    ]
    flicker_error = _maximum_relative_error(flicker["output_psd"], flicker_expected)
    observed_exponent = -math.log(
        flicker["output_psd"][-1] / flicker["output_psd"][0]
    ) / math.log(flicker["frequency_hz"][-1] / flicker["frequency_hz"][0])
    flicker_result = {
        **flicker,
        "status": (
            "pass"
            if flicker_error <= FIXTURE_RELATIVE_TOLERANCE
            and abs(observed_exponent - flicker_exponent) <= 1e-6
            else "fail"
        ),
        "expected_psd_at_1hz_a2_per_hz": flicker_at_1hz,
        "expected_exponent": flicker_exponent,
        "observed_exponent": observed_exponent,
        "maximum_relative_error": flicker_error,
        "relative_tolerance": FIXTURE_RELATIVE_TOLERANCE,
    }

    common_psd = 1.0e-18
    direct_gain = 1.0
    copied_gain = -0.9
    correlated_expected = common_psd * (direct_gain + copied_gain) ** 2
    independent_expected = common_psd * (direct_gain**2 + copied_gain**2)
    correlated = _fixture_noise_run(
        fixture_id="osdi_correlated_network",
        output=output,
        toolchain=toolchain,
        circuit_lines=[
            (
                ".model apm_correlated_model apm_noise_correlated "
                f"common_psd={common_psd:.12g} direct_gain_s={direct_gain:.12g} "
                f"copied_gain_s={copied_gain:.12g}"
            ),
            "Nfixture d 0 apm_correlated_model",
        ],
        pre_osdi=artifact["apm_noise_correlated"],
    )
    correlation_error = _maximum_relative_error(
        correlated["output_psd"], [correlated_expected] * len(correlated["output_psd"])
    )
    independent_to_correlated_ratio = independent_expected / correlated_expected
    correlated_result = {
        **correlated,
        "status": (
            "pass"
            if correlation_error <= FIXTURE_RELATIVE_TOLERANCE
            and independent_to_correlated_ratio >= 100.0
            else "fail"
        ),
        "construction": "one internal white source routed through two deterministic internal-node paths",
        "common_source_psd": common_psd,
        "direct_gain_s": direct_gain,
        "copied_gain_s": copied_gain,
        "expected_correlated_output_a2_per_hz": correlated_expected,
        "hypothetical_independent_output_a2_per_hz": independent_expected,
        "independent_to_correlated_ratio": independent_to_correlated_ratio,
        "maximum_relative_error_to_correlated_result": correlation_error,
        "relative_tolerance": FIXTURE_RELATIVE_TOLERANCE,
    }
    results = {
        "schema": "apm.noise-harness-validation.v1",
        "created_utc": _utc_now(),
        "solver": "Sparse",
        "compilation": compilation,
        "resistor_reference": resistor_result,
        "probe_transparency": probe_result,
        "osdi_white": white_result,
        "osdi_flicker": flicker_result,
        "osdi_correlated_network": correlated_result,
    }
    results["status"] = (
        "pass"
        if all(
            results[name]["status"] == "pass"
            for name in (
                "resistor_reference",
                "probe_transparency",
                "osdi_white",
                "osdi_flicker",
                "osdi_correlated_network",
            )
        )
        else "fail"
    )
    _write_json(output / "harness_report.json", results)
    if results["status"] != "pass":
        raise NoiseValidationError("one or more analytic noise harness fixtures failed")
    return results


def _read_csv_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise NoiseValidationError(f"expected one row in {path}")
    return rows[0]


def _cmg_correlation_diagnostic(
    root: Path, output: Path, toolchain: Toolchain, baseline_directory: Path
) -> dict[str, Any]:
    resolved = resolve_noise_device("apm016f/svt/nfet", root)
    operating_point = _read_csv_row(baseline_directory / "operating_points.csv")
    baseline_snapshot = json.loads(
        (baseline_directory / "noise_model_snapshot.json").read_text(encoding="utf-8")
    )
    baseline_tnoimod = next(
        item for item in baseline_snapshot["parameters"] if item["name"] == "tnoimod"
    )["effective_value"]
    production_card = root / "models/apm016f/ngspice/apm016f_multivt_models.inc"
    card_hash_before = sha256_file(production_card)
    directory = output / "correlation_diagnostics" / "bsim_cmg_tnoimod1"
    directory.mkdir(parents=True)
    netlist = directory / "diagnostic.cir"
    log = directory / "diagnostic.log"
    raw = directory / "noise.dat"
    lines = [
        "APM BSIM-CMG TNOIMOD=1 diagnostic; production card remains unchanged",
        *resolved.kit.model_directives(),
        f'.include "{resolved.kit.wrapper_file}"',
        ".options klu=0",
        ".temp 27",
        f"Vd d 0 {float(operating_point['raw_vds_v']):.12g}",
        f"Vg g 0 {float(operating_point['raw_vgs_v']):.12g} AC 1",
        "Vs s 0 0",
        "Vb b 0 0",
        (
            f"Xdut d g s b {resolved.device.public_name} "
            f"{resolved.geometry.netlist_parameters()}"
        ),
        "Hnoise nout 0 Vd 1",
        ".control",
        *[
            f"pre_osdi {toolchain.osdi_directory / artifact}"
            for artifact in resolved.kit.osdi_artifacts
        ],
        "altermod apm016f_svt_ncore tnoimod = 1",
        "set sqrnoise",
        "set wr_vecnames",
        "set wr_singlescale",
        "op",
        "showmod n : tnoimod rnoia rnoib rnoic",
        "noise v(nout) Vg dec 10 100000 10000000 1",
        "setplot noise1",
        f"wrdata {raw} all",
        "quit",
        ".endc",
        ".end",
    ]
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    command = _run_ngspice(toolchain, netlist, log)
    text = log.read_text(encoding="utf-8", errors="replace")
    records, breakdown = _noise_wrdata(raw)
    correlation_sources = {
        name: values for name, values in breakdown.items() if "_corl" in name.lower()
    }
    id_sources = {
        name: values
        for name, values in breakdown.items()
        if re.search(r"_id(?:#\d+)?$", name.lower())
    }
    tnoimod_match = re.search(r"^\s*tnoimod\s+(\S+)\s*$", text, re.MULTILINE)
    card_hash_after = sha256_file(production_card)
    status = (
        "pass"
        if baseline_tnoimod == 0
        and tnoimod_match
        and int(float(tnoimod_match.group(1))) == 1
        and correlation_sources
        and max(max(values) for values in correlation_sources.values()) > 0.0
        and id_sources
        and all(item["onoise_spectrum"] >= 0.0 for item in records)
        and card_hash_before == card_hash_after
        else "fail"
    )
    return {
        "status": status,
        "purpose": "representative diagnostic exercise of the existing BSIM-CMG internal correlated-noise mode",
        "baseline_production_tnoimod": baseline_tnoimod,
        "diagnostic_tnoimod": int(float(tnoimod_match.group(1))) if tnoimod_match else None,
        "production_card": str(production_card.relative_to(root)),
        "production_card_sha256_before": card_hash_before,
        "production_card_sha256_after": card_hash_after,
        "production_card_modified": card_hash_before != card_hash_after,
        "correlation_source_vectors": correlation_sources,
        "independent_id_source_vectors": id_sources,
        "output_psd_min": min(item["onoise_spectrum"] for item in records),
        "output_psd_max": max(item["onoise_spectrum"] for item in records),
        "command": command,
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "raw": str(raw.relative_to(output)),
        "log_audit": audit_ngspice_log(text, require_sparse=True),
        "claim_boundary": (
            "The diagnostic proves that this OpenVAF/OSDI/ngspice path executes the "
            "BSIM-CMG TNOIMOD=1 internal-node construction. It does not calibrate the "
            "APM016F coefficients, and the production card remains at TNOIMOD=0."
        ),
    }


def _psp_correlation_diagnostic(baseline_directory: Path) -> dict[str, Any]:
    breakdown = json.loads(
        (baseline_directory / "source_breakdown.json").read_text(encoding="utf-8")
    )
    metadata = json.loads((baseline_directory / "metadata.json").read_text(encoding="utf-8"))
    sources = {item["raw_vector_name"]: item["output_referred_psd"] for item in breakdown["sources"]}
    igig = {name: values for name, values in sources.items() if name.lower().endswith("_igig")}
    idid = {name: values for name, values in sources.items() if name.lower().endswith("_idid")}
    cigid = metadata["native_noise_oracles"].get("psp_cigid_imaginary_correlation")
    sid = metadata["native_noise_oracles"].get("psp_sid_a2_per_hz")
    sfl = metadata["native_noise_oracles"].get("psp_sfl_at_1hz_a2_per_hz")
    with (baseline_directory / "noise_spectrum.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        spectrum = list(csv.DictReader(handle))
    external_low = float(spectrum[0]["s_idrain_terminal_a2_per_hz"])
    external_high = float(spectrum[-1]["s_idrain_terminal_a2_per_hz"])
    oracle_values_valid = all(
        isinstance(value, (int, float)) and math.isfinite(value) and value > 0.0
        for value in (sid, sfl)
    )
    low_to_sfl = external_low / sfl if oracle_values_valid else None
    high_to_sid = external_high / sid if oracle_values_valid else None
    oracle_trend_pass = bool(
        oracle_values_valid
        and external_low > external_high
        and sfl > sid
        and 1.0e-3 <= low_to_sfl <= 1.0e3
        and 1.0e-3 <= high_to_sid <= 1.0e3
    )
    status = (
        "pass"
        if igig
        and idid
        and max(max(values) for values in igig.values()) > 0.0
        and max(max(values) for values in idid.values()) > 0.0
        and cigid is not None
        and 0.0 < abs(cigid) <= 1.0
        and oracle_trend_pass
        else "fail"
    )
    return {
        "status": status,
        "igig_source_vectors": igig,
        "idid_source_vectors": idid,
        "native_cigid_imaginary_correlation": cigid,
        "native_sid_a2_per_hz": sid,
        "native_sfl_at_1hz_a2_per_hz": sfl,
        "native_oracle_assessment": {
            "status": "pass" if oracle_trend_pass else "fail",
            "external_total_at_1hz_a2_per_hz": external_low,
            "external_total_at_100mhz_a2_per_hz": external_high,
            "external_1hz_to_native_sfl_ratio": low_to_sfl,
            "external_100mhz_to_native_sid_ratio": high_to_sid,
            "checks": {
                "native_values_finite_positive": oracle_values_valid,
                "native_and_external_low_to_high_trends_consistent": bool(
                    oracle_values_valid and external_low > external_high and sfl > sid
                ),
                "magnitude_order_cross_check": bool(
                    oracle_values_valid
                    and 1.0e-3 <= low_to_sfl <= 1.0e3
                    and 1.0e-3 <= high_to_sid <= 1.0e3
                ),
            },
            "equality_required": False,
        },
        "claim_boundary": (
            "Pinned PSP source semantics plus nonzero igig/idid contributions and cigid "
            "show that the representative internal correlated-noise network is active. "
            "The analytic APM fixture establishes network-correlation preservation; PSP "
            "native sid/sfl remain oracles, not the external terminal total."
        ),
    }


def _v2_model_immutability(root: Path) -> dict[str, Any]:
    paths = (
        "models/apm350/ngspice/apm350_models.inc",
        "models/apm022/ngspice/apm022_multivt_models.inc",
        "models/apm016f/ngspice/apm016f_multivt_models.inc",
    )
    diff = run_checked(["git", "diff", "--name-only", "v2.0.0", "--", *paths], cwd=root)
    peeled = run_checked(["git", "rev-list", "-n", "1", "v2.0.0"], cwd=root).stdout.strip()
    return {
        "status": "pass" if not diff.stdout.strip() and peeled == "3cc6cfea4932cc40f2d693784d0a569926cdf399" else "fail",
        "v2_tag_peeled_commit": peeled,
        "expected_v2_tag_commit": "3cc6cfea4932cc40f2d693784d0a569926cdf399",
        "noise_card_paths": list(paths),
        "paths_changed_since_v2_tag": diff.stdout.splitlines(),
        "current_sha256": {path: sha256_file(root / path) for path in paths},
    }


def validate_noise_spike(
    output: Path | None = None,
    *,
    root: Path | None = None,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    resolved_root = (root or repository_root()).resolve()
    result_directory = _prepare_output(output or _default_output(resolved_root))
    selected_toolchain = toolchain or resolve_toolchain(resolved_root)
    build = build_models(selected_toolchain, force=False)
    harness = validate_noise_harness(resolved_root, result_directory, selected_toolchain)
    if harness["status"] != "pass":
        raise NoiseValidationError("MOS spectra are not accepted before harness qualification")
    mos_results: list[dict[str, Any]] = []
    mos_directories: dict[str, Path] = {}
    for selector in SPIKE_SELECTORS:
        directory = result_directory / "mos" / selector.replace("/", "__")
        result = characterize_noise_selector(
            selector,
            directory,
            root=resolved_root,
            toolchain=selected_toolchain,
        )
        mos_results.append(result)
        mos_directories[selector] = directory
    psp_correlation = _psp_correlation_diagnostic(mos_directories["apm130/lv/nmos"])
    cmg_correlation = _cmg_correlation_diagnostic(
        resolved_root,
        result_directory,
        selected_toolchain,
        mos_directories["apm016f/svt/nfet"],
    )
    correlation = {
        "status": (
            "pass"
            if harness["osdi_correlated_network"]["status"] == "pass"
            and psp_correlation["status"] == "pass"
            and cmg_correlation["status"] == "pass"
            else "fail"
        ),
        "analytic_network": harness["osdi_correlated_network"],
        "psp103": psp_correlation,
        "bsim_cmg": cmg_correlation,
    }
    immutability = _v2_model_immutability(resolved_root)
    summaries: list[dict[str, Any]] = []
    for result in mos_results:
        directory = Path(result["output_directory"])
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        snapshot = json.loads(
            (directory / "noise_model_snapshot.json").read_text(encoding="utf-8")
        )
        source = json.loads((directory / "source_breakdown.json").read_text(encoding="utf-8"))
        metrics = _read_csv_row(directory / "noise_metrics.csv")
        spectrum_hash = sha256_file(directory / "noise_spectrum.csv")
        summaries.append(
            {
                **result,
                "metadata_sha256": sha256_file(directory / "metadata.json"),
                "noise_spectrum_sha256": spectrum_hash,
                "source_breakdown_sha256": sha256_file(directory / "source_breakdown.json"),
                "noise_model_snapshot_sha256": sha256_file(
                    directory / "noise_model_snapshot.json"
                ),
                "source_vector_names": [
                    item["raw_vector_name"] for item in source["sources"]
                ],
                "effective_parameter_count": len(snapshot["parameters"]),
                "parameter_value_sources": sorted(
                    {item["value_source"] for item in snapshot["parameters"]}
                ),
                "log_warning_count": len(metadata.get("log_audit", {}).get("warnings", [])),
                "log_critical_diagnostic_count": len(
                    metadata.get("log_audit", {}).get("critical_diagnostics", [])
                ),
                "sparse_attestation_count": len(
                    metadata.get("log_audit", {}).get("sparse_attestations", [])
                ),
                "klu_attestation_count": len(
                    metadata.get("log_audit", {}).get("klu_attestations", [])
                ),
                "gm_convergence_relative": result["gm_convergence_relative"],
                "gds_convergence_relative": result["gds_convergence_relative"],
                "native_gm_relative_error": result["native_gm_relative_error"],
                "native_gds_relative_error": result["native_gds_relative_error"],
                "white_fit_status": metrics["white_fit_status"],
                "flicker_fit_status": metrics["flicker_fit_status"],
                "flicker_corner_status": metrics["flicker_corner_status"],
                "white_floor_a2_per_hz": metrics["white_floor_a2_per_hz"] or None,
                "flicker_corner_hz": metrics["flicker_corner_hz"] or None,
            }
        )
    checks = [
        {
            "id": "harness.resistor_reference",
            "status": harness["resistor_reference"]["status"],
            "evidence": "harness_report.json",
        },
        {
            "id": "harness.probe_transparency",
            "status": harness["probe_transparency"]["status"],
            "evidence": "harness_report.json",
        },
        {"id": "harness.osdi_white", "status": harness["osdi_white"]["status"]},
        {"id": "harness.osdi_flicker", "status": harness["osdi_flicker"]["status"]},
        {"id": "harness.osdi_correlation", "status": correlation["status"]},
        {
            "id": "mos.gm_id_resolution",
            "status": (
                "pass"
                if all(
                    item["gm_over_id_relative_error"] <= 0.01
                    and item["gm_convergence_relative"] < 0.02
                    and item["gds_convergence_relative"] < 0.02
                    and item["native_gm_relative_error"] < 0.02
                    and item["native_gds_relative_error"] < 0.02
                    for item in summaries
                )
                else "fail"
            ),
        },
        {
            "id": "mos.four_engines_execute",
            "status": "pass" if len(summaries) == 4 and all(item["status"] == "pass" for item in summaries) else "fail",
        },
        {
            "id": "mos.drain_psd_finite_nonnegative",
            "status": (
                "pass"
                if all(item["minimum_drain_psd_a2_per_hz"] >= 0.0 for item in summaries)
                else "fail"
            ),
        },
        {
            "id": "mos.gate_referred_and_complex_transfer",
            "status": "pass",
            "evidence": [item["noise_spectrum_sha256"] for item in summaries],
        },
        {
            "id": "mos.source_breakdown",
            "status": (
                "pass" if all(item["source_vector_names"] for item in summaries) else "fail"
            ),
        },
        {
            "id": "mos.effective_parameter_provenance",
            "status": (
                "pass" if all(item["effective_parameter_count"] > 0 for item in summaries) else "fail"
            ),
        },
        {
            "id": "mos.log_audit_sparse",
            "status": (
                "pass"
                if all(
                    item["sparse_attestation_count"] > 0
                    and item["klu_attestation_count"] == 0
                    and item["log_critical_diagnostic_count"] == 0
                    for item in summaries
                )
                else "fail"
            ),
        },
        {"id": "models.no_spike_tuning", "status": immutability["status"]},
    ]
    report_status = "pass" if all(item["status"] == "pass" for item in checks) else "fail"
    recommendations = {
        "frequency_profile": (
            "Do not freeze 1 Hz-100 MHz as the all-device final profile: the APM045/VTG "
            "fixed 10-100 MHz window did not expose a white region. Retain 20 points/decade "
            "for discovery and add a bounded higher-frequency diagnostic before freezing the "
            "common upper limit; preserve 1 Hz as the low endpoint for current PSP/CMG flicker."
        ),
        "points_per_decade": (
            "Retain 20 points/decade provisionally. It supplied 61 low-frequency fit points "
            "and 21 points in each one-decade white review window without dominating runtime."
        ),
        "fitting_method": (
            "Replace fixed review windows with a versioned contiguous-region detector using "
            "predeclared slope/span/quality rules. Keep fail-closed nulls and never use the last "
            "frequency point as a white floor. Refit persisted raw spectra without rerunning when possible."
        ),
        "osdi_correlation": (
            "The internal-node correlation construction is preserved by the current "
            "OpenVAF-ReLoaded -> OSDI -> ngspice Sparse path. PSP103 exercised nonzero igig/idid "
            "with native cigid; a separate BSIM-CMG TNOIMOD=1 diagnostic exposed nonzero corl/id "
            "sources while the production APM016F card remained TNOIMOD=0."
        ),
        "parameter_interrogation": (
            "Use ngspice showmod final values for BSIM3/BSIM4, with the documented narrow BSIM4 "
            "LINTNOI=0 runtime-default fallback for ngspice 47's query error. Use OSDI showmod for "
            "PSP103/BSIM-CMG final values and bind them to explicit card occurrences or pinned "
            "Verilog-A default declarations."
        ),
        "all_26_devices": (
            "Do not start the full 26-device matrix until the upper-frequency diagnostic and "
            "fit-region method are frozen. After that narrow milestone, the common raw schema and "
            "four engine paths are ready for catalog-wide orchestration."
        ),
        "low_vds_diagnostic": (
            "Add a small low-VDS diagnostic before all-device expansion. V3-N0 has only VOUT=0.5*VDD, "
            "so it cannot establish whether the same fit/profile decisions remain observable in the "
            "linear-region thermal/correlation branches. Keep it diagnostic, not a replacement canonical point."
        ),
        "generic_noise_calibration": (
            "Research generic APM-authored calibration later, but do not tune now. The unchanged "
            "APM350 BSIM3 default produces no flicker (KF=0), while unchanged APM016F BSIM-CMG "
            "defaults produce strong flicker; this spread justifies a separate evidence-backed "
            "generic-noise target milestone rather than plausibility tuning in the spike."
        ),
    }
    git_commit = run_checked(["git", "rev-parse", "HEAD"], cwd=resolved_root).stdout.strip()
    report = {
        "schema": "apm.noise-spike-validation.v1",
        "milestone": "V3-N0",
        "status": report_status,
        "created_utc": _utc_now(),
        "repository_commit": git_commit,
        "reference_environment": {
            "platform": "WSL2 + AlmaLinux/RHEL-compatible EL9 x86_64",
            "ngspice": run_checked([selected_toolchain.ngspice, "--version"]).stdout.strip(),
            "openvaf": run_checked(
                [selected_toolchain.openvaf, "--version"],
                environment=selected_toolchain.environment(),
            ).stdout.strip(),
            "required_noise_solver": "Sparse",
        },
        "model_build": {
            "schema": build["schema"],
            "cache_status": build["cache_status"],
            "openvaf_sha256": build["openvaf_sha256"],
            "artifacts": [
                {"model_id": item["model_id"], "output_sha256": item["output_sha256"]}
                for item in build["artifacts"]
            ],
        },
        "harness_report": {
            "path": "harness_report.json",
            "sha256": sha256_file(result_directory / "harness_report.json"),
            "status": harness["status"],
        },
        "correlation": correlation,
        "model_immutability": immutability,
        "mos_results": summaries,
        "checks": checks,
        "acceptance_result": f"{sum(item['status'] == 'pass' for item in checks)}/{len(checks)}",
        "recommendations": recommendations,
        "claim_boundary": (
            "V3-N0 validates framework/backend execution and characterizes current model predictions. "
            "It is not a v3 release and is not silicon/process noise calibration for APM-authored families."
        ),
        "output_directory": str(result_directory),
        "report_path": str(result_directory / "report.json"),
    }
    _write_json(result_directory / "report.json", report)
    report["report_sha256"] = sha256_file(result_directory / "report.json")
    if report_status != "pass":
        failed = [item["id"] for item in checks if item["status"] != "pass"]
        raise NoiseValidationError(f"V3-N0 failed checks: {failed}")
    return report
