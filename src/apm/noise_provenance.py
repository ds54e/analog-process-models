# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Engine-specific effective noise-parameter provenance for V3-N0."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from .characterize import CharacterizationKit
from .model_build import sha256_file

SHOWMOD_BEGIN = "APM_NOISE_SHOWMOD_BEGIN"
SHOWMOD_END = "APM_NOISE_SHOWMOD_END"

ENGINE_PARAMETERS: dict[str, tuple[tuple[str, str], ...]] = {
    "bsim3": (
        ("noimod", "thermal_and_flicker_model_selector"),
        ("noia", "flicker_coefficient"),
        ("noib", "flicker_coefficient"),
        ("noic", "flicker_coefficient"),
        ("em", "flicker_model_field_parameter"),
        ("ef", "flicker_frequency_exponent"),
        ("af", "flicker_current_exponent"),
        ("kf", "flicker_coefficient"),
        ("lintnoi", "flicker_effective_length_offset"),
    ),
    "bsim4": (
        ("fnoimod", "flicker_model_selector"),
        ("tnoimod", "thermal_model_selector"),
        ("noia", "flicker_coefficient"),
        ("noib", "flicker_coefficient"),
        ("noic", "flicker_coefficient"),
        ("em", "flicker_model_field_parameter"),
        ("ef", "flicker_frequency_exponent"),
        ("af", "flicker_current_exponent"),
        ("kf", "flicker_coefficient"),
        ("lintnoi", "flicker_effective_length_offset"),
        ("tnoia", "thermal_noise_coefficient"),
        ("tnoib", "thermal_noise_coefficient"),
        ("tnoic", "thermal_noise_coefficient"),
        ("rnoia", "induced_gate_noise_coefficient"),
        ("rnoib", "induced_gate_noise_coefficient"),
        ("rnoic", "noise_correlation_coefficient"),
        ("ntnoi", "thermal_noise_exponent"),
    ),
    "psp103": (
        ("fnto", "thermal_noise_coefficient"),
        ("fntexcl", "excess_thermal_noise_length_coefficient"),
        ("nfalw", "flicker_coefficient"),
        ("nfblw", "flicker_coefficient"),
        ("nfclw", "flicker_coefficient"),
        ("efo", "flicker_frequency_exponent"),
        ("lintnoi", "flicker_effective_length_offset"),
        ("alpnoi", "flicker_length_offset_exponent"),
        ("swigate", "gate_current_noise_enabler"),
        ("swjuncap", "junction_noise_mode_selector"),
        ("swedge", "edge_transistor_noise_enabler"),
        ("fntedge", "edge_thermal_noise_coefficient"),
        ("nfaedge", "edge_flicker_coefficient"),
        ("nfbedge", "edge_flicker_coefficient"),
        ("nfcedge", "edge_flicker_coefficient"),
        ("efedge", "edge_flicker_frequency_exponent"),
    ),
    "bsim_cmg": (
        ("tnoimod", "thermal_and_correlation_model_selector"),
        ("fnmod", "flicker_model_selector"),
        ("ef", "flicker_frequency_exponent"),
        ("noia", "flicker_coefficient"),
        ("noib", "flicker_coefficient"),
        ("noic", "flicker_coefficient"),
        ("k0noi", "flicker_drain_factor"),
        ("noia2", "subthreshold_flicker_coefficient"),
        ("qsref", "flicker_transition_charge"),
        ("rnoia", "channel_thermal_noise_coefficient"),
        ("tnoia", "channel_thermal_length_coefficient"),
        ("rnoib", "induced_gate_noise_coefficient"),
        ("tnoib", "induced_gate_noise_length_coefficient"),
        ("rnoic", "noise_correlation_coefficient"),
        ("tnoic", "noise_correlation_length_coefficient"),
        ("tnoik", "low_current_thermal_noise_coefficient"),
        ("rdsmod", "series_resistance_noise_mode"),
        ("rgatemod", "gate_resistance_noise_mode"),
        ("igcmod", "gate_channel_shot_noise_enabler"),
        ("igbmod", "gate_bulk_shot_noise_enabler"),
    ),
}

