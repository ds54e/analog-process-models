# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .benchmark import (
    BenchmarkError,
    load_benchmark_configuration,
    resolve_corner,
    resolve_monte_carlo,
    resolved_passive_value_at_temperature,
    write_resolved_sample,
)
from .characterize import _read_wrdata, _run_ngspice, _threshold_crossing, load_kit
from .model_build import build_models, sha256_file
from .toolchain import Toolchain, resolve_toolchain, run_checked

VALIDATION_SEED = 20260830
VALIDATED_KITS = ("apm130", "apm045", "apm016f")
BOLTZMANN_J_PER_K = 1.380649e-23
VTH_CALIBRATION_RAW_VALUES = tuple(index / 100.0 for index in range(-4, 5))
DRIVE_CALIBRATION_RAW_VALUES = tuple(0.8 + index * 0.05 for index in range(9))


def _observable(log: Path, name: str) -> float:
    text = log.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        rf"^{re.escape(name)}\s*=\s*([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        raise BenchmarkError(f"missing {name} in ngspice log: {log}")
    value = float(match.group(1))
    if not math.isfinite(value):
        raise BenchmarkError(f"non-finite {name} in ngspice log: {log}")
    return value


def _observables(log: Path, name: str) -> list[float]:
    text = log.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(
        rf"^{re.escape(name)}\s*=\s*([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    values = [float(value) for value in matches]
    if not values or not all(math.isfinite(value) for value in values):
        raise BenchmarkError(f"missing or non-finite {name} sequence in ngspice log: {log}")
    return values


def _adapter_calibration(
    toolchain: Toolchain,
    output: Path,
    kit_id: str,
    polarity: str,
) -> dict[str, Any]:
    kit = load_kit(kit_id, toolchain.root)
    configuration = load_benchmark_configuration(toolchain.root)
    adapter = configuration["adapters"]["kit"][kit_id]
    polarity_adapter = adapter[polarity]
    sign = 1.0 if polarity == "n" else -1.0
    if adapter["architecture"] == "planar_bulk":
        geometry = (
            f"w={float(adapter['reference_w_m']):.17g} "
            f"l={float(adapter['reference_l_m']):.17g}"
        )
        criterion = float(adapter["threshold_coefficient_a"]) * float(
            adapter["reference_w_m"]
        ) / float(adapter["reference_l_m"])
    else:
        geometry = (
            f"l={float(adapter['reference_l_m']):.17g} "
            f"nfin={int(adapter['reference_nfin'])}"
        )
        criterion = float(adapter["threshold_coefficient_a"]) * int(
            adapter["reference_nfin"]
        )
    device_path = polarity_adapter["ngspice_device_path_template"].format(instance="xdut")
    vth_parameter = adapter["vth_raw_parameter"]
    drive_parameter = adapter["drive_raw_parameter"]
    vdd = float(adapter["vdd_v"])
    vth_vout = 0.8 * vdd
    raw_paths = [
        output / "calibration" / f"adapter_{kit_id}_{polarity}_vth_{index}.dat"
        for index in range(len(VTH_CALIBRATION_RAW_VALUES))
    ]
    lines = [
        f"APM {kit_id} {polarity} observable-intent adapter calibration",
        *kit.model_directives(),
        f'.include "{kit.wrapper_file}"',
        ".temp 27",
        f"Vd d 0 {sign * vth_vout:.17g}",
        "Vg g 0 0",
        "Vs s 0 0",
        "Vb b 0 0",
        f"Xdut d g s b {kit.public_devices[polarity]} {geometry}",
        ".control",
        *[f"pre_osdi {toolchain.osdi_directory / item}" for item in kit.osdi_artifacts],
        "set numdgt=15",
        "set wr_vecnames",
        "set wr_singlescale",
    ]
    for raw_value, raw_path in zip(VTH_CALIBRATION_RAW_VALUES, raw_paths):
        lines.extend(
            [
                f"alter {device_path}[{vth_parameter}] = {raw_value:.17g}",
                f"dc Vg 0 {sign * vdd:.17g} {sign * vdd / 240.0:.17g}",
                f"wrdata {raw_path} v(g) i(vd)",
            ]
        )
    lines.extend(
        [
            f"alter {device_path}[{vth_parameter}] = 0",
            f"alter Vd = {sign * float(adapter['vout_reference_v']):.17g}",
            f"alter Vg = {sign * float(polarity_adapter['vctrl_reference_v']):.17g}",
        ]
    )
    for raw_value in DRIVE_CALIBRATION_RAW_VALUES:
        lines.extend(
            [
                f"alter {device_path}[{drive_parameter}] = {raw_value:.17g}",
                "op",
                "print i(vd)",
            ]
        )
    lines.extend(["quit", ".endc", ".end"])
    job = f"adapter_{kit_id}_{polarity}"
    netlist = output / "netlists" / f"{job}.cir"
    log = output / "logs" / f"{job}.log"
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)

    thresholds: list[float] = []
    for raw_path in raw_paths:
        curve = [
            {"vctrl_v": abs(values[1]), "idmag_a": abs(values[2])}
            for values in _read_wrdata(raw_path, 3)
        ]
        thresholds.append(_threshold_crossing(curve, criterion))
    nominal_threshold = thresholds[VTH_CALIBRATION_RAW_VALUES.index(0.0)]
    vth_points = []
    for raw_value, threshold in zip(VTH_CALIBRATION_RAW_VALUES, thresholds):
        observed = threshold - nominal_threshold
        predicted = (
            float(polarity_adapter["vth_fit_linear"]) * raw_value
            + float(polarity_adapter["vth_fit_quadratic"]) * raw_value**2
        )
        vth_points.append(
            {
                "raw_value_v": raw_value,
                "threshold_magnitude_v": threshold,
                "observed_shift_v": observed,
                "stored_fit_shift_v": predicted,
                "residual_v": observed - predicted,
                "raw_file": str(raw_paths[len(vth_points)].relative_to(output)),
            }
        )

    drive_currents = [abs(value) for value in _observables(log, "i(vd)")]
    if len(drive_currents) != len(DRIVE_CALIBRATION_RAW_VALUES):
        raise BenchmarkError(
            f"expected {len(DRIVE_CALIBRATION_RAW_VALUES)} drive points in {log}, "
            f"found {len(drive_currents)}"
        )
    nominal_drive_current = drive_currents[DRIVE_CALIBRATION_RAW_VALUES.index(1.0)]
    drive_points = []
    for raw_value, current in zip(DRIVE_CALIBRATION_RAW_VALUES, drive_currents):
        raw_delta = raw_value - 1.0
        observed = current / nominal_drive_current - 1.0
        predicted = (
            float(polarity_adapter["drive_fit_linear"]) * raw_delta
            + float(polarity_adapter["drive_fit_quadratic"]) * raw_delta**2
        )
        drive_points.append(
            {
                "raw_multiplier": raw_value,
                "idmag_a": current,
                "observed_shift_fraction": observed,
                "stored_fit_shift_fraction": predicted,
                "residual_fraction": observed - predicted,
            }
        )
    return {
        "kit_id": kit_id,
        "polarity": polarity,
        "compact_model": kit.compact_model,
        "public_device": kit.public_devices[polarity],
        "temperature_c": 27.0,
        "geometry": geometry,
        "vth_reference": {
            "vout_v": vth_vout,
            "criterion_a": criterion,
            "nominal_observed_threshold_magnitude_v": nominal_threshold,
            "stored_nominal_threshold_magnitude_v": float(
                polarity_adapter["nominal_threshold_magnitude_v"]
            ),
            "points": vth_points,
            "max_abs_stored_fit_residual_v": max(
                abs(point["residual_v"]) for point in vth_points
            ),
        },
        "drive_reference": {
            "vctrl_v": float(polarity_adapter["vctrl_reference_v"]),
            "vout_v": float(adapter["vout_reference_v"]),
            "nominal_observed_id_a": nominal_drive_current,
            "stored_nominal_id_a": float(polarity_adapter["nominal_reference_id_a"]),
            "points": drive_points,
            "max_abs_stored_fit_residual_fraction": max(
                abs(point["residual_fraction"]) for point in drive_points
            ),
        },
        "raw_parameters": {"vth": vth_parameter, "drive": drive_parameter},
        "device_path": device_path,
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
    }


