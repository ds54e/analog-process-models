# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed structural audit for APM v2's model-only Spectre layer."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib

from .catalog import load_catalog


class SpectreStructureError(RuntimeError):
    """Raised when a required Spectre model-only structural check fails."""


ROOT = Path(__file__).resolve().parents[2]
VARIATION_FILE = Path("variation/spectre/benchmark_variation.scs")
PASSIVE_FILE = Path("passives/spectre/benchmark_passives.scs")
DOCUMENTATION_FILE = Path("docs/spectre.md")
LOCAL_NAMES = {
    "apm__mos_vth_local_z",
    "apm__mos_drive_local_z",
    "apm__r_local_z",
    "apm__c_local_z",
}
CORNER_ORDER = ("bench_tt", "bench_ff", "bench_ss", "bench_fs", "bench_sf")


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SpectreStructureError(message)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _subckt_block(text: str, name: str) -> str:
    match = re.search(
        rf"(?msi)^subckt\s+{re.escape(name)}\s+\(d\s+g\s+s\s+b\)\s*$"
        rf"(?P<body>.*?)^ends\s+{re.escape(name)}\s*$",
        text,
    )
    if match is None:
        raise SpectreStructureError(f"missing four-terminal Spectre subckt {name}")
    return match.group(0)


def _section_block(text: str, name: str) -> str:
    match = re.search(
        rf"(?msi)^section\s+{re.escape(name)}\s*$"
        rf"(?P<body>.*?)^endsection\s+{re.escape(name)}\s*$",
        text,
    )
    if match is None:
        raise SpectreStructureError(f"missing Spectre section {name}")
    return match.group(0)


def _parameter_assignments(line: str) -> dict[str, str]:
    return {
        name.lower(): value
        for name, value in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)", line)
    }


def _parameter_value(block: str, name: str) -> float:
    match = re.search(
        rf"(?mi)^parameters\s+[^\n]*\b{re.escape(name)}=([-+0-9.eE]+)(?:\s|$)",
        block,
    )
    if match is None:
        raise SpectreStructureError(f"missing Spectre parameter {name}")
    return float(match.group(1))


def _generator_check(root: Path, tool: str) -> str:
    command = [sys.executable, str(root / tool), "--check"]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    _require(result.returncode == 0, result.stderr.strip() or f"{tool} check failed")
    return result.stdout.strip()


def _expected_global_names(technologies: list[str]) -> set[str]:
    return {
        f"apm_bench_{technology}_{polarity}_{intent}_global_z"
        for technology in technologies
        for polarity in ("n", "p")
        for intent in ("vth", "drive")
    } | {"apm_bench_r_global_z", "apm_bench_c_global_z"}


