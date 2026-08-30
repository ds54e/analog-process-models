# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Manifest-driven V3-N2 stationary-noise catalog orchestration.

The module deliberately wraps the frozen per-device V3-N1 engine.  It owns
catalog planning, semantic request identity, strict resume validation, and
comparison/index generation; it does not introduce another simulator backend
or reinterpret compact-model-specific source names.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import re
import shutil
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .catalog import DeviceSpec, FamilySpec, TechnologySpec, load_catalog
from .characterize import load_family
from .model_build import build_models, sha256_file
from .noise import (
    ACQUISITION_POLICY_ID,
    ACQUISITION_POLICY_VERSION,
    ADAPTIVE_FREQUENCY_STOPS_HZ,
    DEFAULT_FREQUENCY_START_HZ,
    DEFAULT_FREQUENCY_STOP_HZ,
    DEFAULT_GM_OVER_ID_RELATIVE_TOLERANCE,
    DEFAULT_POINTS_PER_DECADE,
    NOISE_SCHEMA,
    characterize_noise_selector,
)
from .noise_fit import FIT_METHOD_IDENTITY
from .noise_method_validate import validate_noise_method
from .paths import repository_root, state_directory
from .toolchain import Toolchain, resolve_toolchain, run_checked

CATALOG_PLAN_SCHEMA = "apm.noise-catalog-plan.v1"
CATALOG_REQUEST_SCHEMA = "apm.noise-catalog-request.v1"
CATALOG_RESULT_SCHEMA = "apm.noise-catalog-result.v1"
CATALOG_REPORT_SCHEMA = "apm.noise-catalog-validation.v1"
COMPARISON_SCHEMA = "apm.noise-comparison.v1"
CATALOG_METHOD_ID = "apm.noise-catalog.manifest-deduplicated-resumable"
CATALOG_METHOD_VERSION = "1.0.0"
REQUEST_HASH_ALGORITHM = "sha256-canonical-json"
RESULT_HASH_ALGORITHM = "sha256-canonical-artifact-inventory"

TEMPERATURES_C = (-40, 27, 85, 125)
INVERSION_TARGETS_PER_V = (5.0, 10.0, 15.0, 20.0, 25.0)
REFERENCE_FREQUENCIES_HZ = (1.0, 1.0e3, 1.0e6, 1.0e7)
INTEGRATION_BAND_HZ = (1.0, 1.0e7)
EXPECTED_TECHNOLOGY_COUNT = 5
EXPECTED_FAMILY_COUNT = 13
EXPECTED_DEVICE_COUNT = 26
TERMINAL_STATUSES = ("validated", "target_not_reachable", "simulation_failed")
REUSABLE_STATUSES = ("validated", "target_not_reachable")

DATASET_TEMPERATURE = "canonical_temperature_matrix"
DATASET_INVERSION = "inversion_sweep"
DATASET_LENGTH = "length_scaling"
DATASET_NFIN = "nfin_scaling"
COMPARISON_THRESHOLD_EQUAL_INVERSION = "threshold_equal_inversion"
COMPARISON_THRESHOLD_EQUAL_BIAS = "threshold_equal_bias"
COMPARISON_CROSS_PROCESS = "cross_process_anchor"