def _mos_simulation(
    toolchain: Toolchain,
    output: Path,
    sample_name: str,
    sample: dict[str, Any],
    kit_id: str,
    *,
    suffix: str = "",
) -> dict[str, Any]:
    kit = load_kit(kit_id, toolchain.root)
    configuration = load_benchmark_configuration(toolchain.root)
    adapter = configuration["adapters"]["kit"][kit_id]
    instances = {
        item["polarity"]: item for item in sample["mos_instances"] if item["kit_id"] == kit_id
    }
    if set(instances) != {"n", "p"}:
        raise BenchmarkError(f"benchmark validation request lacks N/P pair for {kit_id}")
    lines = [
        f"APM benchmark {sample_name} deterministic MOS validation",
        *kit.model_directives(),
        f'.include "{kit.wrapper_file}"',
        ".temp 27",
    ]
    for polarity in ("n", "p"):
        instance = instances[polarity]
        sign = 1.0 if polarity == "n" else -1.0
        vctrl = float(adapter[polarity]["vctrl_reference_v"])
        vout = float(adapter["vout_reference_v"])
        tag = polarity
        lines.extend(
            [
                f"Vd{tag} d{tag} 0 {sign * vout:.17g}",
                f"Vg{tag} g{tag} 0 {sign * vctrl:.17g}",
                f"Vs{tag} s{tag} 0 0",
                f"Vb{tag} b{tag} 0 0",
            ]
        )
        geometry = instance["geometry"]
        if "w_m" in geometry:
            parameters = f"w={geometry['w_m']:.17g} l={geometry['l_m']:.17g}"
        else:
            parameters = f"l={geometry['l_m']:.17g} nfin={geometry['nfin']}"
        lines.append(
            f"{instance['ngspice_instance']} d{tag} g{tag} s{tag} b{tag} "
            f"{kit.public_devices[polarity]} {parameters}"
        )
    alter_commands = [
        command
        for polarity in ("n", "p")
        for command in instances[polarity]["raw_adapter"]["alter_commands"]
    ]
    lines.extend(
        [
            ".control",
            *[f"pre_osdi {toolchain.osdi_directory / item}" for item in kit.osdi_artifacts],
            "set numdgt=15",
            *alter_commands,
            "op",
            "print i(vdn) i(vdp)",
            "quit",
            ".endc",
            ".end",
        ]
    )
    job = f"mos_{kit_id}_{sample_name}{suffix}"
    netlist = output / "netlists" / f"{job}.cir"
    log = output / "logs" / f"{job}.log"
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)
    result: dict[str, Any] = {
        "kit_id": kit_id,
        "variation_origin": "benchmark",
        "variation_mode": sample["variation_mode"],
        "corner_profile": sample["corner_profile"],
        "sample_name": sample_name,
        "sample_id": sample["sample_id"],
        "rng": sample["rng"],
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "idmag_a": {
            "n": abs(_observable(log, "i(vdn)")),
            "p": abs(_observable(log, "i(vdp)")),
        },
        "instances": {
            polarity: {
                "id": instances[polarity]["id"],
                "global_process": sample["global_process"]["mos"][polarity],
                "local_applied": instances[polarity]["local_applied"],
                "total_intents": instances[polarity]["total_intents"],
                "raw_adapter": instances[polarity]["raw_adapter"],
            }
            for polarity in ("n", "p")
        },
    }
    return result


