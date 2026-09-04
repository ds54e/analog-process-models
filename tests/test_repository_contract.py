# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib

from apm.catalog import load_catalog
from apm.characterize import (
    CharacterizationError,
    FinFETGeometry,
    _capacitance_rows,
    _threshold_crossing,
)
from apm.cli import build_parser
from apm.doctor import _extract_observables
from apm.maintenance_validate import audit_current_guidance, audit_frozen_v4_artifacts
from apm.model_build import MODEL_SOURCES
from apm.noise import ACQUISITION_POLICY_ID, ACQUISITION_POLICY_VERSION
from apm.noise_fit import FIT_METHOD_IDENTITY

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TECHNOLOGIES = ("apm350", "apm130", "apm045", "apm022", "apm016f")
EXPECTED_MODELS = {
    "apm350": "bsim3",
    "apm130": "psp103",
    "apm045": "bsim4",
    "apm022": "bsim4",
    "apm016f": "bsim_cmg",
}
EXPECTED_FAMILIES = {
    "apm350": ("general",),
    "apm130": ("lv", "hv"),
    "apm045": ("vtl", "vtg", "vth", "thkox", "io18", "io25"),
    "apm022": ("lvt", "svt", "hvt"),
    "apm016f": ("lvt", "svt", "hvt"),
}


def test_post_v4_goal_and_historical_document_status_are_explicit() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    goal = (ROOT / "GOAL.md").read_text(encoding="utf-8")
    normalized_goal = " ".join(goal.split())
    assert (
        "APM v1.0.0, v2.0.0, v3.0.0, and v4.0.0 are released and immutable"
        in agents
    )
    assert "afecec29ea6ed0703ef441d4839fd40a238bef0b" in agents
    assert "797cdf9462db9dd634bff558802bcadaaeb70015" in agents
    assert "d224f279921c7e1ae637fd867e00d450067766c6" in agents
    assert "v4.0.0 exact-tag requalification: 16/16 required gates passed" in agents
    assert "The repository is public" in agents
    assert goal.startswith("# Post-v4 release maintenance")
    assert (
        "Current `main` is the post-v4 public-maintenance line."
        in normalized_goal
    )
    assert "APM v1.0.0 through v4.0.0 are released and immutable" in normalized_goal
    assert "Complete and release **APM v4.0.0**" not in goal
    assert "must not update a historical release review" in normalized_goal
    assert "changing released model/evidence semantics" in normalized_goal
    assert "validation/evidence/v4_release_candidate.json" in goal
    assert "validation/evidence/v4_post_release_requalification.json" in goal

    for frozen in (
        "V4_MIXED_VOLTAGE.md",
        "RELEASE_V4.md",
        "validation/release_gates_v4.toml",
        "validation/release_review_v4.toml",
        "validation/evidence/v4_*.json",
    ):
        assert frozen in agents
    assert "it is not current technical instruction" in " ".join(agents.split())

    historical_markers = {
        "RELEASE_V3.md": "Historical record — frozen V3-N3 candidate contract",
        "UNATTENDED_EXECUTION.md": "Historical record — preserved V3-N3 procedure",
        "PROJECT_CONTEXT.md": "Historical record — v2 design rationale",
        "RESEARCH_BASELINE.md": "Historical record — dated v2 research baseline",
        "NOISE_N1.md": "Historical/frozen milestone contract",
        "NOISE_N2.md": "Historical/frozen milestone contract",
    }
    for relative, marker in historical_markers.items():
        assert marker in (ROOT / relative).read_text(encoding="utf-8")

    assert (ROOT / "SECURITY.md").is_file()
    assert (ROOT / "CONTRIBUTING.md").is_file()
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    normalized_security = " ".join(security.split())
    assert "Report a vulnerability" in normalized_security
    assert "Private Vulnerability Reporting is enabled" in normalized_security
    assert "APM v4.0.0 is the latest completed release" in normalized_security

    positioning = (ROOT / "APM045_POSITIONING.md").read_text(encoding="utf-8")
    assert positioning.startswith(
        "<!-- SPDX-FileCopyrightText: APM contributors -->\n"
        "<!-- SPDX-License-Identifier: Apache-2.0 -->\n"
    )
    assert "GENERIC 40/45 NM-CLASS" in positioning
    assert "Model/release changes required: **NONE**" in positioning


def test_current_guidance_and_frozen_v4_artifact_audits_pass() -> None:
    guidance = audit_current_guidance(ROOT)
    frozen = audit_frozen_v4_artifacts(ROOT)
    assert guidance["status"] == "pass", guidance
    assert frozen["status"] == "pass", frozen
    assert frozen["artifact_count"] >= 19
    assert frozen["mismatches"] == []