def _check_family_bindings(root: Path) -> dict[str, Any]:
    catalog = load_catalog(root)
    adapters = _load_toml(root / "variation/adapters_v2.toml")["family"]
    benchmark = _load_toml(root / "variation/benchmark_v2.toml")
    family_details: dict[str, Any] = {}
    for technology in catalog.technologies:
        for family in technology.families:
            selector = family.selector
            binding = family.backend("spectre")
            metadata = _load_toml(binding.manifest_path)
            _require(
                metadata.get("status") == "experimental_unverified"
                and metadata.get("real_tool_validation") is False,
                f"{selector}: Spectre binding overstates validation",
            )
            _require(
                not binding.osdi_artifacts,
                f"{selector}: Spectre binding must not depend on ngspice OSDI",
            )
            path = binding.wrapper_path
            _require(path.is_file(), f"{selector}: missing Spectre wrapper")
            text = path.read_text(encoding="utf-8")
            compact = _compact(text)
            _require("EXPERIMENTAL / UNVERIFIED" in text, f"{selector}: missing banner")
            _require("simulator lang=spectre" in text, f"{selector}: missing language")
            adapter = adapters[selector]
            device_details: dict[str, Any] = {}
            for device in family.devices:
                block = _subckt_block(text, device.public_name)
                parameter_lines = [
                    line.strip()
                    for line in block.splitlines()
                    if line.strip().lower().startswith("parameters ")
                ]
                _require(parameter_lines, f"{device.public_name}: missing parameters")
                public = tuple(_parameter_assignments(parameter_lines[0]))
                _require(
                    public == device.parameters,
                    f"{device.public_name}: public parameters {public} != {device.parameters}",
                )
                _require(
                    not ({"m", "nf", "ng"} & set(public)),
                    f"{device.public_name}: forbidden public multiplicity/finger sizing",
                )
                all_parameters = {
                    name for line in parameter_lines for name in _parameter_assignments(line)
                }
                internal = all_parameters - set(public)
                _require(
                    all(name.startswith("apm__") for name in internal),
                    f"{device.public_name}: non-reserved internal parameter",
                )
                device_adapter = adapter["device"][device.device_id]
                coefficients = {
                    "apm__vth_adapter_a": float(device_adapter["vth_fit_linear"]),
                    "apm__vth_adapter_b": float(device_adapter["vth_fit_quadratic"]),
                    "apm__drive_adapter_a": float(device_adapter["drive_fit_linear"]),
                    "apm__drive_adapter_b": float(device_adapter["drive_fit_quadratic"]),
                }
                for name, expected in coefficients.items():
                    _require(
                        math.isclose(
                            _parameter_value(block, name),
                            expected,
                            rel_tol=0.0,
                            abs_tol=0.0,
                        ),
                        f"{device.public_name}: {name} drifted from adapters_v2.toml",
                    )
                global_prefix = f"apm_bench_{technology.technology_id}_{device.polarity}"
                _require(
                    f"{global_prefix}_vth_global_z" in block
                    and f"{global_prefix}_drive_global_z" in block,
                    f"{device.public_name}: wrong Benchmark Global latent scope",
                )
                _require(
                    "apm__mos_vth_local_z/sqrt(apm__match_size)" in compact
                    and "apm__mos_drive_local_z/sqrt(apm__match_size)" in compact,
                    f"{device.public_name}: Benchmark Local size law is missing",
                )
                _require(
                    f"{adapter['vth_raw_parameter'].lower()}=apm__vth_raw" in compact
                    and f"{adapter['drive_raw_parameter'].lower()}=apm__drive_raw" in compact,
                    f"{device.public_name}: calibrated raw handles are missing",
                )
                _require(
                    "min(" not in compact and "max(" not in compact,
                    f"{device.public_name}: adapter silently clips",
                )
                _require(
                    str(metadata["device"][device.device_id]["native_model"]).lower()
                    in block.lower(),
                    f"{device.public_name}: native model identity is missing",
                )
                device_details[device.device_id] = {
                    "public_name": device.public_name,
                    "parameters": list(public),
                    "adapter_coefficients": coefficients,
                    "native_model": metadata["device"][device.device_id]["native_model"],
                }
            for source in binding.model_source_files():
                _require(source.is_file(), f"{selector}: missing Spectre model source {source}")
            family_details[selector] = {
                "binding": str(binding.manifest_path.relative_to(root)),
                "binding_sha256": binding.manifest_sha256,
                "artifact": str(path.relative_to(root)),
                "artifact_sha256": _sha256(path),
                "compact_model_native_name": binding.compact_model_native_name,
                "devices": device_details,
            }
    _require(len(family_details) == 15, "Spectre family coverage is not 15")
    _require(
        sum(len(item["devices"]) for item in family_details.values()) == 30,
        "Spectre device coverage is not 30",
    )
    _require(
        float(benchmark["mos"]["global"]["drive_shift_sigma"]) == 0.03,
        "Spectre generation is not bound to frozen v2 benchmark configuration",
    )
    return {"family_count": 15, "device_count": 30, "families": family_details}