def _passive_simulation(
    toolchain: Toolchain,
    output: Path,
    sample_name: str,
    sample: dict[str, Any],
    temperature_c: float,
) -> dict[str, Any]:
    instances = {item["kind"]: item for item in sample["passive_instances"]}
    if set(instances) != {"resistor", "capacitor"}:
        raise BenchmarkError("benchmark validation request lacks one resistor and one capacitor")
    resistor = instances["resistor"]
    capacitor = instances["capacitor"]
    frequency = 1.0e6
    include = toolchain.root / "passives/ngspice/benchmark_passives.inc"
    lines = [
        f"APM benchmark {sample_name} deterministic passive validation",
        f'.include "{include}"',
        f".temp {temperature_c:.17g}",
        "Vr r 0 1",
        (
            f"Xr r 0 Rbench value={resistor['resolved_value_at_27c']:.17g} "
            f"tc1={resistor['tc1_per_c']:.17g} match_size={resistor['match_size']:.17g}"
        ),
        "Vc c 0 0 AC 1",
        (
            f"Xc c 0 Cbench value={capacitor['resolved_value_at_27c']:.17g} "
            f"tc1={capacitor['tc1_per_c']:.17g} match_size={capacitor['match_size']:.17g}"
        ),
        ".control",
        "set numdgt=15",
        "op",
        "print i(vr)",
        f"ac lin 1 {frequency:.17g} {frequency:.17g}",
        "print imag(i(vc))",
        "quit",
        ".endc",
        ".end",
    ]
    token = str(temperature_c).replace("-", "m").replace(".", "p")
    job = f"passives_{sample_name}_{token}c"
    netlist = output / "netlists" / f"{job}.cir"
    log = output / "logs" / f"{job}.log"
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)
    measured_resistance = 1.0 / abs(_observable(log, "i(vr)"))
    measured_capacitance = abs(_observable(log, "imag(i(vc))")) / (2.0 * math.pi * frequency)
    expected_resistance = resolved_passive_value_at_temperature(resistor, temperature_c)
    expected_capacitance = resolved_passive_value_at_temperature(capacitor, temperature_c)
    return {
        "variation_origin": "benchmark",
        "variation_mode": sample["variation_mode"],
        "corner_profile": sample["corner_profile"],
        "sample_name": sample_name,
        "sample_id": sample["sample_id"],
        "rng": sample["rng"],
        "temperature_c": temperature_c,
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "resistor": {
            "expected_ohm": expected_resistance,
            "measured_ohm": measured_resistance,
            "relative_error": abs(measured_resistance / expected_resistance - 1.0),
        },
        "capacitor": {
            "expected_f": expected_capacitance,
            "measured_f": measured_capacitance,
            "relative_error": abs(measured_capacitance / expected_capacitance - 1.0),
        },
    }