DEFAULT_DECLARATION_FILES = {
    "psp103": Path("models/apm130/vendor/psp103/PSP103_parlist.include"),
    "bsim_cmg": Path(
        "models/apm016f/vendor/bsim-cmg-112.1.0/code/bsimcmg_parameters.include"
    ),
}

# ngspice 47's BSIM4v5 showmod handler returns an error sentinel for LINTNOI
# even though the runtime model initializes and uses the documented zero
# default.  Keep this narrowly scoped; other native parameters remain final-
# value interrogated rather than being copied into a universal parameter API.
NATIVE_SHOWMOD_FALLBACKS: dict[str, dict[str, int | float]] = {
    "bsim4": {"lintnoi": 0.0},
}


class NoiseProvenanceError(RuntimeError):
    """An effective noise parameter could not be audited honestly."""


def showmod_control_line(compact_model: str) -> str:
    if compact_model not in ENGINE_PARAMETERS:
        raise NoiseProvenanceError(f"no noise snapshot adapter for {compact_model!r}")
    device_class = "m" if compact_model in {"bsim3", "bsim4"} else "n"
    parameters = " ".join(name for name, _role in ENGINE_PARAMETERS[compact_model])
    return f"showmod {device_class} : {parameters}"


def _parse_numeric(token: str) -> int | float | str:
    cleaned = token.strip().rstrip(",)")
    if cleaned and set(cleaned) == {"?"}:
        return "unknown"
    try:
        value = float(cleaned)
    except ValueError:
        return cleaned
    if value.is_integer() and not any(character in cleaned.lower() for character in (".", "e")):
        return int(value)
    return value


def parse_showmod_values(log_text: str, compact_model: str) -> dict[str, int | float | str]:
    requested = {name for name, _role in ENGINE_PARAMETERS[compact_model]}
    if SHOWMOD_BEGIN in log_text and SHOWMOD_END in log_text:
        section = log_text.split(SHOWMOD_BEGIN, 1)[1].split(SHOWMOD_END, 1)[0]
    else:
        section = log_text
    values: dict[str, int | float | str] = {}
    for line in section.splitlines():
        match = re.match(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s+(\S+)\s*$", line)
        if match and match.group(1).lower() in requested:
            values[match.group(1).lower()] = _parse_numeric(match.group(2))
            continue
        unavailable = re.match(
            r"^\s*([A-Za-z][A-Za-z0-9_]*)\s+<<NAN,\s*error\s*=\s*\d+>>\s*$",
            line,
            re.IGNORECASE,
        )
        if unavailable and unavailable.group(1).lower() in requested:
            values[unavailable.group(1).lower()] = "backend_unavailable"
    missing = sorted(requested - values.keys())
    if missing:
        raise NoiseProvenanceError(
            f"ngspice showmod omitted required {compact_model} noise parameters: {missing}"
        )
    return values


def _source_closure(root: Path, initial: tuple[Path, ...]) -> tuple[Path, ...]:
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
            candidate = Path(match.group(1))
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            if candidate.is_file():
                pending.append(candidate)
    return tuple(sorted(discovered))


def _assignment_occurrences(paths: tuple[Path, ...], parameter: str, root: Path) -> list[dict[str, Any]]:
    pattern = re.compile(rf"\b{re.escape(parameter)}\s*=\s*([^\s]+)", re.IGNORECASE)
    result: list[dict[str, Any]] = []
    for path in paths:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            for match in pattern.finditer(line):
                token = match.group(1).rstrip(",)")
                result.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "line": line_number,
                        "raw_value": token,
                        "parsed_value": _parse_numeric(token),
                    }
                )
    return result


def _matches_effective(candidate: Any, effective: Any) -> bool:
    if isinstance(candidate, (int, float)) and isinstance(effective, (int, float)):
        return math.isclose(float(candidate), float(effective), rel_tol=1e-9, abs_tol=1e-30)
    return str(candidate).lower() == str(effective).lower()


