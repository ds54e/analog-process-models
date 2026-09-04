# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed APM model provenance and distribution audit."""

from __future__ import annotations

import hashlib
import json
import re
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


class ProvenanceValidationError(RuntimeError):
    """A required licensing, provenance, or distribution check failed."""


ROOT = Path(__file__).resolve().parents[2]
TECHNOLOGIES = ("apm350", "apm130", "apm045", "apm022", "apm016f")
SOURCE_MAPS = ("authored_files", "apm_authored_files", "imported_files", "transformed_files")
OMITTED_MODEL_ROOT_FILES = {"README.md", "provenance.toml"}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
PLACEHOLDER_PATTERN = re.compile(
    r"\b(?:TBD|not_started|candidate-unvendored|draft-values-unfrozen)\b", re.IGNORECASE
)
GENERATED_BINARY_SUFFIXES = {".osdi", ".so", ".dll", ".dylib"}


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProvenanceValidationError(message)


def _model_assets(model_root: Path) -> set[str]:
    return {
        path.relative_to(model_root).as_posix()
        for path in model_root.rglob("*")
        if path.is_file()
        and path.relative_to(model_root).as_posix() not in OMITTED_MODEL_ROOT_FILES
    }


def _source_maps(source: dict[str, Any], provenance_path: Path) -> dict[str, dict[str, str]]:
    maps: dict[str, dict[str, str]] = {}
    for name in SOURCE_MAPS:
        value = source.get(name, {})
        _require(isinstance(value, dict), f"{provenance_path}: source.{name} must be a table")
        maps[name] = {str(path): str(digest) for path, digest in value.items()}
    _require(
        bool(maps["authored_files"]) != bool(maps["apm_authored_files"]),
        f"{provenance_path}: define exactly one authored-file inventory",
    )
    return maps


def _audit_file_inventories(root: Path) -> dict[str, Any]:
    details: dict[str, Any] = {}
    for technology in TECHNOLOGIES:
        model_root = root / "models" / technology
        provenance_path = model_root / "provenance.toml"
        _require(provenance_path.is_file(), f"missing {provenance_path.relative_to(root)}")
        text = provenance_path.read_text(encoding="utf-8")
        _require(
            PLACEHOLDER_PATTERN.search(text) is None,
            f"{provenance_path.relative_to(root)} contains a release placeholder",
        )
        data = _load_toml(provenance_path)
        _require(data.get("id") == technology, f"{provenance_path}: identity mismatch")
        _require(
            data.get("redistribution", {}).get("ship_in_repo") is True,
            f"{technology}: redistribution.ship_in_repo must be true",
        )
        source = data.get("source")
        _require(isinstance(source, dict), f"{technology}: missing source provenance")
        status = source.get("status")
        _require(isinstance(status, str) and bool(status), f"{technology}: missing source.status")
        maps = _source_maps(source, provenance_path)
        declared: dict[str, tuple[str, str]] = {}
        for category, inventory in maps.items():
            for relative, expected_hash in inventory.items():
                _require(
                    relative not in declared,
                    f"{technology}: {relative} appears in multiple provenance inventories",
                )
                _require(
                    SHA256_PATTERN.fullmatch(expected_hash) is not None,
                    f"{technology}: {relative} has an invalid SHA-256",
                )
                path = (model_root / relative).resolve()
                try:
                    path.relative_to(model_root.resolve())
                except ValueError as error:
                    raise ProvenanceValidationError(
                        f"{technology}: provenance path escapes model root: {relative}"
                    ) from error
                _require(path.is_file(), f"{technology}: declared source is missing: {relative}")
                actual_hash = _sha256(path)
                _require(
                    actual_hash == expected_hash,
                    f"{technology}: SHA-256 mismatch for {relative}: "
                    f"expected {expected_hash}, got {actual_hash}",
                )
                if category == "imported_files":
                    _require(
                        relative.startswith("vendor/"),
                        f"{technology}: imported asset is outside vendor/: {relative}",
                    )
                elif category in {"authored_files", "apm_authored_files"}:
                    _require(
                        not relative.startswith("vendor/"),
                        f"{technology}: vendor asset is incorrectly claimed as APM-authored: {relative}",
                    )
                declared[relative] = (category, actual_hash)
        actual_assets = _model_assets(model_root)
        _require(
            set(declared) == actual_assets,
            f"{technology}: provenance inventory differs from shipped assets; "
            f"missing={sorted(actual_assets - set(declared))}, "
            f"extra={sorted(set(declared) - actual_assets)}",
        )
        imported = maps["imported_files"]
        vendor_assets = {item for item in actual_assets if item.startswith("vendor/")}
        _require(
            set(imported) == vendor_assets,
            f"{technology}: every vendored file must have exact imported-file provenance",
        )
        details[technology] = {
            "provenance": str(provenance_path.relative_to(root)),
            "provenance_sha256": _sha256(provenance_path),
            "source_status": status,
            "asset_count": len(declared),
            "authored_count": len(maps["authored_files"] or maps["apm_authored_files"]),
            "imported_count": len(imported),
            "transformed_count": len(maps["transformed_files"]),
            "all_hashes_match": True,
        }
    return details


