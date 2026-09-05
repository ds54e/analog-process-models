# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Independent charge conservation on the persisted replay realizations."""

from __future__ import annotations

import json

import numpy as np

from .compiler_provenance import digest
from .research import SCHEMAS, save, seal, verify
from .research_circuits import logged_deck
from .research_numerics import ResearchError
from .research_spice import leaf, read_values

METHOD = "apm.research-charge.conservation@1"


def charge_metrics(data):
    if data.ndim != 2 or data.shape[1] != 5 or len(data) < 2 or not np.all(np.isfinite(data)):
        raise ResearchError("INCOMPLETE_CHARGE_ACQUISITION")
    q = data[:, 1:]
    scale = float(np.max(abs(q)))
    dynamic = float(np.max(np.ptp(q, axis=0)))
    relative = float(np.max(abs(q.sum(axis=1))) / scale) if scale else 1.0
    return {
        "status": "PASS" if scale > 0 and dynamic > 1e-24 and relative <= 1e-12 else "FAIL",
        "relative_conservation_error": relative,
        "maximum_charge_c": scale,
        "maximum_charge_swing_c": dynamic,
        "points": len(q),
    }


def qualify_charge(binary, replay, output):
    path = replay / "report.json"
    stage = verify(json.loads(path.read_text()), SCHEMAS["report"])
    records = []
    for item in stage["records"]:
        source = replay / item["polarity"] / "runs" / item["run"]
        report = verify(json.loads((source / "run.json").read_text()), SCHEMAS["run"])
        if report["status"] != "PASS" or digest(source / "run.json") != item["report_sha256"]:
            raise ResearchError("REPLAY_RECEIPT_DRIFT")
        if any(digest(source / f) != h for f, h in report["files"].items()):
            raise ResearchError("REPLAY_RAW_DRIFT")
        realization = verify(
            json.loads((source / "realization.json").read_text()), SCHEMAS["realization"]
        )
        request = json.loads((source / "request.json").read_text())
        device = request["devices"][0]
        vectors = " ".join(f"@{leaf(device)}[{q}]" for q in ("qg", "qd", "qs", "qb"))
        deck = (source / "input.cir").read_text()
        deck = deck.replace("set wr_vecnames\n", f"set wr_vecnames\nsave all {vectors}\n", 1)
        for index in (0, 2):
            lines = deck.splitlines()
            at = next(
                i for i, line in enumerate(lines) if line.startswith(f"wrdata analysis{index}.txt ")
            )
            lines.insert(at + 1, f"wrdata charge{index}.txt {vectors}")
            deck = "\n".join(lines) + "\n"
        destination = output / f"{item['polarity']}-{item['temperature_c']:g}"
        run = logged_deck(binary, destination, deck)
        log = (destination / "stdout.txt").read_text() + (destination / "stderr.txt").read_text()
        raw = [d["raw"] for d in realization["devices"]]
        readbacks = all(
            not read_values(log, request["devices"], f"{prefix}{i}", raw)
            for i in (0, 1, 2)
            for prefix in ("applied", "after")
        )
        checks = []
        for i in (0, 2):
            try:
                checks.append(
                    {
                        "analysis": "dc" if i == 0 else "tran",
                        **charge_metrics(np.loadtxt(destination / f"charge{i}.txt", skiprows=1)),
                    }
                )
            except (OSError, ValueError) as error:
                checks.append({"status": "FAIL", "error": str(error)})
        records.append(
            {
                "polarity": item["polarity"],
                "temperature_c": item["temperature_c"],
                "realization_id": realization["content_id"],
                "raw": raw,
                "readback_stable": readbacks,
                "checks": checks,
                "status": "PASS"
                if run["status"] == "PASS"
                and readbacks
                and all(c["status"] == "PASS" for c in checks)
                else "FAIL",
                "run_path": str(destination / "run.json"),
                "run_sha256": digest(destination / "run.json"),
            }
        )
    return save(
        output / "report.json",
        seal(
            {
                "schema": SCHEMAS["report"],
                "method": METHOD,
                "subject_commit": stage["subject_commit"],
                "replay_sha256": digest(path),
                "status": "PASS"
                if len(records) == 8 and all(r["status"] == "PASS" for r in records)
                else "FAIL",
                "records": records,
                "limits": {"relative_conservation_max": 1e-12, "dynamic_charge_min_c": 1e-24},
                "scope": "Finite nonconstant native qg/qd/qs/qb and sum conservation in DC/transient, with unchanged saved raw parameters. Charge partition is model prediction, not measured calibration.",
            }
        ),
    )
