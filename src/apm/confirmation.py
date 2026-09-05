# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Current execution of preserved Research acceptance; not the historical release validator.

Promoted from v5; exact original plan/method bytes and thresholds remain authoritative.
The v6 declared 4096 pairs per geometry is enforced exactly (the old minimum was 1024).
"""
from __future__ import annotations

import json
from pathlib import Path

from .compiler_provenance import digest
from .research import SCHEMAS, verify
from .research_numerics import ResearchError
from .research_qualification import geometries


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
        "spice_count": plan["spice_pairs_per_geometry_polarity"] == 4096,
        "circuit_count": plan["circuit_realizations_per_family"] >= 1024,
        "circuit_families": set(plan["circuit_families"])
        == {"mirror1", "mirror4", "diffpair", "bank1", "bank4", "bank16"},
        "reference_temperature": plan["reference_temperature_k"] == 300,
        "reference_drain_bias": plan["reference_vds_v"] == 0.05,
        "campaign_scalar_count": plan["campaign_scalar_draws"] >= 204800,
        "campaign_risk": plan["campaign_risk_max"] <= 0.001,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}



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
            r["requested_pairs"] == plan["spice_pairs_per_geometry_polarity"]
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
            r["requested"] == plan["circuit_realizations_per_family"] and r["failed"] == 0 and r["status"] == "PASS"
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