def _passive_noise_simulation(
    toolchain: Toolchain,
    output: Path,
    sample_name: str,
    sample: dict[str, Any],
    temperature_c: float,
) -> dict[str, Any]:
    resistor = next(
        (item for item in sample["passive_instances"] if item["kind"] == "resistor"), None
    )
    if resistor is None:
        raise BenchmarkError("benchmark validation request lacks a resistor")
    include = toolchain.root / "passives/ngspice/benchmark_passives.inc"
    frequency = 1.0e3
    lines = [
        f"APM benchmark {sample_name} native resistor Johnson-noise validation",
        f'.include "{include}"',
        f".temp {temperature_c:.17g}",
        "Vinput input 0 0 AC 1",
        (
            f"Xr input output Rbench value={resistor['resolved_value_at_27c']:.17g} "
            f"tc1={resistor['tc1_per_c']:.17g} match_size={resistor['match_size']:.17g}"
        ),
        ".control",
        "set numdgt=15",
        f"noise v(output) Vinput lin 1 {frequency:.17g} {frequency:.17g}",
        "print onoise_spectrum",
        "quit",
        ".endc",
        ".end",
    ]
    job = f"passive_noise_{sample_name}"
    netlist = output / "netlists" / f"{job}.cir"
    log = output / "logs" / f"{job}.log"
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)
    resistance = resolved_passive_value_at_temperature(resistor, temperature_c)
    expected = math.sqrt(4.0 * BOLTZMANN_J_PER_K * (temperature_c + 273.15) * resistance)
    measured = abs(_observable(log, "onoise_spectrum"))
    return {
        "variation_origin": "benchmark",
        "variation_mode": sample["variation_mode"],
        "corner_profile": sample["corner_profile"],
        "sample_name": sample_name,
        "sample_id": sample["sample_id"],
        "rng": sample["rng"],
        "resolved_sample": None,
        "temperature_c": temperature_c,
        "frequency_hz": frequency,
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "primitive_semantic": "native SPICE resistor thermal noise; APM adds no noise source",
        "expected_voltage_noise_v_per_sqrt_hz": expected,
        "measured_voltage_noise_v_per_sqrt_hz": measured,
        "relative_error": abs(measured / expected - 1.0),
    }


