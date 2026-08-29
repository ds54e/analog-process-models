# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model_build import build_models, sha256_file
from .toolchain import Toolchain, ToolchainError, resolve_toolchain, run_checked

NATIVE_BSIM3 = """APM M0 native BSIM3 smoke
Vd d 0 1.0
Vg g 0 1.0
Vs s 0 0
M1 d g s 0 apm_m0_bsim3 w=10u l=1u
.model apm_m0_bsim3 nmos level=49 version=3.3.0 vth0=0.45 u0=450 tox=7.5n
.control
op
print i(vd) @m1[gm]
quit
.endc
.end
"""

NATIVE_BSIM4 = """APM M0 native BSIM4 smoke
Vd d 0 0.8
Vg g 0 0.8
Vs s 0 0
M1 d g s 0 apm_m0_bsim4 w=1u l=0.1u
.model apm_m0_bsim4 nmos level=54 version=4.8.3 vth0=0.35 u0=350 toxe=2n
.control
op
print i(vd) @m1[gm]
quit
.endc
.end
"""


def _psp103_netlist(toolchain: Toolchain) -> str:
    model_library = toolchain.root / "models/apm130/vendor/ihp-sg13g2-models/cornerMOSlv.lib"
    osdi = toolchain.osdi_directory / "psp103.osdi"
    nqs_osdi = toolchain.osdi_directory / "psp103-nqs.osdi"
    return f"""APM M0 PSP103 OSDI smoke using IHP SG13G2 nominal model
.lib \"{model_library}\" mos_tt
Vd d 0 1.0
Vg g 0 1.0
Vs s 0 0
X1 d g s 0 sg13_lv_nmos w=1u l=0.13u
.control
pre_osdi {osdi}
pre_osdi {nqs_osdi}
op
print i(vd)
quit
.endc
.end
"""


def _bsimcmg_netlist(toolchain: Toolchain) -> str:
    osdi = toolchain.osdi_directory / "bsimcmg-112.1.0.osdi"
    # This deliberately small, APM-authored runtime card qualifies the engine.
    # It is not the release APM016F parameter deck and makes no fidelity claim.
    return f"""APM M0 BSIM-CMG OSDI engine smoke with synthetic runtime parameters
.model apm_m0_cmg bsimcmg_va type=1 bulkmod=1 geomod=0
+ l=30n fpitch=42n hfin=32n tfin=8n eot=1.2n phig=4.45
+ nbody=1e24 nsd=2e26 u0=0.03 vsat=90000 rdsw=150 pclm=0.08
Vd d 0 0.7
Vg g 0 0.7
Vs s 0 0
N1 d g s 0 apm_m0_cmg l=30n nfin=2
.control
pre_osdi {osdi}
op
print i(vd)
quit
.endc
.end
"""


def _extract_observables(output: str) -> dict[str, float]:
    pattern = re.compile(
        r"^([@a-z0-9_()\[\].:-]+)\s*=\s*([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    return {match.group(1): float(match.group(2)) for match in pattern.finditer(output)}


def _run_smoke(toolchain: Toolchain, work: Path, smoke_id: str, netlist: str) -> dict[str, Any]:
    netlist_path = work / f"{smoke_id}.cir"
    log_path = work / f"{smoke_id}.log"
    netlist_path.write_text(netlist, encoding="utf-8")
    command = [toolchain.ngspice, "-n", "-b", "-o", log_path, netlist_path]
    result = run_checked(command, environment=toolchain.environment(), cwd=work)
    log = log_path.read_text(encoding="utf-8", errors="replace")
    lowered = log.lower()
    if "fatal error" in lowered or "simulation interrupted" in lowered:
        raise ToolchainError(f"{smoke_id} reported a simulator error; see {log_path}")
    observables = _extract_observables(log)
    if "i(vd)" not in observables:
        raise ToolchainError(f"{smoke_id} produced no observable numeric output; see {log_path}")
    return {
        "id": smoke_id,
        "status": "pass",
        "netlist": str(netlist_path),
        "netlist_sha256": sha256_file(netlist_path),
        "log": str(log_path),
        "command": [str(item) for item in command],
        "stdout": result.stdout,
        "stderr": result.stderr,
        "observables": observables,
    }


def run_doctor(toolchain: Toolchain | None = None) -> dict[str, Any]:
    selected = toolchain or resolve_toolchain()
    ngspice_version = run_checked([selected.ngspice, "--version"])
    version_output = ngspice_version.stdout + ngspice_version.stderr
    if not re.search(r"ngspice[- ]47(?:\D|$)", version_output, re.IGNORECASE):
        raise ToolchainError("reference doctor requires ngspice major version 47")

    model_build = build_models(selected)
    work = selected.state / "doctor"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    smokes = [
        _run_smoke(selected, work, "native-bsim3", NATIVE_BSIM3),
        _run_smoke(selected, work, "native-bsim4", NATIVE_BSIM4),
        _run_smoke(selected, work, "psp103-osdi", _psp103_netlist(selected)),
        _run_smoke(selected, work, "bsimcmg-osdi", _bsimcmg_netlist(selected)),
    ]
    report: dict[str, Any] = {
        "schema": "apm.doctor.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "repository": str(selected.root),
        "ngspice_path": str(selected.ngspice),
        "ngspice_version_output": version_output.strip(),
        "model_build": model_build,
        "smokes": smokes,
    }
    report_path = work / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
