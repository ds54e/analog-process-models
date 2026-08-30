# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Manifest-driven APM v2 Technology/Family/Device catalog.

The compact-model parameter API deliberately does not live here.  This module
describes semantic identity, geometry, operating profiles, and backend binding
mechanics without introducing technology-specific Python loaders.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10 reference environments
    import tomli as tomllib


class CatalogError(RuntimeError):
    """The v2 manifest catalog is incomplete or internally inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CatalogError(f"cannot load catalog manifest {path}: {error}") from error


def _required(data: dict[str, Any], key: str, path: Path) -> Any:
    if key not in data:
        raise CatalogError(f"{path}: required field {key!r} is missing")
    return data[key]


def _tuple_strings(value: Any, field: str, path: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise CatalogError(f"{path}: {field} must be a non-empty string array")
    return tuple(value)


def _optional_float(data: dict[str, Any], key: str, path: Path) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CatalogError(f"{path}: {key} must be numeric when present")
    return float(value)


def _positive_float(value: Any, field: str, path: Path) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0.0:
        raise CatalogError(f"{path}: {field} must be positive")
    return float(value)


def _repo_path(root: Path, value: str, field: str, manifest: Path) -> Path:
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise CatalogError(f"{manifest}: {field} escapes the repository root") from error
    if not candidate.is_file():
        raise CatalogError(f"{manifest}: {field} does not exist: {value}")
    return candidate


@dataclass(frozen=True)
class BiasValidity:
    vgs_min_v: float | None = None
    vgs_max_v: float | None = None
    vds_min_v: float | None = None
    vds_max_v: float | None = None
    vbs_min_v: float | None = None
    vbs_max_v: float | None = None


@dataclass(frozen=True)
class DeviceSpec:
    technology_id: str
    family_id: str
    device_id: str
    polarity: str
    public_name: str
    terminals: tuple[str, ...]
    geometry_kind: str
    parameters: tuple[str, ...]
    lmin_m: float
    lmax_m: float | None
    wmin_m: float | None
    wmax_m: float | None
    default_w_m: float | None
    characterization_lengths_m: tuple[float, ...]
    characterization_nfin: tuple[int, ...]
    bias_validity: BiasValidity

    @property
    def selector(self) -> str:
        return f"{self.technology_id}/{self.family_id}/{self.device_id}"


@dataclass(frozen=True)
class OperatingProfile:
    profile_id: str
    reference_vdd_v: float
    origin: str
    purpose: str
    evidence: str
    temperatures_c: tuple[int, ...]


@dataclass(frozen=True)
class BackendDeviceBinding:
    device_id: str
    native_vector_template: str


@dataclass(frozen=True)
class BackendBinding:
    technology_id: str
    family_id: str
    backend_id: str
    compact_model_native_name: str
    model_library: Path | None
    model_section: str | None
    model_includes: tuple[Path, ...]
    wrapper_path: Path
    osdi_artifacts: tuple[str, ...]
    native_oracle: str
    devices: tuple[BackendDeviceBinding, ...]
    manifest_path: Path
    manifest_sha256: str

    def device(self, device_id: str) -> BackendDeviceBinding:
        for item in self.devices:
            if item.device_id == device_id:
                return item
        raise CatalogError(
            f"backend {self.backend_id} has no binding for "
            f"{self.technology_id}/{self.family_id}/{device_id}"
        )

    def model_source_files(self) -> tuple[Path, ...]:
        library = (self.model_library,) if self.model_library is not None else ()
        return library + self.model_includes


@dataclass(frozen=True)
class ThresholdMethod:
    method: str
    coefficient_a: float
    normalization: str
    vout_low_v: float
    vout_high_fraction_vdd: float


@dataclass(frozen=True)
class CharacterizationPolicy:
    idvg_points: int
    idvd_points: int
    y_frequencies_hz: tuple[float, ...]
    dibl_validation_max_v_per_v: float


@dataclass(frozen=True)
class FamilySpec:
    technology_id: str
    family_id: str
    architecture: str
    compact_model: str
    gate_stack_id: str
    gate_stack_class: str
    threshold_class: str
    origin: str
    upstream_flavor: str | None
    base_family: str | None
    variant_method: str | None
    typical_uses: tuple[str, ...]
    default_operating_profile: str
    operating_profiles: tuple[OperatingProfile, ...]
    devices: tuple[DeviceSpec, ...]
    threshold: ThresholdMethod
    characterization: CharacterizationPolicy
    behavior_targets: dict[str, Any]
    provenance_path: Path
    provenance_sha256: str
    variant_generation_path: Path | None
    variant_generation_sha256: str | None
    backend_bindings: tuple[BackendBinding, ...]
    manifest_path: Path
    manifest_sha256: str

    @property
    def selector(self) -> str:
        return f"{self.technology_id}/{self.family_id}"

    def operating_profile(self, profile_id: str | None = None) -> OperatingProfile:
        selected = profile_id or self.default_operating_profile
        for profile in self.operating_profiles:
            if profile.profile_id == selected:
                return profile
        raise CatalogError(f"{self.selector}: unknown operating profile {selected!r}")

    def backend(self, backend_id: str) -> BackendBinding:
        for binding in self.backend_bindings:
            if binding.backend_id == backend_id:
                return binding
        raise CatalogError(f"{self.selector}: backend {backend_id!r} is not bound")

    def device(self, device_id: str) -> DeviceSpec:
        for item in self.devices:
            if item.device_id == device_id:
                return item
        raise CatalogError(f"{self.selector}: unknown device {device_id!r}")

    def device_for_polarity(self, polarity: str) -> DeviceSpec:
        matches = [item for item in self.devices if item.polarity == polarity]
        if len(matches) != 1:
            raise CatalogError(
                f"{self.selector}: expected one {polarity!r}-polarity device, found {len(matches)}"
            )
        return matches[0]


@dataclass(frozen=True)
class ComparisonSet:
    set_id: str
    kind: str
    members: tuple[str, ...]
    anchor: str | None
    common_overlap_profile: str | None


@dataclass(frozen=True)
class TechnologySpec:
    technology_id: str
    display_name: str
    technology_class: str
    description: str
    cross_process_anchor: str
    comparison_sets: tuple[ComparisonSet, ...]
    families: tuple[FamilySpec, ...]
    manifest_path: Path
    manifest_sha256: str

    def family(self, family_id: str) -> FamilySpec:
        for family in self.families:
            if family.family_id == family_id:
                return family
        raise CatalogError(f"{self.technology_id}: unknown family {family_id!r}")

    def comparison_set(self, set_id: str) -> ComparisonSet:
        for item in self.comparison_sets:
            if item.set_id == set_id:
                return item
        raise CatalogError(f"{self.technology_id}: unknown comparison set {set_id!r}")


@dataclass(frozen=True)
class Catalog:
    root: Path
    technologies: tuple[TechnologySpec, ...]

    def technology(self, technology_id: str) -> TechnologySpec:
        for item in self.technologies:
            if item.technology_id == technology_id:
                return item
        raise CatalogError(f"unknown technology {technology_id!r}")

    def family(self, technology_id: str, family_id: str) -> FamilySpec:
        return self.technology(technology_id).family(family_id)

    def resolve(self, selector: str) -> TechnologySpec | FamilySpec | DeviceSpec:
        parts = tuple(part for part in selector.strip("/").split("/") if part)
        if len(parts) == 1:
            return self.technology(parts[0])
        if len(parts) == 2:
            return self.family(parts[0], parts[1])
        if len(parts) == 3:
            return self.family(parts[0], parts[1]).device(parts[2])
        raise CatalogError(
            "selector must be technology, technology/family, or technology/family/device"
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "apm.catalog-snapshot.v2",
            "technologies": [
                {
                    "technology_id": technology.technology_id,
                    "cross_process_anchor": technology.cross_process_anchor,
                    "manifest_sha256": technology.manifest_sha256,
                    "families": [
                        {
                            "family_id": family.family_id,
                            "manifest_sha256": family.manifest_sha256,
                            "devices": [asdict(device) for device in family.devices],
                        }
                        for family in technology.families
                    ],
                }
                for technology in self.technologies
            ],
        }


def _load_backend_binding(
    root: Path, path: Path, technology_id: str, family_id: str
) -> BackendBinding:
    data = _load_toml(path)
    if data.get("schema") != "apm.backend-binding.v2":
        raise CatalogError(f"{path}: unsupported backend-binding schema")
    if data.get("technology_id") != technology_id or data.get("family_id") != family_id:
        raise CatalogError(f"{path}: backend identity does not match its family")
    model_library_value = data.get("model_library")
    model_library = (
        _repo_path(root, model_library_value, "model_library", path)
        if model_library_value
        else None
    )
    model_section = data.get("model_section")
    if (model_library is None) != (model_section is None):
        raise CatalogError(f"{path}: model_library and model_section must be set together")
    includes = tuple(
        _repo_path(root, value, "model_includes", path) for value in data.get("model_includes", [])
    )
    devices_data = data.get("device", {})
    if not isinstance(devices_data, dict) or not devices_data:
        raise CatalogError(f"{path}: backend device bindings are missing")
    devices = tuple(
        BackendDeviceBinding(
            device_id=device_id,
            native_vector_template=str(_required(item, "native_vector_template", path)),
        )
        for device_id, item in sorted(devices_data.items())
    )
    return BackendBinding(
        technology_id=technology_id,
        family_id=family_id,
        backend_id=str(_required(data, "backend", path)),
        compact_model_native_name=str(_required(data, "compact_model_native_name", path)),
        model_library=model_library,
        model_section=str(model_section) if model_section is not None else None,
        model_includes=includes,
        wrapper_path=_repo_path(root, str(_required(data, "wrapper", path)), "wrapper", path),
        osdi_artifacts=tuple(str(item) for item in data.get("osdi_artifacts", [])),
        native_oracle=str(_required(data, "native_oracle", path)),
        devices=devices,
        manifest_path=path,
        manifest_sha256=sha256_file(path),
    )


def _load_family(root: Path, path: Path, technology_id: str) -> FamilySpec:
    data = _load_toml(path)
    if data.get("schema") != "apm.family.v2":
        raise CatalogError(f"{path}: unsupported family schema")
    if data.get("technology_id") != technology_id:
        raise CatalogError(f"{path}: technology_id does not match containing technology")
    family_id = str(_required(data, "id", path))
    if path.parent.name != family_id:
        raise CatalogError(f"{path}: family id must match its directory name")
    architecture = str(_required(data, "architecture", path))
    if architecture not in {"planar_bulk", "finfet"}:
        raise CatalogError(f"{path}: unsupported architecture {architecture!r}")

    profiles_data = data.get("operating_profile", [])
    if not isinstance(profiles_data, list) or not profiles_data:
        raise CatalogError(f"{path}: at least one operating_profile is required")
    profiles = tuple(
        OperatingProfile(
            profile_id=str(_required(item, "id", path)),
            reference_vdd_v=_positive_float(
                _required(item, "reference_vdd_v", path), "reference_vdd_v", path
            ),
            origin=str(_required(item, "origin", path)),
            purpose=str(_required(item, "purpose", path)),
            evidence=str(_required(item, "evidence", path)),
            temperatures_c=tuple(int(value) for value in _required(item, "temperatures_c", path)),
        )
        for item in profiles_data
    )
    if any(profile.temperatures_c != (-40, 27, 85, 125) for profile in profiles):
        raise CatalogError(f"{path}: release profiles must use -40/27/85/125 degC")

    devices_data = data.get("device", [])
    if not isinstance(devices_data, list) or not devices_data:
        raise CatalogError(f"{path}: at least one device is required")
    devices: list[DeviceSpec] = []
    for item in devices_data:
        device_id = str(_required(item, "id", path))
        geometry_kind = str(_required(item, "geometry_kind", path))
        parameters = _tuple_strings(_required(item, "parameters", path), "parameters", path)
        if geometry_kind == "planar" and parameters != ("w", "l"):
            raise CatalogError(f"{path}: planar {device_id} parameters must be w,l")
        if geometry_kind == "finfet" and parameters != ("l", "nfin"):
            raise CatalogError(f"{path}: FinFET {device_id} parameters must be l,nfin")
        raw_nfin = item.get("characterization_nfin", [])
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in raw_nfin
        ):
            raise CatalogError(f"{path}: {device_id} nfin values must be positive integers")
        lengths = tuple(
            _positive_float(value, "characterization_lengths_m", path)
            for value in _required(item, "characterization_lengths_m", path)
        )
        lmin = _positive_float(_required(item, "lmin_m", path), "lmin_m", path)
        if lmin not in lengths:
            raise CatalogError(f"{path}: {device_id} characterization lengths must include lmin")
        validity_data = item.get("bias_validity", {})
        devices.append(
            DeviceSpec(
                technology_id=technology_id,
                family_id=family_id,
                device_id=device_id,
                polarity=str(_required(item, "polarity", path)),
                public_name=str(_required(item, "public_name", path)),
                terminals=_tuple_strings(_required(item, "terminals", path), "terminals", path),
                geometry_kind=geometry_kind,
                parameters=parameters,
                lmin_m=lmin,
                lmax_m=_optional_float(item, "lmax_m", path),
                wmin_m=_optional_float(item, "wmin_m", path),
                wmax_m=_optional_float(item, "wmax_m", path),
                default_w_m=_optional_float(item, "default_w_m", path),
                characterization_lengths_m=lengths,
                characterization_nfin=tuple(raw_nfin),
                bias_validity=BiasValidity(
                    vgs_min_v=_optional_float(validity_data, "vgs_min_v", path),
                    vgs_max_v=_optional_float(validity_data, "vgs_max_v", path),
                    vds_min_v=_optional_float(validity_data, "vds_min_v", path),
                    vds_max_v=_optional_float(validity_data, "vds_max_v", path),
                    vbs_min_v=_optional_float(validity_data, "vbs_min_v", path),
                    vbs_max_v=_optional_float(validity_data, "vbs_max_v", path),
                ),
            )
        )
    if len({device.device_id for device in devices}) != len(devices):
        raise CatalogError(f"{path}: duplicate device IDs")
    if len({device.public_name for device in devices}) != len(devices):
        raise CatalogError(f"{path}: duplicate public device names")
    if any(device.terminals != ("d", "g", "s", "b") for device in devices):
        raise CatalogError(f"{path}: v2 common terminal order must be d,g,s,b")

    threshold_data = _required(data, "threshold", path)
    characterization_data = _required(data, "characterization", path)
    origin = str(_required(data, "origin", path))
    if origin not in {"upstream_model", "apm_authored", "apm_derived_variant"}:
        raise CatalogError(f"{path}: unsupported family origin {origin!r}")
    base_family = data.get("base_family")
    variant_method = data.get("variant_method")
    variant_generation_value = data.get("variant_generation")
    if origin == "apm_derived_variant":
        if not isinstance(base_family, str) or not base_family:
            raise CatalogError(f"{path}: derived family requires base_family")
        if not isinstance(variant_method, str) or not variant_method:
            raise CatalogError(f"{path}: derived family requires variant_method")
        if not isinstance(variant_generation_value, str) or not variant_generation_value:
            raise CatalogError(f"{path}: derived family requires variant_generation")
    elif any(value is not None for value in (base_family, variant_method, variant_generation_value)):
        raise CatalogError(f"{path}: only derived families may define variant-generation fields")
    provenance_path = _repo_path(root, str(_required(data, "provenance", path)), "provenance", path)
    variant_generation_path = (
        _repo_path(root, variant_generation_value, "variant_generation", path)
        if variant_generation_value is not None
        else None
    )
    binding_paths = tuple(
        _repo_path(root, value, "backend_bindings", path)
        for value in _required(data, "backend_bindings", path)
    )
    bindings = tuple(
        _load_backend_binding(root, binding_path, technology_id, family_id)
        for binding_path in binding_paths
    )
    if len({binding.backend_id for binding in bindings}) != len(bindings):
        raise CatalogError(f"{path}: duplicate backend binding IDs")
    for binding in bindings:
        if {item.device_id for item in binding.devices} != {item.device_id for item in devices}:
            raise CatalogError(f"{binding.manifest_path}: device binding set does not match family")

    return FamilySpec(
        technology_id=technology_id,
        family_id=family_id,
        architecture=architecture,
        compact_model=str(_required(data, "compact_model", path)),
        gate_stack_id=str(_required(data, "gate_stack_id", path)),
        gate_stack_class=str(_required(data, "gate_stack_class", path)),
        threshold_class=str(_required(data, "threshold_class", path)),
        origin=origin,
        upstream_flavor=data.get("upstream_flavor"),
        base_family=base_family,
        variant_method=variant_method,
        typical_uses=tuple(str(value) for value in data.get("typical_uses", [])),
        default_operating_profile=str(_required(data, "default_operating_profile", path)),
        operating_profiles=profiles,
        devices=tuple(devices),
        threshold=ThresholdMethod(
            method=str(_required(threshold_data, "method", path)),
            coefficient_a=_positive_float(
                _required(threshold_data, "coefficient_a", path), "threshold coefficient", path
            ),
            normalization=str(_required(threshold_data, "normalization", path)),
            vout_low_v=_positive_float(
                _required(threshold_data, "vout_low_v", path), "vout_low_v", path
            ),
            vout_high_fraction_vdd=_positive_float(
                _required(threshold_data, "vout_high_fraction_vdd", path),
                "vout_high_fraction_vdd",
                path,
            ),
        ),
        characterization=CharacterizationPolicy(
            idvg_points=int(_required(characterization_data, "idvg_points", path)),
            idvd_points=int(_required(characterization_data, "idvd_points", path)),
            y_frequencies_hz=tuple(
                float(value) for value in _required(characterization_data, "y_frequencies_hz", path)
            ),
            dibl_validation_max_v_per_v=float(
                characterization_data.get("dibl_validation_max_v_per_v", 0.5)
            ),
        ),
        behavior_targets=dict(data.get("behavior_targets", {})),
        provenance_path=provenance_path,
        provenance_sha256=sha256_file(provenance_path),
        variant_generation_path=variant_generation_path,
        variant_generation_sha256=(
            sha256_file(variant_generation_path)
            if variant_generation_path is not None
            else None
        ),
        backend_bindings=bindings,
        manifest_path=path,
        manifest_sha256=sha256_file(path),
    )


def _load_technology(root: Path, path: Path) -> TechnologySpec:
    data = _load_toml(path)
    if data.get("schema") != "apm.technology.v2":
        raise CatalogError(f"{path}: unsupported technology schema")
    technology_id = str(_required(data, "id", path))
    if path.parent.name != technology_id:
        raise CatalogError(f"{path}: technology id must match its directory name")
    family_manifests = sorted((path.parent / "families").glob("*/family.toml"))
    if not family_manifests:
        raise CatalogError(f"{path}: no family manifests discovered")
    families = tuple(_load_family(root, item, technology_id) for item in family_manifests)
    if len({family.family_id for family in families}) != len(families):
        raise CatalogError(f"{path}: duplicate family IDs")
    family_ids = {family.family_id for family in families}
    for family in families:
        if family.base_family is not None and family.base_family not in family_ids:
            raise CatalogError(
                f"{family.manifest_path}: base family {family.base_family!r} is not present"
            )
        if family.base_family == family.family_id:
            raise CatalogError(f"{family.manifest_path}: a family cannot derive from itself")

    comparison_sets_data = data.get("comparison_set", [])
    sets = tuple(
        ComparisonSet(
            set_id=str(_required(item, "id", path)),
            kind=str(_required(item, "kind", path)),
            members=_tuple_strings(_required(item, "members", path), "members", path),
            anchor=item.get("anchor"),
            common_overlap_profile=item.get("common_overlap_profile"),
        )
        for item in comparison_sets_data
    )
    anchor = str(_required(data, "cross_process_anchor", path))
    if anchor not in family_ids:
        raise CatalogError(f"{path}: cross-process anchor {anchor!r} is not a family")
    for item in sets:
        if not set(item.members).issubset(family_ids):
            raise CatalogError(f"{path}: comparison set {item.set_id!r} has unknown members")
        if item.anchor is not None and item.anchor not in item.members:
            raise CatalogError(f"{path}: comparison anchor must be a member")
    return TechnologySpec(
        technology_id=technology_id,
        display_name=str(_required(data, "display_name", path)),
        technology_class=str(_required(data, "technology_class", path)),
        description=str(_required(data, "description", path)),
        cross_process_anchor=anchor,
        comparison_sets=sets,
        families=families,
        manifest_path=path,
        manifest_sha256=sha256_file(path),
    )


def load_catalog(root: Path) -> Catalog:
    selected = root.expanduser().resolve()
    manifests = sorted((selected / "models").glob("*/technology.toml"))
    if not manifests:
        raise CatalogError(f"no APM v2 technology manifests found under {selected / 'models'}")
    technologies = tuple(_load_technology(selected, path) for path in manifests)
    if len({item.technology_id for item in technologies}) != len(technologies):
        raise CatalogError("duplicate technology IDs in catalog")
    public_names = [
        device.public_name
        for technology in technologies
        for family in technology.families
        for device in family.devices
    ]
    if len(set(public_names)) != len(public_names):
        raise CatalogError("public device names must be unique across the v2 catalog")
    return Catalog(root=selected, technologies=technologies)