def _check_variation(root: Path) -> dict[str, Any]:
    path = root / VARIATION_FILE
    text = path.read_text(encoding="utf-8")
    _require("EXPERIMENTAL / UNVERIFIED" in text, "variation banner is missing")
    _require("library apm_benchmark_variation_v2" in text, "v2 variation library missing")
    for phrase in (
        "Benchmark Global = Spectre montecarlo variations=process",
        "Benchmark Local = Spectre montecarlo variations=mismatch",
        "Benchmark All = Spectre montecarlo variations=all",
    ):
        _require(phrase in text, f"variation mode mapping missing: {phrase}")
    catalog = load_catalog(root)
    technologies = [item.technology_id for item in catalog.technologies]
    expected_global = _expected_global_names(technologies)
    mc = _section_block(text, "bench_mc")
    process_match = re.search(r"(?ms)process\s*\{(?P<body>.*?)\}", mc)
    mismatch_match = re.search(r"(?ms)mismatch\s*\{(?P<body>.*?)\}", mc)
    _require(process_match is not None and mismatch_match is not None, "statistics blocks missing")
    process_names = set(
        re.findall(
            r"(?m)^\s*vary\s+(\w+)\s+dist=gauss\s+std=1\s+percent=no\s*$",
            process_match.group("body"),  # type: ignore[union-attr]
        )
    )
    mismatch_names = set(
        re.findall(
            r"(?m)^\s*vary\s+(\w+)\s+dist=gauss\s+std=1\s+percent=no\s*$",
            mismatch_match.group("body"),  # type: ignore[union-attr]
        )
    )
    _require(process_names == expected_global, "Benchmark Global variables are incomplete")
    _require(mismatch_names == LOCAL_NAMES, "Benchmark Local variables are incomplete")
    _require("correlate" not in mc.lower(), "undocumented Spectre correlation is present")
    benchmark = _load_toml(root / "variation/benchmark_v2.toml")
    corner_keys = {
        "vth": {"n": "vth_n_sigma", "p": "vth_p_sigma"},
        "drive": {"n": "drive_n_sigma", "p": "drive_p_sigma"},
    }
    for corner in CORNER_ORDER:
        block = _section_block(text, corner)
        expected = benchmark["corner"][corner]
        for technology in technologies:
            for polarity in ("n", "p"):
                for intent in ("vth", "drive"):
                    name = f"apm_bench_{technology}_{polarity}_{intent}_global_z"
                    _require(
                        _parameter_value(block, name)
                        == float(expected[corner_keys[intent][polarity]]),
                        f"{corner}: {name} differs from benchmark_v2.toml",
                    )
        for name in LOCAL_NAMES:
            _require(_parameter_value(block, name) == 0.0, f"{corner}: {name} is not zero")
    return {
        "artifact": str(VARIATION_FILE),
        "sha256": _sha256(path),
        "global_variables": sorted(expected_global),
        "local_variables": sorted(LOCAL_NAMES),
        "modes": ["global", "local", "all"],
        "spectre_native_mode_mapping": {
            "global": "process",
            "local": "mismatch",
            "all": "all",
        },
        "corners": list(CORNER_ORDER),
    }


def _check_passives(root: Path) -> dict[str, Any]:
    path = root / PASSIVE_FILE
    text = path.read_text(encoding="utf-8")
    compact = _compact(text)
    config = _load_toml(root / "passives/benchmark_v2.toml")
    _require("EXPERIMENTAL / UNVERIFIED" in text, "passive banner is missing")
    details: dict[str, Any] = {}
    for name, kind, global_name, local_name, primitive in (
        ("Rbench", "resistor", "apm_bench_r_global_z", "apm__r_local_z", "r"),
        ("Cbench", "capacitor", "apm_bench_c_global_z", "apm__c_local_z", "c"),
    ):
        match = re.search(
            rf"(?msi)^subckt\s+{name}\s+\(p\s+n\)\s*$(?P<body>.*?)^ends\s+{name}\s*$",
            text,
        )
        _require(match is not None, f"missing Spectre passive {name}")
        block = match.group(0)  # type: ignore[union-attr]
        first = next(
            line.strip() for line in block.splitlines() if line.strip().startswith("parameters ")
        )
        _require(
            tuple(_parameter_assignments(first)) == ("value", "tc1", "match_size"),
            f"{name}: public parameter contract drifted",
        )
        sigma_global = float(config[kind]["global_sigma"])
        sigma_local = float(config[kind]["local_sigma_ref"])
        block_compact = _compact(block)
        _require(global_name in block and local_name in block, f"{name}: latents missing")
        _require("/sqrt(match_size)" in block_compact, f"{name}: size law missing")
        _require(f"{primitive}=value*apm__" in block_compact, f"{name}: value not resolved")
        _require(
            "tc1=tc1" in block_compact and "tnom=27" in block_compact,
            f"{name}: temperature law drifted",
        )
        details[name] = {
            "global_sigma": sigma_global,
            "local_sigma_ref": sigma_local,
            "scaling": "1/sqrt(match_size)",
        }
    _require("min(" not in compact and "max(" not in compact, "passives silently clip")
    return {"artifact": str(PASSIVE_FILE), "sha256": _sha256(path), "devices": details}


def _check_generated_assets(root: Path) -> dict[str, Any]:
    v2 = _generator_check(root, "tools/generate_spectre_v2.py")
    psp = _generator_check(root, "tools/generate_spectre_psp.py")
    psp_files = [
        root / "models/apm130/spectre/sg13g2_lv_psp103_tt.sp",
        root / "models/apm130/spectre/sg13g2_hv_psp103_tt.sp",
    ]
    for family_id, path in zip(("lv", "hv"), psp_files):
        text = path.read_text(encoding="utf-8")
        _require(
            len(
                re.findall(
                    rf"(?mi)^\.model\s+sg13g2_{family_id}_[np]mos_psp\s+psp103\b",
                    text,
                )
            )
            == 2,
            f"generated {family_id} PSP card lacks two native models",
        )
    cmg = root / "models/apm016f/spectre/apm016f_multivt.scs"
    _require(
        len(
            re.findall(
                r"(?mi)^model\s+apm016f_(?:lvt|svt|hvt)_[np]core\s+bsimcmg\b",
                cmg.read_text(encoding="utf-8"),
            )
        )
        == 6,
        "APM016F Spectre card lacks six BSIM-CMG models",
    )
    return {
        "v2_generator": v2,
        "psp_generator": psp,
        "psp_sha256": {path.name: _sha256(path) for path in psp_files},
        "cmg_sha256": _sha256(cmg),
    }


