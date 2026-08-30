# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Real-ngspice validation for APM Benchmark Variation v2."""

from __future__ import annotations

import json
import math
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .benchmark import (
    BENCHMARK_CORNERS,
    BENCHMARK_MODES,
    BenchmarkError,
    load_benchmark_configuration,
    resolve_corner,
    resolve_monte_carlo,
    resolved_passive_value_at_temperature,
    write_resolved_sample,
)
from .catalog import Catalog, FamilySpec, load_catalog
from .characterize import (
    NGSPICE_GMIN_S,
    _read_wrdata,
    _run_ngspice,
    _threshold_crossing,
    load_family,
)
from .model_build import build_models, sha256_file
from .toolchain import Toolchain, resolve_toolchain, run_checked

VALIDATION_SEED = 20260830
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


def _validation_request(catalog: Catalog, configuration: dict[str, Any]) -> dict[str, Any]:
    mos: list[dict[str, Any]] = []
    for technology in catalog.technologies:
        for family in technology.families:
            adapter = configuration["adapters"]["family"][family.selector]
            for device in family.devices:
                device_adapter = adapter["device"][device.device_id]
                geometry: dict[str, Any] = {
                    "l_m": float(device_adapter["reference_l_m"]),
                }
                if family.architecture == "planar_bulk":
                    geometry["w_m"] = float(device_adapter["reference_w_m"])
                else:
                    geometry["nfin"] = int(device_adapter["reference_nfin"])
                instance_id = f"m_{technology.technology_id}_{family.family_id}_{device.device_id}"
                mos.append(
                    {
                        "id": instance_id,
                        "selector": device.selector,
                        "geometry": geometry,
                        "ngspice_instance": f"x{instance_id}",
                    }
                )
    return {
        "schema": "apm.benchmark-request.v2",
        "instances": {
            "mos": mos,
            "resistors": [
                {
                    "id": "rload",
                    "value": 10000.0,
                    "tc1_per_c": 0.001,
                    "match_size": 1.0,
                }
            ],
            "capacitors": [
                {
                    "id": "cload",
                    "value": 1.0e-12,
                    "tc1_per_c": 0.0002,
                    "match_size": 1.0,
                }
            ],
        },
    }


