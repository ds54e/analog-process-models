#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Run one current CLI command and retain its source/data read and import closure."""
import atexit
import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = Path(sys.argv[1]).resolve()
sys.argv = ['apm', *sys.argv[2:]]
reads = set()


def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = os.path.abspath(os.fsdecode(args[0]))
        prefix = str(root) + os.sep
        if path.startswith(prefix):
            relative = path[len(prefix):]
            if relative.split(os.sep)[0] not in ('.apm', '.venv', '.git'):
                reads.add(relative)


def finish():
    output.parent.mkdir(parents=True, exist_ok=True)
    modules = {k: str(getattr(v, '__file__', None)) for k, v in sys.modules.items()
               if k == 'apm' or k.startswith('apm.')}
    output.write_text(json.dumps({'reads': sorted(reads), 'modules': modules}, indent=2) + '\n')


atexit.register(finish)
sys.addaudithook(audit)
from apm.cli import main

raise SystemExit(main())
