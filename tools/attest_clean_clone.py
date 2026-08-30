#!/usr/bin/env python3
# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

"""Record clean-clone and reference-platform facts before APM bootstrap."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# This launcher is itself part of the pre-bootstrap observation. Importing the
# project must not create __pycache__ before clean_clone inventories the tree.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from apm.clean_clone import CleanCloneError, create_clean_clone_attestation


def main() -> int:
    try:
        result = create_clean_clone_attestation(ROOT)
    except CleanCloneError as error:
        print(f"attest_clean_clone: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
