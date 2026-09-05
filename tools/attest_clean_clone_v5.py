#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from apm.clean_clone_v5 import create_clone

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Create an independent fresh v5 candidate clone; no tag action."
    )
    p.add_argument("--destination", type=Path, required=True)
    p.add_argument("--commit", required=True)
    a = p.parse_args()
    print(json.dumps(create_clone(a.destination, a.commit), indent=2))