def _audit_redistribution(root: Path) -> dict[str, Any]:
    expected = {
        "apm016f": {
            "prefix": "vendor/bsim-cmg-112.1.0/",
            "license_field": ("engine_license", "ECL-2.0"),
        },
        "apm045": {
            "prefix": "vendor/freepdk45/",
            "license_field": ("license", "Apache-2.0"),
        },
        "apm130": {
            "prefix": "vendor/",
            "license_field": ("model_card_license", "Apache-2.0"),
        },
    }
    details: dict[str, Any] = {}
    for technology, policy in expected.items():
        data = _load_toml(root / "models" / technology / "provenance.toml")
        source = data["source"]
        imported = source["imported_files"]
        field, license_id = policy["license_field"]
        _require(source.get(field) == license_id, f"{technology}: incorrect {field}")
        _require(
            all(path.startswith(str(policy["prefix"])) for path in imported),
            f"{technology}: imported path is outside the audited upstream prefix",
        )
        redistribution = data.get("redistribution", {})
        _require(
            redistribution.get("upstream_notices_preserved") is True,
            f"{technology}: upstream notice preservation is not affirmed",
        )
        details[technology] = {
            "imported_file_count": len(imported),
            "license_field": field,
            "license": license_id,
            "notices_preserved": True,
        }
    apm130 = _load_toml(root / "models/apm130/provenance.toml")
    _require(
        apm130["source"].get("engine_license") == "LicenseRef-Si2-PSP-103.8.2",
        "apm130: PSP engine license identity drifted",
    )
    psp_terms = (
        root / "LICENSES/LicenseRef-Si2-PSP-103.8.2.txt"
    ).read_text(encoding="utf-8")
    psp_release_notes = (
        root / "models/apm130/vendor/psp103/releasenotesPSP103.8.2.txt"
    ).read_text(encoding="utf-8")
    normalized_psp_terms = " ".join(psp_terms.split())
    normalized_psp_release_notes = " ".join(psp_release_notes.split())
    for required in (
        "right to modify, copy, and redistribute",
        "acknowledge NXP",
        "copyright notice, disclaimer, and list of conditions",
    ):
        _require(
            required in normalized_psp_terms
            and required in normalized_psp_release_notes,
            f"apm130: PSP redistribution condition is missing: {required}",
        )
    third_party = (root / "THIRD_PARTY.md").read_text(encoding="utf-8")
    normalized_third_party = " ".join(third_party.split())
    for developer in (
        "NXP Semiconductors",
        "Delft University of Technology",
        "Commissariat",
    ):
        _require(
            developer in normalized_third_party,
            f"THIRD_PARTY.md is missing the required PSP acknowledgement: {developer}",
        )
    ihp_imported = {
        path
        for path in apm130["source"]["imported_files"]
        if path.startswith("vendor/ihp-sg13g2-models/")
    }
    _require(bool(ihp_imported), "apm130: no pinned IHP model cards are declared")
    for relative in ihp_imported:
        text = (root / "models/apm130" / relative).read_text(
            encoding="utf-8", errors="replace"
        )
        _require(
            "Apache License, Version 2.0" in text,
            f"apm130: IHP file lacks its Apache-2.0 header: {relative}",
        )
    details["apm130"].update(
        {
            "psp_external_redistribution_terms_preserved": True,
            "psp_product_documentation_acknowledgement_present": True,
            "ihp_apache_header_file_count": len(ihp_imported),
        }
    )

    apm045_root = root / "models/apm045"
    apm045 = _load_toml(apm045_root / "provenance.toml")
    apm045_imported = set(apm045["source"]["imported_files"])
    _require(
        not any(
            "svrf" in path.lower() or "eula" in path.lower()
            for path in apm045_imported
        ),
        "apm045: an SVRF/EULA path entered the shipped inventory",
    )
    freepdk_readme = (
        apm045_root / "vendor/freepdk45/UPSTREAM-README.txt"
    ).read_text(encoding="utf-8")
    _require(
        "SVRF files removed" in freepdk_readme
        and "All files are licensed under the Apache License" in freepdk_readme,
        "apm045: open-source-clean mirror boundary is not preserved",
    )
    details["apm045"].update(
        {
            "open_source_clean_mirror_boundary_preserved": True,
            "svrf_or_eula_paths_shipped": [],
        }
    )

    bsim_root = root / "models/apm016f/vendor/bsim-cmg-112.1.0"
    bsim_license = (bsim_root / "LICENSE.txt").read_text(encoding="utf-8")
    bsim_notice = (bsim_root / "NOTICE.txt").read_text(encoding="utf-8")
    _require(
        "Educational Community License, Version 2.0" in bsim_license,
        "apm016f: BSIM-CMG ECL-2.0 license text is missing",
    )
    _require(
        "Silicon Integration Initiative" in bsim_notice,
        "apm016f: BSIM-CMG notice text is missing",
    )
    details["apm016f"].update(
        {
            "ecl_2_0_license_preserved": True,
            "upstream_notice_preserved": True,
        }
    )

    reuse_text = (root / "REUSE.toml").read_text(encoding="utf-8")
    for required in (
        "models/apm130/vendor/psp103/**",
        "LicenseRef-Si2-PSP-103.8.2",
        "models/apm130/vendor/ihp-sg13g2-models/**",
        "models/apm016f/vendor/bsim-cmg-112.1.0/**",
        "ECL-2.0",
        "models/apm045/vendor/freepdk45/**",
    ):
        _require(required in reuse_text, f"REUSE.toml is missing audited annotation {required}")
    details["reuse_annotations"] = "audited upstream trees retain distinct licenses"
    return details


