#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Controlled compiler build, invoked by bootstrap after pinned dependencies exist."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from apm.compiler_provenance import build_compiler, observe_compiler

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--cargo',type=Path,required=True)
    p.add_argument('--llvm',type=Path,required=True)
    p.add_argument('--jobs',type=int,default=4)
    a=p.parse_args()
    if a.destination.exists():
        observed=observe_compiler(a.destination/'bin/openvaf-r',a.destination/'receipt.json')
        if observed['status']!='VERIFIED':
            p.error('Existing prefix is unverified. Preserve it and select a new APM_TOOLCHAIN_DIR.')
        print(json.dumps(observed,indent=2))
    else:
        print(json.dumps(build_compiler(a.source.resolve(),a.destination.resolve(),
            a.cargo.absolute(),a.llvm.resolve(),dict(os.environ),a.jobs),indent=2))
