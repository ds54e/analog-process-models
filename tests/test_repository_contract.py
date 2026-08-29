from __future__ import annotations

import hashlib
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10 on EL9-compatible environments
    import tomli as tomllib

from apm.cli import TECHNOLOGIES, build_parser
from apm.doctor import _extract_observables
from apm.model_build import MODEL_SOURCES

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_KITS = ("apm350", "apm130", "apm045", "apm022", "apm016f")
EXPECTED_MODELS = {
    "apm350": "bsim3",
    "apm130": "psp103",
    "apm045": "bsim4",
    "apm022": "bsim4",
    "apm016f": "bsim_cmg",
}


def load_toml(relative: str) -> dict:
    with (ROOT / relative).open("rb") as handle:
        return tomllib.load(handle)


def test_cli_and_release_gate_use_same_five_kits() -> None:
    gates = load_toml("validation/release_gates.toml")
    assert tuple(gates["kits"]["required"]) == EXPECTED_KITS
    assert TECHNOLOGIES == EXPECTED_KITS


def test_reference_runtime_contract_is_el9_ngspice47_osdi() -> None:
    gates = load_toml("validation/release_gates.toml")
    runtime = gates["runtime"]
    assert runtime["primary_distribution"] == "AlmaLinux 9"
    assert runtime["acceptable_distribution_class"] == "RHEL-compatible EL9"
    assert runtime["architecture"] == "x86_64"
    assert runtime["required_ngspice_major"] == 47
    assert runtime["osdi_required"] is True
    assert runtime["python_minimum"] == "3.9"


def test_public_geometry_contract_stays_small() -> None:
    gates = load_toml("validation/release_gates.toml")
    public = gates["public_devices"]
    assert public["terminals"] == ["d", "g", "s", "b"]
    assert public["planar_parameters"] == ["w", "l"]
    assert public["finfet_parameters"] == ["l", "nfin"]
    assert set(public["forbidden_common_parameters"]) == {"m", "nf", "ng"}


def test_all_provenance_files_match_kit_identity_and_model_family() -> None:
    for kit, compact_model in EXPECTED_MODELS.items():
        provenance = load_toml(f"models/{kit}/provenance.toml")
        assert provenance["id"] == kit
        assert provenance["compact_model"] == compact_model
        assert provenance["validation"]["spectre"] == "experimental_unverified"


def test_audited_vendor_manifests_cover_exact_files_and_hashes() -> None:
    for kit in ("apm130", "apm016f"):
        provenance = load_toml(f"models/{kit}/provenance.toml")
        expected = provenance["source"]["imported_files"]
        vendor = ROOT / "models" / kit / "vendor"
        actual_paths = {
            str(path.relative_to(ROOT / "models" / kit))
            for path in vendor.rglob("*")
            if path.is_file()
        }
        assert set(expected) == actual_paths
        for relative, expected_hash in expected.items():
            payload = (ROOT / "models" / kit / relative).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == expected_hash


def test_required_osdi_sources_are_self_contained() -> None:
    assert set(MODEL_SOURCES) == {"psp103", "psp103-nqs", "bsimcmg-112.1.0"}
    for source in MODEL_SOURCES.values():
        assert (ROOT / source).is_file()


def test_doctor_observable_parser_ignores_unrelated_equals_signs() -> None:
    output = "TEMP = 27 and TNOM = 27\ni(vd) = -2.5e-4\n@m1[gm] = 4.0e-4\n"
    assert _extract_observables(output) == {"i(vd)": -2.5e-4, "@m1[gm]": 4.0e-4}


def test_apm_authored_scaled_models_are_explicitly_not_ptm_derived() -> None:
    apm022 = load_toml("models/apm022/provenance.toml")
    apm016f = load_toml("models/apm016f/provenance.toml")
    assert apm022["model_origin"] == "apm_generic"
    assert apm022["ptm_derived"] is False
    assert apm016f["model_origin"] == "apm_generic"
    assert apm016f["ptm_mg_derived"] is False


def test_benchmark_variation_contract_remains_unfrozen_initially() -> None:
    variation = load_toml("variation/benchmark_v1.toml")
    assert variation["requirements"]["process_mode"] is True
    assert variation["requirements"]["mismatch_mode"] is True
    assert variation["requirements"]["all_mode"] is True
    assert variation["requirements"]["python_rng_for_ngspice"] is True
    assert variation["requirements"]["spectre_statistics_for_spectre"] is True
    assert variation["requirements"]["explicit_distribution_semantics"] is True
    assert variation["requirements"]["explicit_units"] is True
    assert variation["requirements"]["explicit_sign_semantics"] is True
    assert variation["requirements"]["explicit_correlation_semantics"] is True
    assert "Normal(mean=0, std=1)" in variation["distribution"]["normalized_variable"]
    assert "PCG64" in variation["distribution"]["rng_reference"]
    assert variation["distribution"]["resolved_samples_are_persisted"] is True
    assert variation["mos"]["process"]["vth_shift_sigma_units"] == "V"
    assert variation["mos"]["process"]["drive_shift_sigma_units"] == "fractional_Id_change"
    assert "larger |Vth|" in variation["mos"]["intent"]["vth_shift"]
    assert "larger |Id|" in variation["mos"]["intent"]["drive_shift"]
    assert variation["mos"]["intent"]["raw_parameter_sign_is_not_canonical"] is True
    assert variation["mos"]["intent"]["adapter_must_map_sign_per_model_and_polarity"] is True


