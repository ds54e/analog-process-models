from __future__ import annotations

import tomllib
from pathlib import Path

from apm.cli import TECHNOLOGIES, build_parser


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


def test_benchmark_passive_contract_is_technology_neutral() -> None:
    passives = load_toml("passives/benchmark_v1.toml")
    assert passives["resistor"]["public_name"] == "Rbench"
    assert passives["capacitor"]["public_name"] == "Cbench"
    assert passives["requirements"]["match_size_is_dimensionless"] is True
    assert passives["requirements"]["technology_neutral"] is True


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