def _default_declarations(
    root: Path, compact_model: str
) -> dict[str, dict[str, Any]]:
    relative = DEFAULT_DECLARATION_FILES.get(compact_model)
    if relative is None:
        return {}
    path = root / relative
    result: dict[str, dict[str, Any]] = {}
    macro = re.compile(
        r"`(?:MPR|MPI|BPR)[A-Za-z0-9_]*\(\s*([A-Za-z][A-Za-z0-9_]*)\s*,\s*([^,]+),"
    )
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
    ):
        match = macro.search(line)
        if not match:
            continue
        name = match.group(1).lower()
        raw_default = match.group(2).strip()
        result[name] = {
            "path": relative.as_posix(),
            "line": line_number,
            "file_sha256": sha256_file(path),
            "raw_default": raw_default,
            "parsed_default": _parse_numeric(raw_default),
        }
    return result


def build_noise_model_snapshot(
    *,
    kit: CharacterizationKit,
    log_text: str,
    ngspice_version: str,
) -> dict[str, Any]:
    """Bind final backend values to explicit cards or pinned model defaults."""

    root = kit.provenance_path.parents[2]
    values = parse_showmod_values(log_text, kit.compact_model)
    source_files = _source_closure(root, kit.model_source_files())
    defaults = _default_declarations(root, kit.compact_model)
    parameters: list[dict[str, Any]] = []
    for name, role in ENGINE_PARAMETERS[kit.compact_model]:
        interrogated = values[name]
        selector_not_applicable = (
            kit.compact_model == "bsim4"
            and name in {"tnoic", "rnoic"}
            and values.get("tnoimod") != 2
        )
        fallback = NATIVE_SHOWMOD_FALLBACKS.get(kit.compact_model, {}).get(name)
        effective = (
            fallback
            if interrogated == "backend_unavailable" and fallback is not None
            else interrogated
        )
        occurrences = _assignment_occurrences(source_files, name, root)
        matching = [
            item for item in occurrences if _matches_effective(item["parsed_value"], effective)
        ]
        if selector_not_applicable:
            value_source = "derived_by_model"
            origin = kit.compact_model
            method = "not_applicable_for_effective_model_selector"
        elif matching:
            value_source = (
                "explicit_model_card" if kit.model_origin == "upstream_model" else "explicit_apm_card"
            )
            origin = "upstream" if kit.model_origin == "upstream_model" else "apm"
            method = "ngspice_showmod_final_value_plus_model_card_match"
        elif kit.compact_model in {"bsim3", "bsim4"} and effective != "unknown":
            value_source = "backend_resolved_default"
            origin = kit.compact_model
            method = (
                "ngspice47_bsim4_runtime_default_fallback_after_showmod_error"
                if interrogated == "backend_unavailable"
                else "ngspice_showmod_final_value"
            )
        elif name in defaults and effective != "unknown":
            value_source = "compact_model_default"
            origin = "psp103" if kit.compact_model == "psp103" else "bsim_cmg"
            method = "ngspice_osdi_showmod_final_value_plus_vendored_default_declaration"
        else:
            value_source = "unknown"
            origin = "unknown"
            method = "unresolved"
        parameters.append(
            {
                "name": name,
                "role": role,
                "effective_value": (
                    None if effective in {"unknown", "backend_unavailable"} else effective
                ),
                "resolution_status": (
                    "not_applicable"
                    if selector_not_applicable
                    else "resolved"
                    if effective not in {"unknown", "backend_unavailable"}
                    else "unknown"
                ),
                "backend_interrogated_value": interrogated,
                "value_source": value_source,
                "origin": origin,
                "resolution_method": method,
                "matching_explicit_locations": matching,
                "other_card_occurrences": [item for item in occurrences if item not in matching],
                "compact_model_default_declaration": defaults.get(name),
            }
        )
    unresolved = [
        item["name"]
        for item in parameters
        if item["resolution_status"] not in {"resolved", "not_applicable"}
    ]
    return {
        "schema": "apm.noise-model-snapshot.v1",
        "technology_id": kit.technology_id,
        "family_id": kit.family_id,
        "compact_model": kit.compact_model,
        "model_origin": kit.model_origin,
        "backend": "ngspice",
        "backend_version_output": ngspice_version,
        "interrogation_method": "ngspice showmod targeted effective-value query",
        "interrogation_adequate": not unresolved,
        "effective_parameter_snapshot_available": not unresolved,
        "source_files": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
            }
            for path in source_files
        ],
        "parameters": parameters,
        "unresolved_parameters": unresolved,
    }