def test_current_guidance_audit_fails_closed_on_completed_goal(tmp_path: Path) -> None:
    for relative in (
        "AGENTS.md",
        "APM045_POSITIONING.md",
        "ENVIRONMENT.md",
        "GOAL.md",
        "README.md",
        "SECURITY.md",
        "models/apm045/README.md",
    ):
        source = ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    (tmp_path / "GOAL.md").write_text(
        "# APM v4.0.0 — APM045 Mixed-Voltage Electrical Families (complete)\n\n"
        "Complete and release **APM v4.0.0**.\n",
        encoding="utf-8",
    )
    result = audit_current_guidance(tmp_path)
    assert result["status"] == "fail"
    assert "goal_is_post_v4_maintenance" in result["failed_checks"]


def test_psp_product_documentation_acknowledgement_is_preserved() -> None:
    third_party = (ROOT / "THIRD_PARTY.md").read_text(encoding="utf-8")
    normalized_third_party = " ".join(third_party.split())
    for developer in (
        "NXP Semiconductors",
        "Delft University of Technology",
        "Commissariat",
    ):
        assert developer in normalized_third_party
    terms = (ROOT / "LICENSES/LicenseRef-Si2-PSP-103.8.2.txt").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(terms.split())
    assert "right to modify, copy, and redistribute" in normalized
    assert "acknowledge NXP Semiconductors" in normalized


def load_toml(relative: str) -> dict:
    with (ROOT / relative).open("rb") as handle:
        return tomllib.load(handle)


def test_v3_contract_is_frozen_and_v4_contract_matches_the_live_catalog() -> None:
    v3 = load_toml("validation/release_gates.toml")
    v4 = load_toml("validation/release_gates_v4.toml")
    catalog = load_catalog(ROOT)
    assert tuple(v3["technology_catalog"]["required_technologies"]) == EXPECTED_TECHNOLOGIES
    assert v3["technology_catalog"]["required_family_count"] == 13
    assert v3["technology_catalog"]["required_families"]["apm045"] == [
        "vtl",
        "vtg",
        "vth",
        "thkox",
    ]
    assert tuple(v4["technology_catalog"]["required_technologies"]) == EXPECTED_TECHNOLOGIES
    assert v4["technology_catalog"]["required_family_count"] == 15
    assert v4["technology_catalog"]["required_public_device_count"] == 30
    assert tuple(item.technology_id for item in catalog.technologies) == tuple(
        sorted(EXPECTED_TECHNOLOGIES)
    )
    assert sum(len(item.families) for item in catalog.technologies) == 15
    for technology_id, expected in EXPECTED_FAMILIES.items():
        assert {item.family_id for item in catalog.technology(technology_id).families} == set(
            expected
        )
        assert v4["technology_catalog"]["required_families"][technology_id] == list(expected)


def test_reference_runtime_contract_is_el9_ngspice47_osdi() -> None:
    runtime = load_toml("validation/release_gates.toml")["runtime"]
    assert runtime["primary_distribution"] == "AlmaLinux 9"
    assert runtime["acceptable_distribution_class"] == "RHEL-compatible EL9"
    assert runtime["architecture"] == "x86_64"
    assert runtime["required_ngspice_major"] == 47
    assert runtime["osdi_required"] is True
    assert runtime["python_minimum"] == "3.9"


def test_v3_noise_release_contract_freezes_validated_method_identities() -> None:
    noise = load_toml("validation/release_gates.toml")["noise"]
    assert noise["result_schema"] == "apm.noise-characterization.v1"
    assert noise["comparison_schema"] == "apm.noise-comparison.v1"
    assert noise["fit_method_identity"] == FIT_METHOD_IDENTITY
    assert noise["acquisition_policy_identity"] == (
        f"{ACQUISITION_POLICY_ID}@{ACQUISITION_POLICY_VERSION}"
    )
    assert noise["catalog_planned_logical_request_count"] == 376
    assert noise["catalog_unique_request_count"] == 290
    assert noise["process_noise_tuning_authorized"] is False


