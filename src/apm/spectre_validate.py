# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Static release-gate checks for the model-only Spectre artifacts.

This module deliberately does not invoke Spectre. A passing report means that
the repository structure and declared benchmark semantics are internally
consistent; it is not evidence of Spectre parse validity or conformance.
"""

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


class SpectreStructureError(RuntimeError):
    """Raised when a required Spectre model-only structural check fails."""


ROOT = Path(__file__).resolve().parents[2]
VARIATION_FILE = Path("variation/spectre/benchmark_variation.scs")
PASSIVE_FILE = Path("passives/spectre/benchmark_passives.scs")
MODEL_FILES = {
    "apm350": Path("models/apm350/spectre/apm350.scs"),
    "apm130": Path("models/apm130/spectre/apm130.scs"),
    "apm045": Path("models/apm045/spectre/apm045.scs"),
    "apm022": Path("models/apm022/spectre/apm022.scs"),
    "apm016f": Path("models/apm016f/spectre/apm016f.scs"),
}
DERIVED_PSP_FILE = Path("models/apm130/spectre/sg13g2_lv_psp103_tt.sp")
DOCUMENTATION_FILE = Path("docs/spectre.md")
PUBLIC_DEVICES = {
    "apm350": {"n": ("apm350_nmos", ("w", "l")), "p": ("apm350_pmos", ("w", "l"))},
    "apm130": {"n": ("apm130_nmos", ("w", "l")), "p": ("apm130_pmos", ("w", "l"))},
    "apm045": {"n": ("apm045_nmos", ("w", "l")), "p": ("apm045_pmos", ("w", "l"))},
    "apm022": {"n": ("apm022_nmos", ("w", "l")), "p": ("apm022_pmos", ("w", "l"))},
    "apm016f": {
        "n": ("apm016f_nfet", ("l", "nfin")),
        "p": ("apm016f_pfet", ("l", "nfin")),
    },
}
MATCH_EXPRESSIONS = {
    "apm350": "(w*l)/(1u*800n)",
    "apm130": "(w*l)/(1u*260n)",
    "apm045": "(w*l)/(1u*100n)",
    "apm022": "(w*l)/(1u*50n)",
    "apm016f": "(nfin*l)/(1*32n)",
}
ENGINE_CHECKS = {
    "apm350": (Path("models/apm350/ngspice/apm350_models.inc"), r"level\s*=\s*49\b"),
    "apm130": (DERIVED_PSP_FILE, r"(?mi)^\.model\s+sg13g2_lv_[np]mos_psp\s+psp103\b"),
    "apm045": (Path("models/apm045/vendor/freepdk45/NMOS_VTG.inc"), r"level\s*=\s*54\b"),
    "apm022": (Path("models/apm022/ngspice/apm022_models.inc"), r"level\s*=\s*54\b"),
    "apm016f": (MODEL_FILES["apm016f"], r"(?mi)^model\s+apm016f_cmg_[np]\s+bsimcmg\b"),
}
CORNER_PARAMETER_MAP = {
    "apm_bench_n_vth_process_z": "vth_n_sigma",
    "apm_bench_n_drive_process_z": "drive_n_sigma",
    "apm_bench_p_vth_process_z": "vth_p_sigma",
    "apm_bench_p_drive_process_z": "drive_p_sigma",
    "apm_bench_r_process_z": "resistor_scale_sigma",
    "apm_bench_c_process_z": "capacitor_scale_sigma",
}


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SpectreStructureError(message)


def _subckt_block(text: str, name: str) -> str:
    match = re.search(
        rf"(?msi)^subckt\s+{re.escape(name)}\s+\(d\s+g\s+s\s+b\)\s*$"
        rf"(?P<body>.*?)^ends\s+{re.escape(name)}\s*$",
        text,
    )
    if match is None:
        raise SpectreStructureError(f"missing four-terminal Spectre subckt {name}")
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
        raise SpectreStructureError(f"missing internal adapter parameter {name}")
    return float(match.group(1))


def _section_block(text: str, name: str) -> str:
    match = re.search(
        rf"(?msi)^section\s+{re.escape(name)}\s*$"
        rf"(?P<body>.*?)^endsection\s+{re.escape(name)}\s*$",
        text,
    )
    if match is None:
        raise SpectreStructureError(f"missing Spectre variation section {name}")
    return match.group(0)


def _check_model_interfaces(root: Path) -> dict[str, Any]:
    adapters = _load_toml(root / "variation/adapters_v1.toml")["kit"]
    benchmark = _load_toml(root / "variation/benchmark_v1.toml")
    process_vth = float(benchmark["mos"]["process"]["vth_shift_sigma"])
    process_drive = float(benchmark["mos"]["process"]["drive_shift_sigma"])
    local_vth = float(benchmark["mos"]["mismatch"]["vth_shift_sigma_ref"])
    local_drive = float(benchmark["mos"]["mismatch"]["drive_shift_sigma_ref"])
    details: dict[str, Any] = {}
    for kit_id, relative in MODEL_FILES.items():
        path = root / relative
        _require(path.is_file(), f"missing Spectre artifact {relative}")
        text = path.read_text(encoding="utf-8")
        _require("EXPERIMENTAL / UNVERIFIED" in text, f"missing status banner in {relative}")
        _require("simulator lang=spectre" in text, f"missing Spectre language in {relative}")
        provenance = _load_toml(root / f"models/{kit_id}/provenance.toml")
        spectre_metadata = provenance.get("spectre", {})
        kit_relative = str(relative.relative_to(Path("models") / kit_id))
        _require(
            provenance["validation"]["spectre"] == "experimental_unverified",
            f"{kit_id} provenance overstates Spectre validation",
        )
        _require(
            spectre_metadata.get("status") == "experimental_unverified"
            and spectre_metadata.get("real_tool_validation") is False,
            f"{kit_id} Spectre provenance status is incomplete",
        )
        _require(
            spectre_metadata.get("artifact") == kit_relative,
            f"{kit_id} Spectre provenance points to the wrong artifact",
        )
        source = provenance["source"]
        recorded_hashes = {
            **source.get("authored_files", {}),
            **source.get("apm_authored_files", {}),
        }
        _require(
            recorded_hashes.get(kit_relative) == _sha256(path),
            f"{kit_id} Spectre artifact hash is missing or stale in provenance",
        )
        engine_path, engine_pattern = ENGINE_CHECKS[kit_id]
        engine_text = (root / engine_path).read_text(encoding="utf-8")
        _require(
            re.search(engine_pattern, engine_text) is not None,
            f"missing native compact-model mapping for {kit_id}",
        )
        per_polarity: dict[str, Any] = {}
        for polarity, (device, public_parameters) in PUBLIC_DEVICES[kit_id].items():
            block = _subckt_block(text, device)
            parameter_lines = [
                line.strip()
                for line in block.splitlines()
                if line.strip().lower().startswith("parameters ")
            ]
            _require(parameter_lines, f"missing parameters for {device}")
            first_parameters = tuple(_parameter_assignments(parameter_lines[0]))
            _require(
                first_parameters == public_parameters,
                f"{device} public parameters are {first_parameters}, expected {public_parameters}",
            )
            all_parameters = {
                name
                for line in parameter_lines
                for name in _parameter_assignments(line)
            }
            internal = all_parameters - set(public_parameters)
            _require(
                all(name.startswith("apm__") for name in internal),
                f"{device} has non-reserved extra parameters: {sorted(internal)}",
            )
            _require(
                not ({"m", "nf", "ng"} & set(public_parameters)),
                f"{device} exposes forbidden multiplicity/finger sizing",
            )
            polarity_adapter = adapters[kit_id][polarity]
            expected_coefficients = {
                "apm__vth_a": float(polarity_adapter["vth_fit_linear"]),
                "apm__vth_b": float(polarity_adapter["vth_fit_quadratic"]),
                "apm__drive_a": float(polarity_adapter["drive_fit_linear"]),
                "apm__drive_b": float(polarity_adapter["drive_fit_quadratic"]),
            }
            observed_coefficients = {
                name: _parameter_value(block, name) for name in expected_coefficients
            }
            for name, expected in expected_coefficients.items():
                _require(
                    math.isclose(observed_coefficients[name], expected, rel_tol=0, abs_tol=0),
                    f"{device} {name} drifted from variation/adapters_v1.toml",
                )
            compact = re.sub(r"\s+", "", block.lower())
            _require(
                f"apm__match_size={MATCH_EXPRESSIONS[kit_id]}" in compact,
                f"{device} mismatch geometry scaling is not canonical",
            )
            global_prefix = f"apm_bench_{polarity}_"
            _require(
                f"{process_vth:g}*{global_prefix}vth_process_z" in compact,
                f"{device} process threshold sigma drifted",
            )
            _require(
                f"{local_vth:g}*apm__mos_vth_local_z/sqrt(apm__match_size)" in compact,
                f"{device} local threshold sigma/scaling drifted",
            )
            _require(
                f"(1+{process_drive:g}*{global_prefix}drive_process_z)" in compact,
                f"{device} process drive sigma/composition drifted",
            )
            _require(
                f"(1+{local_drive:g}*apm__mos_drive_local_z/sqrt(apm__match_size))" in compact,
                f"{device} local drive sigma/scaling drifted",
            )
            vth_raw = adapters[kit_id]["vth_raw_parameter"].lower()
            drive_raw = adapters[kit_id]["drive_raw_parameter"].lower()
            _require(
                f"{vth_raw}=apm__vth_raw" in compact,
                f"{device} does not apply calibrated threshold handle {vth_raw}",
            )
            _require(
                f"{drive_raw}=apm__drive_raw" in compact,
                f"{device} does not apply calibrated drive handle {drive_raw}",
            )
            if observed_coefficients["apm__vth_b"] == 0.0:
                expected_vth_inverse = "apm__vth_raw=apm__vth_intent/apm__vth_a"
            else:
                root_sign = "+" if observed_coefficients["apm__vth_a"] > 0 else "-"
                expected_vth_inverse = (
                    "apm__vth_raw=2*apm__vth_intent/(apm__vth_a"
                    f"{root_sign}sqrt(apm__vth_a*apm__vth_a+4*apm__vth_b*"
                    "apm__vth_intent))"
                )
            if observed_coefficients["apm__drive_b"] == 0.0:
                expected_drive_inverse = "apm__drive_raw=1+apm__drive_intent/apm__drive_a"
            else:
                root_sign = "+" if observed_coefficients["apm__drive_a"] > 0 else "-"
                expected_drive_inverse = (
                    "apm__drive_raw=1+2*apm__drive_intent/(apm__drive_a"
                    f"{root_sign}sqrt(apm__drive_a*apm__drive_a+4*apm__drive_b*"
                    "apm__drive_intent))"
                )
            _require(
                expected_vth_inverse in compact,
                f"{device} does not use the calibrated near-zero threshold root",
            )
            _require(
                expected_drive_inverse in compact,
                f"{device} does not use the calibrated near-zero drive root",
            )
            _require(
                "min(" not in compact and "max(" not in compact,
                f"{device} silently clips a benchmark adapter expression",
            )
            per_polarity[polarity] = {
                "public_device": device,
                "public_parameters": list(public_parameters),
                "internal_parameter_prefix": "apm__",
                "adapter_coefficients": observed_coefficients,
                "match_size_expression": MATCH_EXPRESSIONS[kit_id],
            }
        details[kit_id] = {
            "artifact": str(relative),
            "sha256": _sha256(path),
            "devices": per_polarity,
        }
    return details


def _check_variation_library(root: Path) -> dict[str, Any]:
    path = root / VARIATION_FILE
    _require(path.is_file(), f"missing {VARIATION_FILE}")
    text = path.read_text(encoding="utf-8")
    _require("EXPERIMENTAL / UNVERIFIED" in text, "variation file lacks status banner")
    _require("library apm_benchmark_variation_v1" in text, "missing variation library")
    _require("statistics" in text, "missing Spectre statistics block")
    mc = _section_block(text, "bench_mc")
    all_statistical_names = set(CORNER_PARAMETER_MAP) | {
        "apm__mos_vth_local_z",
        "apm__mos_drive_local_z",
        "apm__r_local_z",
        "apm__c_local_z",
    }
    for parameter in all_statistical_names:
        _require(
            re.search(
                rf"(?mi)^parameters\s+{re.escape(parameter)}=0\s*$",
                mc,
            )
            is not None,
            f"bench_mc lacks zero-nominal declaration for {parameter}",
        )
    _require(re.search(r"(?ms)process\s*\{.*?\}", mc) is not None, "missing process block")
    _require(re.search(r"(?ms)mismatch\s*\{.*?\}", mc) is not None, "missing mismatch block")
    process_names = set(
        re.findall(
            r"(?m)^\s*vary\s+(apm_bench_[a-z_]+)\s+dist=gauss\s+std=1\s+percent=no\s*$",
            re.search(r"(?ms)process\s*\{(?P<body>.*?)\}", mc).group("body"),  # type: ignore[union-attr]
        )
    )
    _require(process_names == set(CORNER_PARAMETER_MAP), "process variables are incomplete")
    mismatch_names = set(
        re.findall(
            r"(?m)^\s*vary\s+(apm__[a-z_]+)\s+dist=gauss\s+std=1\s+percent=no\s*$",
            re.search(r"(?ms)mismatch\s*\{(?P<body>.*?)\}", mc).group("body"),  # type: ignore[union-attr]
        )
    )
    expected_mismatch = {
        "apm__mos_vth_local_z",
        "apm__mos_drive_local_z",
        "apm__r_local_z",
        "apm__c_local_z",
    }
    _require(mismatch_names == expected_mismatch, "mismatch variables are incomplete")
    _require("correlate" not in mc.lower(), "undocumented statistical correlation is present")
    for mode in ("process", "mismatch", "all"):
        _require(f"variations={mode}" in text, f"missing documented Spectre {mode} mode")

    benchmark = _load_toml(root / "variation/benchmark_v1.toml")
    observed_corners: dict[str, dict[str, float]] = {}
    for corner in ("bench_tt", "bench_ff", "bench_ss", "bench_fs", "bench_sf"):
        block = _section_block(text, corner)
        expected = benchmark["corner"][corner]
        values: dict[str, float] = {}
        for parameter, config_key in CORNER_PARAMETER_MAP.items():
            match = re.search(
                rf"(?mi)^parameters\s+{re.escape(parameter)}=([-+0-9.eE]+)\s*$",
                block,
            )
            _require(match is not None, f"{corner} lacks {parameter}")
            value = float(match.group(1))  # type: ignore[union-attr]
            _require(
                value == float(expected[config_key]),
                f"{corner} {parameter} differs from benchmark_v1.toml",
            )
            values[parameter] = value
        for parameter in expected_mismatch:
            _require(
                re.search(
                    rf"(?mi)^parameters\s+{re.escape(parameter)}=0\s*$",
                    block,
                )
                is not None,
                f"{corner} does not hold {parameter} nominal",
            )
        observed_corners[corner] = values
    return {
        "artifact": str(VARIATION_FILE),
        "sha256": _sha256(path),
        "process_variables": sorted(process_names),
        "mismatch_variables": sorted(mismatch_names),
        "correlation": "all listed normalized variables independent; no correlate statement",
        "modes": ["process", "mismatch", "all"],
        "corners": observed_corners,
    }


def _check_passives(root: Path) -> dict[str, Any]:
    path = root / PASSIVE_FILE
    _require(path.is_file(), f"missing {PASSIVE_FILE}")
    text = path.read_text(encoding="utf-8")
    compact = re.sub(r"\s+", "", text.lower())
    _require("EXPERIMENTAL / UNVERIFIED" in text, "passive file lacks status banner")
    passive = _load_toml(root / "passives/benchmark_v1.toml")
    expected = {
        "Rbench": (
            "r",
            "apm_bench_r_process_z",
            "apm__r_local_z",
            passive["resistor"],
        ),
        "Cbench": (
            "c",
            "apm_bench_c_process_z",
            "apm__c_local_z",
            passive["capacitor"],
        ),
    }
    details: dict[str, Any] = {}
    for name, (primitive_value, process_name, local_name, config) in expected.items():
        match = re.search(
            rf"(?msi)^subckt\s+{name}\s+\(p\s+n\)\s*$(?P<body>.*?)^ends\s+{name}\s*$",
            text,
        )
        _require(match is not None, f"missing Spectre passive {name}")
        block = match.group(0)  # type: ignore[union-attr]
        first_parameter = next(
            line.strip() for line in block.splitlines() if line.strip().startswith("parameters ")
        )
        _require(
            tuple(_parameter_assignments(first_parameter)) == ("value", "tc1", "match_size"),
            f"{name} public parameter contract drifted",
        )
        block_compact = re.sub(r"\s+", "", block.lower())
        process_sigma = float(config["process_sigma"])
        mismatch_sigma = float(config["mismatch_sigma_ref"])
        _require(
            f"(1+{process_sigma:g}*{process_name})" in block_compact,
            f"{name} process sigma drifted",
        )
        _require(
            f"(1+{mismatch_sigma:g}*{local_name}/sqrt(match_size))" in block_compact,
            f"{name} local sigma/scaling drifted",
        )
        _require(
            f"{primitive_value}=value*apm__" in block_compact,
            f"{name} does not apply its resolved scale",
        )
        _require("tc1=tc1" in block_compact and "tnom=27" in block_compact, f"{name} tc1 drifted")
        details[name] = {
            "public_parameters": ["value", "tc1", "match_size"],
            "process_sigma": process_sigma,
            "mismatch_sigma_ref": mismatch_sigma,
            "mismatch_scaling": "1/sqrt(match_size)",
        }
    _require("min(" not in compact and "max(" not in compact, "passive scales are silently clipped")
    return {"artifact": str(PASSIVE_FILE), "sha256": _sha256(path), "devices": details}


def _check_model_only_scope(root: Path) -> dict[str, Any]:
    artifacts = [root / VARIATION_FILE, root / PASSIVE_FILE]
    artifacts.extend(root / path for path in MODEL_FILES.values())
    artifacts.append(root / DERIVED_PSP_FILE)
    analysis_pattern = re.compile(
        r"(?i)^\s*[A-Za-z_][A-Za-z0-9_]*\s+(?:montecarlo|dc|ac|tran|noise|sp|pz|stb|xf|pss|pac)\b"
    )
    source_pattern = re.compile(r"(?i)\)\s+(?:vsource|isource)\b")
    forbidden_suffixes = {".il", ".cdf", ".oa", ".ocn", ".skill", ".sch"}
    for path in artifacts:
        _require(path.is_file(), f"missing model-only artifact {path.relative_to(root)}")
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "*")):
                continue
            _require(not analysis_pattern.search(stripped), f"analysis found in {path.relative_to(root)}")
            _require(not source_pattern.search(stripped), f"source/testbench found in {path.relative_to(root)}")
        _require(path.suffix.lower() not in forbidden_suffixes, f"forbidden artifact {path}")
    spectre_paths = [
        path
        for base in (root / "models", root / "variation", root / "passives")
        for path in base.rglob("*")
        if path.is_file() and "spectre" in path.parts
    ]
    _require(set(spectre_paths) == set(artifacts), "unaccounted Spectre-scope artifact exists")
    return {
        "artifact_count": len(artifacts),
        "analyses": 0,
        "sources": 0,
        "virtuoso_assets": 0,
        "testbenches": 0,
    }


def _check_generated_psp(root: Path) -> dict[str, Any]:
    command = [sys.executable, str(root / "tools/generate_spectre_psp.py"), "--check"]
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    _require(completed.returncode == 0, completed.stderr.strip() or "generated PSP card drifted")
    path = root / DERIVED_PSP_FILE
    text = path.read_text(encoding="utf-8")
    _require("psp103va" not in "\n".join(
        line for line in text.splitlines() if line.lower().startswith(".model")
    ), "derived card still selects the OpenVAF module")
    _require(len(re.findall(r"(?mi)^\.model\s+sg13g2_lv_[np]mos_psp\s+psp103\b", text)) == 2, "derived card lacks two native PSP103 models")
    provenance = _load_toml(root / "models/apm130/provenance.toml")
    kit_relative = str(DERIVED_PSP_FILE.relative_to("models/apm130"))
    _require(
        provenance["source"]["transformed_files"].get(kit_relative) == _sha256(path),
        "derived PSP card hash is missing or stale in APM130 provenance",
    )
    generator = root / provenance["spectre"]["generator"]
    _require(
        provenance["spectre"]["generator_sha256"] == _sha256(generator),
        "Spectre PSP generator hash is stale in APM130 provenance",
    )
    return {
        "artifact": str(DERIVED_PSP_FILE),
        "sha256": _sha256(path),
        "generator_check": completed.stdout.strip(),
        "source_revision": "331c00484213b13414777eec1336ef5c29b969bd",
        "native_model_name": "psp103",
    }


def _check_documentation(root: Path) -> dict[str, Any]:
    path = root / DOCUMENTATION_FILE
    _require(path.is_file(), f"missing {DOCUMENTATION_FILE}")
    text = path.read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", text)
    required = [
        "EXPERIMENTAL / UNVERIFIED",
        "variations=process",
        "variations=mismatch",
        "variations=all",
        "IHP-native Monte Carlo",
        "not been parsed",
        "Virtuoso",
        "user-managed",
        "1/sqrt(match_size)",
    ]
    missing = [item for item in required if item not in normalized]
    _require(not missing, f"Spectre documentation is missing: {missing}")
    return {"artifact": str(DOCUMENTATION_FILE), "sha256": _sha256(path)}


def validate_spectre(output: Path, *, root: Path = ROOT) -> dict[str, Any]:
    """Run the static Spectre model-only audit and persist a JSON report."""

    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    failures: dict[str, str] = {}
    functions: tuple[tuple[str, Callable[[Path], dict[str, Any]]], ...] = (
        ("model_interfaces_and_adapters", _check_model_interfaces),
        ("benchmark_variation_sections_and_statistics", _check_variation_library),
        ("benchmark_passives", _check_passives),
        ("model_only_scope", _check_model_only_scope),
        ("generated_apm130_psp_card", _check_generated_psp),
        ("documentation", _check_documentation),
    )
    for name, function in functions:
        try:
            details[name] = function(root)
            checks[name] = True
        except (OSError, RuntimeError, ValueError) as error:
            checks[name] = False
            failures[name] = str(error)

    spectre_path = shutil.which("spectre")
    report = {
        "schema": "apm.spectre-structural-report.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "structurally_checked" if all(checks.values()) else "failed",
        "backend_status": "experimental_unverified",
        "release_gate": "spectre.model_only",
        "spectre_executable_detected": spectre_path,
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
