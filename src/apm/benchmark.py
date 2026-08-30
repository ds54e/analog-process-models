# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Deterministic APM Benchmark Global/Local/All resolution."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10 reference environments
    import tomli as tomllib

from .catalog import CatalogError, load_catalog
from .paths import repository_root

BENCHMARK_MODES = ("global", "local", "all")
BENCHMARK_CORNERS = ("bench_tt", "bench_ff", "bench_ss", "bench_fs", "bench_sf")
REQUEST_SCHEMA = "apm.benchmark-request.v2"
RESOLVED_SCHEMA = "apm.resolved-variation.v2"
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_TOP_LEVEL_INSTANCE = re.compile(r"^[xX][A-Za-z0-9_]*$")


class BenchmarkError(ValueError):
    """A benchmark request or resolved sample violates the explicit contract."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise BenchmarkError(f"cannot load benchmark configuration {path}: {error}") from error


def load_benchmark_configuration(root: Path | None = None) -> dict[str, Any]:
    selected = (root or repository_root()).resolve()
    paths = {
        "variation": selected / "variation/benchmark_v2.toml",
        "passives": selected / "passives/benchmark_v2.toml",
        "adapters": selected / "variation/adapters_v2.toml",
    }
    configuration = {name: _load_toml(path) for name, path in paths.items()}
    expected = {
        "variation": "apm.benchmark-variation.v2",
        "passives": "apm.benchmark-passives.v2",
        "adapters": "apm.benchmark-adapters.v2",
    }
    for name, schema in expected.items():
        if configuration[name].get("schema") != schema:
            raise BenchmarkError(f"{paths[name]}: expected schema {schema}")
        if not configuration[name].get("status"):
            raise BenchmarkError(f"{paths[name]}: status is missing")
    configuration["identity"] = {
        name: {
            "path": str(path.relative_to(selected)),
            "sha256": _sha256_file(path),
            "schema": configuration[name]["schema"],
            "status": configuration[name]["status"],
        }
        for name, path in paths.items()
    }
    configuration["root"] = selected
    return configuration


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BenchmarkError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise BenchmarkError(f"{name} must be a finite number")
    return result


def _positive_number(value: Any, name: str) -> float:
    result = _finite_number(value, name)
    if result <= 0.0:
        raise BenchmarkError(f"{name} must be greater than zero")
    return result


def _bounded(value: float, lower: float | None, upper: float | None, name: str) -> None:
    if lower is not None and value < lower:
        raise BenchmarkError(f"{name} is below the manifest minimum {lower:g}")
    if upper is not None and value > upper:
        raise BenchmarkError(f"{name} exceeds the manifest maximum {upper:g}")


def _normalize_request(
    request: dict[str, Any], configuration: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    if request.get("schema") != REQUEST_SCHEMA:
        raise BenchmarkError(f"request schema must be {REQUEST_SCHEMA}")
    instances = request.get("instances")
    if not isinstance(instances, dict):
        raise BenchmarkError("request instances must be an object")
    adapters = configuration["adapters"].get("family")
    if not isinstance(adapters, dict):
        raise BenchmarkError("v2 adapters must define family tables")
    try:
        catalog = load_catalog(configuration["root"])
    except CatalogError as error:
        raise BenchmarkError(str(error)) from error
    normalized: dict[str, list[dict[str, Any]]] = {
        "mos": [],
        "resistors": [],
        "capacitors": [],
    }
    seen: set[str] = set()

    def normalize_id(raw: dict[str, Any], kind: str) -> str:
        instance_id = raw.get("id")
        if not isinstance(instance_id, str) or not _IDENTIFIER.fullmatch(instance_id):
            raise BenchmarkError(
                f"{kind} id must start with a letter and contain only letters, digits, or '_'"
            )
        if instance_id in seen:
            raise BenchmarkError(f"duplicate benchmark instance id: {instance_id}")
        seen.add(instance_id)
        return instance_id

    raw_mos = instances.get("mos", [])
    if not isinstance(raw_mos, list):
        raise BenchmarkError("instances.mos must be a list")
    for raw in raw_mos:
        if not isinstance(raw, dict):
            raise BenchmarkError("each MOS instance must be an object")
        instance_id = normalize_id(raw, "MOS")
        selector = raw.get("selector")
        if not isinstance(selector, str) or len(selector.strip("/").split("/")) != 3:
            raise BenchmarkError(
                f"MOS {instance_id} selector must be technology_id/family_id/device_id"
            )
        technology_id, family_id, device_id = selector.strip("/").split("/")
        family_selector = f"{technology_id}/{family_id}"
        try:
            family = catalog.family(technology_id, family_id)
            device = family.device(device_id)
        except CatalogError as error:
            raise BenchmarkError(str(error)) from error
        if family_selector not in adapters:
            raise BenchmarkError(f"no calibrated benchmark adapter for family: {family_selector}")
        family_adapter = adapters[family_selector]
        devices = family_adapter.get("device", {})
        if device_id not in devices:
            raise BenchmarkError(f"no calibrated benchmark adapter for device: {selector}")
        device_adapter = devices[device_id]
        if (
            family_adapter.get("technology_id") != technology_id
            or family_adapter.get("family_id") != family_id
            or family_adapter.get("family_manifest_sha256") != family.manifest_sha256
            or device_adapter.get("public_device") != device.public_name
            or device_adapter.get("polarity") != device.polarity
        ):
            raise BenchmarkError(f"benchmark adapter semantic binding mismatch for {selector}")
        geometry = raw.get("geometry")
        if not isinstance(geometry, dict):
            raise BenchmarkError(f"MOS {instance_id} geometry must be an object")
        l_m = _positive_number(geometry.get("l_m"), f"MOS {instance_id} l_m")
        _bounded(l_m, device.lmin_m, device.lmax_m, f"MOS {instance_id} l_m")
        if family.architecture == "planar_bulk":
            w_m = _positive_number(geometry.get("w_m"), f"MOS {instance_id} w_m")
            _bounded(w_m, device.wmin_m, device.wmax_m, f"MOS {instance_id} w_m")
            normalized_geometry: dict[str, Any] = {"w_m": w_m, "l_m": l_m}
            match_size = (w_m * l_m) / (
                float(device_adapter["reference_w_m"]) * float(device_adapter["reference_l_m"])
            )
        elif family.architecture == "finfet":
            nfin = geometry.get("nfin")
            if isinstance(nfin, bool) or not isinstance(nfin, int) or nfin <= 0:
                raise BenchmarkError(f"MOS {instance_id} nfin must be a positive integer")
            normalized_geometry = {"l_m": l_m, "nfin": nfin}
            match_size = (nfin * l_m) / (
                int(device_adapter["reference_nfin"]) * float(device_adapter["reference_l_m"])
            )
        else:
            raise BenchmarkError(f"unsupported adapter architecture for {family_selector}")
        ngspice_instance = raw.get("ngspice_instance", f"x{instance_id.lower()}")
        if not isinstance(ngspice_instance, str) or not _TOP_LEVEL_INSTANCE.fullmatch(
            ngspice_instance
        ):
            raise BenchmarkError(
                f"MOS {instance_id} ngspice_instance must be a top-level X-instance name"
            )
        normalized["mos"].append(
            {
                "id": instance_id,
                "selector": selector,
                "technology_id": technology_id,
                "family_id": family_id,
                "device_id": device_id,
                "family_selector": family_selector,
                "public_device": device.public_name,
                "polarity": device.polarity,
                "geometry": normalized_geometry,
                "match_size": match_size,
                "ngspice_instance": ngspice_instance.lower(),
            }
        )

    def normalize_passives(kind: str) -> None:
        raw_instances = instances.get(kind, [])
        if not isinstance(raw_instances, list):
            raise BenchmarkError(f"instances.{kind} must be a list")
        for raw in raw_instances:
            if not isinstance(raw, dict):
                raise BenchmarkError(f"each {kind[:-1]} instance must be an object")
            instance_id = normalize_id(raw, kind[:-1])
            normalized[kind].append(
                {
                    "id": instance_id,
                    "value": _positive_number(raw.get("value"), f"{kind[:-1]} value"),
                    "tc1_per_c": _finite_number(
                        raw.get("tc1_per_c", 0.0), f"{kind[:-1]} tc1_per_c"
                    ),
                    "match_size": _positive_number(
                        raw.get("match_size"), f"{kind[:-1]} match_size"
                    ),
                }
            )

    normalize_passives("resistors")
    normalize_passives("capacitors")
    for values in normalized.values():
        values.sort(key=lambda item: item["id"])
    return normalized


def _invert_observable_fit(target: float, linear: float, quadratic: float) -> float:
    if target == 0.0:
        return 0.0
    if abs(quadratic) < 1e-14:
        if linear == 0.0:
            raise BenchmarkError("calibrated observable mapping has zero sensitivity")
        return target / linear
    discriminant = linear * linear + 4.0 * quadratic * target
    if discriminant < 0.0:
        raise BenchmarkError("resolved observable intent is outside the invertible adapter range")
    root = math.sqrt(discriminant)
    candidates = (
        (-linear + root) / (2.0 * quadratic),
        (-linear - root) / (2.0 * quadratic),
    )
    finite = [candidate for candidate in candidates if math.isfinite(candidate)]
    if not finite:
        raise BenchmarkError("resolved observable adapter value is not finite")
    return min(finite, key=abs)


def _raw_adapter(
    configuration: dict[str, Any],
    family_selector: str,
    device_id: str,
    vth_shift_v: float,
    drive_shift_fraction: float,
    ngspice_instance: str,
) -> dict[str, Any]:
    adapter = configuration["adapters"]["family"][family_selector]
    device_adapter = adapter["device"][device_id]
    vth_raw = _invert_observable_fit(
        vth_shift_v,
        float(device_adapter["vth_fit_linear"]),
        float(device_adapter["vth_fit_quadratic"]),
    )
    drive_delta_raw = _invert_observable_fit(
        drive_shift_fraction,
        float(device_adapter["drive_fit_linear"]),
        float(device_adapter["drive_fit_quadratic"]),
    )
    drive_raw = float(adapter["drive_raw_nominal"]) + drive_delta_raw
    if drive_raw <= 0.0:
        raise BenchmarkError(
            f"resolved {family_selector}/{device_id} raw drive multiplier is not positive"
        )
    method = configuration["adapters"]["method"]
    vth_range = method["vth_raw_sweep"]
    drive_range = method["drive_raw_multiplier_sweep"]
    device_path = device_adapter["ngspice_device_path_template"].format(instance=ngspice_instance)
    vth_parameter = adapter["vth_raw_parameter"]
    drive_parameter = adapter["drive_raw_parameter"]
    return {
        "adapter_family_selector": family_selector,
        "adapter_device_id": device_id,
        "vth_parameter": vth_parameter,
        "vth_value": vth_raw,
        "drive_parameter": drive_parameter,
        "drive_value": drive_raw,
        "device_path": device_path,
        "vth_within_calibrated_raw_range": float(vth_range[0]) <= vth_raw <= float(vth_range[1]),
        "drive_within_calibrated_raw_range": float(drive_range[0])
        <= drive_raw
        <= float(drive_range[1]),
        "alter_commands": [
            f"alter {device_path}[{vth_parameter}] = {vth_raw:.17g}",
            f"alter {device_path}[{drive_parameter}] = {drive_raw:.17g}",
        ],
    }


def _sample_id(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
    payload["sample_id"] = _sample_id(payload)
    return payload


def _latent_name(technology_id: str, polarity: str, intent: str) -> str:
    return f"global.mos.{technology_id}.{polarity}.{intent}"


def _resolve(
    request: dict[str, Any],
    configuration: dict[str, Any],
    normalized: dict[str, list[dict[str, Any]]],
    *,
    variation_mode: str,
    corner_profile: str | None,
    seed: int | None,
    global_z: dict[str, float],
    local_z: dict[str, dict[str, float]],
    draw_order: list[dict[str, Any]],
) -> dict[str, Any]:
    variation = configuration["variation"]
    passives = configuration["passives"]
    global_active = variation_mode in ("global", "all")
    local_active = variation_mode in ("local", "all")
    global_vth_sigma = float(variation["mos"]["global"]["vth_shift_sigma"])
    global_drive_sigma = float(variation["mos"]["global"]["drive_shift_sigma"])
    local_vth_sigma = float(variation["mos"]["local"]["vth_shift_sigma_ref"])
    local_drive_sigma = float(variation["mos"]["local"]["drive_shift_sigma_ref"])

    technology_polarities = sorted(
        {(item["technology_id"], item["polarity"]) for item in normalized["mos"]}
    )
    global_stress: dict[str, Any] = {"mos": {}, "passives": {}}
    latent_records: list[dict[str, Any]] = []
    for technology_id, polarity in technology_polarities:
        vth_name = _latent_name(technology_id, polarity, "vth_shift")
        drive_name = _latent_name(technology_id, polarity, "drive_shift")
        vth_z = global_z[vth_name]
        drive_z = global_z[drive_name]
        sampled_vth = global_vth_sigma * vth_z
        sampled_drive = global_drive_sigma * drive_z
        scope = f"{technology_id}/{polarity}"
        global_stress["mos"][scope] = {
            "technology_id": technology_id,
            "polarity": polarity,
            "vth_latent_name": vth_name,
            "drive_latent_name": drive_name,
            "vth_shift_z": vth_z,
            "drive_shift_z": drive_z,
            "sampled_vth_shift_v": sampled_vth,
            "sampled_drive_shift_fraction": sampled_drive,
            "applied_vth_shift_v": sampled_vth if global_active else 0.0,
            "applied_drive_shift_fraction": sampled_drive if global_active else 0.0,
            "sharing_semantic": "shared across every requested family for this technology/polarity",
        }
        latent_records.extend(
            [
                {
                    "name": vth_name,
                    "scope": scope,
                    "intent": "vth_shift",
                    "z": vth_z,
                    "sampled_value": sampled_vth,
                    "applied_value": sampled_vth if global_active else 0.0,
                },
                {
                    "name": drive_name,
                    "scope": scope,
                    "intent": "drive_shift",
                    "z": drive_z,
                    "sampled_value": sampled_drive,
                    "applied_value": sampled_drive if global_active else 0.0,
                },
            ]
        )
    for kind in ("resistor", "capacitor"):
        name = f"global.passives.{kind}.scale"
        z_value = global_z[name]
        sampled = float(passives[kind]["global_sigma"]) * z_value
        global_stress["passives"][kind] = {
            "latent_name": name,
            "scale_z": z_value,
            "sampled_scale_fraction": sampled,
            "applied_scale_fraction": sampled if global_active else 0.0,
        }
        latent_records.append(
            {
                "name": name,
                "scope": kind,
                "intent": "passive_scale",
                "z": z_value,
                "sampled_value": sampled,
                "applied_value": sampled if global_active else 0.0,
            }
        )
    latent_records.sort(key=lambda item: item["name"])

    mos_results: list[dict[str, Any]] = []
    alter_commands: list[str] = []
    for instance in normalized["mos"]:
        instance_id = instance["id"]
        match_size = instance["match_size"]
        vth_z = local_z[instance_id]["vth"]
        drive_z = local_z[instance_id]["drive"]
        sampled_local_vth = local_vth_sigma * vth_z / math.sqrt(match_size)
        sampled_local_drive = local_drive_sigma * drive_z / math.sqrt(match_size)
        local_vth = sampled_local_vth if local_active else 0.0
        local_drive = sampled_local_drive if local_active else 0.0
        global_scope = f"{instance['technology_id']}/{instance['polarity']}"
        shared = global_stress["mos"][global_scope]
        total_vth = shared["applied_vth_shift_v"] + local_vth
        global_drive_factor = 1.0 + shared["applied_drive_shift_fraction"]
        local_drive_factor = 1.0 + local_drive
        total_drive_factor = global_drive_factor * local_drive_factor
        if min(global_drive_factor, local_drive_factor, total_drive_factor) <= 0.0:
            raise BenchmarkError(
                f"resolved MOS drive factor is not positive for instance {instance_id}"
            )
        total_drive_shift = total_drive_factor - 1.0
        raw_adapter = _raw_adapter(
            configuration,
            instance["family_selector"],
            instance["device_id"],
            total_vth,
            total_drive_shift,
            instance["ngspice_instance"],
        )
        if not (
            raw_adapter["vth_within_calibrated_raw_range"]
            and raw_adapter["drive_within_calibrated_raw_range"]
        ):
            raise BenchmarkError(
                f"resolved intents exceed the calibrated adapter range for {instance['selector']}"
            )
        alter_commands.extend(raw_adapter["alter_commands"])
        mos_results.append(
            {
                **instance,
                "benchmark_spec_schema": variation["schema"],
                "global_latent_names": {
                    "vth_shift": shared["vth_latent_name"],
                    "drive_shift": shared["drive_latent_name"],
                },
                "global_applied": {
                    "vth_shift_v": shared["applied_vth_shift_v"],
                    "drive_shift_fraction": shared["applied_drive_shift_fraction"],
                },
                "local_latent_names": {
                    "vth_shift": f"local.mos.{instance_id}.vth_shift",
                    "drive_shift": f"local.mos.{instance_id}.drive_shift",
                },
                "local_random_draws": {"vth_shift_z": vth_z, "drive_shift_z": drive_z},
                "local_sampled": {
                    "vth_shift_v": sampled_local_vth,
                    "drive_shift_fraction": sampled_local_drive,
                },
                "local_applied": {
                    "vth_shift_v": local_vth,
                    "drive_shift_fraction": local_drive,
                },
                "total_intents": {
                    "vth_shift_v": total_vth,
                    "drive_shift_fraction": total_drive_shift,
                    "drive_factor": total_drive_factor,
                },
                "raw_adapter": raw_adapter,
            }
        )

    passive_results: list[dict[str, Any]] = []
    for plural, singular in (("resistors", "resistor"), ("capacitors", "capacitor")):
        shared = global_stress["passives"][singular]
        sigma_ref = float(passives[singular]["local_sigma_ref"])
        for instance in normalized[plural]:
            z_value = local_z[instance["id"]]["scale"]
            sampled_local = sigma_ref * z_value / math.sqrt(instance["match_size"])
            local_scale = sampled_local if local_active else 0.0
            global_factor = 1.0 + shared["applied_scale_fraction"]
            local_factor = 1.0 + local_scale
            resolved_factor = global_factor * local_factor
            resolved_value = instance["value"] * resolved_factor
            if min(global_factor, local_factor, resolved_value) <= 0.0:
                raise BenchmarkError(
                    f"resolved passive scale/value is not positive for instance {instance['id']}"
                )
            passive_results.append(
                {
                    **instance,
                    "kind": singular,
                    "public_name": passives[singular]["public_name"],
                    "global_latent_name": shared["latent_name"],
                    "global_applied_scale_fraction": shared["applied_scale_fraction"],
                    "local_latent_name": f"local.{singular}.{instance['id']}.scale",
                    "local_random_draw": {"scale_z": z_value},
                    "local_sampled_scale_fraction": sampled_local,
                    "local_applied_scale_fraction": local_scale,
                    "resolved_scale_factor": resolved_factor,
                    "resolved_value_at_27c": resolved_value,
                    "temperature_law": "value(T)=resolved_value_at_27c*(1+tc1_per_c*(T-27))",
                }
            )
    passive_results.sort(key=lambda item: item["id"])

    rng_identity = (
        None
        if seed is None
        else {
            "algorithm": "NumPy Generator(PCG64)",
            "bit_generator": "PCG64",
            "seed": seed,
            "numpy_version": np.__version__,
            "draw_policy": "all Global and Local variables are drawn in canonical order regardless of active mode",
        }
    )
    payload: dict[str, Any] = {
        "schema": RESOLVED_SCHEMA,
        "variation_origin": "benchmark",
        "variation_mode": variation_mode,
        "corner_profile": corner_profile,
        "sampling_kind": "deterministic_corner" if corner_profile else "monte_carlo",
        "benchmark_configuration": configuration["identity"],
        "request_schema": request["schema"],
        "rng": rng_identity,
        "distribution": variation["distribution"],
        "composition": variation["mos"]["composition"],
        "correlation": {
            "mos": variation["mos"]["correlation"],
            "passives": passives["variation"],
        },
        "draw_order": draw_order,
        "global_latents": latent_records,
        "global_stress": global_stress,
        "mos_instances": mos_results,
        "passive_instances": passive_results,
        "ngspice_alter_commands": alter_commands,
    }
    return _finalize(payload)


def resolve_monte_carlo(
    request: dict[str, Any],
    *,
    mode: str,
    seed: int,
    root: Path | None = None,
) -> dict[str, Any]:
    if mode not in BENCHMARK_MODES:
        raise BenchmarkError(f"mode must be one of: {', '.join(BENCHMARK_MODES)}")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise BenchmarkError("seed must be a non-negative integer")
    configuration = load_benchmark_configuration(root)
    normalized = _normalize_request(request, configuration)
    rng = np.random.Generator(np.random.PCG64(seed))
    draw_order: list[dict[str, Any]] = []

    def draw(identity: str) -> float:
        value = float(rng.standard_normal())
        draw_order.append({"index": len(draw_order), "identity": identity, "z": value})
        return value

    technology_polarities = sorted(
        {(item["technology_id"], item["polarity"]) for item in normalized["mos"]}
    )
    global_z: dict[str, float] = {}
    for technology_id, polarity in technology_polarities:
        for intent in ("vth_shift", "drive_shift"):
            name = _latent_name(technology_id, polarity, intent)
            global_z[name] = draw(name)
    for kind in ("resistor", "capacitor"):
        name = f"global.passives.{kind}.scale"
        global_z[name] = draw(name)
    local_z: dict[str, dict[str, float]] = {}
    for instance in normalized["mos"]:
        local_z[instance["id"]] = {
            "vth": draw(f"local.mos.{instance['id']}.vth_shift"),
            "drive": draw(f"local.mos.{instance['id']}.drive_shift"),
        }
    for kind in ("resistors", "capacitors"):
        for instance in normalized[kind]:
            local_z[instance["id"]] = {"scale": draw(f"local.{kind[:-1]}.{instance['id']}.scale")}
    return _resolve(
        request,
        configuration,
        normalized,
        variation_mode=mode,
        corner_profile=None,
        seed=seed,
        global_z=global_z,
        local_z=local_z,
        draw_order=draw_order,
    )


def resolve_corner(
    request: dict[str, Any], *, corner: str, root: Path | None = None
) -> dict[str, Any]:
    if corner not in BENCHMARK_CORNERS:
        raise BenchmarkError(f"corner must be one of: {', '.join(BENCHMARK_CORNERS)}")
    configuration = load_benchmark_configuration(root)
    normalized = _normalize_request(request, configuration)
    vector = configuration["variation"]["corner"][corner]
    technology_polarities = sorted(
        {(item["technology_id"], item["polarity"]) for item in normalized["mos"]}
    )
    global_z: dict[str, float] = {}
    for technology_id, polarity in technology_polarities:
        global_z[_latent_name(technology_id, polarity, "vth_shift")] = float(
            vector[f"vth_{polarity}_sigma"]
        )
        global_z[_latent_name(technology_id, polarity, "drive_shift")] = float(
            vector[f"drive_{polarity}_sigma"]
        )
    global_z["global.passives.resistor.scale"] = float(vector["resistor_scale_sigma"])
    global_z["global.passives.capacitor.scale"] = float(vector["capacitor_scale_sigma"])
    local_z: dict[str, dict[str, float]] = {
        instance["id"]: {"vth": 0.0, "drive": 0.0} for instance in normalized["mos"]
    }
    for kind in ("resistors", "capacitors"):
        for instance in normalized[kind]:
            local_z[instance["id"]] = {"scale": 0.0}
    return _resolve(
        request,
        configuration,
        normalized,
        variation_mode="global",
        corner_profile=corner,
        seed=None,
        global_z=global_z,
        local_z=local_z,
        draw_order=[],
    )


def resolved_passive_value_at_temperature(instance: dict[str, Any], temperature_c: float) -> float:
    temperature = _finite_number(temperature_c, "temperature_c")
    value = float(instance["resolved_value_at_27c"]) * (
        1.0 + float(instance["tc1_per_c"]) * (temperature - 27.0)
    )
    if value <= 0.0 or not math.isfinite(value):
        raise BenchmarkError(f"resolved passive value is invalid at {temperature:g} degC")
    return value


def write_resolved_sample(sample: dict[str, Any], path: Path) -> Path:
    target = path.expanduser().resolve()
    expected_id = sample.get("sample_id")
    canonical = dict(sample)
    canonical.pop("sample_id", None)
    if expected_id != _sample_id(canonical):
        raise BenchmarkError("resolved sample_id does not match its canonical payload")
    rendered = json.dumps(sample, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") == rendered:
            return target
        raise BenchmarkError(f"refusing to overwrite a different resolved sample: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    return target


def load_resolved_sample(path: Path) -> dict[str, Any]:
    sample = json.loads(path.read_text(encoding="utf-8"))
    if sample.get("schema") != RESOLVED_SCHEMA:
        raise BenchmarkError(f"resolved sample schema must be {RESOLVED_SCHEMA}")
    expected = sample.get("sample_id")
    canonical = dict(sample)
    canonical.pop("sample_id", None)
    if expected != _sample_id(canonical):
        raise BenchmarkError(f"resolved sample hash mismatch: {path}")
    return sample