def test_public_geometry_and_identity_contract_is_manifest_enforced() -> None:
    gates = load_toml("validation/release_gates.toml")
    public = gates["public_devices"]
    assert public["terminals"] == ["d", "g", "s", "b"]
    assert public["planar_parameters"] == ["w", "l"]
    assert public["finfet_parameters"] == ["l", "nfin"]
    assert set(public["forbidden_common_parameters"]) == {"m", "nf", "ng"}
    catalog = load_catalog(ROOT)
    names: set[str] = set()
    for technology in catalog.technologies:
        for family in technology.families:
            assert {binding.backend_id for binding in family.backend_bindings} == {
                "ngspice",
                "spectre",
            }
            for device in family.devices:
                assert device.terminals == ("d", "g", "s", "b")
                assert device.parameters == (
                    ("l", "nfin") if family.architecture == "finfet" else ("w", "l")
                )
                assert device.public_name.startswith(f"{technology.technology_id}_{family.family_id}_")
                assert device.public_name not in names
                names.add(device.public_name)
    assert len(names) == 30


def test_all_provenance_files_match_identity_model_and_spectre_boundary() -> None:
    for technology, compact_model in EXPECTED_MODELS.items():
        provenance = load_toml(f"models/{technology}/provenance.toml")
        assert provenance["id"] == technology
        assert provenance["compact_model"] == compact_model
        assert provenance["validation"]["spectre"] == "experimental_unverified"
        assert provenance["spectre"]["status"] == "experimental_unverified"
        assert provenance["spectre"]["real_tool_validation"] is False


def test_provenance_inventories_cover_every_shipped_model_asset_and_hash() -> None:
    for technology in EXPECTED_TECHNOLOGIES:
        model_root = ROOT / "models" / technology
        provenance = load_toml(f"models/{technology}/provenance.toml")
        source = provenance["source"]
        inventories = [
            source.get(name, {})
            for name in (
                "authored_files",
                "apm_authored_files",
                "imported_files",
                "transformed_files",
            )
        ]
        declared = {path: digest for inventory in inventories for path, digest in inventory.items()}
        actual = {
            path.relative_to(model_root).as_posix()
            for path in model_root.rglob("*")
            if path.is_file()
            and path.relative_to(model_root).as_posix() not in {"README.md", "provenance.toml"}
        }
        assert set(declared) == actual
        assert set(source.get("imported_files", {})) == {
            path for path in actual if path.startswith("vendor/")
        }
        for relative, expected_hash in declared.items():
            assert hashlib.sha256((model_root / relative).read_bytes()).hexdigest() == expected_hash


def test_required_osdi_sources_are_self_contained_and_generated_binaries_are_ignored() -> None:
    assert set(MODEL_SOURCES) == {"psp103", "psp103-nqs", "bsimcmg-112.1.0"}
    for source in MODEL_SOURCES.values():
        assert (ROOT / source).is_file()
        assert (ROOT / source).resolve().is_relative_to(ROOT.resolve())
    assert not list(ROOT.glob("models/**/*.osdi"))


def test_every_family_wrapper_has_exact_public_names_and_small_interface() -> None:
    catalog = load_catalog(ROOT)
    for technology in catalog.technologies:
        for family in technology.families:
            wrapper = family.backend("ngspice").wrapper_path.read_text(encoding="utf-8")
            for device in family.devices:
                declaration = next(
                    line
                    for line in wrapper.splitlines()
                    if line.lower().startswith(f".subckt {device.public_name.lower()} ")
                )
                assert declaration.lower().split()[2:6] == ["d", "g", "s", "b"]
                public_tail = declaration.lower().split(" b", 1)[1]
                for forbidden in (" m=", " nf=", " ng="):
                    assert forbidden not in public_tail
                if family.architecture == "finfet":
                    assert " nfin=" in public_tail
                    assert " w=" not in public_tail
                else:
                    assert " w=" in public_tail and " l=" in public_tail


def test_apm130_lv_hv_are_independent_upstream_families_with_geometry_semantics() -> None:
    catalog = load_catalog(ROOT)
    technology = catalog.technology("apm130")
    assert {family.family_id for family in technology.families} == {"lv", "hv"}
    lv, hv = technology.family("lv"), technology.family("hv")
    assert lv.origin == hv.origin == "upstream_model"
    assert lv.upstream_flavor == "sg13_lv"
    assert hv.upstream_flavor == "sg13_hv"
    assert lv.operating_profile().reference_vdd_v == 1.2
    assert hv.operating_profile().reference_vdd_v == 3.3
    assert lv.device("nmos").lmin_m != hv.device("nmos").lmin_m
    provenance = load_toml("models/apm130/provenance.toml")
    assert provenance["variation"]["native_process"] is True
    assert provenance["variation"]["native_mismatch"] is True
    assert provenance["variation"]["native_combined_all_profile"] is False
    assert provenance["source"]["revision"] == "331c00484213b13414777eec1336ef5c29b969bd"