def validate_benchmark(
    output_directory: Path,
    toolchain: Toolchain | None = None,
) -> dict[str, Any]:
    selected = toolchain or resolve_toolchain()
    output = output_directory.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise BenchmarkError(f"refusing to overwrite non-empty validation directory: {output}")
    for child in ("samples", "netlists", "logs", "calibration"):
        (output / child).mkdir(parents=True, exist_ok=True)
    build_models(selected, force=False)
    request_path = selected.root / "examples/benchmark_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    samples: dict[str, dict[str, Any]] = {
        mode: resolve_monte_carlo(request, mode=mode, seed=VALIDATION_SEED, root=selected.root)
        for mode in ("process", "mismatch", "all")
    }
    samples.update(
        {
            corner: resolve_corner(request, corner=corner, root=selected.root)
            for corner in ("bench_tt", "bench_ff", "bench_ss", "bench_fs", "bench_sf")
        }
    )
    sample_records: dict[str, Any] = {}
    for name, sample in samples.items():
        path = write_resolved_sample(sample, output / "samples" / f"{name}.json")
        sample_records[name] = {
            "sample_id": sample["sample_id"],
            "path": str(path.relative_to(output)),
            "sha256": sha256_file(path),
            "variation_mode": sample["variation_mode"],
            "corner_profile": sample["corner_profile"],
        }

    simulations = [
        _mos_simulation(selected, output, sample_name, sample, kit_id)
        for sample_name, sample in samples.items()
        for kit_id in VALIDATED_KITS
    ]
    replay = [
        _mos_simulation(selected, output, "all", samples["all"], kit_id, suffix="_replay")
        for kit_id in VALIDATED_KITS
    ]
    passive_simulations = [
        _passive_simulation(selected, output, mode, samples[mode], temperature)
        for mode in ("process", "mismatch", "all")
        for temperature in (27.0, 85.0)
    ]
    passive_noise_simulation = _passive_noise_simulation(
        selected, output, "all", samples["all"], 27.0
    )
    adapter_calibrations = [
        _adapter_calibration(selected, output, kit_id, polarity)
        for kit_id in VALIDATED_KITS
        for polarity in ("n", "p")
    ]
    for simulation in [
        *simulations,
        *replay,
        *passive_simulations,
        passive_noise_simulation,
    ]:
        simulation["resolved_sample"] = sample_records[simulation["sample_name"]]
    simulation_by_key = {
        (item["kit_id"], item["sample_name"]): item for item in simulations
    }
    configuration = load_benchmark_configuration(selected.root)
    nominal_alignment_errors: list[float] = []
    corner_direction_pass = True
    for kit_id in VALIDATED_KITS:
        nominal = simulation_by_key[(kit_id, "bench_tt")]
        adapter = configuration["adapters"]["kit"][kit_id]
        for polarity in ("n", "p"):
            expected = float(adapter[polarity]["nominal_reference_id_a"])
            observed = nominal["idmag_a"][polarity]
            nominal_alignment_errors.append(abs(observed / expected - 1.0))
        ff = simulation_by_key[(kit_id, "bench_ff")]["idmag_a"]
        ss = simulation_by_key[(kit_id, "bench_ss")]["idmag_a"]
        fs = simulation_by_key[(kit_id, "bench_fs")]["idmag_a"]
        sf = simulation_by_key[(kit_id, "bench_sf")]["idmag_a"]
        tt = nominal["idmag_a"]
        corner_direction_pass = corner_direction_pass and (
            ff["n"] > tt["n"]
            and ff["p"] > tt["p"]
            and ss["n"] < tt["n"]
            and ss["p"] < tt["p"]
            and fs["n"] > tt["n"]
            and fs["p"] < tt["p"]
            and sf["n"] < tt["n"]
            and sf["p"] > tt["p"]
        )
    replay_pass = all(
        item["idmag_a"] == simulation_by_key[(item["kit_id"], "all")]["idmag_a"]
        for item in replay
    )
    reproduced = resolve_monte_carlo(
        request, mode="all", seed=VALIDATION_SEED, root=selected.root
    )
    different = resolve_monte_carlo(
        request, mode="all", seed=VALIDATION_SEED + 1, root=selected.root
    )
    raw_ranges_pass = all(
        instance["raw_adapter"]["vth_within_calibrated_raw_range"]
        and instance["raw_adapter"]["drive_within_calibrated_raw_range"]
        for sample in samples.values()
        for instance in sample["mos_instances"]
    )
    passive_error = max(
        max(item["resistor"]["relative_error"], item["capacitor"]["relative_error"])
        for item in passive_simulations
    )
    mc_finite = all(
        item["idmag_a"][polarity] > 0.0 and math.isfinite(item["idmag_a"][polarity])
        for item in simulations
        if item["sample_name"] in ("process", "mismatch", "all")
        for polarity in ("n", "p")
    )
    adapter_vth_fit_error = max(
        item["vth_reference"]["max_abs_stored_fit_residual_v"]
        for item in adapter_calibrations
    )
    adapter_drive_fit_error = max(
        item["drive_reference"]["max_abs_stored_fit_residual_fraction"]
        for item in adapter_calibrations
    )
    adapter_nominal_vth_error = max(
        abs(
            item["vth_reference"]["nominal_observed_threshold_magnitude_v"]
            - item["vth_reference"]["stored_nominal_threshold_magnitude_v"]
        )
        for item in adapter_calibrations
    )
    adapter_nominal_drive_error = max(
        abs(
            item["drive_reference"]["nominal_observed_id_a"]
            / item["drive_reference"]["stored_nominal_id_a"]
            - 1.0
        )
        for item in adapter_calibrations
    )
    checks = {
        "same_seed_identical_sample": reproduced == samples["all"],
        "different_seed_differs": different["sample_id"] != samples["all"]["sample_id"],
        "same_seed_mode_draw_order_identical": samples["process"]["draw_order"]
        == samples["mismatch"]["draw_order"]
        == samples["all"]["draw_order"],
        "deterministic_ngspice_replay": replay_pass,
        "mc_modes_real_tool_finite": mc_finite,
        "corner_current_directions": corner_direction_pass,
        "all_raw_adapter_values_inside_calibrated_range": raw_ranges_pass,
        "nominal_adapter_alignment_max_relative_error": max(nominal_alignment_errors),
        "passive_value_max_relative_error": passive_error,
        "adapter_vth_fit_max_abs_residual_v": adapter_vth_fit_error,
        "adapter_drive_fit_max_abs_residual_fraction": adapter_drive_fit_error,
        "adapter_nominal_vth_max_abs_error_v": adapter_nominal_vth_error,
        "adapter_nominal_drive_max_relative_error": adapter_nominal_drive_error,
    }
    requirements = {
        "seed_reproducibility": checks["same_seed_identical_sample"],
        "different_seed_behavior": checks["different_seed_differs"],
        "mode_composition_draw_identity": checks["same_seed_mode_draw_order_identical"],
        "deterministic_simulator_replay": checks["deterministic_ngspice_replay"],
        "process_mismatch_all_execute": checks["mc_modes_real_tool_finite"],
        "benchmark_corner_semantics": checks["corner_current_directions"],
        "calibrated_adapter_range": checks["all_raw_adapter_values_inside_calibrated_range"],
        "nominal_public_adapter_alignment": checks[
            "nominal_adapter_alignment_max_relative_error"
        ]
        < 1e-5,
        "resolved_native_passive_values": checks["passive_value_max_relative_error"] < 1e-6,
        "native_resistor_johnson_noise": passive_noise_simulation["relative_error"] < 1e-3,
        "observable_vth_adapter_calibration": adapter_vth_fit_error < 5e-5
        and adapter_nominal_vth_error < 5e-8,
        "observable_drive_adapter_calibration": adapter_drive_fit_error < 5e-5
        and adapter_nominal_drive_error < 1e-10,
    }
    checks["requirements"] = requirements
    checks["overall_pass"] = all(requirements.values())
    version = run_checked([selected.ngspice, "--version"])
    report: dict[str, Any] = {
        "schema": "apm.benchmark-validation.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "validated" if checks["overall_pass"] else "checks_failed",
        "variation_origin": "benchmark",
        "validation_seed": VALIDATION_SEED,
        "validated_kits": list(VALIDATED_KITS),
        "ngspice_version": (version.stdout + version.stderr).strip(),
        "request": {
            "path": str(request_path.relative_to(selected.root)),
            "sha256": sha256_file(request_path),
        },
        "benchmark_configuration": configuration["identity"],
        "samples": sample_records,
        "mos_simulations": simulations,
        "replay_simulations": replay,
        "passive_simulations": passive_simulations,
        "passive_noise_simulation": passive_noise_simulation,
        "adapter_calibrations": adapter_calibrations,
        "checks": checks,
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["output_directory"] = str(output)
    report["report_path"] = str(report_path)
    if not checks["overall_pass"]:
        raise BenchmarkError(f"benchmark validation checks failed; see {report_path}")
    return report
