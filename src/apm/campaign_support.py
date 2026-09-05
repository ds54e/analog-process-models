# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Small outer-campaign receipts, file inventories and subprocess execution."""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .compiler_provenance import digest
from .lifecycle import write_report


def read(path):
    return json.loads(Path(path).read_text())


def run(root, output, name, command, *, env=None, timeout=86400):
    output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    tick = time.monotonic()
    stdout, stderr = output / (name + '.stdout'), output / (name + '.stderr')
    if stdout.exists() or stderr.exists():
        raise FileExistsError('EXECUTION_RECEIPT_OCCUPIED: ' + name)
    with stdout.open('w') as out, stderr.open('w') as err:
        try:
            proc = subprocess.run(command, cwd=root, stdout=out, stderr=err, check=False,
                                  timeout=timeout, env={**os.environ, **(env or {})})
            code, error = proc.returncode, None
        except subprocess.TimeoutExpired as exc:
            code, error = None, str(exc)
    result = {'command': command, 'cwd': str(root), 'started_utc': started,
              'completed_utc': datetime.now(timezone.utc).isoformat(),
              'seconds': time.monotonic() - tick, 'returncode': code, 'error': error,
              'stdout': str(stdout), 'stderr': str(stderr),
              'stdout_sha256': digest(stdout), 'stderr_sha256': digest(stderr),
              'status': 'PASS' if code == 0 else 'FAIL'}
    write_report(output / (name + '.json'), result)
    print(f'{name}: {result["status"]} ({result["seconds"]:.1f}s)', flush=True)
    return result


def inventory(folder, destination):
    """Bind every raw file; never follow links to someone else's generated state."""
    files = []
    for path in sorted(folder.rglob('*')):
        if path.is_symlink():
            raise ValueError('RAW_STATE_SYMLINK: ' + str(path))
        if path.is_file() and path != destination:
            files.append({'path': str(path), 'size': path.stat().st_size, 'sha256': digest(path)})
    return write_report(destination, {'schema': 'apm.raw-inventory.v1',
                                      'files': files, 'count': len(files)})


def verify_inventory(path):
    data = read(path)
    files = data['files']
    return bool(files) and len(files) == data['count'] == len({x['path'] for x in files}) and all(
        Path(x['path']).is_file() and Path(x['path']).stat().st_size == x['size']
        and digest(Path(x['path'])) == x['sha256'] for x in files)


def pytest_coverage(path):
    import xml.etree.ElementTree as ET
    document = ET.parse(path).getroot()
    cases = list(document.iter('testcase'))
    failed = [c.attrib for c in cases if len(c)]
    return {'status': 'PASS' if cases and not failed else 'FAIL', 'count': len(cases),
            'failed_or_skipped': failed,
            'cases': [c.attrib for c in cases]}