def test_apm045_threshold_and_gate_stack_domains_are_explicit() -> None:
    technology = load_catalog(ROOT).technology("apm045")
    threshold = technology.comparison_set("threshold")
    gate_stack = technology.comparison_set("gate_stack")
    mixed_voltage = technology.comparison_set("mixed_voltage")
    assert threshold.kind == "threshold_family"
    assert threshold.members == ("vtl", "vtg", "vth")
    assert gate_stack.kind == "gate_stack"
    assert gate_stack.members == ("vtg", "thkox")
    assert gate_stack.common_overlap_profile == "common_overlap_1v0"
    assert mixed_voltage.kind == "mixed_voltage"
    assert mixed_voltage.members == ("vtg", "io18", "io25")
    assert mixed_voltage.anchor == "vtg"
    thkox = technology.family("thkox")
    assert thkox.operating_profile().reference_vdd_v == 2.0
    overlap = thkox.operating_profile("common_overlap_1v0")
    assert overlap.reference_vdd_v == 1.0
    assert overlap.origin == "apm_selected"
    assert bool(overlap.evidence)


def test_apm022_variants_change_only_threshold_and_are_not_ptm_derived() -> None:
    provenance = load_toml("models/apm022/provenance.toml")
    assert provenance["model_origin"] == "apm_generic"
    assert provenance["ptm_derived"] is False
    catalog = load_catalog(ROOT)
    technology = catalog.technology("apm022")
    assert technology.family("svt").origin == "apm_authored"
    for family_id in ("lvt", "hvt"):
        family = technology.family(family_id)
        assert family.origin == "apm_derived_variant"
        assert family.base_family == "svt"
        assert family.variant_method == "threshold_isolated"
        record = load_toml(
            f"models/apm022/families/{family_id}/variant-generation.toml"
        )
        assert record["official_ptm_numeric_input_used"] is False
        assert record["secondary_parameter_changes"] is False
        assert {item["parameter"] for item in record["parameter_change"]} == {"VTH0"}
    model = (ROOT / "models/apm022/ngspice/apm022_multivt_models.inc").read_text().lower()
    assert model.count("level=54 version=4.8.2") == 6
    assert model.count("lpe0=0 lpeb=0") == 6


def test_apm016f_variants_are_workfunction_dominant_and_preserve_nfin() -> None:
    provenance = load_toml("models/apm016f/provenance.toml")
    assert provenance["model_origin"] == "apm_generic"
    assert provenance["ptm_mg_derived"] is False
    catalog = load_catalog(ROOT)
    technology = catalog.technology("apm016f")
    assert technology.family("svt").origin == "apm_authored"
    for family_id in ("lvt", "hvt"):
        family = technology.family(family_id)
        assert family.origin == "apm_derived_variant"
        assert family.variant_method == "workfunction_dominant"
        record = load_toml(
            f"models/apm016f/families/{family_id}/variant-generation.toml"
        )
        assert record["official_ptm_mg_numeric_input_used"] is False
        assert record["secondary_parameter_changes"] is False
        assert {item["parameter"] for item in record["parameter_change"]} == {"PHIG"}
    for family in technology.families:
        for device in family.devices:
            assert device.parameters == ("l", "nfin")
            assert device.characterization_nfin == (1, 2, 4)
    model = (ROOT / "models/apm016f/ngspice/apm016f_multivt_models.inc").read_text().lower()
    assert model.count("bsimcmg_va") == 6


def test_finfet_result_geometry_never_invents_width() -> None:
    geometry = FinFETGeometry(l_m=16e-9, nfin=2)
    assert geometry.netlist_parameters() == "l=1.6e-08 nfin=2"
    assert geometry.threshold_current_a(100e-9) == 200e-9
    fields = geometry.result_fields(16e-9)
    assert fields == {"l_m": 16e-9, "nfin": 2, "l_over_lmin": 1.0}
    assert "w_m" not in fields
    with pytest.raises(CharacterizationError, match="positive integer"):
        FinFETGeometry(l_m=16e-9, nfin=1.5)  # type: ignore[arg-type]


def test_doctor_observable_parser_ignores_unrelated_equals_signs() -> None:
    output = "TEMP = 27 and TNOM = 27\ni(vd) = -2.5e-4\n@m1[gm] = 4.0e-4\n"
    assert _extract_observables(output) == {"i(vd)": -2.5e-4, "@m1[gm]": 4.0e-4}


