#!/usr/bin/env python3
# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Generate the pinned IHP TT PSP103 card for APM's Spectre model wrapper.

The source card names its OpenVAF module ``psp103va``. Spectre's built-in
compact model is named ``psp103``. This deterministic extraction retains the
TT parameters and N/P QS model blocks byte-for-value while changing only that
model-type identifier and adding fixed wrapper-scope values.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "models/apm130/vendor/ihp-sg13g2-models"
CORNER_SOURCE = VENDOR / "cornerMOSlv.lib"
MODEL_SOURCE = VENDOR / "sg13g2_moslv_parm.lib"
TARGET = ROOT / "models/apm130/spectre/sg13g2_lv_psp103_tt.sp"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tt_parameters(text: str) -> list[str]:
    match = re.search(
        r"(?ms)^\.LIB mos_tt\s*$\n(?P<body>.*?)^\s*\.include sg13g2_moslv_mod\.lib\s*$",
        text,
    )
    if match is None:
        raise RuntimeError("could not locate mos_tt parameter section")
    result = []
    for line in match.group("body").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(".param sg13g2_lv_") and "svaricap" not in stripped:
            result.append(stripped)
    if len(result) != 34:
        raise RuntimeError(f"expected 34 TT MOS parameters, found {len(result)}")
    return result


def _model_block(text: str, polarity: str) -> str:
    model_name = f"sg13g2_lv_{polarity}mos_psp"
    match = re.search(
        rf"(?ms)^\.model {model_name} psp103va\b.*?(?=^\.model |\Z)",
        text,
    )
    if match is None:
        raise RuntimeError(f"could not locate {model_name} model block")
    block = match.group(0).rstrip()
    first, *rest = block.splitlines()
    first = re.sub(r"\bpsp103va\b", "psp103", first, count=1)
    return "\n".join([first, *rest])


def render() -> str:
    corner_text = CORNER_SOURCE.read_text(encoding="utf-8")
    model_text = MODEL_SOURCE.read_text(encoding="utf-8")
    parameters = _tt_parameters(corner_text)
    n_model = _model_block(model_text, "n")
    p_model = _model_block(model_text, "p")
    header = f"""* SPDX-FileCopyrightText: 2023 IHP PDK Authors
* SPDX-License-Identifier: Apache-2.0
*
* EXPERIMENTAL / UNVERIFIED APM Spectre model-only compatibility asset.
* GENERATED FILE: run python tools/generate_spectre_psp.py to reproduce.
*
* Source project: IHP SG13G2 Open PDK
* Source revision: 331c00484213b13414777eec1336ef5c29b969bd
* cornerMOSlv.lib SHA-256: {_sha256(CORNER_SOURCE)}
* sg13g2_moslv_parm.lib SHA-256: {_sha256(MODEL_SOURCE)}
*
* Transformation: select the mos_tt N/P global parameters and the two QS
* sg13g2_lv_[np]mos_psp blocks; replace only compact-model type psp103va with
* Spectre's native psp103 name; fix upstream wrapper-only ng/pre_layout/SWSOA
* inputs to their APM public-wrapper nominal values. No parameter value is
* fitted, calibrated, or otherwise changed. See docs/spectre.md.
*
* Copyright 2023 IHP PDK Authors
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*     https://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.

.param pre_layout=1 ng=1 SWSOA=0
"""
    return (
        header
        + "\n".join(parameters)
        + "\n\n"
        + n_model
        + "\n\n"
        + p_model
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero instead of updating when the generated file differs",
    )
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != expected:
            print(f"out of date: {TARGET.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print(f"up to date: {TARGET.relative_to(ROOT)}")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