def _adapter_calibration(
    toolchain: Toolchain,
    output: Path,
    family: FamilySpec,
    device_id: str,
    configuration: dict[str, Any],
) -> dict[str, Any]:
    kit = load_family(family.selector, toolchain.root)
    adapter = configuration["adapters"]["family"][family.selector]
    device_adapter = adapter["device"][device_id]
    device = family.device(device_id)
    polarity = device.polarity
    sign = 1.0 if polarity == "n" else -1.0
    if family.architecture == "planar_bulk":
        geometry = (
            f"w={float(device_adapter['reference_w_m']):.17g} "
            f"l={float(device_adapter['reference_l_m']):.17g}"
        )
        criterion = (
            float(adapter["threshold_coefficient_a"])
            * float(device_adapter["reference_w_m"])
            / float(device_adapter["reference_l_m"])
        )
    else:
        geometry = (
            f"l={float(device_adapter['reference_l_m']):.17g} "
            f"nfin={int(device_adapter['reference_nfin'])}"
        )
        criterion = float(adapter["threshold_coefficient_a"]) * int(
            device_adapter["reference_nfin"]
        )
    device_path = device_adapter["ngspice_device_path_template"].format(instance="xdut")
    vth_parameter = adapter["vth_raw_parameter"]
    drive_parameter = adapter["drive_raw_parameter"]
    vdd = float(adapter["vdd_v"])
    vth_sweep_intervals = max(240, math.ceil(vdd / 0.005))
    vth_vout = 0.8 * vdd
    token = f"{family.technology_id}_{family.family_id}_{device_id}"
    raw_paths = [
        output / "calibration" / f"adapter_{token}_vth_{index}.dat"
        for index in range(len(VTH_CALIBRATION_RAW_VALUES))
    ]
    lines = [
        f"APM v2 {family.selector}/{device_id} observable adapter calibration",
        *kit.model_directives(),
        f'.include "{kit.wrapper_file}"',
        f".options gmin={NGSPICE_GMIN_S:.12g}",
        ".temp 27",
        f"Vd d 0 {sign * vth_vout:.17g}",
        "Vg g 0 0",
        "Vs s 0 0",
        "Vb b 0 0",
        f"Xdut d g s b {device.public_name} {geometry}",
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
                f"dc Vg 0 {sign * vdd:.17g} {sign * vdd / vth_sweep_intervals:.17g}",
                f"wrdata {raw_path} v(g) i(vd)",
            ]
        )
    lines.extend(
        [
            f"alter {device_path}[{vth_parameter}] = 0",
            f"alter Vd = {sign * float(adapter['vout_reference_v']):.17g}",
            f"alter Vg = {sign * float(device_adapter['vctrl_reference_v']):.17g}",
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
    netlist = output / "netlists" / f"adapter_{token}.cir"
    log = output / "logs" / f"adapter_{token}.log"
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
    vth_points: list[dict[str, Any]] = []
    for raw_value, threshold, raw_path in zip(VTH_CALIBRATION_RAW_VALUES, thresholds, raw_paths):
        observed = threshold - nominal_threshold
        predicted = (
            float(device_adapter["vth_fit_linear"]) * raw_value
            + float(device_adapter["vth_fit_quadratic"]) * raw_value**2
        )
        vth_points.append(
            {
                "raw_value_v": raw_value,
                "threshold_magnitude_v": threshold,
                "observed_shift_v": observed,
                "stored_fit_shift_v": predicted,
                "residual_v": observed - predicted,
                "raw_file": str(raw_path.relative_to(output)),
            }
        )
    drive_currents = [abs(value) for value in _observables(log, "i(vd)")]
    if len(drive_currents) != len(DRIVE_CALIBRATION_RAW_VALUES):
        raise BenchmarkError(f"unexpected drive calibration row count in {log}")
    nominal_drive = drive_currents[DRIVE_CALIBRATION_RAW_VALUES.index(1.0)]
    drive_points: list[dict[str, Any]] = []
    for raw_value, current in zip(DRIVE_CALIBRATION_RAW_VALUES, drive_currents):
        raw_delta = raw_value - 1.0
        observed = current / nominal_drive - 1.0
        predicted = (
            float(device_adapter["drive_fit_linear"]) * raw_delta
            + float(device_adapter["drive_fit_quadratic"]) * raw_delta**2
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
        "technology_id": family.technology_id,
        "family_id": family.family_id,
        "device_id": device_id,
        "selector": device.selector,
        "polarity": polarity,
        "compact_model": family.compact_model,
        "public_device": device.public_name,
        "family_manifest_sha256": family.manifest_sha256,
        "temperature_c": 27.0,
        "vth_sweep_step_v": vdd / vth_sweep_intervals,
        "geometry": geometry,
        "vth_reference": {
            "vout_v": vth_vout,
            "criterion_a": criterion,
            "nominal_observed_threshold_magnitude_v": nominal_threshold,
            "stored_nominal_threshold_magnitude_v": float(
                device_adapter["nominal_threshold_magnitude_v"]
            ),
            "points": vth_points,
            "max_abs_stored_fit_residual_v": max(abs(point["residual_v"]) for point in vth_points),
        },
        "drive_reference": {
            "vctrl_v": float(device_adapter["vctrl_reference_v"]),
            "vout_v": float(adapter["vout_reference_v"]),
            "nominal_observed_id_a": nominal_drive,
            "stored_nominal_id_a": float(device_adapter["nominal_reference_id_a"]),
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
    family: FamilySpec,
    configuration: dict[str, Any],
    *,
    suffix: str = "",
) -> dict[str, Any]:
    kit = load_family(family.selector, toolchain.root)
    adapter = configuration["adapters"]["family"][family.selector]
    instances = {
        item["device_id"]: item
        for item in sample["mos_instances"]
        if item["family_selector"] == family.selector
    }
    if set(instances) != {device.device_id for device in family.devices}:
        raise BenchmarkError(
            f"benchmark request lacks family device coverage for {family.selector}"
        )
    lines = [
        f"APM v2 benchmark {sample_name} {family.selector} MOS validation",
        *kit.model_directives(),
        f'.include "{kit.wrapper_file}"',
        f".options gmin={NGSPICE_GMIN_S:.12g}",
        ".temp 27",
    ]
    source_names: dict[str, str] = {}
    for device in family.devices:
        instance = instances[device.device_id]
        sign = 1.0 if device.polarity == "n" else -1.0
        device_adapter = adapter["device"][device.device_id]
        vctrl = float(device_adapter["vctrl_reference_v"])
        vout = float(adapter["vout_reference_v"])
        tag = device.device_id
        source = f"Vd_{tag}"
        source_names[device.device_id] = source.lower()
        lines.extend(
            [
                f"{source} d_{tag} 0 {sign * vout:.17g}",
                f"Vg_{tag} g_{tag} 0 {sign * vctrl:.17g}",
                f"Vs_{tag} s_{tag} 0 0",
                f"Vb_{tag} b_{tag} 0 0",
            ]
        )
        geometry = instance["geometry"]
        parameters = (
            f"w={geometry['w_m']:.17g} l={geometry['l_m']:.17g}"
            if "w_m" in geometry
            else f"l={geometry['l_m']:.17g} nfin={geometry['nfin']}"
        )
        lines.append(
            f"{instance['ngspice_instance']} d_{tag} g_{tag} s_{tag} b_{tag} "
            f"{device.public_name} {parameters}"
        )
    alter_commands = [
        command
        for device in family.devices
        for command in instances[device.device_id]["raw_adapter"]["alter_commands"]
    ]
    lines.extend(
        [
            ".control",
            *[f"pre_osdi {toolchain.osdi_directory / item}" for item in kit.osdi_artifacts],
            "set numdgt=15",
            *alter_commands,
            "op",
            "print "
            + " ".join(f"i({source_names[device.device_id]})" for device in family.devices),
            "quit",
            ".endc",
            ".end",
        ]
    )
    token = f"{family.technology_id}_{family.family_id}_{sample_name}{suffix}"
    netlist = output / "netlists" / f"mos_{token}.cir"
    log = output / "logs" / f"mos_{token}.log"
    netlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ngspice(toolchain, netlist, log)
    return {
        "technology_id": family.technology_id,
        "family_id": family.family_id,
        "family_selector": family.selector,
        "variation_origin": "benchmark",
        "variation_mode": sample["variation_mode"],
        "corner_profile": sample["corner_profile"],
        "sample_name": sample_name,
        "sample_id": sample["sample_id"],
        "rng": sample["rng"],
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "idmag_a": {
            device.device_id: abs(_observable(log, f"i({source_names[device.device_id]})"))
            for device in family.devices
        },
        "instances": {
            device.device_id: {
                "id": instances[device.device_id]["id"],
                "polarity": device.polarity,
                "global_latent_names": instances[device.device_id]["global_latent_names"],
                "global_applied": instances[device.device_id]["global_applied"],
                "local_applied": instances[device.device_id]["local_applied"],
                "total_intents": instances[device.device_id]["total_intents"],
                "raw_adapter": instances[device.device_id]["raw_adapter"],
            }
            for device in family.devices
        },
    }


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
        f"APM v2 benchmark {sample_name} deterministic passive validation",
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
    netlist = output / "netlists" / f"passives_{sample_name}_{token}c.cir"
    log = output / "logs" / f"passives_{sample_name}_{token}c.log"
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
        f"APM v2 benchmark {sample_name} native resistor Johnson-noise validation",
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
    netlist = output / "netlists" / f"passive_noise_{sample_name}.cir"
    log = output / "logs" / f"passive_noise_{sample_name}.log"
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
        "temperature_c": temperature_c,
        "frequency_hz": frequency,
        "netlist": str(netlist.relative_to(output)),
        "log": str(log.relative_to(output)),
        "primitive_semantic": "native SPICE resistor thermal noise; APM adds no noise source",
        "expected_voltage_noise_v_per_sqrt_hz": expected,
        "measured_voltage_noise_v_per_sqrt_hz": measured,
        "relative_error": abs(measured / expected - 1.0),
    }


def _distribution_check(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    # Exercise the frozen RNG directly here. Resolving arbitrary Gaussian-tail
    # samples through compact-model adapters would conflate the distribution
    # check with each adapter's deliberately finite real-tool calibration range.
    global_z: list[float] = []
    local_z: list[float] = []
    for seed in range(256):
        generator = np.random.Generator(np.random.PCG64(seed))
        global_z.extend(float(value) for value in generator.standard_normal(64))
        local_z.extend(float(value) for value in generator.standard_normal(64))
    global_mean = statistics.mean(global_z)
    global_std = statistics.stdev(global_z)
    local_mean = statistics.mean(local_z)
    local_std = statistics.stdev(local_z)
    size_request = {
        "schema": "apm.benchmark-request.v2",
        "instances": {
            "mos": [
                {
                    "id": "small",
                    "selector": "apm045/vtg/nmos",
                    "geometry": {"w_m": 1.0e-6, "l_m": 1.0e-7},
                },
                {
                    "id": "large",
                    "selector": "apm045/vtg/nmos",
                    "geometry": {"w_m": 2.0e-6, "l_m": 2.0e-7},
                },
            ],
            "resistors": [],
            "capacitors": [],
        },
    }
    sized = resolve_monte_carlo(size_request, mode="local", seed=VALIDATION_SEED, root=root)
    by_id = {item["id"]: item for item in sized["mos_instances"]}
    coefficients = {
        item: abs(
            by_id[item]["local_sampled"]["vth_shift_v"]
            / by_id[item]["local_random_draws"]["vth_shift_z"]
        )
        for item in ("small", "large")
    }
    return {
        "seed_count": 256,
        "draw_count_per_population": len(global_z),
        "rng": "numpy.random.Generator(PCG64)",
        "global_z_mean": global_mean,
        "global_z_std": global_std,
        "local_z_mean": local_mean,
        "local_z_std": local_std,
        "local_vth_sigma_coefficient_by_instance": coefficients,
        "large_over_small_sigma_coefficient": coefficients["large"] / coefficients["small"],
        "overall_pass": abs(global_mean) < 0.05
        and 0.95 < global_std < 1.05
        and abs(local_mean) < 0.05
        and 0.95 < local_std < 1.05
        and math.isclose(coefficients["large"] / coefficients["small"], 0.5, abs_tol=1e-12),
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
    catalog = load_catalog(selected.root)
    configuration = load_benchmark_configuration(selected.root)
    families = tuple(
        family for technology in catalog.technologies for family in technology.families
    )
    request = _validation_request(catalog, configuration)
    request_path = output / "request.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    samples: dict[str, dict[str, Any]] = {
        mode: resolve_monte_carlo(request, mode=mode, seed=VALIDATION_SEED, root=selected.root)
        for mode in BENCHMARK_MODES
    }
    samples.update(
        {
            corner: resolve_corner(request, corner=corner, root=selected.root)
            for corner in BENCHMARK_CORNERS
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
        _mos_simulation(selected, output, sample_name, sample, family, configuration)
        for sample_name, sample in samples.items()
        for family in families
    ]
    replay = [
        _mos_simulation(
            selected,
            output,
            "all",
            samples["all"],
            family,
            configuration,
            suffix="_replay",
        )
        for family in families
    ]
    passive_simulations = [
        _passive_simulation(selected, output, mode, samples[mode], temperature)
        for mode in BENCHMARK_MODES
        for temperature in (27.0, 85.0)
    ]
    passive_noise = _passive_noise_simulation(selected, output, "all", samples["all"], 27.0)
    adapter_calibrations = [
        _adapter_calibration(selected, output, family, device.device_id, configuration)
        for family in families
        for device in family.devices
    ]
    for simulation in [*simulations, *replay, *passive_simulations, passive_noise]:
        simulation["resolved_sample"] = sample_records[simulation["sample_name"]]

    simulation_by_key = {
        (item["family_selector"], item["sample_name"]): item for item in simulations
    }
    nominal_alignment_errors: list[float] = []
    corner_direction_pass = True
    for family in families:
        adapter = configuration["adapters"]["family"][family.selector]
        nominal = simulation_by_key[(family.selector, "bench_tt")]
        for device in family.devices:
            expected = float(adapter["device"][device.device_id]["nominal_reference_id_a"])
            observed = nominal["idmag_a"][device.device_id]
            nominal_alignment_errors.append(abs(observed / expected - 1.0))
            tt = observed
            ff = simulation_by_key[(family.selector, "bench_ff")]["idmag_a"][device.device_id]
            ss = simulation_by_key[(family.selector, "bench_ss")]["idmag_a"][device.device_id]
            split_fast = "bench_fs" if device.polarity == "n" else "bench_sf"
            split_slow = "bench_sf" if device.polarity == "n" else "bench_fs"
            fast = simulation_by_key[(family.selector, split_fast)]["idmag_a"][device.device_id]
            slow = simulation_by_key[(family.selector, split_slow)]["idmag_a"][device.device_id]
            corner_direction_pass = corner_direction_pass and ff > tt > ss and fast > tt > slow

    replay_pass = all(
        item["idmag_a"] == simulation_by_key[(item["family_selector"], "all")]["idmag_a"]
        for item in replay
    )
    reproduced = resolve_monte_carlo(request, mode="all", seed=VALIDATION_SEED, root=selected.root)
    different_seed = 42
    different = resolve_monte_carlo(request, mode="all", seed=different_seed, root=selected.root)
    raw_ranges_pass = all(
        instance["raw_adapter"]["vth_within_calibrated_raw_range"]
        and instance["raw_adapter"]["drive_within_calibrated_raw_range"]
        for sample in samples.values()
        for instance in sample["mos_instances"]
    )
    shared_global_latents = True
    for sample in samples.values():
        for technology in catalog.technologies:
            for polarity in ("n", "p"):
                group = [
                    item
                    for item in sample["mos_instances"]
                    if item["technology_id"] == technology.technology_id
                    and item["polarity"] == polarity
                ]
                if group:
                    shared_global_latents = shared_global_latents and (
                        len({item["global_latent_names"]["vth_shift"] for item in group}) == 1
                        and len({item["global_latent_names"]["drive_shift"] for item in group}) == 1
                        and len({item["global_applied"]["vth_shift_v"] for item in group}) == 1
                        and len({item["global_applied"]["drive_shift_fraction"] for item in group})
                        == 1
                    )
    passive_error = max(
        max(item["resistor"]["relative_error"], item["capacitor"]["relative_error"])
        for item in passive_simulations
    )
    stochastic_finite = all(
        value > 0.0 and math.isfinite(value)
        for item in simulations
        if item["sample_name"] in BENCHMARK_MODES
        for value in item["idmag_a"].values()
    )
    adapter_vth_fit_error = max(
        item["vth_reference"]["max_abs_stored_fit_residual_v"] for item in adapter_calibrations
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
    distribution = _distribution_check(selected.root, request)
    adapter_method = configuration["adapters"]["method"]
    checks: dict[str, Any] = {
        "catalog_family_count": len(families),
        "catalog_device_count": sum(len(family.devices) for family in families),
        "adapter_family_count": len(configuration["adapters"]["family"]),
        "adapter_device_count": sum(
            len(item["device"]) for item in configuration["adapters"]["family"].values()
        ),
        "same_seed_identical_sample": reproduced == samples["all"],
        "different_seed_differs": different["sample_id"] != samples["all"]["sample_id"],
        "different_seed": different_seed,
        "same_seed_mode_draw_order_identical": samples["global"]["draw_order"]
        == samples["local"]["draw_order"]
        == samples["all"]["draw_order"],
        "shared_technology_polarity_global_latents": shared_global_latents,
        "deterministic_ngspice_replay": replay_pass,
        "stochastic_modes_real_tool_finite": stochastic_finite,
        "corner_current_directions": corner_direction_pass,
        "all_raw_adapter_values_inside_calibrated_range": raw_ranges_pass,
        "nominal_adapter_alignment_max_relative_error": max(nominal_alignment_errors),
        "passive_value_max_relative_error": passive_error,
        "passive_noise_relative_error": passive_noise["relative_error"],
        "adapter_vth_fit_max_abs_residual_v": adapter_vth_fit_error,
        "adapter_drive_fit_max_abs_residual_fraction": adapter_drive_fit_error,
        "adapter_nominal_vth_max_abs_error_v": adapter_nominal_vth_error,
        "adapter_nominal_drive_max_relative_error": adapter_nominal_drive_error,
        "distribution": distribution,
    }
    requirements = {
        "all_13_families_and_26_devices": checks["catalog_family_count"]
        == checks["adapter_family_count"]
        == 13
        and checks["catalog_device_count"] == checks["adapter_device_count"] == 26,
        "seed_reproducibility": checks["same_seed_identical_sample"],
        "different_seed_behavior": checks["different_seed_differs"],
        "mode_composition_draw_identity": checks["same_seed_mode_draw_order_identical"],
        "shared_global_observable_latents": checks["shared_technology_polarity_global_latents"],
        "deterministic_simulator_replay": checks["deterministic_ngspice_replay"],
        "global_local_all_execute": checks["stochastic_modes_real_tool_finite"],
        "benchmark_corner_semantics": checks["corner_current_directions"],
        "calibrated_adapter_range": checks["all_raw_adapter_values_inside_calibrated_range"],
        "nominal_public_adapter_alignment": checks["nominal_adapter_alignment_max_relative_error"]
        < 1e-9,
        "resolved_native_passive_values": checks["passive_value_max_relative_error"] < 1e-6,
        "native_resistor_johnson_noise": checks["passive_noise_relative_error"] < 1e-3,
        "observable_vth_adapter_calibration": adapter_vth_fit_error
        <= float(adapter_method["vth_fit_max_residual_acceptance_v"])
        and adapter_nominal_vth_error < 1e-9,
        "observable_drive_adapter_calibration": adapter_drive_fit_error
        <= float(adapter_method["drive_fit_max_residual_acceptance_fraction"])
        and adapter_nominal_drive_error < 1e-9,
        "normal_distribution_and_local_size_law": distribution["overall_pass"],
    }
    checks["requirements"] = requirements
    checks["overall_pass"] = all(requirements.values())
    version = run_checked([selected.ngspice, "--version"])
    report: dict[str, Any] = {
        "schema": "apm.benchmark-validation.v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "validated" if checks["overall_pass"] else "checks_failed",
        "variation_origin": "benchmark",
        "validation_seed": VALIDATION_SEED,
        "validated_technologies": [item.technology_id for item in catalog.technologies],
        "validated_families": [family.selector for family in families],
        "validated_devices": [device.selector for family in families for device in family.devices],
        "ngspice_version": (version.stdout + version.stderr).strip(),
        "request": {
            "path": str(request_path.relative_to(output)),
            "sha256": sha256_file(request_path),
        },
        "benchmark_configuration": configuration["identity"],
        "samples": sample_records,
        "mos_simulations": simulations,
        "replay_simulations": replay,
        "passive_simulations": passive_simulations,
        "passive_noise_simulation": passive_noise,
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