def test_benchmark_passive_contract_is_technology_neutral() -> None:
    passives = load_toml("passives/benchmark_v1.toml")
    assert passives["resistor"]["public_name"] == "Rbench"
    assert passives["capacitor"]["public_name"] == "Cbench"
    assert passives["requirements"]["match_size_is_dimensionless"] is True
    assert passives["requirements"]["technology_neutral"] is True
    assert passives["requirements"]["explicit_sign_semantics"] is True
    assert passives["requirements"]["explicit_correlation_semantics"] is True
    assert passives["requirements"]["explicit_temperature_semantics"] is True
    assert passives["temperature"]["reference_c"] == 27.0
    assert passives["temperature"]["tc1_units"] == "1/degC"
    assert "increases resolved resistance" in passives["resistor"]["positive_scale_semantic"]
    assert "increases resolved capacitance" in passives["capacitor"]["positive_scale_semantic"]


def test_release_validation_flag_is_part_of_cli_contract() -> None:
    parser = build_parser()
    args = parser.parse_args(["validate", "--release"])
    assert args.command == "validate"
    assert args.release is True


def test_spectre_is_not_a_real_tool_release_gate() -> None:
    gates = load_toml("validation/release_gates.toml")
    assert gates["spectre"]["status"] == "experimental_unverified"
    assert gates["spectre"]["real_tool_validation_required"] is False
    assert gates["spectre"]["virtuoso_integration_required"] is False


def test_reference_clean_clone_is_required_and_visibility_change_forbidden() -> None:
    gates = load_toml("validation/release_gates.toml")
    policy = gates["policy"]
    assert policy["clean_clone_required"] is True
    assert policy["repository_visibility_may_change"] is False
    assert policy["missing_evidence_is_failure"] is True
    assert policy["required_skipped_check_is_failure"] is True


def test_release_contract_requires_final_version_and_resolved_metadata() -> None:
    gates = load_toml("validation/release_gates.toml")
    release = gates["release_metadata"]
    assert release["target_version"] == "1.0.0"
    assert release["package_version_must_match_target"] is True
    assert release["release_notes_required"] is True
    assert release["release_notes_path"] == "CHANGELOG.md"
    assert release["unresolved_release_placeholders_forbidden"] is True
    assert "TBD" in release["forbidden_release_placeholder_tokens"]
    assert "not_started" in release["forbidden_release_placeholder_tokens"]
    gate_ids = {gate["id"] for gate in gates["gate"]}
    assert "release.metadata_complete" in gate_ids


def test_project_context_exists_and_is_explicitly_informative() -> None:
    text = (ROOT / "PROJECT_CONTEXT.md").read_text(encoding="utf-8")
    assert "informative, not normative" in text
    assert "Commonize the characterization contract, not the compact-model API" in text
    assert "PTM/PTM-MG" in text
    assert "ngspice 47" in text
    assert "AlmaLinux 9" in text


def test_initial_environment_is_explicitly_unvalidated_bootstrap_input() -> None:
    text = (ROOT / "ENVIRONMENT.md").read_text(encoding="utf-8")
    assert "ngspice is **not currently installed**" in text
    assert "M0 Runtime qualification" in text
    assert "--enable-osdi" in text
    assert "pre_osdi" in text


def test_research_baseline_is_dated_and_non_normative() -> None:
    text = (ROOT / "RESEARCH_BASELINE.md").read_text(encoding="utf-8")
    assert "2026-08-29" in text
    assert "not immutable policy" in text
    assert "BSIM-CMG" in text
    assert "112.1.0" in text
    assert "PSP 103.6" in text


def test_unattended_protocol_requires_full_context_and_status() -> None:
    text = (ROOT / "UNATTENDED_EXECUTION.md").read_text(encoding="utf-8")
    assert "PROJECT_CONTEXT.md" in text
    assert "ENVIRONMENT.md" in text
    assert "RESEARCH_BASELINE.md" in text
    assert "STATUS.md" in text
    assert "apm validate --release" in text
    assert "fresh clone" in text.lower()
