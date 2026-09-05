# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Reproduce the pre-migration inventory from pinned Git objects, never live files."""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

BASE = "25140f57c4c3714f6ab4c9c9df44698ad7732662"
ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", "--no-replace-objects", *args], cwd=ROOT)


def tree(commit, *paths):
    result = {}
    for row in git("ls-tree", "-rz", "--full-tree", commit, "--", *paths).split(b"\0"):
        if row:
            meta, name = row.split(b"\t", 1)
            mode, kind, blob = meta.decode().split()
            result[name.decode()] = {"mode": mode, "kind": kind, "blob": blob}
    return result


def constants(path):
    result = {}
    for node in ast.parse(git("show", f"{BASE}:{path}")).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                result[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return result


def capture():
    files = tree(BASE)
    payloads = {p: git("cat-file", "blob", e["blob"]) for p, e in files.items()}
    policy = constants("src/apm/maintenance_validate.py")
    scopes = {}
    for name, authority, selector in (
        ("v4", policy["V4_FROZEN_AUTHORITY_COMMIT"], policy["FROZEN_V4_PATHSPECS"]),
        ("v5", policy["V5_FROZEN_AUTHORITY_COMMIT"], policy["FROZEN_V5_PATHS"]),
        ("preflight", policy["PREFLIGHT_COMMIT"], policy["PREFLIGHT_PATHS"]),
        ("released_inputs", policy["V4_FROZEN_AUTHORITY_COMMIT"],
         ["models", "variation/adapters_v2.toml", "variation/benchmark_v2.toml",
          "variation/spectre", "src/apm/benchmark.py", "src/apm/native_variation.py"]),
    ):
        entries = tree(authority, *selector)
        if name in ("v4", "v5"):
            entries = {p: e for p, e in entries.items() if not p.startswith("validation/evidence/")
                       or (p.startswith(f"validation/evidence/{name}_")
                           and (name != "v4" or p.endswith(".json")))}
        if name == "released_inputs":
            entries = {p: e for p, e in entries.items() if not p.endswith("README.md")}
        scopes[name] = {"authority": authority, "selector": list(selector), "entries": entries}
    # These references are part of the local scientific/provenance closure, even
    # when their names contain old milestones. Other evidence is reconstructible.
    retained_evidence = {
        "v5_source_decision.md", "v5_preflight_source_audit.md",
        "v2_benchmark_adapters.json", "v2_apm130_native.json",
        "v4_generation_epoch3_calibration.json", "v4_mixed_voltage_qualification.json",
        "v4_modelgen_foundation.json", "v4_qualification_epoch1_failure.json",
        "v4_qualification_epoch2_failure.json",
    }
    normative = {"DEVICE_FAMILY_MODEL.md", "RESULT_CONTRACT.md", "NOISE_CHARACTERIZATION.md",
                 "NOISE_N1.md", "NOISE_N2.md", "V4_MIXED_VOLTAGE.md",
                 "V5_RESEARCH_VARIATION.md", "APM045_POSITIONING.md"}
    historical = {"RELEASE_V3.md", "RELEASE_V4.md", "RELEASE_V5.md", "V5_PREFLIGHT.md",
                  "UNATTENDED_EXECUTION.md", "PROJECT_CONTEXT.md", "RESEARCH_BASELINE.md",
                  "docs/release-validation.md", "docs/release-readiness-v5.md",
                  "docs/release-publication-v5.md", "tools/CODEX_V5_PROMPT.md",
                  "tests/test_release_validate.py", "tests/test_release_validate_v5.py",
                  "tests/test_v5_exact_tag_procedure.py"}
    artifacts = []
    for path, entry in files.items():
        name = Path(path).name
        if path.startswith(("models/", "variation/", "passives/", "LICENSES/")):
            role, action = "A", "retain_exact"
        elif path.startswith("validation/evidence/") and name != "README.md":
            role, action = ("A", "retain_exact") if name in retained_evidence else ("E", "retire_after_export")
        elif path in normative or path.startswith("tools/modelgen/") or path in {
            "validation/mixed_voltage_comparison_v1.toml", "validation/v5_confirmation_plan.toml",
            "validation/v5_reference_constraints.txt", "validation/release_gates_v4.toml",
            "tools/v5/source_reanalysis.py", "tools/v5_preflight/source_audit.toml",
        }:
            role, action = "B", "retain_exact"
        elif (path in historical or path.startswith(("tools/v5_preflight/", "validation/release_"))
              or name.startswith(("release_validate", "clean_clone", "attest_clean_clone"))
              or name == "requalify_v5_tag.py"):
            role, action = "D", "retire_after_export"
        else:
            role, action = "C", "maintain"
        references = []
        for source, data in payloads.items():
            if source == path:
                continue
            # Full-path and basename references, plus Python import spellings.
            needles = {path, name}
            if path.endswith(".py"):
                needles.add(Path(path).stem)
            hits = [n for n in needles if n.encode() in data]
            if hits:
                references.append({"path": source, "tokens": sorted(hits)})
        protected = {k: v["authority"] for k, v in scopes.items() if path in v["entries"]}
        artifacts.append({"path": path, **entry, "sha256": hashlib.sha256(payloads[path]).hexdigest(),
                          "role": role, "action": action, "protected_by": protected,
                          "references": references, "locator": f"{BASE}:{path}"})
    return {"schema": "apm.migration-inventory.v1", "commit": BASE,
            "tree": git("rev-parse", BASE + "^{tree}").decode().strip(),
            "roles": {"A": "current local scientific/license asset", "B": "current normative reference",
                      "C": "current maintainer/runtime helper or user guidance", "D": "historical implementation/procedure",
                      "E": "historical evidence"},
            "frozen_scopes": scopes, "artifacts": artifacts}


if __name__ == "__main__":
    destination = ROOT / "releases/migration-v6.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(capture(), sort_keys=True, indent=2) + "\n")
    print(destination.relative_to(ROOT))
