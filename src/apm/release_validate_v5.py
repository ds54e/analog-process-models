# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Independent, fail-closed v5 candidate evaluation. Never creates tags/releases."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import __version__
from .benchmark_validate import validate_benchmark
from .clean_clone_v5 import audit_clone, git
from .compare import validate_all_characterizations
from .compiler_provenance import digest, observe_compiler
from .doctor import run_doctor
from .maintenance_validate import V4_FROZEN_AUTHORITY_COMMIT, validate_maintenance_repository
from .native_variation import validate_apm130_native
from .noise_catalog import validate_noise_catalog
from .noise_method_validate import validate_noise_method
from .paths import repository_root
from .release_validate import _run_logged_command
from .research import SCHEMAS, describe, load_profile, save, seal, verify
from .research_charge import qualify_charge
from .research_numerics import ResearchError
from .research_qualification import geometries, qualify
from .toolchain import resolve_toolchain

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

CANDIDATE_GATES = frozenset(
    (
        "legacy.immutable_baseline",
        "source.quantitative_vtg_profile",
        "toolchain.observed_provenance",
        "methods.extraction",
        "mapping.reference_geometry",
        "sampling.identity_statistics",
        "mapping.tail_domain",
        "application.hierarchy_isolation",
        "execution.replay_fail_closed",
        "statistics.spice_recovery",
        "circuits.local_mismatch",
        "transfer.io_assessment",
        "capabilities.claim_boundaries",
        "compatibility.legacy_flows",
        "quality.public_hygiene",
        "release.clean_candidate",
    )
)