def _check_model_only_scope(root: Path) -> dict[str, Any]:
    artifacts = [
        path
        for base in (root / "models", root / "variation", root / "passives")
        for path in base.rglob("*")
        if path.is_file() and "spectre" in path.parts
    ]
    analysis_pattern = re.compile(
        r"(?i)^\s*[A-Za-z_][A-Za-z0-9_]*\s+"
        r"(?:montecarlo|dc|ac|tran|noise|sp|pz|stb|xf|pss|pac)\b"
    )
    source_pattern = re.compile(r"(?i)\)\s+(?:vsource|isource)\b")
    forbidden_suffixes = {".il", ".cdf", ".oa", ".ocn", ".skill", ".sch"}
    for path in artifacts:
        _require(path.suffix.lower() not in forbidden_suffixes, f"forbidden asset {path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "*", "#")):
                continue
            _require(
                not analysis_pattern.search(stripped),
                f"analysis/testbench found in {path.relative_to(root)}",
            )
            _require(
                not source_pattern.search(stripped),
                f"source/testbench found in {path.relative_to(root)}",
            )
    _require(len(artifacts) == 35, f"expected 35 Spectre-scope files, found {len(artifacts)}")
    return {
        "artifact_count": len(artifacts),
        "artifacts": [str(path.relative_to(root)) for path in sorted(artifacts)],
        "analyses": 0,
        "sources": 0,
        "virtuoso_assets": 0,
        "testbenches": 0,
    }


def _check_documentation(root: Path) -> dict[str, Any]:
    path = root / DOCUMENTATION_FILE
    _require(path.is_file(), f"missing {DOCUMENTATION_FILE}")
    text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
    required = [
        "EXPERIMENTAL / UNVERIFIED",
        "Benchmark Global",
        "Benchmark Local",
        "Benchmark All",
        "variations=process",
        "variations=mismatch",
        "variations=all",
        "all 15",
        "not been parsed",
        "Virtuoso",
        "user-managed",
        "1/sqrt(match_size)",
    ]
    missing = [phrase for phrase in required if phrase not in text]
    _require(not missing, f"Spectre documentation is missing {missing}")
    return {"artifact": str(DOCUMENTATION_FILE), "sha256": _sha256(path)}


def validate_spectre(output: Path, *, root: Path = ROOT) -> dict[str, Any]:
    """Run the static v2 Spectre model-only audit and persist a JSON report."""

    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SpectreStructureError(f"refusing to overwrite non-empty directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    failures: dict[str, str] = {}
    functions: tuple[tuple[str, Callable[[Path], dict[str, Any]]], ...] = (
        ("all_family_bindings_and_adapters", _check_family_bindings),
        ("benchmark_global_local_all_and_corners", _check_variation),
        ("benchmark_passives", _check_passives),
        ("deterministic_generated_assets", _check_generated_assets),
        ("model_only_scope", _check_model_only_scope),
        ("documentation", _check_documentation),
    )
    for name, function in functions:
        try:
            details[name] = function(root)
            checks[name] = True
        except (OSError, RuntimeError, ValueError) as error:
            checks[name] = False
            failures[name] = str(error)
    report: dict[str, Any] = {
        "schema": "apm.spectre-structural-report.v2",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "structurally_checked" if all(checks.values()) else "failed",
        "backend_status": "experimental_unverified",
        "release_gate": "spectre.model_only",
        "spectre_executable_detected": shutil.which("spectre"),
        "real_tool_validation_performed": False,
        "parse_validity_claimed": False,
        "numerical_conformance_claimed": False,
        "checks": checks,
        "details": details,
        "failures": failures,
    }
    report_path = output / "spectre_structural_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["output_directory"] = str(output)
    report["report_path"] = str(report_path)
    if failures:
        summary = "; ".join(f"{name}: {message}" for name, message in failures.items())
        raise SpectreStructureError(summary)
    return report
