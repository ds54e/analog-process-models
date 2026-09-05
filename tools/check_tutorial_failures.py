#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Exercise documented diagnostics on copies of tutorial inputs; preserve saved devices."""
import argparse
import json
from pathlib import Path

from apm.journeys import negative_journey
from apm.paths import repository_root

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
result = negative_journey(repository_root(), args.output.resolve())
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['status'] == 'PASS' else 1)
