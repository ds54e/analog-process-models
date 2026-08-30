# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from apm.catalog import DeviceSpec, FamilySpec, TechnologySpec, load_catalog

ROOT = Path(__file__).resolve().parents[1]


def test_anchor_families_are_discovered_from_v2_manifests() -> None:
    catalog = load_catalog(ROOT)
    assert {item.technology_id for item in catalog.technologies} == {
        "apm350",
        "apm130",
        "apm045",
        "apm022",
        "apm016f",
    }
    expected = {
        "apm350": "general",
        "apm130": "lv",
        "apm045": "vtg",
        "apm022": "svt",
        "apm016f": "svt",
    }
    assert {
        item.technology_id: item.cross_process_anchor for item in catalog.technologies
    } == expected
    for technology_id, family_id in expected.items():
        family = catalog.family(technology_id, family_id)
        assert family.selector == f"{technology_id}/{family_id}"
        assert all(
            device.public_name.startswith(f"{technology_id}_{family_id}_")
            for device in family.devices
        )
        assert family.backend("ngspice").wrapper_path.is_file()


def test_selector_identity_levels() -> None:
    catalog = load_catalog(ROOT)
    assert isinstance(catalog.resolve("apm045"), TechnologySpec)
    assert isinstance(catalog.resolve("apm045/vtg"), FamilySpec)
    assert isinstance(catalog.resolve("apm045/vtg/nmos"), DeviceSpec)


def test_fixture_family_requires_no_production_loader_branch(tmp_path: Path) -> None:
    model_root = tmp_path / "models" / "fixture"
    family_root = model_root / "families" / "solo"
    backend_root = family_root / "ngspice"
    backend_root.mkdir(parents=True)
    (model_root / "provenance.toml").write_text('schema = "fixture.provenance"\n', encoding="utf-8")
    (backend_root / "model.inc").write_text("* fixture model\n", encoding="utf-8")
    (backend_root / "wrapper.inc").write_text("* fixture wrapper\n", encoding="utf-8")
    (model_root / "technology.toml").write_text(
        """schema = "apm.technology.v2"
id = "fixture"
display_name = "Fixture"
technology_class = "fixture-class"
description = "Sparse manifest loader fixture."
cross_process_anchor = "solo"
""",
        encoding="utf-8",
    )
    (family_root / "family.toml").write_text(
        """schema = "apm.family.v2"
technology_id = "fixture"
id = "solo"
architecture = "planar_bulk"
compact_model = "fixture_model"
gate_stack_id = "unknown"
gate_stack_class = "unknown"
threshold_class = "native"
origin = "apm_authored"
default_operating_profile = "nominal"
provenance = "models/fixture/provenance.toml"
backend_bindings = ["models/fixture/families/solo/ngspice/binding.toml"]

[[operating_profile]]
id = "nominal"
reference_vdd_v = 1.0
origin = "fixture"
purpose = "test"
evidence = "fixture"
temperatures_c = [-40, 27, 85, 125]

[[device]]
id = "native_nmos"
polarity = "n"
public_name = "fixture_solo_native_nmos"
terminals = ["d", "g", "s", "b"]
geometry_kind = "planar"
parameters = ["w", "l"]
lmin_m = 1e-7
default_w_m = 1e-6
characterization_lengths_m = [1e-7, 2e-7]

[threshold]
method = "constant_current"
coefficient_a = 1e-7
normalization = "coefficient * W/L"
vout_low_v = 0.05
vout_high_fraction_vdd = 0.8

[characterization]
idvg_points = 21
idvd_points = 21
y_frequencies_hz = [1e5, 1e6]
""",
        encoding="utf-8",
    )
    (backend_root / "binding.toml").write_text(
        """schema = "apm.backend-binding.v2"
technology_id = "fixture"
family_id = "solo"
backend = "ngspice"
compact_model_native_name = "fixture"
model_includes = ["models/fixture/families/solo/ngspice/model.inc"]
wrapper = "models/fixture/families/solo/ngspice/wrapper.inc"
native_oracle = "fixture"

[device.native_nmos]
native_vector_template = "@m.xdut.mfixture[{quantity}]"
""",
        encoding="utf-8",
    )

    catalog = load_catalog(tmp_path)
    family = catalog.family("fixture", "solo")
    assert [item.device_id for item in family.devices] == ["native_nmos"]
    assert family.devices[0].polarity == "n"