class NoiseCatalogError(RuntimeError):
    """The V3-N2 catalog plan or execution failed closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _hash_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise NoiseCatalogError(f"cannot read JSON artifact {path}: {error}") from error
    if not isinstance(value, dict):
        raise NoiseCatalogError(f"{path}: expected a JSON object")
    return value


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    if not fields:
        fields = ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as error:
        raise NoiseCatalogError(f"cannot read CSV artifact {path}: {error}") from error


def _relative_path(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _file_identity(root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    unique = sorted({path.resolve() for path in paths}, key=lambda item: str(item))
    result: list[dict[str, Any]] = []
    for path in unique:
        if not path.is_file():
            raise NoiseCatalogError(f"semantic input is missing: {path}")
        result.append(
            {
                "path": _relative_path(root, path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return result


def _model_source_closure(root: Path, initial: Iterable[Path]) -> tuple[Path, ...]:
    pending = list(initial)
    discovered: set[Path] = set()
    directive = re.compile(
        r"^\s*\.(?:include|inc|lib)\s+[\"']?([^\"'\s]+)", re.IGNORECASE
    )
    while pending:
        path = pending.pop().resolve()
        if path in discovered or not path.is_file():
            continue
        try:
            path.relative_to(root.resolve())
        except ValueError:
            continue
        discovered.add(path)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = directive.match(line)
            if not match:
                continue
            referenced = Path(match.group(1))
            candidate = referenced if referenced.is_absolute() else path.parent / referenced
            if candidate.is_file():
                pending.append(candidate)
    return tuple(sorted(discovered))


def _code_identity(root: Path) -> dict[str, Any]:
    paths = sorted((root / "src" / "apm").glob("*.py"))
    paths.append(root / "pyproject.toml")
    files = _file_identity(root, paths)
    return {"files": files, "aggregate_sha256": _hash_value(files)}


def _tool_identity(toolchain: Toolchain) -> dict[str, Any]:
    ngspice_version = run_checked([toolchain.ngspice, "--version"]).stdout.strip()
    openvaf_version = run_checked(
        [toolchain.openvaf, "--version"], environment=toolchain.environment()
    ).stdout.strip()
    return {
        "ngspice": {
            "path": str(toolchain.ngspice),
            "sha256": sha256_file(toolchain.ngspice),
            "version_output": ngspice_version,
            "required_major": 47,
        },
        "openvaf": {
            "path": str(toolchain.openvaf),
            "sha256": sha256_file(toolchain.openvaf),
            "version_output": openvaf_version,
        },
        "required_noise_solver": "Sparse",
        "klu_permitted_for_required_noise": False,
    }


def _environment_identity() -> dict[str, Any]:
    os_release: dict[str, str] = {}
    path = Path("/etc/os-release")
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                os_release[key] = value.strip().strip('"')
    return {
        "platform": "WSL2 + RHEL-compatible EL9 Linux + x86_64",
        "os_release": os_release,
        "kernel": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
    }


def _geometry(device: DeviceSpec, *, l_m: float, nfin: int | None = None) -> dict[str, Any]:
    if device.geometry_kind == "planar":
        if nfin is not None or device.default_w_m is None:
            raise NoiseCatalogError(f"{device.selector}: invalid planar geometry request")
        return {
            "geometry_kind": "planar",
            "l_m": float(l_m),
            "w_m": float(device.default_w_m),
            "l_over_lmin": float(l_m) / device.lmin_m,
        }
    if device.geometry_kind == "finfet":
        resolved_nfin = 1 if nfin is None else nfin
        if resolved_nfin not in device.characterization_nfin:
            raise NoiseCatalogError(
                f"{device.selector}: NFIN={resolved_nfin} is outside the manifest grid"
            )
        return {
            "geometry_kind": "finfet",
            "l_m": float(l_m),
            "nfin": int(resolved_nfin),
            "l_over_lmin": float(l_m) / device.lmin_m,
        }
    raise NoiseCatalogError(f"{device.selector}: unsupported geometry kind")


def _binding_identity(
    root: Path,
    technology: TechnologySpec,
    family: FamilySpec,
    toolchain: Toolchain,
) -> dict[str, Any]:
    binding = family.backend("ngspice")
    kit = load_family(family.selector, root)
    paths: list[Path] = [
        technology.manifest_path,
        family.manifest_path,
        family.provenance_path,
        binding.manifest_path,
        *_model_source_closure(
            root, (binding.wrapper_path, *binding.model_source_files())
        ),
    ]
    if family.variant_generation_path is not None:
        paths.append(family.variant_generation_path)
    osdi = []
    for name in sorted(kit.osdi_artifacts):
        artifact = toolchain.osdi_directory / name
        if not artifact.is_file():
            raise NoiseCatalogError(f"{family.selector}: missing OSDI artifact {artifact}")
        osdi.append(
            {"name": name, "size_bytes": artifact.stat().st_size, "sha256": sha256_file(artifact)}
        )
    files = _file_identity(root, paths)
    identity = {
        "technology_id": technology.technology_id,
        "family_id": family.family_id,
        "operating_profile_id": family.default_operating_profile,
        "reference_vdd_v": family.operating_profile().reference_vdd_v,
        "compact_model": family.compact_model,
        "model_origin": family.origin,
        "semantic_files": files,
        "osdi_artifacts": osdi,
    }
    identity["aggregate_sha256"] = _hash_value(identity)
    return identity


def _membership(dataset: str, coordinate: dict[str, Any]) -> dict[str, Any]:
    value = {"dataset": dataset, "coordinate": coordinate}
    value["logical_request_id"] = f"logical-{_hash_value(value)[:24]}"
    return value


def _request_payload(
    *,
    device: DeviceSpec,
    profile_id: str,
    reference_vdd_v: float,
    temperature_c: int,
    geometry: dict[str, Any],
    bias: dict[str, Any],
    binding: dict[str, Any],
    code: dict[str, Any],
    tools: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": CATALOG_REQUEST_SCHEMA,
        "catalog_method": {"id": CATALOG_METHOD_ID, "version": CATALOG_METHOD_VERSION},
        "selector": device.selector,
        "public_device": device.public_name,
        "polarity": device.polarity,
        "operating_profile": {
            "id": profile_id,
            "reference_vdd_v": reference_vdd_v,
        },
        "temperature_c": temperature_c,
        "geometry": geometry,
        "output_bias": {
            "mode": "half_reference_vdd",
            "fraction_reference_vdd": 0.5,
            "vout_v": 0.5 * reference_vdd_v,
        },
        "bias": bias,
        "acquisition": {
            "policy_id": ACQUISITION_POLICY_ID,
            "policy_version": ACQUISITION_POLICY_VERSION,
            "start_hz": DEFAULT_FREQUENCY_START_HZ,
            "base_stop_hz": DEFAULT_FREQUENCY_STOP_HZ,
            "points_per_decade": DEFAULT_POINTS_PER_DECADE,
            "extension_stops_hz": list(ADAPTIVE_FREQUENCY_STOPS_HZ),
        },
        "fit_method_identity": FIT_METHOD_IDENTITY,
        "result_schema": NOISE_SCHEMA,
        "semantic_binding": binding,
        "implementation_code_sha256": code["aggregate_sha256"],
        "reference_tool_hashes": {
            "ngspice_sha256": tools["ngspice"]["sha256"],
            "openvaf_sha256": tools["openvaf"]["sha256"],
        },
    }


def _add_request(
    jobs: dict[str, dict[str, Any]],
    payload: dict[str, Any],
    membership: dict[str, Any],
) -> None:
    request_hash = _hash_value(payload)
    request_id = f"n2-{request_hash[:32]}"
    if request_id not in jobs:
        jobs[request_id] = {
            "request_id": request_id,
            "request_hash": request_hash,
            "request": payload,
            "memberships": [],
        }
    elif jobs[request_id]["request_hash"] != request_hash:
        raise NoiseCatalogError(f"request ID collision for {request_id}")
    logical_id = membership["logical_request_id"]
    if all(item["logical_request_id"] != logical_id for item in jobs[request_id]["memberships"]):
        jobs[request_id]["memberships"].append(membership)


def build_noise_catalog_plan(
    root: Path | None = None,
    *,
    toolchain: Toolchain | None = None,
    code_identity: dict[str, Any] | None = None,
    tool_identity: dict[str, Any] | None = None,
    binding_identities: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the complete deterministic N2 logical/physical request plan."""

    resolved_root = (root or repository_root()).resolve()
    selected_toolchain = toolchain
    if selected_toolchain is None and (
        tool_identity is None or binding_identities is None
    ):
        selected_toolchain = resolve_toolchain(resolved_root)
    catalog = load_catalog(resolved_root)
    code = code_identity or _code_identity(resolved_root)
    if tool_identity is not None:
        tools = tool_identity
    elif selected_toolchain is not None:
        tools = _tool_identity(selected_toolchain)
    else:  # pragma: no cover - guarded above
        raise NoiseCatalogError("tool identity requires a resolved toolchain")
    jobs: dict[str, dict[str, Any]] = {}
    bindings: dict[str, dict[str, Any]] = {}

    technologies = sorted(catalog.technologies, key=lambda item: item.technology_id)
    families = [
        family
        for technology in technologies
        for family in sorted(technology.families, key=lambda item: item.family_id)
    ]
    devices = [
        device
        for family in families
        for device in sorted(family.devices, key=lambda item: item.device_id)
    ]
    if (len(technologies), len(families), len(devices)) != (
        EXPECTED_TECHNOLOGY_COUNT,
        EXPECTED_FAMILY_COUNT,
        EXPECTED_DEVICE_COUNT,
    ):
        raise NoiseCatalogError(
            "catalog coverage mismatch: expected 5/13/26 technologies/families/devices, "
            f"found {len(technologies)}/{len(families)}/{len(devices)}"
        )

    def context(device: DeviceSpec) -> tuple[FamilySpec, dict[str, Any], float, str]:
        family = catalog.family(device.technology_id, device.family_id)
        technology = catalog.technology(device.technology_id)
        key = family.selector
        if key not in bindings:
            if binding_identities is not None:
                if key not in binding_identities:
                    raise NoiseCatalogError(f"test binding identity is missing {key}")
                bindings[key] = binding_identities[key]
            elif selected_toolchain is not None:
                bindings[key] = _binding_identity(
                    resolved_root, technology, family, selected_toolchain
                )
            else:  # pragma: no cover - guarded above
                raise NoiseCatalogError("binding identity requires a resolved toolchain")
        profile = family.operating_profile()
        return family, bindings[key], profile.reference_vdd_v, profile.profile_id

    def add_gm(
        device: DeviceSpec,
        *,
        temperature_c: int,
        geometry: dict[str, Any],
        target: float,
        membership: dict[str, Any],
    ) -> None:
        _family, binding, vdd, profile_id = context(device)
        payload = _request_payload(
            device=device,
            profile_id=profile_id,
            reference_vdd_v=vdd,
            temperature_c=temperature_c,
            geometry=geometry,
            bias={
                "mode": "gm_over_id_target",
                "target_per_v": target,
                "relative_tolerance": DEFAULT_GM_OVER_ID_RELATIVE_TOLERANCE,
                "canonical_derivative": "terminal_finite_difference",
                "native_op_oracle_required_for_acceptance": False,
            },
            binding=binding,
            code=code,
            tools=tools,
        )
        _add_request(jobs, payload, membership)

    def add_equal_bias(device: DeviceSpec, membership: dict[str, Any]) -> None:
        _family, binding, vdd, profile_id = context(device)
        geometry = _geometry(device, l_m=2.0 * device.lmin_m)
        payload = _request_payload(
            device=device,
            profile_id=profile_id,
            reference_vdd_v=vdd,
            temperature_c=27,
            geometry=geometry,
            bias={
                "mode": "explicit_vctrl",
                "vctrl_v": 0.5 * vdd,
                "canonical_derivative": "terminal_finite_difference",
                "native_op_oracle_required_for_acceptance": False,
            },
            binding=binding,
            code=code,
            tools=tools,
        )
        _add_request(jobs, payload, membership)

    for device in devices:
        canonical_geometry = _geometry(device, l_m=2.0 * device.lmin_m)
        for temperature_c in TEMPERATURES_C:
            add_gm(
                device,
                temperature_c=temperature_c,
                geometry=canonical_geometry,
                target=15.0,
                membership=_membership(
                    DATASET_TEMPERATURE,
                    {"selector": device.selector, "temperature_c": temperature_c},
                ),
            )
        for target in INVERSION_TARGETS_PER_V:
            add_gm(
                device,
                temperature_c=27,
                geometry=canonical_geometry,
                target=target,
                membership=_membership(
                    DATASET_INVERSION,
                    {"selector": device.selector, "gm_over_id_target_per_v": target},
                ),
            )
        for length_m in sorted(device.characterization_lengths_m):
            add_gm(
                device,
                temperature_c=27,
                geometry=_geometry(device, l_m=length_m),
                target=15.0,
                membership=_membership(
                    DATASET_LENGTH,
                    {"selector": device.selector, "l_m": length_m},
                ),
            )
        if device.technology_id == "apm016f":
            for nfin in sorted(device.characterization_nfin):
                add_gm(
                    device,
                    temperature_c=27,
                    geometry=_geometry(device, l_m=2.0 * device.lmin_m, nfin=nfin),
                    target=15.0,
                    membership=_membership(
                        DATASET_NFIN,
                        {"selector": device.selector, "nfin": nfin},
                    ),
                )

    comparison_definitions: list[dict[str, Any]] = []
    for technology in technologies:
        for comparison_set in sorted(
            technology.comparison_sets, key=lambda item: item.set_id
        ):
            if comparison_set.kind != "threshold_family":
                continue
            definition = {
                "technology_id": technology.technology_id,
                "comparison_set_id": comparison_set.set_id,
                "members": list(comparison_set.members),
                "views": [
                    COMPARISON_THRESHOLD_EQUAL_INVERSION,
                    COMPARISON_THRESHOLD_EQUAL_BIAS,
                ],
            }
            comparison_definitions.append(definition)
            for family_id in comparison_set.members:
                family = technology.family(family_id)
                for device in sorted(family.devices, key=lambda item: item.device_id):
                    coordinate = {
                        "technology_id": technology.technology_id,
                        "comparison_set_id": comparison_set.set_id,
                        "family_id": family_id,
                        "polarity": device.polarity,
                    }
                    add_gm(
                        device,
                        temperature_c=27,
                        geometry=_geometry(device, l_m=2.0 * device.lmin_m),
                        target=15.0,
                        membership=_membership(
                            COMPARISON_THRESHOLD_EQUAL_INVERSION, coordinate
                        ),
                    )
                    add_equal_bias(
                        device,
                        _membership(COMPARISON_THRESHOLD_EQUAL_BIAS, coordinate),
                    )

    anchor_definition = {
        "comparison_set_id": "cross_process_anchors",
        "view": COMPARISON_CROSS_PROCESS,
        "families": [],
    }
    for technology in technologies:
        family = technology.family(technology.cross_process_anchor)
        anchor_definition["families"].append(family.selector)
        for device in sorted(family.devices, key=lambda item: item.device_id):
            add_gm(
                device,
                temperature_c=27,
                geometry=_geometry(device, l_m=2.0 * device.lmin_m),
                target=15.0,
                membership=_membership(
                    COMPARISON_CROSS_PROCESS,
                    {
                        "technology_id": technology.technology_id,
                        "family_id": family.family_id,
                        "polarity": device.polarity,
                    },
                ),
            )
    comparison_definitions.append(anchor_definition)

    requests = sorted(jobs.values(), key=lambda item: item["request_id"])
    for item in requests:
        item["memberships"] = sorted(
            item["memberships"], key=lambda value: value["logical_request_id"]
        )
    logical_counts = Counter(
        membership["dataset"]
        for request in requests
        for membership in request["memberships"]
    )
    dataset_names = (DATASET_TEMPERATURE, DATASET_INVERSION, DATASET_LENGTH, DATASET_NFIN)
    comparison_names = (
        COMPARISON_THRESHOLD_EQUAL_INVERSION,
        COMPARISON_THRESHOLD_EQUAL_BIAS,
        COMPARISON_CROSS_PROCESS,
    )
    plan_core = {
        "schema": CATALOG_PLAN_SCHEMA,
        "method_id": CATALOG_METHOD_ID,
        "method_version": CATALOG_METHOD_VERSION,
        "catalog": {
            "technology_count": len(technologies),
            "family_count": len(families),
            "public_device_count": len(devices),
            "selectors": [device.selector for device in devices],
            "snapshot_sha256": _hash_value(catalog.snapshot()),
        },
        "frozen_methods": {
            "noise_result_schema": NOISE_SCHEMA,
            "acquisition_policy": f"{ACQUISITION_POLICY_ID}@{ACQUISITION_POLICY_VERSION}",
            "fit_method": FIT_METHOD_IDENTITY,
            "required_solver": "Sparse",
        },
        "implementation_code": code,
        "reference_tools": tools,
        "family_bindings": [bindings[key] for key in sorted(bindings)],
        "logical_request_counts": dict(sorted(logical_counts.items())),
        "dataset_logical_request_count": sum(logical_counts[name] for name in dataset_names),
        "comparison_logical_request_count": sum(
            logical_counts[name] for name in comparison_names
        ),
        "planned_logical_request_count": sum(logical_counts.values()),
        "unique_request_count": len(requests),
        "deduplicated_logical_request_count": sum(logical_counts.values()) - len(requests),
        "comparison_definitions": comparison_definitions,
        "requests": requests,
    }
    plan_hash = _hash_value(plan_core)
    return {
        **plan_core,
        "plan_hash_algorithm": REQUEST_HASH_ALGORITHM,
        "plan_hash": plan_hash,
    }


