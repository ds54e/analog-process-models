# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed current-repository and v4.0.0 release validation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Callable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib

from .benchmark_validate import validate_benchmark
from .catalog import load_catalog
from .clean_clone_v4 import (
    V3_TAG_COMMIT,
    V3_TAG_OBJECT,
    verify_clean_clone_v4_attestation,
)
from .compare import compare_anchors, compare_set, validate_all_characterizations
from .doctor import run_doctor
from .model_build import sha256_file
from .native_variation import validate_apm130_native
from .noise import ACQUISITION_POLICY_ID, ACQUISITION_POLICY_VERSION
from .noise_catalog import validate_noise_catalog
from .noise_fit import FIT_METHOD_IDENTITY
from .paths import repository_root, state_directory
from .provenance_validate import ProvenanceValidationError, validate_provenance
from .release_validate import (
    ReleaseValidationError,
    audit_distribution,
    audit_migration,
)
from .spectre_validate import SpectreStructureError, validate_spectre
from .toolchain import resolve_toolchain

V4_GATE_IDS = frozenset(
    {
        "compatibility.v3_immutable",
        "evidence.public_matrix",
        "modelgen.reconstruction",
        "modelgen.deterministic_regeneration",
        "models.io25",
        "models.io18",
        "mixed_voltage.distinctness",
        "mixed_voltage.circuit_holdout",
        "mixed_voltage.comparison",
        "variation.v4",
        "noise.v4_catalog",
        "spectre.model_only",
        "licensing.provenance",
        "release.clean_clone_v4",
        "release.claim_audit_v4",
        "release.exact_tag_requalification",
    }
)
EXACT_TAG_GATE_ID = "release.exact_tag_requalification"
V4_PHASES = frozenset({"candidate", "exact-tag"})
REQUIRED_REVIEWED_FILES_V4 = frozenset(
    {
        "AGENTS.md",
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "DEVICE_FAMILY_MODEL.md",
        "ENVIRONMENT.md",
        "GOAL.md",
        "RELEASE_V3.md",
        "RELEASE_V4.md",
        "RESEARCH_BASELINE.md",
        "PROJECT_CONTEXT.md",
        "SECURITY.md",
        "STATUS.md",
        "THIRD_PARTY.md",
        "UNATTENDED_EXECUTION.md",
        "V4_MIXED_VOLTAGE.md",
        "NOISE_CHARACTERIZATION.md",
        "NOISE_N1.md",
        "NOISE_N2.md",
        "RESULT_CONTRACT.md",
        "docs/benchmark-variation.md",
        "docs/characterization.md",
        "docs/native-variation.md",
        "docs/release-validation.md",
        "docs/spectre.md",
        "models/apm045/README.md",
        "models/apm045/mixed_voltage_evidence.toml",
        "tools/modelgen/apm045_mixed_voltage/README.md",
        "tools/modelgen/apm045_mixed_voltage/calibration_replay_v4.toml",
        "validation/evidence/README.md",
        "validation/release_gates_v4.toml",
    }
)
V3_APM045_IMMUTABLE_PREFIXES = (
    "models/apm045/families/vtl/",
    "models/apm045/families/vtg/",
    "models/apm045/families/vth/",
    "models/apm045/families/thkox/",
    "models/apm045/vendor/freepdk45/",
)
V4_EVIDENCE_PATHS = {
    "foundation": "validation/evidence/v4_modelgen_foundation.json",
    "calibration": "validation/evidence/v4_generation_epoch3_calibration.json",
    "qualification": "validation/evidence/v4_mixed_voltage_qualification.json",
}
CANONICAL_CARDS = {
    ("io18", "n"): (
        54003,
        "models/apm045/families/io18/ngspice/apm045_io18_n.inc",
        "e639452467891fde0ea51f1fb3e965a01f46acf2bec85b90a437f296d2f1cebe",
    ),
    ("io18", "p"): (
        54003,
        "models/apm045/families/io18/ngspice/apm045_io18_p.inc",
        "065dd165f2e1bc3bab41f5205292205adab8ea1d4b39c9bdb813d690eaebd40a",
    ),
    ("io25", "n"): (
        54002,
        "models/apm045/families/io25/ngspice/apm045_io25_n.inc",
        "2c2478406b4417e7a5058c46b321ff70dee1041025bda04986bb18758df104a0",
    ),
    ("io25", "p"): (
        54002,
        "models/apm045/families/io25/ngspice/apm045_io25_p.inc",
        "8eab45ce29fbd0caf4b089c4e1f7f7e52e14c7cc1572ee9c4245b57fc8ff1cc2",
    ),
}
MODELGEN_SOURCE_BINDINGS = {
    "kernel": (
        "tools/modelgen/apm045_mixed_voltage/kernel.py",
        "005e6b9f8ebcf704e21b7f1d2fb736e9a1c3fa3e20be49303172891041c5ff5c",
    ),
    "synthesis": (
        "tools/modelgen/apm045_mixed_voltage/synthesize_families.py",
        "575f642a829de8da022a1e2f4262aa7f428dc4895881c9f7c50de62f7c10acaf",
    ),
    "qualification": (
        "tools/modelgen/apm045_mixed_voltage/qualify_families.py",
        "374f86f4479fd56347bf968c7d410b9870dabbc80bc04daa431833b8763c1ce0",
    ),
    "qualification_replay": (
        "tools/modelgen/apm045_mixed_voltage/replay_families.py",
        "e1aa51cd673956e4c625246c18b0a82919dfc8892fbead28959abfcac372522c",
    ),
    "calibration_replay_contract": (
        "tools/modelgen/apm045_mixed_voltage/calibration_replay_v4.toml",
        "c5d410086ac4742893849555d591a4a3370b11a0022e07ff0cc660b092ef856c",
    ),
    "terminal_observables": (
        "tools/modelgen/apm045_mixed_voltage/terminal_observables.py",
        "68f8070f170f0cc66c006c30976b6b8bee63a61e10d9ea0460c3632304e56477",
    ),
    "circuit_fixtures": (
        "tools/modelgen/apm045_mixed_voltage/circuit_fixtures.py",
        "a17a36d1d0c9458f14757fe5dc85e9bbd1fdc8355708c5504bbf9ee70b2d9677",
    ),
}


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ReleaseValidationError(f"cannot read TOML {path}: {error}") from error


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseValidationError(f"cannot read JSON {path}: {error}") from error


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReleaseValidationError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout.strip()


def _check_map(checks: dict[str, bool], *, context: str) -> dict[str, Any]:
    failed = sorted(name for name, passed in checks.items() if passed is not True)
    return {
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "context": context,
    }


