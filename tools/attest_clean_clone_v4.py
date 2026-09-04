#!/usr/bin/env python3
# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Record v4 clean-clone facts before APM bootstrap creates local state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from apm.clean_clone_v4 import CleanCloneV4Error, create_clean_clone_v4_attestation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("candidate", "exact-tag"), required=True)
    arguments = parser.parse_args()
    try:
        result = create_clean_clone_v4_attestation(ROOT, phase=arguments.phase)
    except CleanCloneV4Error as error:
        print(f"attest_clean_clone_v4: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
