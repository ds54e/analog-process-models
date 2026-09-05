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


def test_preserved_catalog_matches_current_manifests() -> None:
    catalog = load_catalog(ROOT)
    assert tuple(t.technology_id for t in catalog.technologies) == tuple(sorted(EXPECTED_TECHNOLOGIES))
    assert sum(len(t.families) for t in catalog.technologies) == 15
    for technology, expected in EXPECTED_FAMILIES.items():
        assert {f.family_id for f in catalog.technology(technology).families} == set(expected)


def test_reference_runtime_pin_is_preserved() -> None:
    from apm.compiler_provenance import EXPECTED_COMMIT
    assert EXPECTED_COMMIT == "fdf2522b70f42793f64b1c72f0195c96dea0cc19"
    bootstrap = (ROOT / "tools/bootstrap-el9.sh").read_text()
    assert 'apm_ngspice_version="47"' in bootstrap
    assert '"${VERSION_ID%%.*}" == "9"' in bootstrap
    assert '--enable-osdi' in bootstrap
    assert 'x86_64' in bootstrap


def test_preserved_noise_method_identities() -> None:
    assert FIT_METHOD_IDENTITY == "apm.noise-fit.contiguous-regions@1.0.0"
    assert f"{ACQUISITION_POLICY_ID}@{ACQUISITION_POLICY_VERSION}" == "apm.noise-acquisition.bounded-white-search@1.0.0"


def test_public_geometry_and_identity_contract_is_manifest_enforced() -> None:
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
    for technology in load_catalog(ROOT).technologies:
        for family in technology.families:
            assert family.backend("spectre").wrapper_path.is_file()
        provenance = load_toml(f"models/{technology.technology_id}/provenance.toml")
        assert provenance["spectre"]["status"] == "experimental_unverified"
        assert provenance["spectre"]["real_tool_validation"] is False















