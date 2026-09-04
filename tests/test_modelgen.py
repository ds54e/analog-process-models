# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib

from tools.modelgen.apm045_mixed_voltage.kernel import (
    Curve,
    ModelgenError,
    ModelSource,
    NgspiceEvaluator,
    ParameterBound,
    SweepRequest,
    curves_sha256,
    hard_constraint_observations,
    render_bsim4_card,
)
from tools.modelgen.apm045_mixed_voltage.qualify_reconstruction import (
    COMPLETION_STATE,
    REQUIRED_RECORD_IDS,
    SUBSET_COMPLETION_STATE,
    _coverage,
)
from tools.modelgen.apm045_mixed_voltage.synthesize_families import (
    _candidate_parameters,
    _draws,
    _geometry,
    _validate_configuration,
    _width_challenge_audit,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIGURATION = ROOT / "tools/modelgen/apm045_mixed_voltage/reconstruction.toml"
GENERATION_CONFIGURATION = (
    ROOT / "tools/modelgen/apm045_mixed_voltage/generation_epoch_1.toml"
)
NGSPICE = ROOT / ".apm/toolchain/ngspice-47/bin/ngspice"


def _configuration() -> dict:
    with CONFIGURATION.open("rb") as handle:
        return tomllib.load(handle)


def _generation_configuration() -> dict:
    with GENERATION_CONFIGURATION.open("rb") as handle:
        return tomllib.load(handle)


def _parameters(polarity: str = "n") -> dict[str, float]:
    configuration = _configuration()
    result = {
        name: float(value) for name, value in configuration["fixed_parameters"].items()
    }
    result.update(
        {
            str(item["name"]): float(item[f"initial_{polarity}"])
            for item in configuration["parameter"]
        }
    )
    return result


def _curve(*, cgg_scale: float = 1.0) -> Curve:
    request = SweepRequest(
        request_id="unit-idvg",
        kind="idvg",
        temperature_c=27,
        l_m=1.0e-7,
        w_m=1.0e-6,
        fixed_bias_v=0.5,
        sweep_stop_v=1.0,
        points=5,
    )
    return Curve(
        request=request,
        sweep_v=np.linspace(0.0, 1.0, 5),
        idmag_a=np.asarray([1.0e-8, 2.0e-8, 4.0e-8, 8.0e-8, 1.6e-7]),
        terminal_cgg_f=cgg_scale * np.asarray([1.0e-15, 1.1e-15, 1.2e-15, 1.3e-15, 1.4e-15]),
    )


def test_reconstruction_input_has_frozen_fixtures_stages_and_sealed_grids() -> None:
    configuration = _configuration()
    gates_path = ROOT / "validation/release_gates_v4.toml"
    with gates_path.open("rb") as handle:
        gates = tomllib.load(handle)

    assert configuration["schema"] == "apm.modelgen.reconstruction-input.v1"
    assert configuration["seeds"] == [41001, 41002, 41003]
    assert {item["id"] for item in configuration["fixture"]} == {
        "apm022_svt",
        "apm045_vtg",
    }
    counts: dict[str, int] = {}
    for item in configuration["parameter"]:
        counts[str(item["stage"])] = counts.get(str(item["stage"]), 0) + 1
    limits = gates["modelgen"]["stage_limits"]
    for stage, count in counts.items():
        assert count <= int(limits[f"{stage}_max_free_parameters"])
    for fixture in configuration["fixture"]:
        assert fixture["calibration"] != fixture["holdout"]
        assert set(fixture["calibration"]["temperatures_c"]).isdisjoint(
            fixture["holdout"]["temperatures_c"]
        )


def test_public_evidence_matrix_separates_facts_priors_and_contracts() -> None:
    matrix_path = ROOT / "models/apm045/mixed_voltage_evidence.toml"
    with matrix_path.open("rb") as handle:
        matrix = tomllib.load(handle)
    with (ROOT / "validation/release_gates_v4.toml").open("rb") as handle:
        required = tomllib.load(handle)["public_evidence"]["required_fields"]

    assert matrix["schema"] == "apm.public-evidence-matrix.v1"
    assert matrix["technology_id"] == "apm045"
    assert matrix["private_or_proprietary_inputs_used"] is False
    evidence_ids = {item["id"] for item in matrix["evidence"]}
    assert len(evidence_ids) == len(matrix["evidence"])
    for item in matrix["evidence"]:
        assert set(required).issubset(item)
        assert item["observed_fact"].strip()
        assert item["allowed_use"]
        assert item["forbidden_use"]
    for prior in matrix["engineering_prior"]:
        assert set(prior["basis_evidence_ids"]).issubset(evidence_ids)
    forbidden_text = " ".join(
        rule for item in matrix["evidence"] for rule in item["forbidden_use"]
    ).lower()
    assert "toxe" in forbidden_text
    assert "do not copy" in forbidden_text
    assert matrix["apm_behavior_contract"]


def test_renderer_is_canonical_and_disables_unqualified_features() -> None:
    arguments = {
        "model_name": "apm_modelgen_unit_n",
        "polarity": "n",
        "parameters": _parameters(),
        "lmin_m": 5.0e-8,
        "lmax_m": 1.0e-6,
        "wmin_m": 9.0e-8,
        "wmax_m": 1.6e-5,
    }
    first = render_bsim4_card(**arguments)
    second = render_bsim4_card(**arguments)
    assert first.encode("utf-8") == second.encode("utf-8")
    assert ".model apm_modelgen_unit_n nmos level=54 version=4.8.2" in first
    assert "igcmod=0 igbmod=0 gidlmod=0" in first
    assert "rbodymod=0 rgatemod=0 acnqsmod=0 trnqsmod=0" in first
    assert "k3=0 k3b=0 w0=0" in first
    assert "SPDX-License-Identifier: Apache-2.0" in first


def test_generation_epoch_is_sealed_and_matches_frozen_geometry_search() -> None:
    configuration = _generation_configuration()
    audit = _validate_configuration(configuration, ROOT)

    assert configuration["generation_epoch"] == 1
    assert configuration["epoch_state"] == "SEALED_BEFORE_FINAL_CANDIDATE_GENERATION"
    assert configuration["kernel"] == "apm.modelgen.observable-kernel@1.1.0"
    assert configuration["seeds"] == [52001, 52002, 52003, 52004, 52005]
    assert audit["stage_parameter_counts"] == {
        "electrostatics": 8,
        "transport": 4,
        "output": 5,
        "charge": 4,
        "temperature": 3,
    }
    assert audit["width_challenge_um"] == [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 16.0]
    assert audit["declared_width_outcome"] == "WIDTH_INVARIANT_IN_SCOPE"
    assert all(audit["calibration_holdout_separation"].values())
    assert math.isclose(_geometry(configuration, "io18").lmin_m, 0.08e-6)
    assert math.isclose(_geometry(configuration, "io25").lmin_m, 0.18e-6)


def test_generation_draws_are_deterministic_independent_and_center_bounded() -> None:
    configuration = _generation_configuration()
    parameter_sets: list[dict[str, float]] = []
    draw_sets: list[dict[str, float]] = []
    for family in ("io18", "io25"):
        for polarity in ("n", "p"):
            for seed in configuration["seeds"]:
                first = _draws(configuration, family, polarity, int(seed))
                second = _draws(configuration, family, polarity, int(seed))
                assert first == second
                assert all(-1.0 <= value <= 1.0 for value in first.values())
                draw_sets.append(first)
                parameter_sets.append(
                    _candidate_parameters(
                        configuration, family, polarity, first, scale=1.0
                    )
                )
                assert _candidate_parameters(
                    configuration, family, polarity, first, scale=0.0
                ) != parameter_sets[-1]
    assert len({tuple(sorted(item.items())) for item in draw_sets}) == 20
    assert len({tuple(sorted(item.items())) for item in parameter_sets}) == 20


def test_width_challenge_audit_passes_only_invariant_full_grid() -> None:
    configuration = _generation_configuration()
    geometry = _geometry(configuration, "io18")
    widths_um = configuration["width_challenge"]["widths_um"]

    def curves(narrow_scale: float) -> dict[str, Curve]:
        result: dict[str, Curve] = {}
        for width_um in widths_um:
            request = SweepRequest(
                request_id=f"width-{width_um:g}",
                kind="idvg",
                temperature_c=27,
                l_m=geometry.lmin_m,
                w_m=float(width_um) * 1e-6,
                fixed_bias_v=geometry.native_vdd_v,
                sweep_stop_v=geometry.native_vdd_v,
                points=5,
            )
            scale = narrow_scale if math.isclose(float(width_um), 0.25) else 1.0
            result[request.request_id] = Curve(
                request=request,
                sweep_v=np.linspace(0.0, geometry.native_vdd_v, 5),
                idmag_a=(
                    request.w_m
                    * scale
                    * np.asarray([1.0, 2.0, 4.0, 7.0, 11.0])
                ),
                terminal_cgg_f=None,
            )
        return result

    passing = _width_challenge_audit(
        curves(1.0), configuration=configuration, geometry=geometry
    )
    failing = _width_challenge_audit(
        curves(0.5), configuration=configuration, geometry=geometry
    )
    assert passing["status"] == "pass"
    assert passing["outcome"] == "WIDTH_INVARIANT_IN_SCOPE"
    assert all(passing["checks"].values())
    assert failing["status"] == "fail"
    assert failing["outcome"] is None
    assert failing["checks"]["current_density_invariant"] is False


def test_parameter_bounds_fail_closed() -> None:
    with pytest.raises(ModelgenError):
        ParameterBound(name="bad", stage="output", lower=1.0, initial=1.0, upper=2.0)
    with pytest.raises(ModelgenError):
        ParameterBound(
            name="bad-log",
            stage="charge",
            lower=0.0,
            initial=1.0,
            upper=2.0,
            transform="log",
        )


def test_terminal_cgg_participates_in_hash_and_hard_rejection() -> None:
    first = _curve()
    second = _curve(cgg_scale=1.01)
    assert curves_sha256({"curve": first}) != curves_sha256({"curve": second})
    assert hard_constraint_observations({"curve": first}, 1.0e-10)["status"] == "pass"
    invalid = Curve(
        request=first.request,
        sweep_v=first.sweep_v,
        idmag_a=first.idmag_a,
        terminal_cgg_f=-first.terminal_cgg_f,
    )
    audit = hard_constraint_observations({"curve": invalid}, 1.0e-10)
    assert audit["status"] == "fail"
    assert audit["checks"]["curve.positive_terminal_cgg"] is False


def test_filtered_runs_cannot_claim_full_kernel_qualification() -> None:
    full = _coverage([{"id": record_id} for record_id in REQUIRED_RECORD_IDS])
    subset = _coverage([{"id": REQUIRED_RECORD_IDS[0]}])
    assert full["full_required_coverage"] is True
    assert subset["full_required_coverage"] is False
    assert COMPLETION_STATE == "MODELGEN_KERNEL_QUALIFIED"
    assert SUBSET_COMPLETION_STATE != COMPLETION_STATE


@pytest.mark.skipif(not NGSPICE.is_file(), reason="bootstrapped ngspice 47 is unavailable")
def test_real_ngspice_terminal_cgg_is_external_and_bias_dependent(tmp_path: Path) -> None:
    request = SweepRequest(
        request_id="real-vtg-n-idvg",
        kind="idvg",
        temperature_c=27,
        l_m=5.0e-8,
        w_m=1.0e-6,
        fixed_bias_v=0.5,
        sweep_stop_v=1.0,
        points=7,
    )
    evaluator = NgspiceEvaluator(ngspice=NGSPICE, work_directory=tmp_path)
    curve = evaluator.evaluate(
        source=ModelSource(
            model_name="NMOS_VTG",
            include_paths=(ROOT / "models/apm045/vendor/freepdk45/NMOS_VTG.inc",),
        ),
        polarity="n",
        requests=(request,),
        token="cgg",
        measure_terminal_cgg=True,
    )[request.request_id]
    assert evaluator.evaluation_count == 2
    assert curve.terminal_cgg_f is not None
    assert np.all(np.isfinite(curve.terminal_cgg_f))
    assert np.all(curve.terminal_cgg_f > 0.0)
    assert not math.isclose(
        float(curve.terminal_cgg_f[0]),
        float(curve.terminal_cgg_f[-1]),
        rel_tol=1.0e-3,
    )
    terminal_netlist = (tmp_path / "cgg/terminal-cgg.cir").read_text(
        encoding="utf-8"
    )
    assert "i(Vcg" in terminal_netlist
    assert "@m" not in terminal_netlist.lower()
