#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Create/attest an independent authoritative clone; never create a tag/release."""
import argparse
import json
from pathlib import Path

from apm.candidate import create_clone

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--commit', required=True)
parser.add_argument('--destination', type=Path, required=True)
args = parser.parse_args()
print(json.dumps(create_clone(args.destination, args.commit), indent=2))