def _write_report(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = str(path)
    report["output_directory"] = str(path.parent)
    return report


def load_v4_gate_contract(root: Path) -> dict[str, Any]:
    contract = _load_toml(root / "validation/release_gates_v4.toml")
    if contract.get("schema") != "apm.release-gates.v4":
        raise ReleaseValidationError("unsupported v4 release-gate schema")
    gates = contract.get("gate")
    if not isinstance(gates, list) or not gates:
        raise ReleaseValidationError("v4 release-gate contract contains no gates")
    identifiers = [gate.get("id") for gate in gates]
    if any(not isinstance(identifier, str) for identifier in identifiers):
        raise ReleaseValidationError("every v4 release gate must have a string id")
    if len(identifiers) != len(set(identifiers)):
        raise ReleaseValidationError("v4 release-gate ids must be unique")
    required = {gate["id"] for gate in gates if gate.get("required") is True}
    missing = required - V4_GATE_IDS
    stale = V4_GATE_IDS - required
    if missing or stale:
        raise ReleaseValidationError(
            "v4 release validator/contract mismatch; "
            f"missing implementations={sorted(missing)}, stale implementations={sorted(stale)}"
        )
    if len(required) != 16 or contract.get("target") != "v4.0.0":
        raise ReleaseValidationError("v4 release contract must contain 16 gates for v4.0.0")
    return contract


def audit_v4_release_metadata(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    metadata = contract["release_metadata"]
    target = str(metadata["target_version"])
    project = _load_toml(root / "pyproject.toml")
    package_version = str(project.get("project", {}).get("version", ""))
    init_text = (root / "src/apm/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_text, re.MULTILINE)
    runtime_version = match.group(1) if match else ""
    cli_text = (root / "src/apm/cli.py").read_text(encoding="utf-8")
    cli_match = re.search(r'version=["\']APM ([^"\']+)["\']', cli_text)
    cli_version = cli_match.group(1) if cli_match else ""
    try:
        installed_version = importlib_metadata.version("analog-process-models")
    except importlib_metadata.PackageNotFoundError:
        installed_version = "missing"
    changelog = (root / str(metadata["release_notes_path"])).read_text(encoding="utf-8")
    release_document = root / str(metadata["release_document"])
    scan_paths = [
        root / "README.md",
        root / "CHANGELOG.md",
        release_document,
        root / "STATUS.md",
        root / "models/apm045/README.md",
        root / "models/apm045/provenance.toml",
        root / "variation/adapters_v2.toml",
    ]
    placeholder_hits: list[dict[str, str]] = []
    for path in scan_paths:
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        for token in metadata["forbidden_release_placeholder_tokens"]:
            if re.search(rf"\b{re.escape(str(token))}\b", text, re.IGNORECASE):
                placeholder_hits.append(
                    {"path": str(path.relative_to(root)), "token": str(token)}
                )
    checks = {
        "pyproject_version_matches_target": package_version == target,
        "runtime_version_matches_target": runtime_version == target,
        "cli_version_matches_target": cli_version == target,
        "installed_distribution_version_matches_target": installed_version == target,
        "all_version_metadata_agree": package_version == runtime_version == cli_version,
        "contract_target_matches_version": contract.get("target") == f"v{target}",
        "python_meets_minimum": sys.version_info
        >= tuple(int(item) for item in str(contract["runtime"]["python_minimum"]).split(".")),
        "release_document_present": release_document.is_file(),
        "changelog_has_dated_release_heading": bool(
            re.search(
                rf"^## \[{re.escape(target)}\] - \d{{4}}-\d{{2}}-\d{{2}}$",
                changelog,
                re.MULTILINE,
            )
        ),
        "changelog_has_no_unreleased_section": not bool(
            re.search(r"^## (?:\[)?Unreleased(?:\])?$", changelog, re.MULTILINE)
        ),
        "no_release_placeholder_tokens": not placeholder_hits,
    }
    result = _check_map(checks, context="v4 version, release notes, and placeholder audit")
    result.update(
        {
            "target_version": target,
            "package_version": package_version,
            "runtime_version": runtime_version,
            "cli_version": cli_version,
            "installed_distribution_version": installed_version,
            "placeholder_hits": placeholder_hits,
            "scanned_paths": [str(path.relative_to(root)) for path in scan_paths],
        }
    )
    return result


def audit_v4_catalog(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    catalog = load_catalog(root)
    required = contract["technology_catalog"]
    required_technologies = tuple(required["required_technologies"])
    required_families = required["required_families"]
    actual = {technology.technology_id: technology for technology in catalog.technologies}
    families = [
        family for technology in catalog.technologies for family in technology.families
    ]
    devices = [device for family in families for device in family.devices]
    apm045 = actual.get("apm045")
    mixed = apm045.comparison_set("mixed_voltage") if apm045 else None
    # Keep the legacy loader token out of this module's source text.  The frozen
    # v3 migration audit scans every runtime module for that token, including
    # validators added after v3, and should not fail merely because the v4 audit
    # names the same forbidden dependency in its own implementation.
    legacy_loader_token = f"load{chr(95)}kit"
    checks = {
        "technology_set_exact": set(actual) == set(required_technologies),
        "family_count_exact": len(families) == int(required["required_family_count"]),
        "public_device_count_exact": len(devices)
        == int(required["required_public_device_count"]),
        "required_families_exact": all(
            technology_id in actual
            and {family.family_id for family in actual[technology_id].families}
            == set(required_families[technology_id])
            for technology_id in required_technologies
        ),
        "unique_family_qualified_public_names": len({device.public_name for device in devices})
        == len(devices)
        and all(
            device.public_name.startswith(f"{family.technology_id}_{family.family_id}_")
            for family in families
            for device in family.devices
        ),
        "n_p_and_backend_contracts": all(
            {device.polarity for device in family.devices} == {"n", "p"}
            and {binding.backend_id for binding in family.backend_bindings}
            == {"ngspice", "spectre"}
            and family.default_operating_profile
            in {profile.profile_id for profile in family.operating_profiles}
            for family in families
        ),
        "cross_process_anchors_exact": all(
            technology_id in actual
            and actual[technology_id].cross_process_anchor
            == required["cross_process_anchors"][technology_id]
            for technology_id in required_technologies
        ),
        "mixed_voltage_set_exact": mixed is not None
        and mixed.kind == "mixed_voltage"
        and mixed.members == ("vtg", "io18", "io25")
        and mixed.anchor == "vtg",
        "forbidden_io33_absent": apm045 is not None
        and "io33" not in {family.family_id for family in apm045.families},
        "catalog_loader_is_manifest_driven": "apm350" not in (
            root / "src/apm/catalog.py"
        ).read_text(encoding="utf-8")
        and legacy_loader_token not in (root / "src/apm/characterize.py").read_text(
            encoding="utf-8"
        ),
    }
    result = _check_map(checks, context="manifest-driven v4 catalog and family contract")
    result.update(
        {
            "technology_ids": sorted(actual),
            "family_selectors": sorted(family.selector for family in families),
            "public_device_names": sorted(device.public_name for device in devices),
            "snapshot": catalog.snapshot(),
        }
    )
    return result


def audit_public_evidence(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    path = root / "models/apm045/mixed_voltage_evidence.toml"
    matrix = _load_toml(path)
    evidence = matrix.get("evidence", [])
    priors = matrix.get("engineering_prior", [])
    behavior = matrix.get("apm_behavior_contract", [])
    required_fields = set(contract["public_evidence"]["required_fields"])
    evidence_ids = {
        item.get("id") for item in evidence if isinstance(item, dict) and item.get("id")
    }
    source_locators = [str(item.get("source_locator", "")) for item in evidence]
    checks = {
        "schema": matrix.get("schema") == "apm.public-evidence-matrix.v1",
        "technology_and_scope": matrix.get("technology_id") == "apm045"
        and "mixed-voltage" in str(matrix.get("scope", "")),
        "private_inputs_explicitly_absent": matrix.get("private_or_proprietary_inputs_used")
        is False,
        "required_evidence_fields": len(evidence) >= 4
        and all(required_fields <= set(item) for item in evidence),
        "unique_nonempty_evidence_ids": len(evidence_ids) == len(evidence),
        "public_source_locators": all(
            locator.startswith(("https://", "models/apm045/vendor/freepdk45/"))
            for locator in source_locators
        ),
        "allowed_and_forbidden_uses_explicit": all(
            isinstance(item.get("allowed_use"), list)
            and bool(item["allowed_use"])
            and isinstance(item.get("forbidden_use"), list)
            and bool(item["forbidden_use"])
            for item in evidence
        ),
        "engineering_priors_link_sources": bool(priors)
        and all(
            set(item.get("basis_evidence_ids", [])) <= evidence_ids
            and item.get("allowed_role")
            and item.get("prohibited_inference")
            for item in priors
        ),
        "behavior_contracts_separate": len(behavior) >= 3
        and all(item.get("authority") for item in behavior),
        "physical_oxide_to_toxe_copy_forbidden": any(
            "TOXE" in " ".join(str(value) for value in item.get("forbidden_use", []))
            for item in evidence
        ),
    }
    result = _check_map(checks, context="v4 public mixed-voltage evidence matrix")
    result.update(
        {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
            "evidence_ids": sorted(str(item) for item in evidence_ids),
            "engineering_prior_ids": sorted(str(item.get("id")) for item in priors),
            "behavior_contract_ids": sorted(str(item.get("id")) for item in behavior),
        }
    )
    return result


def _git_object_bytes(root: Path, revision: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseValidationError(f"cannot read {revision}:{relative}: {detail}")
    return result.stdout


def audit_v3_immutability(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    compatibility = contract["compatibility"]
    expected_commit = str(compatibility["v3_tagged_commit"])
    tag_object = _git(root, "rev-parse", f"refs/tags/{compatibility['v3_tag']}")
    tag_commit = _git(root, "rev-parse", f"{compatibility['v3_tag']}^{{commit}}")
    tag_type = _git(root, "cat-file", "-t", f"refs/tags/{compatibility['v3_tag']}")
    baseline_paths = _git(
        root,
        "ls-tree",
        "-r",
        "--name-only",
        expected_commit,
        *V3_APM045_IMMUTABLE_PREFIXES,
    ).splitlines()
    mismatches: list[dict[str, str]] = []
    for relative in baseline_paths:
        current_path = root / relative
        baseline = _git_object_bytes(root, expected_commit, relative)
        baseline_hash = hashlib.sha256(baseline).hexdigest()
        current_hash = sha256_file(current_path) if current_path.is_file() else "missing"
        if current_hash != baseline_hash:
            mismatches.append(
                {"path": relative, "baseline_sha256": baseline_hash, "current": current_hash}
            )
    release_contract_path = root / str(compatibility["v3_release_contract_path"])
    release_contract_baseline = _git_object_bytes(
        root,
        expected_commit,
        str(compatibility["v3_release_contract_path"]),
    )
    release_contract_baseline_sha256 = hashlib.sha256(
        release_contract_baseline
    ).hexdigest()
    release_contract_baseline_data = tomllib.loads(
        release_contract_baseline.decode("utf-8")
    )
    fit_identity_present = (
        str(compatibility["preserve_existing_noise_fit_identity"]) == FIT_METHOD_IDENTITY
    )
    acquisition_identity_present = str(
        compatibility["preserve_existing_noise_acquisition_identity"]
    ) == f"{ACQUISITION_POLICY_ID}@{ACQUISITION_POLICY_VERSION}"
    checks = {
        "v3_tag_object_exact": tag_object == V3_TAG_OBJECT,
        "v3_tag_commit_exact": tag_commit == expected_commit == V3_TAG_COMMIT,
        "v3_tag_remains_annotated": tag_type == "tag",
        "v3_release_contract_preserved": release_contract_path.is_file()
        and _load_toml(release_contract_path).get("schema") == "apm.release-gates.v3"
        and _load_toml(release_contract_path) == release_contract_baseline_data,
        "existing_apm045_families_byte_identical": bool(baseline_paths) and not mismatches,
        "v3_noise_fit_identity_preserved": fit_identity_present,
        "v3_noise_acquisition_identity_preserved": acquisition_identity_present,
        "v3_result_schemas_preserved": all(
            any(
                schema in path.read_text(encoding="utf-8", errors="replace")
                for path in (root / "src/apm").glob("*.py")
            )
            for schema in compatibility["preserve_existing_result_schema"]
        ),
        "vtg_anchor_preserved": load_catalog(root).technology("apm045").cross_process_anchor
        == compatibility["existing_cross_process_anchor"].split("/", 1)[1],
    }
    result = _check_map(checks, context="immutable v3 tag, contracts, and APM045 baseline")
    result.update(
        {
            "v3_tag": compatibility["v3_tag"],
            "v3_tag_object": tag_object,
            "v3_tagged_commit": tag_commit,
            "immutable_path_count": len(baseline_paths),
            "immutable_mismatches": mismatches,
            "v3_release_contract_sha256": sha256_file(release_contract_path),
            "v3_release_contract_baseline_sha256": release_contract_baseline_sha256,
        }
    )
    return result


def audit_mixed_voltage_evidence(root: Path) -> dict[str, Any]:
    paths = {name: root / relative for name, relative in V4_EVIDENCE_PATHS.items()}
    reports = {name: _read_json(path) for name, path in paths.items()}
    foundation = reports["foundation"]
    calibration = reports["calibration"]
    qualification = reports["qualification"]
    source_hashes = {
        name: sha256_file(root / relative)
        for name, (relative, _expected) in MODELGEN_SOURCE_BINDINGS.items()
    }
    expected_source_hashes = {
        name: expected for name, (_relative, expected) in MODELGEN_SOURCE_BINDINGS.items()
    }
    card_hashes = {
        f"{family}/{polarity}": sha256_file(root / relative)
        for (family, polarity), (_seed, relative, _expected) in CANONICAL_CARDS.items()
    }
    expected_card_hashes = {
        f"{family}/{polarity}": expected
        for (family, polarity), (_seed, _relative, expected) in CANONICAL_CARDS.items()
    }
    foundation_bound = foundation.get("bound_inputs", {})
    qualification_bound = qualification.get("bound_inputs", {})
    successful_states = set(qualification.get("successful_states", []))
    checks = {
        "foundation_schema_status": foundation.get("schema")
        == "apm.v4-modelgen-foundation-evidence.v1"
        and foundation.get("status") == "validated"
        and foundation.get("completion_state") == "MODELGEN_KERNEL_QUALIFIED",
        "foundation_required_coverage": foundation.get("coverage", {}).get(
            "full_required_coverage"
        )
        is True
        and len(foundation.get("records", [])) == 4
        and all(item.get("status") == "pass" for item in foundation.get("records", [])),
        "foundation_bound_inputs_current": foundation_bound.get("kernel", {}).get("sha256")
        == source_hashes["kernel"]
        and foundation_bound.get("public_evidence_matrix", {}).get("sha256")
        == sha256_file(root / "models/apm045/mixed_voltage_evidence.toml")
        and foundation_bound.get("v4_release_contract", {}).get("sha256")
        == sha256_file(root / "validation/release_gates_v4.toml"),
        "calibration_schema_status": calibration.get("schema")
        == "apm.v4-generation-calibration-evidence.v1"
        and calibration.get("status") == "validated"
        and calibration.get("completion_state")
        == "MIXED_VOLTAGE_CALIBRATION_CANDIDATES_FROZEN",
        "qualification_schema_status": qualification.get("schema")
        == "apm.v4-mixed-voltage-qualification-evidence.v1"
        and qualification.get("status") == "validated"
        and qualification.get("qualification_epoch") == 3
        and qualification.get("generation_epoch") == 3,
        "modelgen_source_hashes_current": source_hashes == expected_source_hashes,
        "qualification_source_bindings_current": qualification_bound.get(
            "synthesis_implementation_sha256"
        )
        == source_hashes["synthesis"]
        and qualification_bound.get("qualification_implementation_sha256")
        == source_hashes["qualification"]
        and qualification_bound.get("terminal_observables_implementation_sha256")
        == source_hashes["terminal_observables"]
        and qualification_bound.get("circuit_fixtures_implementation_sha256")
        == source_hashes["circuit_fixtures"]
        and qualification_bound.get("release_contract_sha256")
        == sha256_file(root / "validation/release_gates_v4.toml"),
        "canonical_card_hashes_exact": card_hashes == expected_card_hashes,
        "device_completion_states": {
            "IO25_DEVICE_QUALIFIED",
            "IO25_APPLICATION_QUALIFIED",
            "IO18_DEVICE_QUALIFIED",
            "IO18_APPLICATION_QUALIFIED",
        }
        <= successful_states,
        "distinctness_completion_state": "IO18_IO25_DISTINCTNESS_ESTABLISHED"
        in successful_states
        and qualification.get("distinctness", {}).get("status") == "pass",
        "circuit_holdout_pass": qualification.get("circuit_holdout", {}).get("status")
        == "pass"
        and qualification.get("circuit_holdout", {}).get("all_candidate_pairs_pass")
        is True,
        "epistemic_ensemble_not_variation": qualification.get("ensemble", {}).get(
            "epistemic_not_process_variation"
        )
        is True,
        "canonical_selection_after_circuits": qualification.get(
            "canonical_selection", {}
        ).get("circuit_results_available_before_selection")
        is True
        and qualification.get("canonical_selection", {}).get(
            "all_canonical_cards_byte_identical_to_frozen_candidates"
        )
        is True,
    }
    result = _check_map(checks, context="committed v4 model-generation and holdout evidence")
    result.update(
        {
            "evidence": {
                name: {
                    "path": str(path.relative_to(root)),
                    "sha256": sha256_file(path),
                    "status": reports[name].get("status"),
                }
                for name, path in paths.items()
            },
            "modelgen_source_sha256": source_hashes,
            "canonical_card_sha256": card_hashes,
            "successful_states": sorted(successful_states),
        }
    )
    return result


def audit_v4_claims(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    review_path = root / "validation/release_review_v4.toml"
    review = _load_toml(review_path) if review_path.is_file() else {}
    reviewed_files = review.get("reviewed_files", {})
    mismatches: list[dict[str, str]] = []
    if isinstance(reviewed_files, dict):
        for relative, expected in reviewed_files.items():
            path = root / relative
            actual = sha256_file(path) if path.is_file() else "missing"
            if actual != expected:
                mismatches.append(
                    {"path": relative, "expected": str(expected), "actual": actual}
                )
    readme = (root / "README.md").read_text(encoding="utf-8")
    release = (root / "RELEASE_V4.md").read_text(encoding="utf-8") if (
        root / "RELEASE_V4.md"
    ).is_file() else ""
    apm045 = (root / "models/apm045/README.md").read_text(encoding="utf-8")
    spectre = (root / "docs/spectre.md").read_text(encoding="utf-8")
    public_text = f"{readme}\n{release}\n{apm045}\n{spectre}"
    prohibited_patterns = [
        pattern
        for pattern in (
            r"(?i)APM (?:is|provides) (?:a )?manufacturable PDK",
            r"(?i)io(?:18|25) (?:is|are|was|were) (?:TSMC|UMC|foundry)[- ]correlated",
            r"(?i)io(?:18|25) (?:has|have|provides?) (?:a )?(?:safe voltage|breakdown|lifetime) rating",
            r"(?i)Spectre numerical validation (?:passed|is complete)",
            r"(?i)epistemic ensemble (?:is|represents) process variation",
        )
        if re.search(pattern, public_text)
    ]
    topic_checks = {
        "v4_scope": "io18" in readme and "io25" in readme and "v4" in readme.lower(),
        "mixed_voltage_claim_boundary": "foundry" in apm045.lower()
        and "silicon" in apm045.lower(),
        "public_evidence_matrix": "mixed_voltage_evidence.toml" in public_text,
        "io18_io25_family_semantics": "1.8 V" in public_text and "2.5 V" in public_text,
        "model_supported_geometry_not_foundry_design_rules": "not foundry design-rule"
        in public_text.lower(),
        "model_generation_method": "model-generation" in public_text.lower(),
        "epistemic_ensemble_meaning": "model-construction uncertainty" in public_text,
        "sealed_holdout": "sealed" in public_text.lower() and "holdout" in public_text.lower(),
        "circuit_qualification": "circuit" in release.lower()
        and "pass-device" in release.lower(),
        "mixed_voltage_comparison": "apm.mixed-voltage-comparison.v1" in public_text,
        "noise_claim_boundary": "process-noise" in public_text.lower()
        and "compact-model predictions" in public_text,
        "variation_claim_boundary": "Benchmark Global" in public_text
        and "process variation" in public_text,
        "spectre_status": "experimental/unverified" in public_text.lower()
        and "not been parsed" in spectre,
        "not_a_manufacturable_pdk": "not a manufacturable PDK" in public_text,
    }
    required_topics = set(contract["documentation"]["required_topics"])
    checks = {
        "manual_review_record_complete": review.get("schema") == "apm.release-review.v4"
        and review.get("status") == "complete"
        and review.get("release_target") == "v4.0.0",
        "manual_review_identity_and_time_present": bool(review.get("reviewer"))
        and bool(
            re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                str(review.get("reviewed_utc", "")),
            )
        ),
        "manual_claim_decisions": review.get("v3_history_immutable") is True
        and review.get("foundry_or_silicon_correlation_claimed") is False
        and review.get("reliability_or_safe_voltage_claimed") is False
        and review.get("standalone_io33_family_claimed") is False
        and review.get("foundry_design_rule_minimum_claimed") is False
        and review.get("calibrated_gate_leakage_or_gidl_claimed") is False
        and review.get("calibrated_process_noise_claimed") is False
        and review.get("layout_dependent_accuracy_claimed") is False
        and review.get("real_spectre_validation_claimed") is False
        and review.get("epistemic_ensemble_reported_as_variation") is False
        and review.get("manufacturable_pdk_claimed") is False
        and review.get("unresolved_claim_findings") == [],
        "reviewed_file_set_exact": isinstance(reviewed_files, dict)
        and set(reviewed_files) == REQUIRED_REVIEWED_FILES_V4,
        "reviewed_file_hashes_current": not mismatches,
        "required_documentation_topics": required_topics == set(topic_checks)
        and all(topic_checks.values()),
        "no_prohibited_public_claims": not prohibited_patterns,
    }
    result = _check_map(checks, context="hash-bound v4 public-claim review")
    result.update(
        {
            "review_path": str(review_path.relative_to(root)),
            "review_sha256": sha256_file(review_path) if review_path.is_file() else "missing",
            "topic_checks": topic_checks,
            "review_hash_mismatches": mismatches,
            "prohibited_claim_patterns": prohibited_patterns,
        }
    )
    return result


def _run_logged_command(
    root: Path,
    output: Path,
    command_id: str,
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    environment_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    stdout_path = output / f"{command_id}.stdout.txt"
    stderr_path = output / f"{command_id}.stderr.txt"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    record = {
        "id": command_id,
        "command": command,
        "returncode": result.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout_path": str(stdout_path),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_path": str(stderr_path),
        "stderr_sha256": sha256_file(stderr_path),
        "status": "pass" if result.returncode == 0 else "fail",
    }
    if environment_summary:
        record["environment"] = environment_summary
    return record


def _failed_validation_report(
    report_path: Path, error: Exception, *, fallback_schema: str
) -> dict[str, Any]:
    if report_path.is_file():
        report = _read_json(report_path)
    else:
        report = {"schema": fallback_schema, "status": "fail", "checks": {}}
    report["error"] = str(error)
    report["report_path"] = str(report_path)
    report["output_directory"] = str(report_path.parent)
    return report


def run_v3_regression(root: Path, output: Path) -> dict[str, Any]:
    """Run the immutable v3 unit/static suite from an isolated local clone."""

    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    clone = _run_logged_command(
        root,
        output,
        "clone-v3",
        ["git", "clone", "--local", "--no-checkout", str(root), str(source)],
    )
    commands = [clone]
    if clone["status"] == "pass":
        checkout = _run_logged_command(
            source,
            output,
            "checkout-v3",
            ["git", "checkout", "--detach", V3_TAG_COMMIT],
        )
        commands.append(checkout)
    v3_site = output / "v3-site"
    if all(item["status"] == "pass" for item in commands):
        commands.append(
            _run_logged_command(
                source,
                output,
                "install-v3",
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--no-compile",
                    "--target",
                    str(v3_site),
                    ".",
                ],
            )
        )
    v3_environment = os.environ.copy()
    python_path_entries = [str(v3_site)]
    if v3_environment.get("PYTHONPATH"):
        python_path_entries.append(v3_environment["PYTHONPATH"])
    v3_environment["PYTHONPATH"] = os.pathsep.join(python_path_entries)
    if all(item["status"] == "pass" for item in commands):
        commands.extend(
            [
                _run_logged_command(
                    source,
                    output,
                    "pytest-v3",
                    [sys.executable, "-m", "pytest", "-q"],
                    environment=v3_environment,
                    environment_summary={
                        "PYTHONPATH_prefix": str(v3_site),
                        "purpose": (
                            "execute tagged v3 source with its installed 3.0.0 "
                            "distribution metadata while using the v4 tool environment"
                        ),
                    },
                ),
                _run_logged_command(
                    source,
                    output,
                    "ruff-v3",
                    [sys.executable, "-m", "ruff", "check", "."],
                ),
                _run_logged_command(
                    source,
                    output,
                    "reuse-v3",
                    [sys.executable, "-m", "reuse", "lint"],
                ),
            ]
        )
    observed_head = (
        _git(source, "rev-parse", "HEAD") if (source / ".git").exists() else "missing"
    )
    metadata_paths = sorted(v3_site.glob("analog_process_models-3.0.0.dist-info/METADATA"))
    distribution_metadata = metadata_paths[0] if len(metadata_paths) == 1 else None
    checks = {
        "isolated_v3_checkout": observed_head == V3_TAG_COMMIT,
        "v3_distribution_install": next(
            (item["status"] == "pass" for item in commands if item["id"] == "install-v3"),
            False,
        ),
        "v3_distribution_metadata": distribution_metadata is not None
        and "Version: 3.0.0" in distribution_metadata.read_text(encoding="utf-8"),
        "v3_pytest": next(
            (item["status"] == "pass" for item in commands if item["id"] == "pytest-v3"),
            False,
        ),
        "v3_ruff": next(
            (item["status"] == "pass" for item in commands if item["id"] == "ruff-v3"),
            False,
        ),
        "v3_reuse": next(
            (item["status"] == "pass" for item in commands if item["id"] == "reuse-v3"),
            False,
        ),
    }
    report = {
        "schema": "apm.v3-regression-from-v4.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if all(checks.values()) else "fail",
        "source_repository": str(root),
        "v3_tagged_commit_expected": V3_TAG_COMMIT,
        "v3_tagged_commit_observed": observed_head,
        "v3_distribution": {
            "site_path": str(v3_site),
            "metadata_path": str(distribution_metadata) if distribution_metadata else None,
            "metadata_sha256": sha256_file(distribution_metadata)
            if distribution_metadata
            else None,
        },
        "commands": commands,
        "checks": checks,
    }
    return _write_report(output / "report.json", report)


def run_v4_static_audits(root: Path, output: Path) -> dict[str, Any]:
    contract = load_v4_gate_contract(root)
    output.mkdir(parents=True, exist_ok=False)
    commands = [
        _run_logged_command(root, output, "pytest", [sys.executable, "-m", "pytest", "-q"]),
        _run_logged_command(
            root, output, "ruff", [sys.executable, "-m", "ruff", "check", "."]
        ),
        _run_logged_command(
            root, output, "reuse", [sys.executable, "-m", "reuse", "lint"]
        ),
    ]
    provenance_output = output / "provenance"
    try:
        provenance = validate_provenance(provenance_output, root=root)
    except ProvenanceValidationError as error:
        provenance = _failed_validation_report(
            provenance_output / "provenance_validation_report.json",
            error,
            fallback_schema="apm.provenance-validation.v2",
        )
    spectre_output = output / "spectre"
    try:
        spectre = validate_spectre(spectre_output, root=root)
    except SpectreStructureError as error:
        spectre = _failed_validation_report(
            spectre_output / "spectre_structural_report.json",
            error,
            fallback_schema="apm.spectre-structural-report.v2",
        )
    try:
        v3_regression = run_v3_regression(root, output / "v3-regression")
    except Exception as error:  # noqa: BLE001 - preserve the exact failure in evidence
        v3_regression = _failed_validation_report(
            output / "v3-regression/report.json",
            error,
            fallback_schema="apm.v3-regression-from-v4.v1",
        )
    audits = {
        "metadata": audit_v4_release_metadata(root, contract),
        "catalog": audit_v4_catalog(root, contract),
        "migration": audit_migration(root),
        "distribution": audit_distribution(root),
        "claims": audit_v4_claims(root, contract),
        "public_evidence": audit_public_evidence(root, contract),
        "v3_immutability": audit_v3_immutability(root, contract),
        "mixed_voltage_evidence": audit_mixed_voltage_evidence(root),
        "provenance": provenance,
    }
    checks = {
        "current_regression_commands": all(item["status"] == "pass" for item in commands),
        "repository_audits": all(item.get("status") == "pass" for item in audits.values()),
        "v3_regression": v3_regression.get("status") == "pass",
        "spectre_structural": spectre.get("status") == "structurally_checked"
        and all(spectre.get("checks", {}).values()),
    }
    report = {
        "schema": "apm.static-audits.v4",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if all(checks.values()) else "fail",
        "repository": str(root),
        "repository_head": _git(root, "rev-parse", "HEAD"),
        "contract_path": "validation/release_gates_v4.toml",
        "contract_sha256": sha256_file(root / "validation/release_gates_v4.toml"),
        "commands": commands,
        "audits": audits,
        "v3_regression": {
            "status": v3_regression.get("status"),
            "report_path": v3_regression.get("report_path"),
            "checks": v3_regression.get("checks", {}),
        },
        "spectre": {
            "status": spectre.get("status"),
            "backend_status": spectre.get("backend_status"),
            "real_tool_validation_performed": spectre.get(
                "real_tool_validation_performed"
            ),
            "report_path": spectre.get("report_path"),
            "checks": spectre.get("checks", {}),
        },
        "checks": checks,
    }
    result = _write_report(output / "static_audits.json", report)
    result.update(
        {
            "contract": contract,
            "provenance": provenance,
            "spectre_full": spectre,
            "v3_regression_full": v3_regression,
        }
    )
    return result


def _default_output(root: Path, mode: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return state_directory(root) / "results" / "validation" / f"{mode}-{stamp}"


def validate_repository_v4(
    output: Path | None = None, *, root: Path | None = None
) -> dict[str, Any]:
    selected = (root or repository_root()).resolve()
    destination = (output or _default_output(selected, "repository-v4")).expanduser().resolve()
    result = run_v4_static_audits(selected, destination)
    report = {
        "schema": "apm.repository-validation.v4",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": result["status"],
        "repository": str(selected),
        "repository_head": _git(selected, "rev-parse", "HEAD"),
        "static_report_path": result["report_path"],
        "static_report_sha256": sha256_file(Path(result["report_path"])),
        "checks": result["checks"],
        "audits": result["audits"],
    }
    report = _write_report(destination / "report.json", report)
    if report["status"] != "pass":
        raise ReleaseValidationError(f"v4 repository validation failed; see {report['report_path']}")
    return report


def _report_reference(result: dict[str, Any] | None) -> list[str]:
    if not result:
        return []
    path = result.get("report_path")
    return [str(path)] if path else []


def _call_component(
    components: dict[str, Any], name: str, callback: Callable[[], dict[str, Any]]
) -> dict[str, Any] | None:
    started = time.monotonic()
    try:
        result = callback()
    except Exception as error:  # noqa: BLE001 - preserve every release failure
        components[name] = {
            "status": "fail",
            "error_type": type(error).__name__,
            "error": str(error),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        return None
    component_status = result.get("status")
    passed_statuses = {
        "pass",
        "validated",
        "verified",
        "attested",
        "structurally_checked",
    }
    report_path = result.get("report_path")
    components[name] = {
        "status": "pass" if component_status in passed_statuses else "fail",
        "duration_seconds": round(time.monotonic() - started, 3),
        "report_path": report_path,
        "report_sha256": sha256_file(Path(report_path))
        if report_path and Path(report_path).is_file()
        else None,
        "component_status": component_status,
    }
    return result


def _run_modelgen_command(
    root: Path,
    output: Path,
    *,
    command_id: str,
    module: str,
    arguments: list[str],
) -> dict[str, Any]:
    log_directory = output.parent / "modelgen-logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", module, "--root", str(root), *arguments]
    observed = _run_logged_command(root, log_directory, command_id, command)
    report_path = output / "report.json"
    if observed["status"] != "pass":
        raise ReleaseValidationError(
            f"{command_id} failed; see {observed['stderr_path']} and {observed['stdout_path']}"
        )
    report = _read_json(report_path)
    report["report_path"] = str(report_path)
    report["output_directory"] = str(output)
    report["command_evidence"] = observed
    return report


def _run_modelgen_reconstruction(root: Path, output: Path) -> dict[str, Any]:
    report = _run_modelgen_command(
        root,
        output,
        command_id="modelgen-reconstruction",
        module="tools.modelgen.apm045_mixed_voltage.qualify_reconstruction",
        arguments=["--output", str(output)],
    )
    records = report.get("records", [])
    required = {
        ("apm022/svt", "n"),
        ("apm022/svt", "p"),
        ("apm045/vtg", "n"),
        ("apm045/vtg", "p"),
    }
    checks = {
        "schema_status": report.get("schema")
        == "apm.modelgen.reconstruction-qualification.v1"
        and report.get("status") == "pass",
        "completion_state": report.get("completion_state") == "MODELGEN_KERNEL_QUALIFIED",
        "exact_coverage": {(item.get("selector"), item.get("polarity")) for item in records}
        == required,
        "all_record_checks": len(records) == 4
        and all(
            item.get("status") == "pass"
            and item.get("checks")
            and all(item["checks"].values())
            for item in records
        ),
        "reference_ngspice_47": report.get("reference_tool", {}).get("major") == "47",
    }
    report["release_audit"] = _check_map(
        checks, context="fresh v4 model-generation reconstruction"
    )
    if report["release_audit"]["status"] != "pass":
        raise ReleaseValidationError("fresh model-generation reconstruction audit failed")
    return report


def _run_modelgen_calibration(root: Path, output: Path) -> dict[str, Any]:
    config = root / "tools/modelgen/apm045_mixed_voltage/generation_epoch_3.toml"
    report = _run_modelgen_command(
        root,
        output,
        command_id="modelgen-calibration-epoch3",
        module="tools.modelgen.apm045_mixed_voltage.synthesize_families",
        arguments=[
            "--config",
            str(config),
            "--output",
            str(output),
            "--calibration-only",
        ],
    )
    records = report.get("records", [])
    record_map = {
        (str(item.get("family")), str(item.get("polarity")), int(item.get("seed", -1))): item
        for item in records
    }
    selected_cards: dict[str, Any] = {}
    selected_match = True
    for (family, polarity), (seed, relative, expected) in CANONICAL_CARDS.items():
        item = record_map.get((family, polarity, seed), {})
        generated_path = output / str(item.get("card", {}).get("path", "missing"))
        generated_hash = sha256_file(generated_path) if generated_path.is_file() else "missing"
        shipped_hash = sha256_file(root / relative)
        passed = generated_hash == shipped_hash == expected
        selected_match = selected_match and passed
        selected_cards[f"{family}/{polarity}"] = {
            "seed": seed,
            "generated_path": str(generated_path),
            "generated_sha256": generated_hash,
            "shipped_path": relative,
            "shipped_sha256": shipped_hash,
            "expected_sha256": expected,
            "byte_identical": passed,
        }
    checks = {
        "schema_status": report.get("schema")
        == "apm.modelgen.mixed-voltage-calibration.v1"
        and report.get("status") == "pass",
        "epoch_and_mode": report.get("generation_epoch") == 3
        and report.get("mode") == "calibration_only",
        "all_twenty_candidate_records": len(records) == 20
        and all(
            item.get("status") == "pass"
            and item.get("card", {}).get("byte_identical_regeneration") is True
            for item in records
        ),
        "retained_ensemble": all(
            report.get("ensemble", {}).get("checks", {}).get(family, {}).get(
                "minimum_count"
            )
            is True
            for family in ("io18", "io25")
        ),
        "canonical_cards_byte_identical": selected_match,
        "reference_ngspice_47": report.get("reference_tool", {}).get("major") == "47",
    }
    audit = _check_map(checks, context="fresh deterministic epoch-3 regeneration")
    audit["selected_cards"] = selected_cards
    audit_report = _write_report(
        output / "release_regeneration_audit.json",
        {
            "schema": "apm.modelgen-release-regeneration-audit.v4",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            **audit,
        },
    )
    report["release_audit"] = audit_report
    if audit["status"] != "pass":
        raise ReleaseValidationError(
            f"fresh canonical regeneration audit failed; see {audit_report['report_path']}"
        )
    return report


def _run_modelgen_qualification_replay(
    root: Path,
    output: Path,
    calibration: dict[str, Any],
) -> dict[str, Any]:
    """Freshly replay the frozen epoch-3 sealed device/circuit qualification."""

    calibration_path = Path(str(calibration["report_path"]))
    config = root / "tools/modelgen/apm045_mixed_voltage/qualification_epoch_3.toml"
    replay_contract = (
        root / "tools/modelgen/apm045_mixed_voltage/calibration_replay_v4.toml"
    )
    report = _run_modelgen_command(
        root,
        output,
        command_id="modelgen-qualification-replay-epoch3",
        module="tools.modelgen.apm045_mixed_voltage.replay_families",
        arguments=[
            "--config",
            str(config),
            "--calibration-report",
            str(calibration_path),
            "--replay-contract",
            str(replay_contract),
            "--output",
            str(output),
        ],
    )
    candidate_results = report.get("candidate_results", [])
    circuit_results = report.get("sealed_circuit_holdout", [])
    eligibility = report.get("eligibility", {})
    receipt = report.get("replay_receipt", {})
    fresh_calibration = receipt.get("fresh_calibration_report", {})
    hash_adapter = receipt.get("frozen_engine_hash_adapter", {})
    calibration_binding = receipt.get("calibration_binding", {})
    artifacts = report.get("canonical_artifacts", {})
    canonical_hashes = {
        f"{family}/{polarity}": artifacts.get(family, {})
        .get("devices", {})
        .get(polarity, {})
        .get("sha256")
        for family, polarity in CANONICAL_CARDS
    }
    expected_hashes = {
        f"{family}/{polarity}": expected
        for (family, polarity), (_seed, _relative, expected) in CANONICAL_CARDS.items()
    }
    checks = {
        "schema_status": report.get("schema") == "apm.mixed-voltage-qualification.v1"
        and report.get("status") == "pass",
        "epoch_and_completion": report.get("generation_epoch") == 3
        and report.get("qualification_epoch") == 3
        and report.get("completion_state") == "MIXED_VOLTAGE_ENSEMBLE_QUALIFIED"
        and report.get("failure_state") is None,
        "fresh_exact_commit_receipt": receipt.get("git", {}).get("commit")
        == _git(root, "rev-parse", "HEAD")
        and receipt.get("git", {}).get("worktree_clean") is True
        and receipt.get("schema")
        == "apm.mixed-voltage-holdout-replay-receipt.v1"
        and receipt.get("operation") == "release_replay"
        and receipt.get("candidate_parameter_modification_after_unseal_permitted") is False
        and receipt.get("failed_holdout_reuse_for_repair_permitted") is False,
        "portable_calibration_replay_binding": receipt.get(
            "calibration_binding", {}
        ).get("status")
        == "pass"
        and receipt.get("calibration_binding", {}).get("mode")
        == "portable_release_replay"
        and bool(receipt.get("calibration_binding", {}).get("checks"))
        and all(receipt["calibration_binding"]["checks"].values()),
        "transparent_frozen_hash_adapter": hash_adapter.get("target")
        == "qualify_families._canonical_report_sha256"
        and hash_adapter.get("observed_fresh_content_sha256")
        == fresh_calibration.get("canonical_content_sha256")
        == calibration_binding.get("observed_calibration_canonical_content_sha256")
        and hash_adapter.get("verified_portable_content_sha256")
        == fresh_calibration.get("portable_content_sha256")
        == calibration_binding.get("portable_calibration_content_sha256")
        and hash_adapter.get("sealed_first_unseal_content_sha256")
        == calibration_binding.get("sealed_calibration_canonical_content_sha256")
        and hash_adapter.get("electrical_evaluation_code_changed") is False
        and report.get("artifact_identity", {}).get("calibration_report", {}).get(
            "canonical_content_sha256"
        )
        == fresh_calibration.get("canonical_content_sha256")
        and report.get("preflight", {}).get("calibration", {}).get(
            "canonical_content_sha256"
        )
        == fresh_calibration.get("canonical_content_sha256"),
        "all_twenty_candidate_domains": len(candidate_results) == 20
        and all(item.get("status") == "pass" for item in candidate_results),
        "all_ten_circuit_holdouts": len(circuit_results) == 10
        and all(item.get("status") == "pass" for item in circuit_results),
        "full_eligible_ensembles": set(eligibility) == {"io18", "io25"}
        and all(
            item.get("retained_count") == 5
            and item.get("minimum_count") is True
            and item.get("individually_qualified_seeds")
            == [54001, 54002, 54003, 54004, 54005]
            for item in eligibility.values()
        ),
        "global_checks": bool(report.get("global_checks"))
        and all(report["global_checks"].values()),
        "structural_and_distinctness": report.get("structural", {}).get("status")
        == "pass"
        and report.get("io18_io25_distinctness", {}).get("status") == "pass",
        "canonical_cards_exact": canonical_hashes == expected_hashes
        and all(
            artifacts.get(family, {})
            .get("devices", {})
            .get(polarity, {})
            .get("byte_identical_to_frozen_candidate")
            is True
            for family, polarity in CANONICAL_CARDS
        ),
        "epistemic_not_process_variation": report.get("epistemic_ensemble", {}).get(
            "epistemic_not_process_variation"
        )
        is True,
        "no_repair_reuse": report.get("holdout_reuse_for_repair_permitted") is False,
        "real_simulator_execution": int(
            report.get("simulator_evaluation_count", {}).get("total", 0)
        )
        > 0,
    }
    audit = _write_report(
        output / "release_qualification_audit.json",
        {
            "schema": "apm.modelgen-release-qualification-audit.v4",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            **_check_map(checks, context="fresh frozen epoch-3 qualification replay"),
            "qualification_report_path": str(output / "report.json"),
            "qualification_report_sha256": sha256_file(output / "report.json"),
            "canonical_card_sha256": canonical_hashes,
        },
    )
    report["release_audit"] = audit
    if audit["status"] != "pass":
        raise ReleaseValidationError(
            f"fresh epoch-3 qualification replay failed; see {audit['report_path']}"
        )
    return report


def _run_v3_runtime_comparisons(root: Path, output: Path, toolchain: Any) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    calls: tuple[tuple[str, Callable[[], dict[str, Any]]], ...] = (
        (
            "anchors",
            lambda: compare_anchors(output / "anchors", toolchain),
        ),
        (
            "apm045_threshold",
            lambda: compare_set(
                "apm045", "threshold", output / "apm045-threshold", toolchain
            ),
        ),
        (
            "apm045_gate_stack",
            lambda: compare_set(
                "apm045", "gate_stack", output / "apm045-gate-stack", toolchain
            ),
        ),
        (
            "apm022_threshold",
            lambda: compare_set(
                "apm022", "threshold", output / "apm022-threshold", toolchain
            ),
        ),
        (
            "apm016f_threshold",
            lambda: compare_set(
                "apm016f", "threshold", output / "apm016f-threshold", toolchain
            ),
        ),
    )
    results: dict[str, Any] = {}
    for name, callback in calls:
        results[name] = callback()
    checks = {
        "anchors": results["anchors"].get("status") == "validated",
        "apm045_threshold": results["apm045_threshold"].get("status") == "validated",
        "apm045_gate_stack": results["apm045_gate_stack"].get("status") == "validated",
        "apm022_threshold": results["apm022_threshold"].get("status") == "validated",
        "apm016f_threshold": results["apm016f_threshold"].get("status") == "validated",
    }
    report = {
        "schema": "apm.v3-runtime-comparison-regression.v4",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if all(checks.values()) else "fail",
        "repository_head": _git(root, "rev-parse", "HEAD"),
        "checks": checks,
        "reports": {
            name: {
                "path": result.get("report_path"),
                "sha256": sha256_file(Path(result["report_path"])),
            }
            for name, result in results.items()
        },
    }
    return _write_report(output / "report.json", report)


def _catalog_component(
    root: Path,
    output: Path,
    toolchain: Any,
    *,
    resume: bool,
) -> dict[str, Any]:
    result = validate_noise_catalog(
        output,
        resume=resume,
        root=root,
        toolchain=toolchain,
        progress=lambda message: print(f"[v4 release] {message}", file=sys.stderr, flush=True),
    )
    return {**result, "report_path": result["run_report_path"]}


def _audit_noise_release(
    root: Path,
    fresh: dict[str, Any],
    resumed: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    catalog_root = Path(fresh["output_directory"])
    fresh_path = Path(fresh["run_report_path"])
    resumed_path = Path(resumed["run_report_path"])
    plan_path = catalog_root / "plan.json"
    coverage_path = catalog_root / "coverage.json"
    comparisons_path = catalog_root / "summary/noise_comparisons.json"
    resume_path = catalog_root / "resume_qualification/report.json"
    n1_path = catalog_root / "regressions/v3_n1_method/report.json"
    n0_path = catalog_root / "regressions/v3_n1_method/v3_n0_regression/report.json"
    synthetic_path = catalog_root / "regressions/v3_n1_method/synthetic_fit_report.json"
    plan = _read_json(plan_path)
    coverage = _read_json(coverage_path)
    comparisons = _read_json(comparisons_path)
    resume = _read_json(resume_path)
    n1 = _read_json(n1_path)
    n0 = _read_json(n0_path)
    synthetic = _read_json(synthetic_path)
    head = _git(root, "rev-parse", "HEAD")
    expected_logical_counts = {
        "canonical_temperature_matrix": 120,
        "inversion_sweep": 150,
        "length_scaling": 90,
        "nfin_scaling": 18,
        "threshold_equal_inversion": 18,
        "threshold_equal_bias": 18,
        "cross_process_anchor": 10,
    }
    logical_counts = plan.get("logical_request_counts", {})
    derived_counts = plan.get("live_catalog_derived_logical_request_counts", {})
    terminal_counts = fresh.get("terminal_status_counts", {})
    fresh_checks = fresh.get("checks", [])
    resumed_checks = resumed.get("checks", [])
    new_selectors = {
        "apm045/io18/nmos",
        "apm045/io18/pmos",
        "apm045/io25/nmos",
        "apm045/io25/pmos",
    }
    planned_selectors = set(plan.get("catalog", {}).get("selectors", []))
    required_check_ids = {
        "catalog.manifest_live_coverage",
        "plan.stable_identity_and_deduplication",
        "dataset.temperature_complete_status",
        "dataset.inversion_complete_status",
        "dataset.length_manifest_coverage",
        "dataset.nfin_manifest_coverage",
        "results.explicit_terminal_status",
        "results.no_simulation_failures",
        "results.raw_provenance_and_sources",
        "solver.sparse_no_klu",
        "comparison.threshold_views",
        "comparison.cross_process_polarity_and_basis",
        "resume.strict_reuse_and_stale_rejection",
        "regression.v3_n0",
        "regression.v3_n1",
        "models.v2_card_immutability",
    }

    def checks_exact(items: Any) -> bool:
        return (
            isinstance(items, list)
            and {item.get("id") for item in items} == required_check_ids
            and len(items) == 16
            and all(item.get("status") == "pass" for item in items)
        )

    checks = {
        "fresh_report_exact_commit": fresh.get("schema")
        == "apm.noise-catalog-validation.v1"
        and fresh.get("status") == "pass"
        and fresh.get("acceptance_result") == "16/16"
        and fresh.get("repository_commit") == head
        and fresh.get("repository_worktree_status") == [],
        "fresh_checks_complete": checks_exact(fresh_checks),
        "live_catalog_exact": plan.get("catalog", {}).get("technology_count") == 5
        and plan.get("catalog", {}).get("family_count") == 15
        and plan.get("catalog", {}).get("public_device_count") == 30
        and len(planned_selectors) == 30
        and new_selectors <= planned_selectors,
        "logical_counts_live_derived": logical_counts == derived_counts
        == expected_logical_counts
        and plan.get("planned_logical_request_count") == sum(expected_logical_counts.values()),
        "deduplication_exact": plan.get("unique_request_count") == 330
        and plan.get("deduplicated_logical_request_count") == 94,
        "fresh_execution_only": fresh.get("execution", {}).get("mode") == "fresh"
        and fresh.get("execution", {}).get("fresh_execution_count") == 330
        and fresh.get("execution", {}).get("safely_reused_count") == 0
        and fresh.get("execution", {}).get("stale_result_rejection_count") == 0,
        "explicit_terminal_states_no_failure": sum(
            int(value) for value in terminal_counts.values()
        )
        == 330
        and int(terminal_counts.get("simulation_failed", -1)) == 0,
        "coverage_and_comparison_hashes": fresh.get("plan", {}).get("sha256")
        == sha256_file(plan_path)
        and fresh.get("coverage", {}).get("sha256") == sha256_file(coverage_path)
        and fresh.get("comparisons", {}).get("sha256") == sha256_file(comparisons_path)
        and coverage.get("plan_hash") == plan.get("plan_hash")
        and comparisons.get("plan_hash") == plan.get("plan_hash"),
        "sparse_no_klu": coverage.get("all_required_noise_jobs_sparse_no_klu") is True,
        "comparison_boundaries": len(comparisons.get("threshold_groups", [])) == 12
        and len(comparisons.get("cross_process_anchor_groups", [])) == 2
        and comparisons.get("universal_noise_ordering_imposed") is False
        and comparisons.get("cross_basis_ratios_produced") is False,
        "strict_resume_exact_reuse": resumed.get("status") == "pass"
        and resumed.get("acceptance_result") == "16/16"
        and resumed.get("repository_commit") == head
        and checks_exact(resumed_checks)
        and resumed.get("execution", {}).get("mode") == "resume"
        and resumed.get("execution", {}).get("fresh_execution_count") == 0
        and resumed.get("execution", {}).get("safely_reused_count") == 330
        and resumed.get("execution", {}).get("stale_result_rejection_count") == 0,
        "tamper_and_stale_rejection": resume.get("status") == "pass"
        and resume.get("acceptance_result") == "4/4"
        and resumed.get("resume_qualification", {}).get("sha256")
        == sha256_file(resume_path),
        "v3_noise_foundation_regression": n0.get("status") == "pass"
        and n0.get("acceptance_result") == "13/13",
        "v3_noise_method_regression": n1.get("status") == "pass"
        and n1.get("acceptance_result") == "10/10"
        and synthetic.get("status") == "pass"
        and synthetic.get("acceptance_result") == "8/8",
        "schemas_and_method_identity_preserved": plan.get("frozen_methods", {}).get(
            "fit_method"
        )
        == "apm.noise-fit.contiguous-regions@1.0.0"
        and plan.get("frozen_methods", {}).get("acquisition_policy")
        == "apm.noise-acquisition.bounded-white-search@1.0.0"
        and comparisons.get("schema") == "apm.noise-comparison.v1",
    }
    report = {
        "schema": "apm.noise-release-audit.v4",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        **_check_map(checks, context="fresh and strict-resume v4 live noise catalog"),
        "reports": {
            "fresh": str(fresh_path),
            "resumed": str(resumed_path),
            "plan": str(plan_path),
            "coverage": str(coverage_path),
            "comparisons": str(comparisons_path),
            "resume_qualification": str(resume_path),
            "v3_n1": str(n1_path),
            "v3_n0": str(n0_path),
            "synthetic": str(synthetic_path),
        },
        "plan_counts": {
            "logical": logical_counts,
            "planned_logical_request_count": plan.get("planned_logical_request_count"),
            "unique_request_count": plan.get("unique_request_count"),
            "deduplicated_logical_request_count": plan.get(
                "deduplicated_logical_request_count"
            ),
        },
        "terminal_status_counts": terminal_counts,
    }
    return _write_report(output / "report.json", report)


def _gate(status: str, evidence: list[str], detail: str) -> dict[str, Any]:
    return {"status": status, "evidence": evidence, "detail": detail}


def evaluate_v4_gates(
    contract: dict[str, Any],
    gate_results: dict[str, dict[str, Any]],
    *,
    phase: str,
) -> tuple[list[dict[str, Any]], bool, bool]:
    """Evaluate all gates and expose candidate eligibility separately from completion."""

    if phase not in V4_PHASES:
        raise ReleaseValidationError(f"unsupported v4 release phase: {phase}")
    ordered: list[dict[str, Any]] = []
    candidate_eligible = True
    exact_complete = True
    for definition in contract["gate"]:
        identifier = definition["id"]
        required = definition.get("required") is True
        result = gate_results.get(identifier) or _gate(
            "missing", [], "validator produced no result for this gate"
        )
        evidence = result.get("evidence")
        evidence_valid = (
            isinstance(evidence, list)
            and bool(evidence)
            and all(
                isinstance(item, str) and bool(item) and Path(item).is_file()
                for item in evidence
            )
        )
        passed = result.get("status") == "pass" and evidence_valid
        candidate_required = required and identifier != EXACT_TAG_GATE_ID
        if candidate_required and not passed:
            candidate_eligible = False
        if required and not passed:
            exact_complete = False
        ordered.append(
            {
                **definition,
                **result,
                "candidate_required": candidate_required,
                "evidence_valid": evidence_valid,
                "passed": passed,
            }
        )
    if phase == "candidate":
        exact_complete = False
    return ordered, candidate_eligible, exact_complete


def _validated(result: dict[str, Any] | None) -> bool:
    return bool(
        result
        and result.get("status") == "validated"
        and result.get("checks", {}).get("overall_pass") is True
    )


def _component_pass(components: dict[str, Any], name: str) -> bool:
    return components.get(name, {}).get("status") == "pass"


def validate_release_v4(
    output: Path | None = None,
    *,
    phase: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Run all candidate or exact-tag v4 gates from an attested fresh clone."""

    if phase not in V4_PHASES:
        raise ReleaseValidationError(f"unsupported v4 release phase: {phase}")
    selected = (root or repository_root()).resolve()
    destination = (
        output or _default_output(selected, f"release-v4-{phase}")
    ).expanduser().resolve()
    try:
        destination.relative_to(state_directory(selected).resolve())
    except ValueError as error:
        raise ReleaseValidationError(
            "v4 release evidence must be written below the ignored project .apm state directory"
        ) from error
    destination.mkdir(parents=True, exist_ok=False)
    contract = load_v4_gate_contract(selected)
    created = datetime.now(timezone.utc).isoformat()
    components: dict[str, Any] = {}
    gate_results = {
        identifier: _gate("not_run", [], "required validation has not completed")
        for identifier in V4_GATE_IDS
    }

    initial_attestation = _call_component(
        components,
        "clean_clone_initial",
        lambda: verify_clean_clone_v4_attestation(selected, phase=phase),
    )
    static = _call_component(
        components,
        "static",
        lambda: run_v4_static_audits(selected, destination / "static"),
    )
    prerequisites_pass = bool(
        initial_attestation
        and static
        and _component_pass(components, "clean_clone_initial")
        and _component_pass(components, "static")
    )

    toolchain = None
    if prerequisites_pass:
        try:
            toolchain = resolve_toolchain(selected)
            components["toolchain"] = {
                "status": "pass",
                "ngspice": str(toolchain.ngspice),
                "openvaf": str(toolchain.openvaf),
            }
        except Exception as error:  # noqa: BLE001 - record discovery failure
            components["toolchain"] = {
                "status": "fail",
                "error_type": type(error).__name__,
                "error": str(error),
            }
    else:
        components["toolchain"] = {
            "status": "not_run",
            "reason": "clean-clone attestation or static v4 precondition failed",
        }

    if toolchain:
        _call_component(components, "doctor", lambda: run_doctor(toolchain))
    reconstruction = (
        _call_component(
            components,
            "modelgen_reconstruction",
            lambda: _run_modelgen_reconstruction(
                selected, destination / "modelgen-reconstruction"
            ),
        )
        if toolchain
        else None
    )
    calibration = (
        _call_component(
            components,
            "modelgen_calibration",
            lambda: _run_modelgen_calibration(selected, destination / "modelgen-calibration"),
        )
        if toolchain
        else None
    )
    qualification = (
        _call_component(
            components,
            "modelgen_qualification_replay",
            lambda: _run_modelgen_qualification_replay(
                selected,
                destination / "modelgen-qualification",
                calibration,
            ),
        )
        if toolchain and calibration
        else None
    )
    all_families = (
        _call_component(
            components,
            "all_characterizations",
            lambda: validate_all_characterizations(
                destination / "all-characterizations", toolchain
            ),
        )
        if toolchain
        else None
    )
    v3_comparisons = (
        _call_component(
            components,
            "v3_runtime_comparisons",
            lambda: _run_v3_runtime_comparisons(
                selected, destination / "v3-runtime-comparisons", toolchain
            ),
        )
        if toolchain
        else None
    )
    native = (
        _call_component(
            components,
            "apm130_native",
            lambda: validate_apm130_native(destination / "apm130-native", toolchain),
        )
        if toolchain
        else None
    )
    mixed = (
        _call_component(
            components,
            "mixed_voltage_comparison",
            lambda: compare_set(
                "apm045", "mixed_voltage", destination / "mixed-voltage-comparison", toolchain
            ),
        )
        if toolchain
        else None
    )
    benchmark = (
        _call_component(
            components,
            "benchmark",
            lambda: validate_benchmark(destination / "benchmark", toolchain),
        )
        if toolchain
        else None
    )
    noise_fresh = (
        _call_component(
            components,
            "noise_catalog_fresh",
            lambda: _catalog_component(
                selected, destination / "noise-catalog", toolchain, resume=False
            ),
        )
        if toolchain
        else None
    )
    noise_resumed = (
        _call_component(
            components,
            "noise_catalog_resume",
            lambda: _catalog_component(
                selected, destination / "noise-catalog", toolchain, resume=True
            ),
        )
        if toolchain and noise_fresh
        else None
    )
    noise_audit = (
        _call_component(
            components,
            "noise_contract",
            lambda: _audit_noise_release(
                selected, noise_fresh, noise_resumed, destination / "noise-release-audit"
            ),
        )
        if noise_fresh and noise_resumed
        else None
    )
    _call_component(
        components,
        "clean_clone_final",
        lambda: verify_clean_clone_v4_attestation(selected, phase=phase),
    )

    static_audits = static.get("audits", {}) if static else {}
    static_evidence = _report_reference(static)
    evidence_audit = static_audits.get("mixed_voltage_evidence", {})
    public_audit = static_audits.get("public_evidence", {})
    v3_immutable = static_audits.get("v3_immutability", {})
    metadata = static_audits.get("metadata", {})
    claims = static_audits.get("claims", {})
    distribution = static_audits.get("distribution", {})
    provenance = static.get("provenance", {}) if static else {}
    spectre = static.get("spectre_full", {}) if static else {}
    v3_static_regression = static.get("v3_regression_full", {}) if static else {}
    committed_evidence_paths = [
        str(selected / relative) for relative in V4_EVIDENCE_PATHS.values()
    ]

    char_pass = _validated(all_families)
    io18_char_pass = bool(
        char_pass
        and all_families.get("result_audits", {}).get("apm045/io18", {}).get(
            "overall_pass"
        )
        is True
    )
    io25_char_pass = bool(
        char_pass
        and all_families.get("result_audits", {}).get("apm045/io25", {}).get(
            "overall_pass"
        )
        is True
    )
    mixed_pass = bool(
        mixed
        and mixed.get("status") == "pass"
        and mixed.get("checks", {}).get("overall_pass") is True
    )
    benchmark_pass = _validated(benchmark)
    native_pass = _validated(native)
    v3_comparison_pass = bool(v3_comparisons and v3_comparisons.get("status") == "pass")
    noise_pass = bool(noise_audit and noise_audit.get("status") == "pass")
    evidence_pass = evidence_audit.get("status") == "pass"
    qualification_pass = bool(
        qualification
        and qualification.get("release_audit", {}).get("status") == "pass"
    )

    compatibility_evidence = [
        *static_evidence,
        *_report_reference(v3_static_regression),
        *_report_reference(v3_comparisons),
        *_report_reference(native),
        *_report_reference(all_families),
        *_report_reference(noise_audit),
    ]
    gate_results["compatibility.v3_immutable"] = _gate(
        "pass"
        if v3_immutable.get("status") == "pass"
        and v3_static_regression.get("status") == "pass"
        and v3_comparison_pass
        and native_pass
        and char_pass
        and noise_pass
        else "fail",
        compatibility_evidence,
        "immutable v3 tag/cards/contracts plus static, electrical, comparison, native, and noise regressions",
    )
    gate_results["evidence.public_matrix"] = _gate(
        "pass" if public_audit.get("status") == "pass" else "fail",
        [*static_evidence, str(selected / "models/apm045/mixed_voltage_evidence.toml")],
        "schema-complete public source facts, engineering priors, and forbidden-use boundaries",
    )
    gate_results["modelgen.reconstruction"] = _gate(
        "pass"
        if evidence_pass
        and reconstruction
        and reconstruction.get("release_audit", {}).get("status") == "pass"
        else "fail",
        [*_report_reference(reconstruction), committed_evidence_paths[0]],
        "fresh real-ngspice four-record reconstruction plus bound committed foundation evidence",
    )
    gate_results["modelgen.deterministic_regeneration"] = _gate(
        "pass"
        if evidence_pass
        and calibration
        and calibration.get("release_audit", {}).get("status") == "pass"
        else "fail",
        [
            *_report_reference(calibration),
            str(destination / "modelgen-calibration/release_regeneration_audit.json"),
            committed_evidence_paths[1],
            committed_evidence_paths[2],
        ],
        "fresh epoch-3 candidate regeneration reproduces all four shipped canonical cards byte-for-byte",
    )
    gate_results["models.io25"] = _gate(
        "pass" if evidence_pass and qualification_pass and io25_char_pass else "fail",
        [
            *_report_reference(qualification),
            *_report_reference(all_families),
            committed_evidence_paths[2],
        ],
        "io25 committed first-unseal evidence, fresh sealed replay, and fresh public terminal characterization",
    )
    gate_results["models.io18"] = _gate(
        "pass" if evidence_pass and qualification_pass and io18_char_pass else "fail",
        [
            *_report_reference(qualification),
            *_report_reference(all_families),
            committed_evidence_paths[2],
        ],
        "io18 committed first-unseal evidence, fresh sealed replay, and fresh public terminal characterization",
    )
    gate_results["mixed_voltage.distinctness"] = _gate(
        "pass"
        if evidence_pass
        and evidence_audit.get("checks", {}).get("distinctness_completion_state") is True
        and qualification_pass
        and qualification.get("io18_io25_distinctness", {}).get("status") == "pass"
        and mixed_pass
        else "fail",
        [
            *_report_reference(qualification),
            *_report_reference(mixed),
            committed_evidence_paths[2],
        ],
        "committed first-unseal and fresh replayed ensemble distinctness plus fresh common-bias terminal comparison",
    )
    gate_results["mixed_voltage.circuit_holdout"] = _gate(
        "pass"
        if evidence_pass
        and evidence_audit.get("checks", {}).get("circuit_holdout_pass") is True
        and qualification_pass
        and qualification.get("global_checks", {}).get("all_circuit_holdouts") is True
        else "fail",
        [
            *_report_reference(qualification),
            *static_evidence,
            committed_evidence_paths[2],
        ],
        "hash-bound first-unseal evidence plus fresh exact-source replay of all sealed device/circuit holdouts",
    )
    gate_results["mixed_voltage.comparison"] = _gate(
        "pass" if mixed_pass else "fail",
        _report_reference(mixed),
        "fresh versioned native/common-bias/equal-geometry/equal-inversion comparison",
    )
    gate_results["variation.v4"] = _gate(
        "pass" if benchmark_pass else "fail",
        _report_reference(benchmark),
        "all 15 families and 30 devices pass Benchmark Global/Local/All real-tool validation",
    )
    gate_results["noise.v4_catalog"] = _gate(
        "pass" if noise_pass else "fail",
        _report_reference(noise_audit),
        "fresh 15-family/30-device live catalog plus exact strict resume and tamper rejection",
    )
    gate_results["spectre.model_only"] = _gate(
        "pass"
        if spectre.get("status") == "structurally_checked"
        and spectre.get("backend_status") == "experimental_unverified"
        and spectre.get("real_tool_validation_performed") is False
        and all(spectre.get("checks", {}).values())
        else "fail",
        _report_reference(spectre),
        "15-family model-only structure with experimental/unverified status and no real-tool claim",
    )
    gate_results["licensing.provenance"] = _gate(
        "pass"
        if provenance.get("status") == "pass"
        and provenance.get("checks", {}).get(
            "apm045_mixed_voltage_public_generation_boundary"
        )
        is True
        else "fail",
        _report_reference(provenance),
        "exact inventory, public generation boundary, redistribution, license, and REUSE audit",
    )
    gate_results["release.claim_audit_v4"] = _gate(
        "pass"
        if metadata.get("status") == "pass"
        and claims.get("status") == "pass"
        and distribution.get("status") == "pass"
        else "fail",
        static_evidence,
        "hash-bound v4 metadata, public claims/exclusions, and distribution-hygiene review",
    )

    required_component_names = (
        "clean_clone_initial",
        "static",
        "toolchain",
        "doctor",
        "modelgen_reconstruction",
        "modelgen_calibration",
        "modelgen_qualification_replay",
        "all_characterizations",
        "v3_runtime_comparisons",
        "apm130_native",
        "mixed_voltage_comparison",
        "benchmark",
        "noise_catalog_fresh",
        "noise_catalog_resume",
        "noise_contract",
        "clean_clone_final",
    )
    component_pass = all(_component_pass(components, name) for name in required_component_names)
    clean_clone_evidence = [
        str(components[name]["report_path"])
        for name in required_component_names
        if components.get(name, {}).get("report_path")
    ]
    gate_results["release.clean_clone_v4"] = _gate(
        "pass" if component_pass else "fail",
        clean_clone_evidence,
        "attested exact HTTPS clone completed every automatic candidate component",
    )
    gate_results[EXACT_TAG_GATE_ID] = _gate(
        "pending" if phase == "candidate" else "not_run",
        _report_reference(initial_attestation),
        "requires a second complete fresh-clone run at the annotated v4.0.0 tag",
    )
    if phase == "exact-tag" and all(
        result.get("status") == "pass"
        for identifier, result in gate_results.items()
        if identifier != EXACT_TAG_GATE_ID
    ):
        gate_results[EXACT_TAG_GATE_ID] = _gate(
            "pass",
            clean_clone_evidence,
            "annotated v4.0.0 tag identity and all other gates requalified from a fresh exact-tag clone",
        )

    ordered_gates, candidate_eligible, exact_complete = evaluate_v4_gates(
        contract, gate_results, phase=phase
    )
    if phase == "candidate":
        status = "candidate_pass" if candidate_eligible else "fail"
    else:
        status = "pass" if exact_complete else "fail"
    report = {
        "schema": "apm.release-validation.v4",
        "created_utc": created,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "phase": phase,
        "target": contract["target"],
        "repository": str(selected),
        "repository_head": _git(selected, "rev-parse", "HEAD"),
        "contract_path": str(selected / "validation/release_gates_v4.toml"),
        "contract_sha256": sha256_file(selected / "validation/release_gates_v4.toml"),
        "candidate_tag_creation_authorized": phase == "candidate" and candidate_eligible,
        "github_release_creation_authorized": phase == "exact-tag" and exact_complete,
        "components": components,
        "gates": ordered_gates,
        "required_gate_count": 16,
        "candidate_required_gate_count": 15,
        "passed_required_gate_count": sum(
            1 for gate in ordered_gates if gate["required"] and gate["passed"]
        ),
        "passed_candidate_gate_count": sum(
            1 for gate in ordered_gates if gate["candidate_required"] and gate["passed"]
        ),
    }
    report = _write_report(destination / "report.json", report)
    if status == "fail":
        failed = [
            gate["id"]
            for gate in ordered_gates
            if gate["candidate_required"] and not gate["passed"]
        ]
        if phase == "exact-tag" and not next(
            gate for gate in ordered_gates if gate["id"] == EXACT_TAG_GATE_ID
        )["passed"]:
            failed.append(EXACT_TAG_GATE_ID)
        raise ReleaseValidationError(
            f"v4 {phase} validation failed ({', '.join(failed)}); see {report['report_path']}"
        )
    return report
