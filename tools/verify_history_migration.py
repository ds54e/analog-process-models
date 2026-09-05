#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Explicit outer archive campaign; never executes historical Python code."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from apm.history import export_tree, git_text, load_index, verify_history


def campaign(root, output):
    output.mkdir(parents=True, exist_ok=False)
    checks = {'original_history': verify_history(root)}
    exports = []
    for release in load_index(root)['legacy']:
        for kind in ('source', 'evidence'):
            exports.append(export_tree(root, release['tag'], kind,
                                       output / 'exports' / release['tag'] / kind))
    for name in load_index(root)['snapshot']:
        exports.append(export_tree(root, name, 'source', output / 'exports' / name / 'source'))
    bundle = output / 'history.bundle'
    commands = [
        ['git', '--no-replace-objects', 'bundle', 'create', str(bundle), '--all'],
        ['git', '--no-replace-objects', 'bundle', 'verify', str(bundle)],
        ['git', 'clone', '--no-local', str(bundle), str(output / 'restored')],
    ]
    executions = []
    for i, command in enumerate(commands):
        r = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
        log = output / f'bundle-{i}.txt'
        log.write_text(r.stdout + r.stderr)
        executions.append({'command': command, 'returncode': r.returncode,
                           'log': str(log), 'sha256': hashlib.sha256(log.read_bytes()).hexdigest()})
        if r.returncode:
            break
    restored = output / 'restored'
    restoration = verify_history(restored) if restored.is_dir() else {'status': 'NOT_VERIFIED'}
    # Git lists prerequisites separately from contained refs. An empty repository
    # can clone a self-contained bundle; additionally require verify's declaration.
    complete = (output / 'bundle-1.txt').is_file() and 'complete history' in (
        output / 'bundle-1.txt').read_text()
    report = {'schema': 'apm.history-migration-campaign.v1',
              'subject_commit': git_text(root, 'rev-parse', 'HEAD'),
              'subject_tree': git_text(root, 'rev-parse', 'HEAD^{tree}'),
              'status': 'PASS' if checks['original_history']['status'] == 'PASS'
                  and len(exports) == 13 and all(x['status'] == 'PASS' for x in exports)
                  and len(executions) == 3 and all(x['returncode'] == 0 for x in executions)
                  and complete and restoration['status'] == 'PASS' else 'FAIL',
              'checks': checks, 'exports': exports, 'executions': executions,
              'bundle_sha256': hashlib.sha256(bundle.read_bytes()).hexdigest() if bundle.is_file() else None,
              'self_contained': complete, 'offline_restoration': restoration,
              'limits': 'Only committed source/evidence and Git objects; ignored raw runs and external tools are not backed up.'}
    (output / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = campaign(ROOT, args.output.resolve())
    print(json.dumps({'status': result['status'], 'report': str(args.output / 'report.json')}))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