def _audit_apm045_mixed_voltage_generation(root: Path) -> dict[str, Any]:
    """Bind the independently authored io18/io25 cards to public generation evidence."""

    provenance_path = root / "models/apm045/provenance.toml"
    provenance = _load_toml(provenance_path)
    generation = provenance.get("apm_generation", {})
    _require(generation.get("scope") == "io18/io25 only", "apm045: bad generation scope")
    _require(
        generation.get("origin") == "independently_apm_authored",
        "apm045: io18/io25 authorship boundary is missing",
    )
    _require(generation.get("license") == "Apache-2.0", "apm045: bad authored license")
    for field, expected in (
        ("public_inputs_only", True),
        ("private_or_proprietary_pdk_input_used", False),
        ("foundry_parameter_copy_used", False),
        ("epistemic_ensemble_is_process_variation", False),
        ("canonical_cards_byte_identically_regenerable", True),
    ):
        _require(generation.get(field) is expected, f"apm045: generation field {field} drifted")

    bound_files: dict[str, dict[str, str]] = {}
    for path_field, hash_field in (
        ("generator_contract", "generator_contract_sha256"),
        ("qualification_contract", "qualification_contract_sha256"),
        ("generation_evidence", "generation_evidence_sha256"),
        ("qualification_evidence", "qualification_evidence_sha256"),
    ):
        relative = generation.get(path_field)
        expected_hash = generation.get(hash_field)
        _require(isinstance(relative, str) and bool(relative), f"apm045: missing {path_field}")
        _require(
            isinstance(expected_hash, str) and SHA256_PATTERN.fullmatch(expected_hash) is not None,
            f"apm045: invalid {hash_field}",
        )
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as error:
            raise ProvenanceValidationError(f"apm045: {path_field} escapes repository") from error
        _require(path.is_file(), f"apm045: missing bound generation file {relative}")
        _require(_sha256(path) == expected_hash, f"apm045: hash mismatch for {relative}")
        bound_files[path_field] = {"path": relative, "sha256": expected_hash}

    qualification = _load_toml(root / generation["qualification_contract"])
    _require(
        qualification.get("generation_contract_sha256")
        == generation["generator_contract_sha256"],
        "apm045: qualification contract does not bind the generation contract",
    )
    generation_evidence = json.loads(
        (root / generation["generation_evidence"]).read_text(encoding="utf-8")
    )
    qualification_evidence = json.loads(
        (root / generation["qualification_evidence"]).read_text(encoding="utf-8")
    )
    _require(
        generation_evidence.get("status") == "validated"
        and qualification_evidence.get("status") == "validated",
        "apm045: generation or qualification evidence is not passing",
    )
    _require(
        generation_evidence.get("bound_inputs", {})
        .get("public_evidence_matrix_sha256")
        == _sha256(root / "models/apm045/mixed_voltage_evidence.toml"),
        "apm045: public evidence matrix binding mismatch",
    )
    selected = qualification_evidence.get("canonical_selection", {})
    catalog = load_catalog(root)
    card_hashes: dict[str, dict[str, str]] = {}
    for family_id in ("io18", "io25"):
        family = catalog.family("apm045", family_id)
        _require(family.origin == "apm_authored", f"{family.selector}: origin drifted")
        family_selection = selected.get(family_id, {})
        per_polarity: dict[str, str] = {}
        for polarity in ("n", "p"):
            path = (
                root
                / "models/apm045/families"
                / family_id
                / "ngspice"
                / f"apm045_{family_id}_{polarity}.inc"
            )
            digest = _sha256(path)
            _require(
                family_selection.get(f"{polarity}_card_sha256") == digest,
                f"{family.selector}: canonical {polarity.upper()} card binding mismatch",
            )
            per_polarity[polarity] = digest
        card_hashes[family_id] = per_polarity
    _require(
        selected.get("all_canonical_cards_byte_identical_to_frozen_candidates") is True,
        "apm045: canonical card regeneration evidence is not affirmative",
    )
    return {
        "origin": "independently_apm_authored",
        "public_inputs_only": True,
        "bound_files": bound_files,
        "canonical_card_sha256": card_hashes,
        "kernel": generation.get("kernel"),
        "canonical_selection": generation.get("canonical_selection"),
        "epistemic_ensemble_is_process_variation": False,
    }