def test_constant_current_threshold_is_linearly_interpolated() -> None:
    curve = [
        {"vctrl_v": 0.3, "idmag_a": 1.0e-7},
        {"vctrl_v": 0.4, "idmag_a": 3.0e-7},
    ]
    assert _threshold_crossing(curve, 2.0e-7) == 0.35


def test_capacitance_derivation_uses_raw_ordered_gate_y_terms() -> None:
    frequency = 1.0e6
    omega = 2.0 * math.pi * frequency
    imag = [[0.0] * 4 for _ in range(4)]
    imag[1][1] = omega * 2.0e-15
    imag[1][0] = -omega * 3.0e-16
    imag[1][2] = -omega * 4.0e-16
    record = {
        "technology_id": "apm130",
        "family_id": "lv",
        "device_id": "nmos",
        "public_device": "apm130_lv_nmos",
        "polarity": "n",
        "operating_profile_id": "native_1v2",
        "temperature_c": 27,
        "w_m": 1.0e-6,
        "l_m": 2.6e-7,
        "l_over_lmin": 2.0,
        "vctrl_v": 0.6,
        "vout_v": 0.6,
        "bias_mode": "equal_bias",
        "frequency_hz": frequency,
        "terminal_order": ["d", "g", "s", "b"],
        "y_imag_s": imag,
    }
    row = _capacitance_rows([record])[0]
    assert math.isclose(row["cgg_f"], 2.0e-15)
    assert math.isclose(row["cgd_f"], 3.0e-16)
    assert math.isclose(row["cgs_f"], 4.0e-16)


def test_benchmark_v2_contract_has_global_local_all_and_technology_latents() -> None:
    variation = load_toml("variation/benchmark_v2.toml")
    assert variation["requirements"]["global_mode"] is True
    assert variation["requirements"]["local_mode"] is True
    assert variation["requirements"]["all_mode"] is True
    assert variation["requirements"]["shared_technology_polarity_latents"] is True
    assert variation["distribution"]["resolved_samples_are_persisted"] is True
    assert "technology_id/polarity/intent" in variation["mos"]["global"]["latent_scope"]
    assert variation["mos"]["correlation"]["physical_process_correlation_claim"] == "none"


def test_v1_runtime_single_sources_are_removed() -> None:
    assert not list((ROOT / "models").glob("*/kit.toml"))
    assert not (ROOT / "variation/benchmark_v1.toml").exists()
    assert not (ROOT / "variation/adapters_v1.toml").exists()
    assert not (ROOT / "passives/benchmark_v1.toml").exists()
    assert not list((ROOT / "models").glob("*/ngspice/*_wrappers.inc"))


def test_release_validation_and_provenance_commands_are_cli_contracts(tmp_path: Path) -> None:
    parser = build_parser()
    release = parser.parse_args(["validate", "--release", "--output", str(tmp_path / "release")])
    assert release.command == "validate"
    assert release.release is True
    provenance = parser.parse_args(
        ["provenance-check", "--output", str(tmp_path / "provenance")]
    )
    assert provenance.command == "provenance-check"


def test_spectre_is_model_only_experimental_and_not_real_tool_gate() -> None:
    spectre = load_toml("validation/release_gates.toml")["spectre"]
    assert spectre["artifacts_required_for_all_families"] is True
    assert spectre["model_only"] is True
    assert spectre["status"] == "experimental_unverified"
    assert spectre["real_tool_validation_required"] is False
    assert spectre["virtuoso_integration_required"] is False


def test_release_contract_requires_v3_metadata_and_all_18_gates() -> None:
    contract = load_toml("validation/release_gates.toml")
    release = contract["release_metadata"]
    assert contract["schema"] == "apm.release-gates.v3"
    assert contract["target"] == "v3.0.0"
    assert release["target_version"] == "3.0.0"
    assert release["package_version_must_match_target"] is True
    assert release["unresolved_release_placeholders_forbidden"] is True
    gates = contract["gate"]
    assert len(gates) == 18
    assert all(gate["required"] is True for gate in gates)
    assert len({gate["id"] for gate in gates}) == 18


def test_reference_clean_clone_and_fail_closed_policy_remain_required() -> None:
    policy = load_toml("validation/release_gates.toml")["policy"]
    assert policy["clean_clone_required"] is True
    assert policy["repository_visibility_may_change"] is False
    assert policy["missing_evidence_is_failure"] is True
    assert policy["required_skipped_check_is_failure"] is True
    assert policy["historical_evidence_satisfies_v3"] is False
    assert policy["final_tag_creation_authorized"] is False
    assert policy["github_release_creation_authorized"] is False
