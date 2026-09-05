# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Observed compiler provenance. A configured pin is never an observation."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

EXPECTED_COMMIT = 'fdf2522b70f42793f64b1c72f0195c96dea0cc19'
SCHEMA = 'apm.compiler-build-receipt.v1'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def source_state(source: Path) -> dict:
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()
    return {'commit': git('rev-parse', 'HEAD'), 'tree': git('rev-parse', 'HEAD^{tree}'),
            'dirty': git('status', '--porcelain', '--untracked-files=all'),
            'submodules': git('submodule', 'status', '--recursive')}


def build_compiler(source: Path, destination: Path, cargo: Path, llvm: Path,
                   environment: dict[str, str], jobs: int = 4) -> dict:
    """Build into a new target directory, then install exactly that output."""
    destination.mkdir(parents=True, exist_ok=False)
    before = source_state(source)
    if before['commit'] != EXPECTED_COMMIT or before['dirty'] or any(
            s.startswith(('-', '+', 'U')) for s in before['submodules'].splitlines()):
        raise ValueError('COMPILER_SOURCE_NOT_CLEAN_PIN')
    env = {**environment, 'CARGO_TARGET_DIR': str(destination / 'target')}
    command = [str(cargo), 'build', '--locked', '--release', '-p', 'openvaf-driver',
               '--features', 'llvm20', '-j', str(jobs)]
    observed_tools = {}
    for name, executable, flag in [('cargo', cargo, '-V'),
                                  ('rustc', Path(shutil.which('rustc', path=env['PATH'])), '-Vv'),
                                  ('llvm', llvm, '--version')]:
        observed_tools[name] = {'path': str(executable.resolve()), 'sha256': digest(executable),
            'version': subprocess.check_output([str(executable), flag], env=env, text=True).strip()}
    configuration = {'command': command, 'cwd': str(source.resolve()), 'tools': observed_tools,
        'environment': {k: env.get(k) for k in ('RUSTUP_HOME', 'CARGO_HOME', 'RUSTFLAGS',
            'LLVM_SYS_201_PREFIX', 'LD_LIBRARY_PATH', 'PATH', 'CARGO_TARGET_DIR')},
        'platform': platform.platform()}
    (destination / 'configuration.json').write_text(json.dumps(configuration, indent=2)+'\n')
    with (destination / 'build.log').open('w') as log:
        result = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=log, check=False)
    after = source_state(source)
    if result.returncode or after != before:
        raise ValueError('COMPILER_BUILD_FAILED_OR_SOURCE_DRIFT')
    binary = destination / 'bin/openvaf-r'
    binary.parent.mkdir()
    shutil.copy2(destination / 'target/release/openvaf-r', binary)
    receipt = {'schema': SCHEMA, 'source_path': str(source.resolve()), 'before': before,
               'after': after, 'binary_sha256': digest(binary), 'configuration': configuration,
               'configuration_sha256': digest(destination/'configuration.json'),
               'build_log_sha256': digest(destination/'build.log'), 'returncode': 0}
    receipt['receipt_id'] = identity(receipt)
    (destination/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def observe_compiler(binary: Path, receipt_path: Path | None = None) -> dict:
    configured = os.environ.get('APM_OPENVAF_RECEIPT')
    path = receipt_path or (Path(configured) if configured else binary.parent.parent/'receipt.json')
    result = {'expected_commit': EXPECTED_COMMIT, 'binary_sha256': digest(binary),
              'receipt_path': str(path), 'status': 'UNVERIFIED', 'errors': []}
    try:
        receipt = json.loads(path.read_text())
        seal = receipt.pop('receipt_id')
        checks = {'schema': receipt['schema'] == SCHEMA, 'seal': identity(receipt) == seal,
                  'binary': receipt['binary_sha256'] == result['binary_sha256'],
                  'clean_pin': receipt['before']['commit'] == EXPECTED_COMMIT
                    and not receipt['before']['dirty'],
                  'source_unchanged': receipt['before'] == receipt['after']
                    == source_state(Path(receipt['source_path'])),
                  'configuration': digest(path.parent/'configuration.json') == receipt['configuration_sha256'],
                  'log': digest(path.parent/'build.log') == receipt['build_log_sha256'],
                  'build_succeeded': receipt['returncode'] == 0}
        result.update(receipt_sha256=digest(path), observed_commit=receipt['before']['commit'],
                      checks=checks)
        result['errors'] = [k for k, v in checks.items() if not v]
        if not result['errors']:
            result['status'] = 'VERIFIED'
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        result['errors'].append(str(error))
    return result