def _audit_independent_models(root: Path) -> dict[str, Any]:
    catalog = load_catalog(root)
    expectations = {
        "apm022": ("ptm_derived", "threshold_isolated", "official_ptm_numeric_input_used"),
        "apm016f": (
            "ptm_mg_derived",
            "workfunction_dominant",
            "official_ptm_mg_numeric_input_used",
        ),
    }
    details: dict[str, Any] = {}
    for technology, (provenance_flag, method, oracle_flag) in expectations.items():
        model_root = root / "models" / technology
        provenance = _load_toml(model_root / "provenance.toml")
        _require(provenance.get(provenance_flag) is False, f"{technology}: independence flag failed")
        source = provenance["source"]
        _require(
            not any("ptm" in path.lower() for path in source.get("imported_files", {})),
            f"{technology}: PTM model-card asset was imported",
        )
        tech = catalog.technology(technology)
        _require(
            tech.family("svt").origin == "apm_authored",
            f"{technology}: SVT must be independently APM-authored",
        )
        variants: dict[str, Any] = {}
        for family_id in ("lvt", "hvt"):
            family = tech.family(family_id)
            _require(family.origin == "apm_derived_variant", f"{family.selector}: bad origin")
            _require(family.base_family == "svt", f"{family.selector}: bad base family")
            _require(family.variant_method == method, f"{family.selector}: bad method")
            _require(family.variant_generation_path is not None, f"{family.selector}: no record")
            record = _load_toml(family.variant_generation_path)
            _require(record.get("schema") == "apm.variant-generation.v2", "bad variant schema")
            _require(record.get("method") == method, f"{family.selector}: method drifted")
            _require(record.get(oracle_flag) is False, f"{family.selector}: PTM numeric use claimed")
            _require(
                record.get("secondary_parameter_changes") is False,
                f"{family.selector}: variant is not isolated",
            )
            variants[family_id] = {
                "method": method,
                "record": str(family.variant_generation_path.relative_to(root)),
                "record_sha256": _sha256(family.variant_generation_path),
                "official_ptm_numeric_input_used": False,
            }
        details[technology] = {
            "provenance_flag": False,
            "base_family": "svt",
            "variants": variants,
        }
    return details