def _artifact_inventory(directory: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == "catalog_result.json":
            continue
        artifacts.append(
            {
                "path": str(path.relative_to(directory)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return artifacts


def _result_content_hash(artifacts: Sequence[dict[str, Any]]) -> str:
    return _hash_value(
        {
            "algorithm": RESULT_HASH_ALGORITHM,
            "artifacts": list(artifacts),
        }
    )


def _finalize_result_manifest(
    directory: Path,
    job: dict[str, Any],
    *,
    status: str,
    repository_commit: str,
    detail: dict[str, Any],
) -> dict[str, Any]:
    if status not in TERMINAL_STATUSES:
        raise NoiseCatalogError(f"cannot finalize unsupported result status {status!r}")
    artifacts = _artifact_inventory(directory)
    manifest = {
        "schema": CATALOG_RESULT_SCHEMA,
        "status": status,
        "completed": True,
        "created_utc": _utc_now(),
        "repository_commit": repository_commit,
        "request_id": job["request_id"],
        "request_hash": job["request_hash"],
        "request_hash_algorithm": REQUEST_HASH_ALGORITHM,
        "result_hash_algorithm": RESULT_HASH_ALGORITHM,
        "result_content_sha256": _result_content_hash(artifacts),
        "artifacts": artifacts,
        "detail": detail,
    }
    _write_json(directory / "catalog_result.json", manifest)
    return manifest


def _float_matches(first: Any, second: Any) -> bool:
    try:
        return math.isclose(float(first), float(second), rel_tol=1.0e-12, abs_tol=1.0e-18)
    except (TypeError, ValueError):
        return False


def _validate_geometry(request: dict[str, Any], row: dict[str, str]) -> bool:
    geometry = request["geometry"]
    if not _float_matches(row.get("l_m"), geometry["l_m"]):
        return False
    if geometry["geometry_kind"] == "planar":
        return _float_matches(row.get("w_m"), geometry["w_m"]) and not row.get("nfin")
    try:
        return int(row.get("nfin", "")) == int(geometry["nfin"]) and not row.get("w_m")
    except ValueError:
        return False


def _validate_completed_result(
    job: dict[str, Any], directory: Path
) -> dict[str, Any]:
    """Validate a result sufficiently for strict N2 reuse without trusting filenames."""

    def reject(reason: str, *, status: str | None = None) -> dict[str, Any]:
        return {
            "valid": False,
            "reusable": False,
            "reason": reason,
            "status": status,
        }

    manifest_path = directory / "catalog_result.json"
    if not directory.is_dir() or not manifest_path.is_file():
        return reject("incomplete_result_missing_catalog_manifest")
    try:
        manifest = _read_json(manifest_path)
    except NoiseCatalogError as error:
        return reject(f"malformed_catalog_manifest:{error}")
    status = manifest.get("status")
    if manifest.get("schema") != CATALOG_RESULT_SCHEMA:
        return reject("catalog_result_schema_mismatch", status=status)
    if manifest.get("completed") is not True:
        return reject("catalog_result_not_completed", status=status)
    if manifest.get("request_id") != job["request_id"]:
        return reject("request_id_mismatch", status=status)
    if manifest.get("request_hash") != job["request_hash"]:
        return reject("request_hash_mismatch", status=status)
    if status not in TERMINAL_STATUSES:
        return reject("terminal_status_invalid", status=status)
    recorded_artifacts = manifest.get("artifacts")
    if not isinstance(recorded_artifacts, list):
        return reject("artifact_inventory_missing", status=status)
    current_artifacts = _artifact_inventory(directory)
    if recorded_artifacts != current_artifacts:
        return reject("artifact_inventory_or_hash_mismatch", status=status)
    content_hash = _result_content_hash(current_artifacts)
    if manifest.get("result_content_sha256") != content_hash:
        return reject("result_content_hash_mismatch", status=status)

    request = job["request"]
    if status == "validated":
        required = (
            "metadata.json",
            "operating_points.csv",
            "noise_spectrum.csv",
            "noise_metrics.csv",
            "source_breakdown.json",
            "noise_model_snapshot.json",
            "bias_resolution.json",
            "fit_diagnostics.json",
            "acquisition.json",
        )
        if not all((directory / name).is_file() for name in required):
            return reject("validated_result_contract_artifact_missing", status=status)
        try:
            metadata = _read_json(directory / "metadata.json")
            acquisition = _read_json(directory / "acquisition.json")
            snapshot = _read_json(directory / "noise_model_snapshot.json")
            source = _read_json(directory / "source_breakdown.json")
            operating_rows = _read_csv(directory / "operating_points.csv")
            spectrum_rows = _read_csv(directory / "noise_spectrum.csv")
        except NoiseCatalogError as error:
            return reject(f"validated_result_parse_error:{error}", status=status)
        binding = metadata.get("catalog_request", {})
        if metadata.get("schema") != NOISE_SCHEMA or metadata.get("status") != "pass":
            return reject("per_device_result_schema_or_status_mismatch", status=status)
        if metadata.get("selector") != request["selector"]:
            return reject("per_device_selector_mismatch", status=status)
        if binding.get("request_id") != job["request_id"] or binding.get(
            "request_hash"
        ) != job["request_hash"]:
            return reject("per_device_request_binding_mismatch", status=status)
        if metadata.get("temperature_c") != request["temperature_c"]:
            return reject("per_device_temperature_mismatch", status=status)
        if len(operating_rows) != 1 or not _validate_geometry(request, operating_rows[0]):
            return reject("per_device_geometry_mismatch", status=status)
        operating = operating_rows[0]
        if request["bias"]["mode"] == "gm_over_id_target":
            if operating.get("bias_mode") != "gm_over_id_target" or not _float_matches(
                operating.get("gm_over_id_target_per_v"), request["bias"]["target_per_v"]
            ):
                return reject("per_device_gm_over_id_target_mismatch", status=status)
            if float(operating["gm_over_id_relative_error"]) > float(
                request["bias"]["relative_tolerance"]
            ):
                return reject("per_device_gm_over_id_tolerance_failed", status=status)
        else:
            if operating.get("bias_mode") != "explicit_vctrl" or not _float_matches(
                operating.get("requested_vctrl_v"), request["bias"]["vctrl_v"]
            ):
                return reject("per_device_explicit_vctrl_mismatch", status=status)
        if not _float_matches(operating.get("vout_v"), request["output_bias"]["vout_v"]):
            return reject("per_device_vout_mismatch", status=status)
        if acquisition.get("policy_id") != ACQUISITION_POLICY_ID or acquisition.get(
            "policy_version"
        ) != ACQUISITION_POLICY_VERSION:
            return reject("acquisition_policy_mismatch", status=status)
        if acquisition.get("fit_method_identity") != FIT_METHOD_IDENTITY:
            return reject("fit_method_mismatch", status=status)
        attempts = acquisition.get("attempts", [])
        if not attempts or not all(
            item.get("required_solver") == "Sparse"
            and item.get("sparse_attestation_count", 0) > 0
            and item.get("klu_attestation_count") == 0
            and item.get("log_critical_diagnostic_count") == 0
            for item in attempts
        ):
            return reject("sparse_no_klu_audit_failed", status=status)
        if snapshot.get("effective_parameter_snapshot_available") is not True:
            return reject("effective_parameter_snapshot_incomplete", status=status)
        if source.get("namespace") != "raw_backend_model_specific" or source.get(
            "cross_engine_semantic_mapping"
        ) != "none":
            return reject("raw_source_breakdown_semantics_mismatch", status=status)
        required_spectrum = {
            "frequency_hz",
            "s_idrain_terminal_a2_per_hz",
            "s_vgate_equivalent_v2_per_hz",
            "y_dg_real_s",
            "y_dg_imag_s",
        }
        if not spectrum_rows or not required_spectrum.issubset(spectrum_rows[0]):
            return reject("canonical_spectrum_fields_missing", status=status)
        try:
            frequencies = [float(row["frequency_hz"]) for row in spectrum_rows]
            drain = [float(row["s_idrain_terminal_a2_per_hz"]) for row in spectrum_rows]
            gate = [float(row["s_vgate_equivalent_v2_per_hz"]) for row in spectrum_rows]
            transfer = [
                float(row["y_dg_real_s"]) ** 2 + float(row["y_dg_imag_s"]) ** 2
                for row in spectrum_rows
            ]
        except (KeyError, TypeError, ValueError) as error:
            return reject(f"canonical_spectrum_malformed:{error}", status=status)
        if not all(
            math.isfinite(value)
            for value in [*frequencies, *drain, *gate, *transfer]
        ) or not all(value > 0.0 for value in frequencies):
            return reject("canonical_spectrum_nonfinite", status=status)
        if not all(first < second for first, second in zip(frequencies, frequencies[1:])):
            return reject("canonical_spectrum_frequency_order_invalid", status=status)
        if not all(value >= 0.0 for value in drain) or not all(value >= 0.0 for value in gate):
            return reject("canonical_spectrum_negative_psd", status=status)
        if not all(value > 0.0 for value in transfer):
            return reject("canonical_spectrum_zero_transfer", status=status)
    elif status == "target_not_reachable":
        path = directory / "bias_resolution.json"
        if request["bias"]["mode"] != "gm_over_id_target" or not path.is_file():
            return reject("unreachable_result_missing_gm_target_diagnostic", status=status)
        try:
            bias = _read_json(path)
        except NoiseCatalogError as error:
            return reject(f"unreachable_diagnostic_parse_error:{error}", status=status)
        if bias.get("status") != "target_not_reachable" or not _float_matches(
            bias.get("target_per_v"), request["bias"]["target_per_v"]
        ):
            return reject("unreachable_diagnostic_mismatch", status=status)

    return {
        "valid": True,
        "reusable": status in REUSABLE_STATUSES,
        "reason": "validated_exact_request_and_artifact_hashes",
        "status": status,
        "result_content_sha256": content_hash,
        "manifest": manifest,
    }


def _quarantine_stale_result(
    output: Path,
    directory: Path,
    request_id: str,
    reason: str,
) -> Path:
    inventory = _artifact_inventory(directory) if directory.is_dir() else []
    token = _hash_value({"inventory": inventory, "reason": reason})[:20]
    destination = output / "stale_results" / request_id / token
    if destination.exists():
        raise NoiseCatalogError(f"stale-result quarantine collision: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(directory), str(destination))
    _write_json(
        destination / "stale_rejection.json",
        {
            "schema": "apm.noise-catalog-stale-rejection.v1",
            "request_id": request_id,
            "reason": reason,
            "reused": False,
            "quarantined_utc": _utc_now(),
        },
    )
    return destination


def _execute_request(
    root: Path,
    output: Path,
    job: dict[str, Any],
    toolchain: Toolchain,
    repository_commit: str,
    plan_hash: str,
) -> dict[str, Any]:
    directory = output / "results" / job["request_id"]
    request = job["request"]
    geometry = request["geometry"]
    kwargs: dict[str, Any] = {
        "operating_profile_id": request["operating_profile"]["id"],
        "temperature_c": request["temperature_c"],
        "l_m": geometry["l_m"],
        "root": root,
        "toolchain": toolchain,
        "catalog_request": {
            "schema": CATALOG_REQUEST_SCHEMA,
            "request_id": job["request_id"],
            "request_hash": job["request_hash"],
            "plan_hash": plan_hash,
            "semantic_binding_sha256": request["semantic_binding"]["aggregate_sha256"],
        },
        "require_native_oracle_agreement": False,
    }
    if geometry["geometry_kind"] == "planar":
        kwargs["w_m"] = geometry["w_m"]
    else:
        kwargs["nfin"] = geometry["nfin"]
    if request["bias"]["mode"] == "gm_over_id_target":
        kwargs["gm_over_id_target"] = request["bias"]["target_per_v"]
    else:
        kwargs["vctrl_v"] = request["bias"]["vctrl_v"]
    try:
        result = characterize_noise_selector(
            request["selector"],
            directory,
            **kwargs,
        )
        manifest = _finalize_result_manifest(
            directory,
            job,
            status="validated",
            repository_commit=repository_commit,
            detail={"per_device_result": result},
        )
    except (OSError, RuntimeError, ValueError) as error:
        bias_path = directory / "bias_resolution.json"
        bias: dict[str, Any] | None = None
        if bias_path.is_file():
            try:
                bias = _read_json(bias_path)
            except NoiseCatalogError:
                bias = None
        if bias is not None and bias.get("status") == "target_not_reachable":
            status = "target_not_reachable"
            detail = {
                "reason": bias.get("reason"),
                "exception_type": type(error).__name__,
                "exception": str(error),
            }
        else:
            status = "simulation_failed"
            detail = {
                "exception_type": type(error).__name__,
                "exception": str(error),
            }
            directory.mkdir(parents=True, exist_ok=True)
            _write_json(
                directory / "simulation_failure.json",
                {
                    "schema": "apm.noise-catalog-simulation-failure.v1",
                    "status": status,
                    **detail,
                },
            )
        manifest = _finalize_result_manifest(
            directory,
            job,
            status=status,
            repository_commit=repository_commit,
            detail=detail,
        )
    validation = _validate_completed_result(job, directory)
    if not validation["valid"]:
        raise NoiseCatalogError(
            f"fresh result {job['request_id']} failed contract validation: "
            f"{validation['reason']}"
        )
    return manifest


def _nullable_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _interpolate_spectrum_value(
    frequencies: Sequence[float], values: Sequence[float], target_hz: float
) -> tuple[float | None, str]:
    for frequency, value in zip(frequencies, values):
        if math.isclose(frequency, target_hz, rel_tol=1.0e-10, abs_tol=1.0e-15):
            return value, "exact_grid"
    if target_hz < frequencies[0] or target_hz > frequencies[-1]:
        return None, "outside_acquired_spectrum"
    for index in range(len(frequencies) - 1):
        lower_f = frequencies[index]
        upper_f = frequencies[index + 1]
        if lower_f < target_hz < upper_f:
            lower_v = values[index]
            upper_v = values[index + 1]
            fraction = (math.log(target_hz) - math.log(lower_f)) / (
                math.log(upper_f) - math.log(lower_f)
            )
            if lower_v > 0.0 and upper_v > 0.0:
                value = math.exp(math.log(lower_v) + fraction * (math.log(upper_v) - math.log(lower_v)))
                return value, "log_frequency_log_psd_linear"
            value = lower_v + fraction * (upper_v - lower_v)
            return value, "log_frequency_linear_psd"
    return None, "target_not_bracketed"


def _integrate_spectrum_band(
    frequencies: Sequence[float], values: Sequence[float], minimum_hz: float, maximum_hz: float
) -> tuple[float | None, str]:
    if minimum_hz < frequencies[0] or maximum_hz > frequencies[-1] or minimum_hz >= maximum_hz:
        return None, "band_not_fully_acquired"
    points: list[tuple[float, float]] = []
    for boundary in (minimum_hz, maximum_hz):
        value, _method = _interpolate_spectrum_value(frequencies, values, boundary)
        if value is None:
            return None, "band_boundary_not_resolved"
        points.append((boundary, value))
    points.extend(
        (frequency, value)
        for frequency, value in zip(frequencies, values)
        if minimum_hz < frequency < maximum_hz
    )
    points.sort(key=lambda item: item[0])
    integral = sum(
        0.5 * (first[1] + second[1]) * (second[0] - first[0])
        for first, second in zip(points, points[1:])
    )
    if not math.isfinite(integral) or integral < 0.0:
        return None, "integral_nonfinite"
    return integral, "trapezoidal_linear_frequency_with_log_frequency_boundary_interpolation"


def _frequency_field_token(frequency_hz: float) -> str:
    names = {1.0: "1hz", 1.0e3: "1khz", 1.0e6: "1mhz", 1.0e7: "10mhz"}
    return names[frequency_hz]


def _source_summary(job: dict[str, Any], output: Path) -> dict[str, Any]:
    directory = output / "results" / job["request_id"]
    validation = _validate_completed_result(job, directory)
    if not validation["valid"]:
        raise NoiseCatalogError(
            f"cannot summarize invalid result {job['request_id']}: {validation['reason']}"
        )
    request = job["request"]
    result: dict[str, Any] = {
        "request_id": job["request_id"],
        "request_hash": job["request_hash"],
        "result_content_sha256": validation["result_content_sha256"],
        "status": validation["status"],
        "selector": request["selector"],
        "technology_id": request["selector"].split("/")[0],
        "family_id": request["selector"].split("/")[1],
        "device_id": request["selector"].split("/")[2],
        "public_device": request["public_device"],
        "polarity": request["polarity"],
        "temperature_c": request["temperature_c"],
        "operating_profile_id": request["operating_profile"]["id"],
        "reference_vdd_v": request["operating_profile"]["reference_vdd_v"],
        "vout_v": request["output_bias"]["vout_v"],
        "bias_mode": request["bias"]["mode"],
        "gm_over_id_target_per_v": request["bias"].get("target_per_v"),
        "requested_vctrl_v": request["bias"].get("vctrl_v"),
        "geometry_kind": request["geometry"]["geometry_kind"],
        "l_m": request["geometry"]["l_m"],
        "l_over_lmin": request["geometry"]["l_over_lmin"],
        "w_m": request["geometry"].get("w_m"),
        "nfin": request["geometry"].get("nfin"),
        "fit_method_identity": FIT_METHOD_IDENTITY,
        "acquisition_policy": f"{ACQUISITION_POLICY_ID}@{ACQUISITION_POLICY_VERSION}",
        "required_solver": "Sparse",
        "klu_used": False,
    }
    if validation["status"] != "validated":
        result.update(
            {
                "comparison_status": f"not_comparable_{validation['status']}",
                "fit_method_status": None,
                "flicker_fit_status": None,
                "white_fit_status": None,
                "flicker_corner_status": None,
                "selected_stop_hz": None,
                "acquisition_attempt_count": None,
            }
        )
        return result

    operating = _read_csv(directory / "operating_points.csv")[0]
    metrics = _read_csv(directory / "noise_metrics.csv")[0]
    spectrum_rows = _read_csv(directory / "noise_spectrum.csv")
    acquisition = _read_json(directory / "acquisition.json")
    snapshot = _read_json(directory / "noise_model_snapshot.json")
    source = _read_json(directory / "source_breakdown.json")
    frequencies = [float(row["frequency_hz"]) for row in spectrum_rows]
    drain_psd = [float(row["s_idrain_terminal_a2_per_hz"]) for row in spectrum_rows]
    gate_psd = [float(row["s_vgate_equivalent_v2_per_hz"]) for row in spectrum_rows]
    result.update(
        {
            "comparison_status": "comparable_side_by_side",
            "vctrl_v": _nullable_float(operating.get("vctrl_v")),
            "idmag_a": _nullable_float(operating.get("idmag_a")),
            "gm_s": _nullable_float(operating.get("gm_s")),
            "gds_s": _nullable_float(operating.get("gds_s")),
            "gm_over_id_per_v": _nullable_float(operating.get("gm_over_id_per_v")),
            "gm_over_gds": _nullable_float(operating.get("gm_over_gds")),
            "gm_over_id_relative_error": _nullable_float(
                operating.get("gm_over_id_relative_error")
            ),
            "fit_method_status": metrics.get("fit_method_status"),
            "flicker_fit_status": metrics.get("flicker_fit_status"),
            "flicker_coefficient_a2_per_hz_at_1hz": _nullable_float(
                metrics.get("flicker_coefficient_a2_per_hz_at_1hz")
            ),
            "flicker_alpha": _nullable_float(metrics.get("flicker_alpha")),
            "white_fit_status": metrics.get("white_fit_status"),
            "white_floor_a2_per_hz": _nullable_float(
                metrics.get("white_floor_a2_per_hz")
            ),
            "flicker_corner_status": metrics.get("flicker_corner_status"),
            "flicker_corner_hz": _nullable_float(metrics.get("flicker_corner_hz")),
            "gamma_eff_total_status": metrics.get("gamma_eff_total_status"),
            "gamma_eff_total": _nullable_float(metrics.get("gamma_eff_total")),
            "selected_stop_hz": acquisition["selected_stop_hz"],
            "acquisition_attempt_count": len(acquisition["attempts"]),
            "white_region_status": acquisition["white_region_status"],
            "effective_noise_parameter_count": len(snapshot.get("parameters", [])),
            "effective_parameter_snapshot_sha256": sha256_file(
                directory / "noise_model_snapshot.json"
            ),
            "raw_backend_source_count": len(source.get("sources", [])),
            "raw_backend_source_names": [
                item["raw_vector_name"] for item in source.get("sources", [])
            ],
            "source_breakdown_sha256": sha256_file(directory / "source_breakdown.json"),
        }
    )
    methods: set[str] = set()
    for frequency_hz in REFERENCE_FREQUENCIES_HZ:
        token = _frequency_field_token(frequency_hz)
        drain_value, drain_method = _interpolate_spectrum_value(
            frequencies, drain_psd, frequency_hz
        )
        gate_value, gate_method = _interpolate_spectrum_value(
            frequencies, gate_psd, frequency_hz
        )
        methods.update((drain_method, gate_method))
        result[f"s_idrain_terminal_a2_per_hz_at_{token}"] = drain_value
        result[f"s_vgate_equivalent_v2_per_hz_at_{token}"] = gate_value
    gate_integral, integration_method = _integrate_spectrum_band(
        frequencies, gate_psd, *INTEGRATION_BAND_HZ
    )
    result.update(
        {
            "reference_frequency_value_methods": sorted(methods),
            "gate_referred_integrated_noise_1hz_to_10mhz_v2": gate_integral,
            "gate_referred_integrated_noise_1hz_to_10mhz_rms_v": (
                math.sqrt(gate_integral) if gate_integral is not None else None
            ),
            "gate_referred_integration_status": (
                "valid" if gate_integral is not None else "invalid"
            ),
            "gate_referred_integration_method": integration_method,
        }
    )
    return result


def _status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row["status"]) for row in rows)
    return {key: counts.get(key, 0) for key in TERMINAL_STATUSES}


def _scaling_exponent(points: Sequence[tuple[float, float | None]]) -> dict[str, Any]:
    usable = [(x, y) for x, y in points if x > 0.0 and y is not None and y > 0.0]
    if len(usable) < 2:
        return {"status": "not_observed", "value": None, "point_count": len(usable)}
    x_values = [math.log(item[0]) for item in usable]
    y_values = [math.log(float(item[1])) for item in usable]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    denominator = sum((value - x_mean) ** 2 for value in x_values)
    if denominator <= 0.0:
        return {"status": "invalid_geometry_span", "value": None, "point_count": len(usable)}
    slope = sum(
        (x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values)
    ) / denominator
    return {
        "status": "descriptive_only",
        "value": slope,
        "point_count": len(usable),
        "interpretation": "log(metric) versus log(geometry) OLS slope; no monotonic law imposed",
    }


def _summary_artifact(path: Path, output: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(output)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _generate_summaries(
    plan: dict[str, Any],
    output: Path,
    execution_records: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    summaries = {
        job["request_id"]: _source_summary(job, output) for job in plan["requests"]
    }
    membership_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in plan["requests"]:
        source = summaries[job["request_id"]]
        for membership in job["memberships"]:
            membership_rows[membership["dataset"]].append(
                {
                    "logical_request_id": membership["logical_request_id"],
                    "dataset": membership["dataset"],
                    **membership["coordinate"],
                    **source,
                }
            )
    for rows in membership_rows.values():
        rows.sort(
            key=lambda row: (
                row.get("selector", ""),
                row.get("temperature_c", 0),
                row.get("gm_over_id_target_per_v") or 0,
                row.get("l_m") or 0,
                row.get("nfin") or 0,
                row["logical_request_id"],
            )
        )

    summary_directory = output / "summary"
    dataset_paths = {
        DATASET_TEMPERATURE: summary_directory / "noise_temperature.csv",
        DATASET_INVERSION: summary_directory / "noise_inversion.csv",
        DATASET_LENGTH: summary_directory / "noise_length_scaling.csv",
        DATASET_NFIN: summary_directory / "noise_nfin_scaling.csv",
    }
    for dataset, path in dataset_paths.items():
        _write_csv(path, membership_rows[dataset])

    operating_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    for request_id in sorted(summaries):
        source = summaries[request_id]
        operating_rows.append(
            {
                key: source.get(key)
                for key in (
                    "request_id",
                    "request_hash",
                    "result_content_sha256",
                    "status",
                    "selector",
                    "technology_id",
                    "family_id",
                    "device_id",
                    "public_device",
                    "polarity",
                    "temperature_c",
                    "operating_profile_id",
                    "reference_vdd_v",
                    "bias_mode",
                    "gm_over_id_target_per_v",
                    "requested_vctrl_v",
                    "vctrl_v",
                    "vout_v",
                    "idmag_a",
                    "gm_s",
                    "gds_s",
                    "gm_over_id_per_v",
                    "gm_over_gds",
                    "gm_over_id_relative_error",
                    "geometry_kind",
                    "l_m",
                    "l_over_lmin",
                    "w_m",
                    "nfin",
                )
            }
        )
        metric_rows.append(
            {
                key: source.get(key)
                for key in (
                    "request_id",
                    "request_hash",
                    "result_content_sha256",
                    "status",
                    "selector",
                    "temperature_c",
                    "bias_mode",
                    "gm_over_id_target_per_v",
                    "requested_vctrl_v",
                    "l_m",
                    "w_m",
                    "nfin",
                    "fit_method_identity",
                    "fit_method_status",
                    "flicker_fit_status",
                    "flicker_coefficient_a2_per_hz_at_1hz",
                    "flicker_alpha",
                    "white_fit_status",
                    "white_floor_a2_per_hz",
                    "flicker_corner_status",
                    "flicker_corner_hz",
                    "gamma_eff_total_status",
                    "gamma_eff_total",
                    "selected_stop_hz",
                    "acquisition_attempt_count",
                    "white_region_status",
                    "gate_referred_integrated_noise_1hz_to_10mhz_v2",
                    "gate_referred_integrated_noise_1hz_to_10mhz_rms_v",
                    "gate_referred_integration_status",
                )
            }
        )
    operating_path = summary_directory / "operating_point_index.csv"
    metrics_path = summary_directory / "noise_metrics_index.csv"
    _write_csv(operating_path, operating_rows)
    _write_csv(metrics_path, metric_rows)

    job_rows = []
    dispositions = {item["request_id"]: item for item in execution_records}
    for job in plan["requests"]:
        source = summaries[job["request_id"]]
        disposition = dispositions[job["request_id"]]
        job_rows.append(
            {
                "request_id": job["request_id"],
                "request_hash": job["request_hash"],
                "selector": source["selector"],
                "status": source["status"],
                "execution_disposition": disposition["execution_disposition"],
                "reuse_validation_reason": disposition.get("reuse_validation_reason"),
                "stale_result_rejected": disposition.get("stale_result_rejected", False),
                "result_content_sha256": source["result_content_sha256"],
                "membership_count": len(job["memberships"]),
                "datasets": sorted({item["dataset"] for item in job["memberships"]}),
            }
        )
    job_path = output / "job_index.csv"
    _write_csv(job_path, job_rows)

    comparison_rows = [
        *membership_rows[COMPARISON_THRESHOLD_EQUAL_INVERSION],
        *membership_rows[COMPARISON_THRESHOLD_EQUAL_BIAS],
        *membership_rows[COMPARISON_CROSS_PROCESS],
    ]
    comparison_rows.sort(
        key=lambda row: (
            row["dataset"],
            row.get("technology_id", ""),
            row.get("comparison_set_id", ""),
            row.get("polarity", ""),
            row.get("family_id", ""),
        )
    )
    comparison_csv_path = summary_directory / "noise_comparisons.csv"
    _write_csv(comparison_csv_path, comparison_rows)

    threshold_groups: list[dict[str, Any]] = []
    for view in (
        COMPARISON_THRESHOLD_EQUAL_INVERSION,
        COMPARISON_THRESHOLD_EQUAL_BIAS,
    ):
        rows = membership_rows[view]
        keys = sorted(
            {
                (
                    row["technology_id"],
                    row["comparison_set_id"],
                    row["polarity"],
                )
                for row in rows
            }
        )
        for technology_id, set_id, polarity in keys:
            members = [
                row
                for row in rows
                if row["technology_id"] == technology_id
                and row["comparison_set_id"] == set_id
                and row["polarity"] == polarity
            ]
            members.sort(key=lambda row: row["family_id"])
            threshold_groups.append(
                {
                    "view": view,
                    "technology_id": technology_id,
                    "comparison_set_id": set_id,
                    "polarity": polarity,
                    "status": (
                        "complete"
                        if len(members) == 3 and all(row["status"] == "validated" for row in members)
                        else "explicit_partial_or_not_comparable"
                    ),
                    "member_count": len(members),
                    "members": members,
                    "noise_ordering_requirement": "none",
                    "claim_boundary": (
                        "Controlled APM generic threshold/workfunction variants; not foundry "
                        "multi-Vt noise truth."
                        if technology_id in {"apm022", "apm016f"}
                        else "Observed upstream model predictions; no universal Vt-noise ordering imposed."
                    ),
                }
            )

    anchor_groups: list[dict[str, Any]] = []
    anchor_rows = membership_rows[COMPARISON_CROSS_PROCESS]
    for polarity in ("n", "p"):
        members = sorted(
            [row for row in anchor_rows if row["polarity"] == polarity],
            key=lambda row: row["technology_id"],
        )
        anchor_groups.append(
            {
                "view": COMPARISON_CROSS_PROCESS,
                "polarity": polarity,
                "status": (
                    "complete"
                    if len(members) == 5 and all(row["status"] == "validated" for row in members)
                    else "explicit_partial_or_not_comparable"
                ),
                "member_count": len(members),
                "members": members,
                "geometry_basis_rule": (
                    "Side-by-side values retain explicit planar W or FinFET NFIN geometry. "
                    "No planar-per-width versus FinFET-per-fin drain-noise ratio is produced."
                ),
                "cross_basis_ratios": None,
            }
        )
    comparisons = {
        "schema": COMPARISON_SCHEMA,
        "plan_hash": plan["plan_hash"],
        "source_reference_contract": (
            "Every member references request_id, request_hash, and exact result_content_sha256."
        ),
        "reference_frequencies_hz": list(REFERENCE_FREQUENCIES_HZ),
        "reference_frequency_interpolation": (
            "exact grid when present; otherwise deterministic log-frequency/log-PSD linear "
            "interpolation, with zero-valued fallback recorded explicitly"
        ),
        "gate_referred_integration_band_hz": list(INTEGRATION_BAND_HZ),
        "threshold_groups": threshold_groups,
        "cross_process_anchor_groups": anchor_groups,
        "universal_noise_ordering_imposed": False,
        "cross_basis_ratios_produced": False,
    }
    comparison_json_path = summary_directory / "noise_comparisons.json"
    _write_json(comparison_json_path, comparisons)

    scaling_observations: list[dict[str, Any]] = []
    for dataset, coordinate_field in ((DATASET_LENGTH, "l_m"), (DATASET_NFIN, "nfin")):
        rows = membership_rows[dataset]
        for selector in sorted({row["selector"] for row in rows}):
            points = [row for row in rows if row["selector"] == selector]
            points.sort(key=lambda row: float(row[coordinate_field]))
            scaling_observations.append(
                {
                    "dataset": dataset,
                    "selector": selector,
                    "coordinate": coordinate_field,
                    "geometry_values": [row[coordinate_field] for row in points],
                    "point_statuses": [row["status"] for row in points],
                    "descriptive_exponents": {
                        "drain_psd_at_1khz": _scaling_exponent(
                            [
                                (
                                    float(row[coordinate_field]),
                                    row.get("s_idrain_terminal_a2_per_hz_at_1khz"),
                                )
                                for row in points
                            ]
                        ),
                        "gate_referred_integrated_1hz_to_10mhz": _scaling_exponent(
                            [
                                (
                                    float(row[coordinate_field]),
                                    row.get(
                                        "gate_referred_integrated_noise_1hz_to_10mhz_v2"
                                    ),
                                )
                                for row in points
                            ]
                        ),
                        "white_floor": _scaling_exponent(
                            [
                                (
                                    float(row[coordinate_field]),
                                    row.get("white_floor_a2_per_hz"),
                                )
                                for row in points
                            ]
                        ),
                    },
                    "interpretation": (
                        "Descriptive current compact-model prediction only; no universal "
                        "monotonic or proportional scaling law is imposed."
                    ),
                }
            )
    scaling_path = summary_directory / "noise_scaling_observations.json"
    _write_json(
        scaling_path,
        {
            "schema": "apm.noise-scaling-observations.v1",
            "observations": scaling_observations,
        },
    )

    unique_rows = list(summaries.values())
    valid_rows = [row for row in unique_rows if row["status"] == "validated"]
    coverage = {
        "schema": "apm.noise-catalog-coverage.v1",
        "plan_hash": plan["plan_hash"],
        "catalog": plan["catalog"],
        "planned_logical_request_count": plan["planned_logical_request_count"],
        "dataset_logical_request_count": plan["dataset_logical_request_count"],
        "comparison_logical_request_count": plan["comparison_logical_request_count"],
        "unique_request_count": plan["unique_request_count"],
        "deduplicated_logical_request_count": plan["deduplicated_logical_request_count"],
        "unique_terminal_status_counts": _status_counts(unique_rows),
        "logical_status_counts": {
            dataset: _status_counts(rows) for dataset, rows in sorted(membership_rows.items())
        },
        "adaptive_selected_stop_distribution_hz": dict(
            sorted(
                Counter(str(row["selected_stop_hz"]) for row in valid_rows).items(),
                key=lambda item: float(item[0]),
            )
        ),
        "fit_status_coverage": {
            "flicker": dict(sorted(Counter(row["flicker_fit_status"] for row in valid_rows).items())),
            "white": dict(sorted(Counter(row["white_fit_status"] for row in valid_rows).items())),
            "corner": dict(
                sorted(Counter(row["flicker_corner_status"] for row in valid_rows).items())
            ),
        },
        "temperature_coverage_c": {
            str(value): _status_counts(
                row
                for row in membership_rows[DATASET_TEMPERATURE]
                if row["temperature_c"] == value
            )
            for value in TEMPERATURES_C
        },
        "inversion_coverage_per_v": {
            str(value): _status_counts(
                row
                for row in membership_rows[DATASET_INVERSION]
                if _float_matches(row["gm_over_id_target_per_v"], value)
            )
            for value in INVERSION_TARGETS_PER_V
        },
        "length_request_count": len(membership_rows[DATASET_LENGTH]),
        "length_selector_count": len(
            {row["selector"] for row in membership_rows[DATASET_LENGTH]}
        ),
        "nfin_request_count": len(membership_rows[DATASET_NFIN]),
        "nfin_selector_count": len({row["selector"] for row in membership_rows[DATASET_NFIN]}),
        "nfin_values": sorted({int(row["nfin"]) for row in membership_rows[DATASET_NFIN]}),
        "threshold_comparison_group_count": len(threshold_groups),
        "cross_process_anchor_group_count": len(anchor_groups),
        "all_required_noise_jobs_sparse_no_klu": all(
            row.get("required_solver") == "Sparse" and not row.get("klu_used")
            for row in valid_rows
        ),
        "raw_result_set_sha256": _hash_value(
            [
                {
                    "request_id": row["request_id"],
                    "request_hash": row["request_hash"],
                    "status": row["status"],
                    "result_content_sha256": row["result_content_sha256"],
                }
                for row in sorted(unique_rows, key=lambda item: item["request_id"])
            ]
        ),
    }
    coverage_path = output / "coverage.json"
    _write_json(coverage_path, coverage)

    artifact_paths = [
        *dataset_paths.values(),
        operating_path,
        metrics_path,
        job_path,
        comparison_csv_path,
        comparison_json_path,
        scaling_path,
        coverage_path,
    ]
    return {
        "coverage": coverage,
        "comparisons": comparisons,
        "source_summaries": summaries,
        "artifacts": [_summary_artifact(path, output) for path in artifact_paths],
    }


def _model_card_immutability(root: Path) -> dict[str, Any]:
    paths = (
        "models/apm350/ngspice/apm350_models.inc",
        "models/apm022/ngspice/apm022_multivt_models.inc",
        "models/apm016f/ngspice/apm016f_multivt_models.inc",
    )
    rows = []
    for relative in paths:
        baseline = run_checked(["git", "show", f"v2.0.0:{relative}"], cwd=root).stdout.encode(
            "utf-8"
        )
        current_path = root / relative
        baseline_hash = hashlib.sha256(baseline).hexdigest()
        current_hash = sha256_file(current_path)
        rows.append(
            {
                "path": relative,
                "v2_tag_sha256": baseline_hash,
                "current_sha256": current_hash,
                "unchanged": baseline_hash == current_hash,
            }
        )
    peeled = run_checked(["git", "rev-parse", "v2.0.0^{}"], cwd=root).stdout.strip()
    result = {
        "status": (
            "pass"
            if peeled == "3cc6cfea4932cc40f2d693784d0a569926cdf399"
            and all(row["unchanged"] for row in rows)
            else "fail"
        ),
        "v2_tag_commit": peeled,
        "expected_v2_tag_commit": "3cc6cfea4932cc40f2d693784d0a569926cdf399",
        "cards": rows,
        "noise_coefficients_tuned_by_n2": False,
    }
    return result


def _qualify_resume_validator(output: Path, repository_commit: str) -> dict[str, Any]:
    qualification = output / "resume_qualification"
    if qualification.exists():
        shutil.rmtree(qualification)
    qualification.mkdir(parents=True)
    payload = {
        "schema": CATALOG_REQUEST_SCHEMA,
        "selector": "fixture/general/nmos",
        "temperature_c": 27,
        "geometry": {"geometry_kind": "planar", "l_m": 2.0e-6, "w_m": 1.0e-6},
        "output_bias": {"vout_v": 0.5},
        "bias": {"mode": "gm_over_id_target", "target_per_v": 15.0},
    }
    request_hash = _hash_value(payload)
    job = {
        "request_id": f"resume-fixture-{request_hash[:16]}",
        "request_hash": request_hash,
        "request": payload,
        "memberships": [],
    }

    valid_directory = qualification / "valid_reusable"
    valid_directory.mkdir()
    _write_json(
        valid_directory / "bias_resolution.json",
        {
            "schema": "apm.noise-bias-resolution.v1",
            "status": "target_not_reachable",
            "target_per_v": 15.0,
            "reason": "synthetic_resume_contract_fixture",
        },
    )
    _finalize_result_manifest(
        valid_directory,
        job,
        status="target_not_reachable",
        repository_commit=repository_commit,
        detail={"qualification_fixture": True},
    )
    valid = _validate_completed_result(job, valid_directory)

    request_mismatch_directory = qualification / "request_mismatch"
    shutil.copytree(valid_directory, request_mismatch_directory)
    changed_job = {**job, "request_hash": "0" * 64}
    request_mismatch = _validate_completed_result(changed_job, request_mismatch_directory)

    artifact_mismatch_directory = qualification / "artifact_mismatch"
    shutil.copytree(valid_directory, artifact_mismatch_directory)
    _write_json(
        artifact_mismatch_directory / "bias_resolution.json",
        {
            "schema": "apm.noise-bias-resolution.v1",
            "status": "target_not_reachable",
            "target_per_v": 10.0,
            "reason": "deliberate_stale_artifact",
        },
    )
    artifact_mismatch = _validate_completed_result(job, artifact_mismatch_directory)

    incomplete_directory = qualification / "incomplete"
    incomplete_directory.mkdir()
    incomplete = _validate_completed_result(job, incomplete_directory)
    checks = [
        {
            "id": "exact_completed_result_is_reusable",
            "status": "pass" if valid["valid"] and valid["reusable"] else "fail",
            "observation": valid,
        },
        {
            "id": "request_hash_mismatch_is_rejected",
            "status": (
                "pass"
                if not request_mismatch["valid"]
                and request_mismatch["reason"] == "request_hash_mismatch"
                else "fail"
            ),
            "observation": request_mismatch,
        },
        {
            "id": "artifact_tamper_is_rejected",
            "status": (
                "pass"
                if not artifact_mismatch["valid"]
                and artifact_mismatch["reason"] == "artifact_inventory_or_hash_mismatch"
                else "fail"
            ),
            "observation": artifact_mismatch,
        },
        {
            "id": "incomplete_result_is_rejected",
            "status": (
                "pass"
                if not incomplete["valid"]
                and incomplete["reason"] == "incomplete_result_missing_catalog_manifest"
                else "fail"
            ),
            "observation": incomplete,
        },
    ]
    report = {
        "schema": "apm.noise-catalog-resume-qualification.v1",
        "status": "pass" if all(item["status"] == "pass" for item in checks) else "fail",
        "checks": checks,
        "acceptance_result": f"{sum(item['status'] == 'pass' for item in checks)}/{len(checks)}",
    }
    _write_json(qualification / "report.json", report)
    report["path"] = str((qualification / "report.json").relative_to(output))
    report["sha256"] = sha256_file(qualification / "report.json")
    return report


def _regression_summary(
    root: Path,
    output: Path,
    toolchain: Toolchain,
    *,
    resume: bool,
    progress: Callable[[str], None] | None,
) -> dict[str, Any]:
    directory = output / "regressions" / "v3_n1_method"
    report_path = directory / "report.json"
    disposition = "fresh_execution"
    report: dict[str, Any]
    if resume:
        prior_runs = sorted((output / "run_reports").glob("run-*.json"))
        expected_hash = None
        if prior_runs:
            prior_report = _read_json(prior_runs[-1])
            expected_hash = prior_report.get("regressions", {}).get("report_sha256")
        reuse_valid = False
        if report_path.is_file() and expected_hash == sha256_file(report_path):
            report = _read_json(report_path)
            nested_path = directory / "v3_n0_regression" / "report.json"
            reuse_valid = (
                report.get("schema") == "apm.noise-method-validation.v1"
                and report.get("status") == "pass"
                and report.get("acceptance_result") == "10/10"
                and report.get("v3_n0_regression", {}).get("status") == "pass"
                and nested_path.is_file()
                and report.get("v3_n0_regression", {}).get("report_sha256")
                == sha256_file(nested_path)
            )
        if reuse_valid:
            disposition = "safely_reused"
        else:
            if directory.exists():
                stale_identity = _hash_value(
                    {
                        "expected_hash": expected_hash,
                        "observed_hash": (
                            sha256_file(report_path) if report_path.is_file() else None
                        ),
                    }
                )[:20]
                stale = output / "stale_results" / "v3_n1_regression" / stale_identity
                if stale.exists():
                    raise NoiseCatalogError(
                        f"V3-N1 regression stale-quarantine collision: {stale}"
                    )
                stale.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(directory), str(stale))
                disposition = "fresh_execution_after_stale_rejection"
                if progress:
                    progress("V3-N2 regression: stale V3-N1 evidence rejected; rerunning")
            report = validate_noise_method(directory, root=root, toolchain=toolchain)
    else:
        disposition = "fresh_execution"
        if progress:
            progress("V3-N2 regression: running complete V3-N1 method (includes V3-N0)")
        report = validate_noise_method(directory, root=root, toolchain=toolchain)
    return {
        "status": report["status"],
        "execution_disposition": disposition,
        "v3_n1_acceptance_result": report["acceptance_result"],
        "v3_n0_status": report["v3_n0_regression"]["status"],
        "v3_n0_acceptance_result": report["v3_n0_regression"]["acceptance_result"],
        "report_path": str(report_path.relative_to(output)),
        "report_sha256": sha256_file(report_path),
        "v3_n0_report_sha256": report["v3_n0_regression"]["report_sha256"],
    }


def _prepare_catalog_output(output: Path, *, resume: bool) -> Path:
    resolved = output.resolve()
    if resume:
        if not resolved.is_dir() or not (resolved / "plan.json").is_file():
            raise NoiseCatalogError("--resume requires an existing N2 output with plan.json")
    else:
        if resolved.exists() and any(resolved.iterdir()):
            raise NoiseCatalogError(f"refusing to overwrite non-empty output: {resolved}")
        resolved.mkdir(parents=True, exist_ok=True)
    for name in ("results", "summary", "run_reports"):
        (resolved / name).mkdir(parents=True, exist_ok=True)
    return resolved


def _default_catalog_output(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return state_directory(root) / "results" / f"v3-n2-noise-catalog-{stamp}"


def validate_noise_catalog(
    output: Path | None = None,
    *,
    resume: bool = False,
    root: Path | None = None,
    toolchain: Toolchain | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Execute and qualify the complete V3-N2 catalog from a deterministic plan."""

    resolved_root = (root or repository_root()).resolve()
    selected_toolchain = toolchain or resolve_toolchain(resolved_root)
    build_models(selected_toolchain, force=False)
    result_directory = _prepare_catalog_output(
        output or _default_catalog_output(resolved_root), resume=resume
    )
    plan = build_noise_catalog_plan(resolved_root, toolchain=selected_toolchain)
    plan_path = result_directory / "plan.json"
    if resume:
        stored_plan = _read_json(plan_path)
        if stored_plan.get("plan_hash") != plan["plan_hash"]:
            raise NoiseCatalogError(
                "resume plan mismatch: current semantic/tool/model plan hash does not match "
                f"stored plan ({plan['plan_hash']} != {stored_plan.get('plan_hash')})"
            )
        if _canonical_json(stored_plan) != _canonical_json(plan):
            raise NoiseCatalogError("resume plan payload changed despite its recorded hash")
    else:
        _write_json(plan_path, plan)
    if progress:
        progress(
            "V3-N2 plan: "
            f"{plan['planned_logical_request_count']} logical -> "
            f"{plan['unique_request_count']} unique requests; plan {plan['plan_hash'][:12]}"
        )

    repository_commit = run_checked(
        ["git", "rev-parse", "HEAD"], cwd=resolved_root
    ).stdout.strip()
    execution_records: list[dict[str, Any]] = []
    stale_rejections: list[dict[str, Any]] = []
    total = len(plan["requests"])
    for index, job in enumerate(plan["requests"], start=1):
        directory = result_directory / "results" / job["request_id"]
        execution_disposition = "fresh_execution"
        reuse_reason: str | None = None
        stale_rejected = False
        if directory.exists():
            if not resume:
                raise NoiseCatalogError(f"unexpected result directory in fresh run: {directory}")
            validation = _validate_completed_result(job, directory)
            if validation["valid"] and validation["reusable"]:
                execution_disposition = "safely_reused"
                reuse_reason = validation["reason"]
                manifest = validation["manifest"]
            else:
                stale_rejected = True
                stale_reason = validation["reason"]
                quarantined = _quarantine_stale_result(
                    result_directory, directory, job["request_id"], stale_reason
                )
                stale_rejections.append(
                    {
                        "request_id": job["request_id"],
                        "reason": stale_reason,
                        "quarantine_path": str(quarantined.relative_to(result_directory)),
                    }
                )
                execution_disposition = "fresh_execution_after_stale_rejection"
                manifest = _execute_request(
                    resolved_root,
                    result_directory,
                    job,
                    selected_toolchain,
                    repository_commit,
                    plan["plan_hash"],
                )
        else:
            manifest = _execute_request(
                resolved_root,
                result_directory,
                job,
                selected_toolchain,
                repository_commit,
                plan["plan_hash"],
            )
        execution_records.append(
            {
                "request_id": job["request_id"],
                "status": manifest["status"],
                "execution_disposition": execution_disposition,
                "reuse_validation_reason": reuse_reason,
                "stale_result_rejected": stale_rejected,
                "result_content_sha256": manifest["result_content_sha256"],
            }
        )
        if progress:
            progress(
                f"V3-N2 [{index}/{total}] {job['request']['selector']} "
                f"{manifest['status']} ({execution_disposition})"
            )

    summaries = _generate_summaries(plan, result_directory, execution_records)
    coverage = summaries["coverage"]
    resume_qualification = _qualify_resume_validator(result_directory, repository_commit)
    regression = _regression_summary(
        resolved_root,
        result_directory,
        selected_toolchain,
        resume=resume,
        progress=progress,
    )
    immutability = _model_card_immutability(resolved_root)

    terminal_counts = coverage["unique_terminal_status_counts"]
    disposition_counts = Counter(item["execution_disposition"] for item in execution_records)
    threshold_groups = summaries["comparisons"]["threshold_groups"]
    anchor_groups = summaries["comparisons"]["cross_process_anchor_groups"]
    source_summaries = list(summaries["source_summaries"].values())
    validated_sources = [row for row in source_summaries if row["status"] == "validated"]
    logical_counts = plan["logical_request_counts"]
    checks = [
        {
            "id": "catalog.manifest_5_13_26",
            "status": (
                "pass"
                if plan["catalog"]["technology_count"] == 5
                and plan["catalog"]["family_count"] == 13
                and plan["catalog"]["public_device_count"] == 26
                else "fail"
            ),
        },
        {
            "id": "plan.stable_identity_and_deduplication",
            "status": (
                "pass"
                if plan["unique_request_count"] < plan["planned_logical_request_count"]
                and plan["deduplicated_logical_request_count"] > 0
                else "fail"
            ),
        },
        {
            "id": "dataset.temperature_complete_status",
            "status": (
                "pass"
                if logical_counts.get(DATASET_TEMPERATURE) == 104
                and sum(coverage["logical_status_counts"][DATASET_TEMPERATURE].values()) == 104
                else "fail"
            ),
        },
        {
            "id": "dataset.inversion_complete_status",
            "status": (
                "pass"
                if logical_counts.get(DATASET_INVERSION) == 130
                and sum(coverage["logical_status_counts"][DATASET_INVERSION].values()) == 130
                else "fail"
            ),
        },
        {
            "id": "dataset.length_manifest_coverage",
            "status": (
                "pass"
                if coverage["length_selector_count"] == 26
                and coverage["length_request_count"] == logical_counts.get(DATASET_LENGTH)
                else "fail"
            ),
        },
        {
            "id": "dataset.nfin_manifest_coverage",
            "status": (
                "pass"
                if coverage["nfin_selector_count"] == 6
                and coverage["nfin_values"] == [1, 2, 4]
                and coverage["nfin_request_count"] == logical_counts.get(DATASET_NFIN)
                else "fail"
            ),
        },
        {
            "id": "results.explicit_terminal_status",
            "status": (
                "pass"
                if sum(terminal_counts.values()) == plan["unique_request_count"]
                else "fail"
            ),
        },
        {
            "id": "results.no_simulation_failures",
            "status": "pass" if terminal_counts["simulation_failed"] == 0 else "fail",
        },
        {
            "id": "results.raw_provenance_and_sources",
            "status": (
                "pass"
                if validated_sources
                and all(
                    row["effective_noise_parameter_count"] > 0
                    and row["raw_backend_source_count"] > 0
                    and row["effective_parameter_snapshot_sha256"]
                    and row["source_breakdown_sha256"]
                    for row in validated_sources
                )
                else "fail"
            ),
        },
        {
            "id": "solver.sparse_no_klu",
            "status": (
                "pass" if coverage["all_required_noise_jobs_sparse_no_klu"] else "fail"
            ),
        },
        {
            "id": "comparison.threshold_views",
            "status": (
                "pass"
                if len(threshold_groups) == 12
                and all(group["member_count"] == 3 for group in threshold_groups)
                else "fail"
            ),
        },
        {
            "id": "comparison.cross_process_polarity_and_basis",
            "status": (
                "pass"
                if len(anchor_groups) == 2
                and all(group["member_count"] == 5 for group in anchor_groups)
                and all(group["cross_basis_ratios"] is None for group in anchor_groups)
                else "fail"
            ),
        },
        {
            "id": "resume.strict_reuse_and_stale_rejection",
            "status": resume_qualification["status"],
        },
        {
            "id": "regression.v3_n0",
            "status": (
                "pass"
                if regression["v3_n0_status"] == "pass"
                and regression["v3_n0_acceptance_result"] == "13/13"
                else "fail"
            ),
        },
        {
            "id": "regression.v3_n1",
            "status": (
                "pass"
                if regression["status"] == "pass"
                and regression["v3_n1_acceptance_result"] == "10/10"
                else "fail"
            ),
        },
        {"id": "models.v2_card_immutability", "status": immutability["status"]},
    ]
    status = "pass" if all(item["status"] == "pass" for item in checks) else "fail"
    existing_runs = sorted((result_directory / "run_reports").glob("run-*.json"))
    invocation_number = len(existing_runs) + 1
    prior_fresh = 0
    prior_reused = 0
    for path in existing_runs:
        prior = _read_json(path)
        prior_fresh += int(prior.get("execution", {}).get("fresh_execution_count", 0))
        prior_reused += int(prior.get("execution", {}).get("safely_reused_count", 0))
    fresh_count = sum(
        count
        for key, count in disposition_counts.items()
        if key.startswith("fresh_execution")
    )
    reused_count = disposition_counts.get("safely_reused", 0)
    report = {
        "schema": CATALOG_REPORT_SCHEMA,
        "milestone": "V3-N2",
        "status": status,
        "created_utc": _utc_now(),
        "repository_commit": repository_commit,
        "repository_worktree_status": run_checked(
            ["git", "status", "--short"], cwd=resolved_root
        ).stdout.splitlines(),
        "environment": _environment_identity(),
        "reference_tools": plan["reference_tools"],
        "plan": {
            "path": "plan.json",
            "sha256": sha256_file(plan_path),
            "plan_hash": plan["plan_hash"],
            "planned_logical_request_count": plan["planned_logical_request_count"],
            "dataset_logical_request_count": plan["dataset_logical_request_count"],
            "comparison_logical_request_count": plan["comparison_logical_request_count"],
            "unique_request_count": plan["unique_request_count"],
            "deduplicated_logical_request_count": plan[
                "deduplicated_logical_request_count"
            ],
            "logical_request_counts": logical_counts,
        },
        "execution": {
            "invocation_number": invocation_number,
            "mode": "resume" if resume else "fresh",
            "fresh_execution_count": fresh_count,
            "safely_reused_count": reused_count,
            "fresh_after_stale_rejection_count": disposition_counts.get(
                "fresh_execution_after_stale_rejection", 0
            ),
            "stale_result_rejection_count": len(stale_rejections),
            "stale_result_rejections": stale_rejections,
            "cumulative_fresh_execution_count": prior_fresh + fresh_count,
            "cumulative_safely_reused_count": prior_reused + reused_count,
        },
        "terminal_status_counts": terminal_counts,
        "coverage": {
            "path": "coverage.json",
            "sha256": sha256_file(result_directory / "coverage.json"),
            **coverage,
        },
        "comparisons": {
            "schema": COMPARISON_SCHEMA,
            "path": "summary/noise_comparisons.json",
            "sha256": sha256_file(
                result_directory / "summary" / "noise_comparisons.json"
            ),
            "threshold_group_count": len(threshold_groups),
            "cross_process_anchor_group_count": len(anchor_groups),
            "cross_basis_ratios_produced": False,
        },
        "summary_artifacts": summaries["artifacts"],
        "resume_qualification": resume_qualification,
        "regressions": regression,
        "model_immutability": immutability,
        "checks": checks,
        "acceptance_result": f"{sum(item['status'] == 'pass' for item in checks)}/{len(checks)}",
        "recommendation": {
            "next_milestone": (
                "v3_release_hardening" if status == "pass" else "v3_n2_remediation"
            ),
            "ready_for_release_hardening": status == "pass",
            "reason": (
                "The frozen method completed the catalog plan with explicit terminal states, "
                "strict reuse identity, and auditable comparison outputs."
                if status == "pass"
                else "Resolve failed V3-N2 checks before release hardening."
            ),
            "process_noise_calibration_authorized": False,
        },
        "claim_boundary": (
            "V3-N2 characterizes existing compact-model predictions. It does not establish "
            "silicon/foundry noise accuracy, universal Vt ordering, or planar/FinFET "
            "effective-width equivalence."
        ),
        "output_directory": str(result_directory),
        "report_path": str(result_directory / "report.json"),
    }
    _write_json(result_directory / "report.json", report)
    run_report_path = result_directory / "run_reports" / f"run-{invocation_number:04d}.json"
    shutil.copyfile(result_directory / "report.json", run_report_path)
    report_sha256 = sha256_file(result_directory / "report.json")
    result = {**report, "report_sha256": report_sha256, "run_report_path": str(run_report_path)}
    if status != "pass":
        failed = [item["id"] for item in checks if item["status"] != "pass"]
        raise NoiseCatalogError(f"V3-N2 failed checks: {failed}")
    return result