def audit_plan(plan):
    anchors = {(w, l) for w in (1.0, 2.0, 4.0) for l in (0.12, 0.24, 0.4)}
    actual = set(geometries(plan))
    holdouts = actual - anchors
    checks = {
        "both_polarities": set(plan["polarity"]) == {"n", "p"},
        "all_nine_anchors": anchors <= actual,
        "intermediate_geometries": len(holdouts) >= 2
        and all(1 < w < 4 and 0.12 < l < 0.4 for w, l in holdouts),
        "pure_count": plan["pure_pairs"] >= 65536,
        "spice_count": plan["spice_pairs_per_geometry_polarity"] >= 1024,
        "circuit_count": plan["circuit_realizations_per_family"] >= 1024,
        "circuit_families": set(plan["circuit_families"])
        == {"mirror1", "mirror4", "diffpair", "bank1", "bank4", "bank16"},
        "reference_temperature": plan["reference_temperature_k"] == 300,
        "reference_drain_bias": plan["reference_vds_v"] == 0.05,
        "campaign_scalar_count": plan["campaign_scalar_draws"] >= 204800,
        "campaign_risk": plan["campaign_risk_max"] <= 0.001,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def evaluate_gates(contract, results, commit):
    definitions = [x["id"] for x in contract["gate"] if x["phase"] == "candidate" and x["required"]]
    required = set(definitions)
    if required != CANDIDATE_GATES or len(definitions) != len(required):
        raise ResearchError("V5_REQUIRED_GATE_INVENTORY_DRIFT")
    indexed = {r["id"]: r for r in results}
    unique = len(indexed) == len(results) and set(indexed) == required
    evaluated = []
    for name in sorted(required):
        r = indexed.get(name, {})
        valid = unique and r.get("status") == "PASS" and r.get("subject_commit") == commit
        evidence = r.get("evidence", [])
        valid = valid and isinstance(evidence, list) and bool(evidence)
        if not isinstance(evidence, list):
            evidence = []
        for ref in evidence:
            try:
                valid = valid and digest(Path(ref["path"])) == ref["sha256"]
            except (OSError, KeyError, TypeError):
                valid = False
        evaluated.append(
            {**r, "id": name, "status": "PASS" if valid else "FAIL", "evidence_valid": bool(valid)}
        )
    return evaluated, all(r["status"] == "PASS" for r in evaluated)


def source_audit(root, output):
    registry = tomllib.loads((root / "variation/research/apm045/sources.toml").read_text())
    profilepath = root / "variation/research/apm045/derived/hart_tsmc40_profile.json"
    profile = load_profile(profilepath, root=root)
    data = json.loads((profilepath.parent / "hart_tsmc40_reanalysis.json").read_text())
    pdf = Path(os.environ.get("APM_V5_SOURCE_PDF", str(root / ".apm/v5/sources/companion.pdf")))
    script = root / "tools/v5/source_reanalysis.py"
    spec = importlib.util.spec_from_file_location("apm_v5_source_reanalysis", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observed = module.analyze(pdf)
    original = next(x for x in registry["source"] if x["id"] == "hart2020_st40_original")
    checks = {
        "original_beta_remains_blocked": all(
            original[k] == "BLOCKED_NORMALIZATION_CONFLICT"
            for k in ("beta_status_n", "beta_status_p")
        ),
        "coherent_companion_pdf": observed["pdf_sha256"] == data["pdf_sha256"],
        "coefficient_vectors_reproduced": observed["coefficients"] == data["coefficients"],
        "four_fixed_length_slopes": len(observed["fixed_length_slope_checks"]) == 2
        and all(
            max(abs(v) for v in x["relative_difference"]) < 0.01
            for x in observed["fixed_length_slope_checks"]
        ),
        "current_checks_recomputed": len(observed["independent_current_checks"]) == 30,
        "both_polarities": set(profile["coefficients"]) == {"n", "p"},
        "license_retained": data["licensing"]["license"] == "CC-BY-4.0"
        and (root / "LICENSES/CC-BY-4.0.txt").is_file(),
    }
    current = []
    for x in observed["independent_current_checks"]:
        a, b = x["predicted_parameter_interval"], x["observed_interval"]
        current.append(a[0] <= b[1] and b[0] <= a[1])
    checks["independent_source_current_bounds"] = bool(current) and all(current)
    for pol, values in profile["coefficients"].items():
        for x in values:
            source = next(
                s
                for s in data["coefficients"]
                if s["polarity"] == pol and abs(s["length_nm"] * 1e-9 - x["l_m"]) < 1e-20
            )
            checks[f"normalized_{pol}_{x['l_m']}"] = bool(
                np.allclose(
                    [x["a_vt_v_m"], x["a_beta_m"]],
                    [source["vth_mV_um"] * 1e-9, source["beta_percent_um"] * 1e-8],
                    rtol=1e-12,
                    atol=0,
                )
            )
    return save(
        output / "source.json",
        {
            "schema": "apm.v5-source-audit.v1",
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "profile_sha256": digest(profilepath),
            "pdf_sha256": digest(pdf),
            "script_sha256": digest(script),
            "limitations": "Explicit geometry inference, reference-offset cancellation, source confidence/digitization bounds and unquantified transfer error; not silicon calibration.",
        },
    )


def released_inputs(root):
    paths = [
        "models",
        "variation/adapters_v2.toml",
        "variation/benchmark_v2.toml",
        "variation/spectre",
        "src/apm/benchmark.py",
        "src/apm/native_variation.py",
    ]
    names = git(
        root, "ls-tree", "-r", "--name-only", V4_FROZEN_AUTHORITY_COMMIT, "--", *paths
    ).splitlines()
    # Live model portfolio READMEs were explicitly mutable after v4; electrical,
    # provenance, family and native/Benchmark configuration bytes remain exact.
    names = [n for n in names if not n.endswith("README.md")]
    expected_inventory = git(
        root, "ls-tree", "-r", V4_FROZEN_AUTHORITY_COMMIT, "--", *paths
    ).splitlines()
    observed_inventory = git(root, "ls-tree", "-r", "HEAD", "--", *paths).splitlines()
    expected_inventory = [n for n in expected_inventory if not n.endswith("README.md")]
    observed_inventory = [n for n in observed_inventory if not n.endswith("README.md")]
    mismatches = []
    for name in names:
        expected = subprocess.check_output(
            ["git", "show", V4_FROZEN_AUTHORITY_COMMIT + ":" + name], cwd=root
        )
        if not (root / name).is_file() or (root / name).read_bytes() != expected:
            mismatches.append(name)
    inventory = expected_inventory == observed_inventory
    return {
        "status": "PASS" if names and not mismatches and inventory else "FAIL",
        "compared": len(names),
        "mismatches": mismatches,
        "exact_inventory_modes_blobs": inventory,
    }


def validate_run_file(path, expected_hash):
    try:
        if digest(path) != expected_hash:
            return False
        r = verify(json.loads(path.read_text()), SCHEMAS["run"])
        return (
            r["status"] == "PASS"
            and bool(r["files"])
            and set(r["files"]) | {"run.json"} == {p.name for p in path.parent.iterdir()}
            and all(digest(path.parent / f) == h for f, h in r["files"].items())
        )
    except (OSError, KeyError, ValueError, TypeError):
        return False


def audit_confirmation(root, output, plan, head):
    reports = {}
    refs = {}
    issues = []
    expected = {(p, w, l) for p in ("n", "p") for w, l in geometries(plan)}
    for stage in ("sampler", "mapping", "statistics", "circuits", "replay", "io"):
        path = output / stage / "report.json"
        try:
            r = verify(json.loads(path.read_text()), SCHEMAS["report"])
            if (
                r["subject_commit"] != head
                or r["plan_sha256"] != digest(root / "validation/v5_confirmation_plan.toml")
                or r["profile_sha256"] != digest(root / plan["profile"])
                or r["status"] != "PASS"
            ):
                raise ResearchError("STALE_OR_FAILED_CONFIRMATION")
            reports[stage] = r
            refs[stage] = {"path": str(path), "sha256": digest(path)}
        except (OSError, KeyError, ValueError, TypeError) as error:
            reports[stage] = {}
            issues.append({"stage": stage, "error": str(error)})
    m = reports["mapping"]
    s = reports["statistics"]
    c = reports["circuits"]
    a = reports["sampler"]
    re = reports["replay"]
    io = reports["io"]

    def coverage(report):
        return (
            len(report.get("records", [])) == len(expected)
            and {(r["polarity"], r["w_um"], r["l_um"]) for r in report.get("records", [])}
            == expected
        )

    checks = {
        "methods": bool(m)
        and coverage(m)
        and all(max(r["extraction_error_over_sigma"]) <= 0.005 for r in m["records"]),
        "mapping": bool(m)
        and coverage(m)
        and all(
            len(r["cases"]) == 26
            and r["condition"] <= 100
            and r["half_step"] <= 0.02
            and all(
                x["status"] == "PASS" and max(x["error_over_sigma"]) <= 0.02 and x["twin_equal"]
                for x in r["cases"]
            )
            for r in m["records"]
        ),
        "sampling": bool(a)
        and a.get("requested_pairs", 0) >= 65536
        and a.get("executed_pairs") == a.get("requested_pairs")
        and a.get("failed_pairs") == 0
        and bool(a.get("checks"))
        and all(a["checks"].values()),
        "tail": bool(m) and m.get("tail_risk", {}).get("expected_count", 1) <= 0.001,
        "application": bool(m)
        and len(m.get("controls", {}).get("records", [])) == 18
        and all(r["status"] == "PASS" for r in m["controls"]["records"]),
        "statistics": bool(s)
        and coverage(s)
        and all(
            r["requested_pairs"] >= 1024
            and r["executed_pairs"] == r["requested_pairs"]
            and r["failed_pairs"] == 0
            and bool(r.get("checks"))
            and all(r["checks"].values())
            for r in s["records"]
        ),
        "circuits": bool(c)
        and {(r["polarity"], r["family"]) for r in c.get("records", [])}
        == {(p, k) for p in ("n", "p") for k in plan["circuit_families"]}
        and all(
            r["requested"] >= 1024 and r["failed"] == 0 and r["status"] == "PASS"
            for r in c["records"]
        ),
        "replay": bool(re)
        and len(re.get("records", [])) == 8
        and all(
            r["status"] == "PASS"
            and abs(r["ac_tran_amplitude_ratio"] - 1) <= 0.02
            and abs(r["ac_tran_phase_difference"]) <= 0.03
            and r["terminal_kcl_relative"] < 1e-8
            for r in re["records"]
        ),
        "io": bool(io)
        and {(r["family"], r["polarity"]) for r in io.get("records", [])}
        == {(f, p) for f in ("io18", "io25") for p in ("n", "p")}
        and all(
            r["status"] == "PASS"
            and r["outcome"] in ("SUPPORTED_HYPOTHESIS", "UNRESOLVED_WITH_EVIDENCE")
            and len(r["rows"]) == 48
            for r in io["records"]
        ),
    }
    checks["declared_minimum_plan"] = audit_plan(plan)["status"] == "PASS"
    checks["sampler_raw_integrity"] = (
        bool(a)
        and (output / "sampler/draws.npz").is_file()
        and digest(output / "sampler/draws.npz") == a.get("draws_sha256")
    )
    checks["mapping_raw_integrity"] = bool(m) and all(
        validate_run_file(
            output
            / "mapping"
            / f"{r['polarity']}-{r['w_um']:g}-{r['l_um']:g}"
            / "runs"
            / x["run"]
            / "run.json",
            x["report_sha256"],
        )
        for r in m.get("records", [])
        for x in r.get("cases", [])
    )
    checks["replay_raw_integrity"] = bool(re) and all(
        validate_run_file(
            output / "replay" / r["polarity"] / "runs" / r["run"] / "run.json", r["report_sha256"]
        )
        for r in re.get("records", [])
    )
    checks["io_raw_integrity"] = bool(io)
    for r in io.get("records", []):
        for row in r["rows"]:
            path = Path(row["run"])
            try:
                raw = json.loads((path / "run.json").read_text())
                checks["io_raw_integrity"] &= (
                    digest(path / "run.json") == row["sha256"]
                    and bool(raw["files"])
                    and all(digest(path / f) == h for f, h in raw["files"].items())
                )
            except (OSError, KeyError, ValueError):
                checks["io_raw_integrity"] = False
    # Audit the expected cohort inventory, its summary binding, every requested
    # sample index and each successful sample's raw artifact receipt.
    for stage in ("statistics", "circuits"):
        complete = bool(reports[stage])
        expected_paths = set()
        for r in reports[stage].get("records", []):
            relative = (
                f"{r['polarity']}-{r['w_um']:g}-{r['l_um']:g}"
                if stage == "statistics"
                else f"{r['polarity']}/{r['family']}"
            )
            folder = output / stage / relative / "cohort.json"
            expected_paths.add(folder)
            try:
                cohort = json.loads(folder.read_text())
                n = r["requested_pairs"] if stage == "statistics" else r["requested"]
                if (
                    digest(folder) != r["cohort_sha256"]
                    or cohort["requested"] != n
                    or len(cohort["rows"]) != n
                    or {x["index"] for x in cohort["rows"]} != set(range(n))
                ):
                    complete = False
                for row in cohort["rows"]:
                    if row.get("status") != "PASS" or not validate_run_file(
                        folder.parent / "runs" / row.get("run", "missing") / "run.json",
                        row.get("report_sha256"),
                    ):
                        complete = False
            except (OSError, KeyError, ValueError, TypeError):
                complete = False
        complete &= expected_paths == set((output / stage).rglob("cohort.json"))
        checks[f"{stage}_raw_integrity"] = complete and bool(reports[stage])
    checks["cross_bias_regions"] = bool(s) and all(
        len(
            {
                b["gm_id"]
                for r in s.get("records", [])
                if r["polarity"] == p
                for b in r.get("cross_bias", [])
                if b.get("valid_sensitivity_region")
            }
        )
        >= 2
        for p in ("n", "p")
    )
    return {
        "status": "PASS" if checks and all(checks.values()) else "FAIL",
        "checks": checks,
        "reports": reports,
        "references": refs,
        "issues": issues,
    }


def test_coverage(root, output, repository):
    """Inspect executed current pytest and rerun the separate frozen preflight tests."""
    output.mkdir(parents=True, exist_ok=True)
    static = Path(repository["static_report_path"])
    if digest(static) != repository["static_report_sha256"]:
        raise ResearchError("STATIC_REPORT_DRIFT")
    report = json.loads(static.read_text())
    current = next(r for r in report["commands"] if r["id"] == "pytest")
    separate = _run_logged_command(
        root,
        output,
        "preflight-tests",
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "pythonpath=src . tools/v5_preflight",
            "tools/v5_preflight/tests",
        ],
    )
    results = []
    for item in (current, separate):
        text = Path(item["stdout_path"]).read_text()
        passed = re.findall(r"(\d+) passed", text)
        valid = (
            item["status"] == "pass"
            and digest(Path(item["stdout_path"])) == item["stdout_sha256"]
            and digest(Path(item["stderr_path"])) == item["stderr_sha256"]
        )
        valid &= (
            bool(passed)
            and int(passed[-1]) > 0
            and not re.search(
                r"\b[1-9]\d* (?:skipped|xfailed|xpassed|deselected|failed|errors?)\b", text
            )
        )
        results.append(
            {
                "id": item["id"],
                "status": "PASS" if valid else "FAIL",
                "passed": int(passed[-1]) if passed else 0,
                "execution": item,
            }
        )
    return {
        "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
        "tests": results,
    }


def reference_platform():
    release = dict(
        line.split("=", 1)
        for line in Path("/etc/os-release").read_text().splitlines()
        if "=" in line
    )
    family = (release.get("ID", "") + " " + release.get("ID_LIKE", "")).replace('"', "").split()
    return {
        "status": "PASS"
        if platform.machine() == "x86_64"
        and release.get("VERSION_ID", "").strip('"').split(".")[0] == "9"
        and bool(set(family) & {"rhel", "centos", "almalinux", "rocky"})
        else "FAIL",
        "os_release": release,
        "machine": platform.machine(),
        "kernel": platform.release(),
        "python": sys.version,
    }


def capability_flow(root, output, maps):
    output.mkdir(parents=True, exist_ok=True)
    request = root / "examples/research/request.json"
    realization = output / "realization.json"
    arguments = [
        ["describe"],
        [
            "sample",
            "--profile",
            str(root / "variation/research/apm045/derived/hart_tsmc40_profile.json"),
            "--request",
            str(request),
            "--seed",
            "1001",
            "--index",
            "0",
            "--state",
            str(maps),
            "--output",
            str(realization),
        ],
        [
            "run",
            "--request",
            str(request),
            "--realization",
            str(realization),
            "--output",
            str(output / "runs"),
        ],
        [
            "run",
            "--request",
            str(request),
            "--realization",
            str(realization),
            "--temperature-c",
            "85",
            "--output",
            str(output / "runs"),
        ],
    ]
    records = []
    saved_hash = None
    for i, args in enumerate(arguments):
        r = _run_logged_command(
            root, output, f"cli-{i}", [sys.executable, "-m", "apm.cli", "research", *args]
        )
        try:
            value = json.loads(Path(r["stdout_path"]).read_text())
            if i == 0:
                valid = (
                    value["other_families"] == "UNSUPPORTED"
                    and value["io18_io25"] == "ASSESSMENT_ONLY; beta unknown"
                    and len(value["approved_profiles"]) == 1
                )
            elif i == 1:
                valid = value["status"] == "RESOLVED"
                saved_hash = digest(realization)
            else:
                valid = value["status"] == "PASS" and digest(realization) == saved_hash
            r["status"] = "PASS" if r["status"] == "pass" and valid else "FAIL"
        except (OSError, KeyError, ValueError):
            r["status"] = "FAIL"
        records.append(r)
    return {
        "status": "PASS" if all(r["status"] == "PASS" for r in records) else "FAIL",
        "executions": records,
        "saved_realization_sha256": saved_hash,
        "request_sha256": digest(request),
        "circuit_sha256": digest(root / "examples/research/mirror.cir"),
    }


def validate_release_v5(output: Path | None, *, root: Path | None = None):
    root = (root or repository_root()).resolve()
    output = (
        output
        or root / ".apm/v5" / ("candidate-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    ).resolve()
    output.mkdir(parents=True, exist_ok=False)
    head = git(root, "rev-parse", "HEAD")
    before = git(root, "status", "--porcelain", "--untracked-files=all")
    contract = tomllib.loads((root / "validation/release_gates_v5.toml").read_text())
    plan = tomllib.loads((root / "validation/v5_confirmation_plan.toml").read_text())
    tool = resolve_toolchain(root)
    components = {}
    refs = {}

    def component(name, function):
        try:
            result = function()
        except Exception as error:  # noqa: BLE001 - retain failure and continue independent gates
            result = {"status": "FAIL", "error": str(error)}
        path = output / f"{name}.json"
        save(path, result)
        components[name] = result
        refs[name] = {"path": str(path), "sha256": digest(path)}
        print(f"v5 component {name}: {result.get('status')}", flush=True)
        return result

    clone = component("clean_clone", lambda: audit_clone(root))
    source = component("source", lambda: source_audit(root, output))
    observed = component(
        "compiler", lambda: observe_compiler(tool.openvaf, environment=tool.environment())
    )
    doctor = component("doctor", lambda: run_doctor(tool))
    platform_report = component("platform", reference_platform)
    compatibility = {
        "repository": lambda: validate_maintenance_repository(output / "repository", root=root),
        "benchmark": lambda: validate_benchmark(output / "benchmark", tool),
        "native": lambda: validate_apm130_native(output / "native", tool),
        "electrical": lambda: validate_all_characterizations(output / "electrical"),
        "noise_method": lambda: validate_noise_method(output / "noise-method"),
        "noise_catalog": lambda: validate_noise_catalog(output / "noise-catalog"),
    }
    for name, function in compatibility.items():
        component(name, function)
    component(
        "test_coverage",
        lambda: test_coverage(root, output / "test-coverage", components["repository"]),
    )
    component("legacy_inputs", lambda: released_inputs(root))
    for stage in ("sampler", "mapping", "statistics", "circuits", "replay", "io"):
        component(
            "research_" + stage,
            lambda stage=stage: qualify(root, tool.ngspice, output / "research", stage),
        )
    component(
        "charge",
        lambda: qualify_charge(tool.ngspice, output / "research/replay", output / "charge"),
    )
    component(
        "capability", lambda: capability_flow(root, output / "capability", output / "research/maps")
    )
    try:
        audit = audit_confirmation(root, output / "research", plan, head)
    except Exception as error:  # noqa: BLE001 - retain failure and continue independent gates
        audit = {"checks": {}, "issues": [str(error)]}
    component("confirmation_audit", lambda: audit)
    checks = audit["checks"]
    results = []

    def gate(name, passed, dependencies, detail):
        results.append(
            {
                "id": name,
                "subject_commit": head,
                "status": "PASS" if passed else "FAIL",
                "evidence": [refs[x] for x in dependencies],
                "detail": detail,
            }
        )

    repository = components["repository"]
    audits = repository.get("audits", {})
    gate(
        "legacy.immutable_baseline",
        components["legacy_inputs"].get("status") == "PASS"
        and all(
            audits.get(k, {}).get("status") == "pass"
            for k in ("frozen_v4_artifacts", "frozen_preflight", "released_v3_compatibility")
        ),
        ["repository", "legacy_inputs"],
        "Exact released bytes, catalogs, frozen snapshots and tags.",
    )
    gate(
        "source.quantitative_vtg_profile",
        source.get("status") == "PASS",
        ["source"],
        "Coherent companion reanalysis; original ST beta blocked.",
    )
    gate(
        "toolchain.observed_provenance",
        observed.get("status") == "VERIFIED" and doctor.get("status") == "pass",
        ["compiler", "doctor"],
        "Observed source, clean submodules, build tools/libraries, executable and OSDI binding.",
    )
    for name, required in [
        ("methods.extraction", ("methods", "mapping_raw_integrity")),
        (
            "mapping.reference_geometry",
            ("mapping", "mapping_raw_integrity", "declared_minimum_plan"),
        ),
        ("sampling.identity_statistics", ("sampling", "sampler_raw_integrity")),
        ("mapping.tail_domain", ("tail", "mapping", "mapping_raw_integrity")),
        ("application.hierarchy_isolation", ("application", "mapping", "mapping_raw_integrity")),
        ("execution.replay_fail_closed", ("application", "replay", "replay_raw_integrity")),
        ("transfer.io_assessment", ("io", "io_raw_integrity")),
    ]:
        gate(
            name,
            all(checks.get(check) is True for check in required)
            and (
                name != "execution.replay_fail_closed"
                or components["charge"].get("status") == "PASS"
            ),
            ["confirmation_audit", "charge"]
            if name == "execution.replay_fail_closed"
            else ["confirmation_audit"],
            list(required),
        )
    gate(
        "statistics.spice_recovery",
        all(
            checks.get(x) is True
            for x in ("statistics", "statistics_raw_integrity", "cross_bias_regions")
        ),
        ["confirmation_audit"],
        "Simultaneous sigma equivalence, nonlinear ratios and separate sensitivity/Croon predictions.",
    )
    gate(
        "circuits.local_mismatch",
        checks.get("circuits") is True and checks.get("circuits_raw_integrity") is True,
        ["confirmation_audit"],
        "Both mirror ratios, differential offsets and independent unit banks.",
    )
    capability = describe(root)
    gate(
        "capabilities.claim_boundaries",
        bool(capability["approved_profiles"])
        and components["capability"].get("status") == "PASS"
        and checks.get("application") is True
        and checks.get("replay") is True,
        ["source", "confirmation_audit", "capability"],
        "Explicit source/transfer tiers, unsupported families/effects and fail-closed typed API.",
    )
    gate(
        "compatibility.legacy_flows",
        all(
            components[x].get("status")
            == ("validated" if x in ("benchmark", "native", "electrical") else "pass")
            for x in compatibility
        ),
        list(compatibility),
        "Legacy electrical, noise, Benchmark and native executions, with preserved schemas.",
    )
    gate(
        "quality.public_hygiene",
        repository.get("status") == "pass" and components["test_coverage"].get("status") == "PASS",
        ["repository", "source", "test_coverage"],
        "Current pytest and separate preflight tests with no skips; Ruff/REUSE/provenance/distribution and source license checks.",
    )
    clean = (
        not before
        and not git(root, "status", "--porcelain", "--untracked-files=all")
        and git(root, "rev-parse", "HEAD") == head
    )
    gate(
        "release.clean_candidate",
        clone.get("status") == "PASS"
        and clean
        and __version__ == "5.0.0"
        and platform_report["status"] == "PASS"
        and sys.version_info >= (3, 9),
        ["clean_clone", "repository", "platform"],
        "Exact clean 5.0.0 candidate from independently created fresh clone.",
    )
    gates, passed = evaluate_gates(contract, results, head)
    report = seal(
        {
            "schema": "apm.release-readiness.v5",
            "status": "V5_RELEASE_READY" if passed else "BLOCKED",
            "subject_commit": head,
            "version": __version__,
            "gate_contract_sha256": digest(root / "validation/release_gates_v5.toml"),
            "passed_gates": sum(g["status"] == "PASS" for g in gates),
            "required_gates": len(gates),
            "gates": gates,
            "create_tag_authorized": False,
            "publish_release_authorized": False,
            "post_tag_is_candidate_dependency": False,
        }
    )
    save(output / "report.json", report)
    if not passed:
        raise ResearchError(f"V5 candidate blocked; see {output / 'report.json'}")
    return {**report, "report_path": str(output / "report.json"), "output_directory": str(output)}