def _audit_catalog_distribution(root: Path) -> dict[str, Any]:
    catalog = load_catalog(root)
    source_paths: set[Path] = set()
    backend_counts = {"ngspice": 0, "spectre": 0}
    for technology in catalog.technologies:
        source_paths.add(technology.manifest_path)
        for family in technology.families:
            source_paths.update(
                {
                    family.manifest_path,
                    family.provenance_path,
                    *(path for path in (family.variant_generation_path,) if path is not None),
                }
            )
            _require(
                {binding.backend_id for binding in family.backend_bindings}
                == {"ngspice", "spectre"},
                f"{family.selector}: both v2 backends must be bound",
            )
            for binding in family.backend_bindings:
                backend_counts[binding.backend_id] += 1
                source_paths.add(binding.manifest_path)
                source_paths.add(binding.wrapper_path)
                source_paths.update(binding.model_source_files())
                for path in (binding.wrapper_path, *binding.model_source_files()):
                    try:
                        path.resolve().relative_to(root.resolve())
                    except ValueError as error:
                        raise ProvenanceValidationError(
                            f"{family.selector}/{binding.backend_id}: source escapes repository"
                        ) from error
                    _require(path.is_file(), f"missing bound model source: {path}")
    _require(backend_counts == {"ngspice": 15, "spectre": 15}, "backend coverage drifted")
    v3_contract = _load_toml(root / "validation/release_gates.toml")
    v4_contract = _load_toml(root / "validation/release_gates_v4.toml")
    _require(
        v3_contract.get("distribution", {}).get("separate_transistor_model_download_required")
        is False,
        "frozen v3 contract does not require a self-contained transistor distribution",
    )
    _require(
        v4_contract.get("distribution", {}).get("generated_binaries_committed") is False,
        "v4 distribution contract permits committed generated binaries",
    )
    return {
        "family_count": 15,
        "backend_bindings": backend_counts,
        "bound_source_count": len(source_paths),
        "all_bound_sources_inside_repository": True,
        "separate_model_download_required": False,
    }


def _git_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=False
    )
    _require(result.returncode == 0, result.stderr.decode(errors="replace").strip())
    return {item.decode("utf-8") for item in result.stdout.split(b"\0") if item}


def _audit_tracked_distribution(root: Path) -> dict[str, Any]:
    tracked = _git_paths(root)
    required: set[str] = set()
    for technology in TECHNOLOGIES:
        model_root = root / "models" / technology
        required.add((model_root / "provenance.toml").relative_to(root).as_posix())
        required.update(
            (model_root / relative).relative_to(root).as_posix()
            for relative in _model_assets(model_root)
        )
    missing = sorted(required - tracked)
    _require(not missing, f"release model assets are not tracked by git: {missing}")
    generated = sorted(
        path
        for path in tracked
        if Path(path).suffix.lower() in GENERATED_BINARY_SUFFIXES
        or path.startswith(".apm/")
    )
    _require(not generated, f"generated binaries/build state are tracked: {generated}")
    raw_results = sorted(path for path in tracked if path.startswith("results/"))
    _require(not raw_results, f"large/raw result paths are tracked: {raw_results}")
    obsolete = sorted(
        path
        for path in tracked
        if path.endswith("/kit.toml")
        or path in {
            "variation/adapters_v1.toml",
            "variation/benchmark_v1.toml",
            "passives/benchmark_v1.toml",
        }
    )
    _require(not obsolete, f"obsolete v1 runtime assets remain tracked: {obsolete}")
    return {
        "required_model_asset_count": len(required),
        "all_release_model_assets_tracked": True,
        "generated_binaries_tracked": [],
        "raw_results_tracked": [],
        "obsolete_v1_runtime_assets_tracked": [],
    }


def _audit_spectre_claim_boundary(root: Path) -> dict[str, Any]:
    catalog = load_catalog(root)
    artifacts = []
    for technology in catalog.technologies:
        provenance = _load_toml(root / "models" / technology.technology_id / "provenance.toml")
        spectre = provenance.get("spectre", {})
        _require(
            spectre.get("status") == "experimental_unverified",
            f"{technology.technology_id}: Spectre status is overstated",
        )
        _require(
            spectre.get("real_tool_validation") is False,
            f"{technology.technology_id}: unperformed Spectre validation is claimed",
        )
        for family in technology.families:
            binding = _load_toml(family.backend("spectre").manifest_path)
            _require(binding.get("status") == "experimental_unverified", "Spectre status drift")
            _require(binding.get("real_tool_validation") is False, "Spectre tool claim drift")
            artifacts.append(str(family.backend("spectre").wrapper_path.relative_to(root)))
    return {
        "status": "experimental_unverified",
        "real_tool_validation_performed": False,
        "family_artifact_count": len(artifacts),
        "artifacts": sorted(artifacts),
    }


def _audit_reuse(root: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "reuse", "lint"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(result.returncode == 0, result.stderr.strip() or result.stdout.strip())
    _require("Missing licenses: 0" in result.stdout, "REUSE reported missing licenses")
    _require(
        "Missing copyright and licensing information: 0" in result.stdout
        or "Files with license information:" in result.stdout,
        "REUSE did not report complete file coverage",
    )
    _require("ERROR" not in result.stderr, f"REUSE emitted an error: {result.stderr.strip()}")
    return {
        "command": f"{sys.executable} -m reuse lint",
        "status": "pass",
        "summary": result.stdout.strip(),
    }


def validate_provenance(output: Path, *, root: Path = ROOT) -> dict[str, Any]:
    """Audit exact source hashes, licensing boundaries, and shipped model closure."""

    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ProvenanceValidationError(f"refusing to overwrite non-empty directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    failures: dict[str, str] = {}
    functions: tuple[tuple[str, Callable[[Path], dict[str, Any]]], ...] = (
        ("complete_exact_file_hash_inventories", _audit_file_inventories),
        ("third_party_redistribution_and_license_boundaries", _audit_redistribution),
        ("apm045_mixed_voltage_public_generation_boundary", _audit_apm045_mixed_voltage_generation),
        ("apm022_apm016f_independent_authorship", _audit_independent_models),
        ("catalog_model_sources_self_contained", _audit_catalog_distribution),
        ("release_assets_tracked_and_generated_outputs_excluded", _audit_tracked_distribution),
        ("spectre_experimental_unverified_claim_boundary", _audit_spectre_claim_boundary),
        ("reuse_spdx_compliance", _audit_reuse),
    )
    for name, function in functions:
        try:
            details[name] = function(root)
            checks[name] = True
        except (OSError, RuntimeError, ValueError, tomllib.TOMLDecodeError) as error:
            checks[name] = False
            failures[name] = str(error)
    report: dict[str, Any] = {
        "schema": "apm.provenance-validation.v2",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if all(checks.values()) else "fail",
        "release_gates": ["licensing.provenance", "distribution.public_hygiene"],
        "checks": checks,
        "details": details,
        "failures": failures,
    }
    report_path = output / "provenance_validation_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["output_directory"] = str(output)
    report["report_path"] = str(report_path)
    if failures:
        summary = "; ".join(f"{name}: {message}" for name, message in failures.items())
        raise ProvenanceValidationError(summary)
    return report
