# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
import json

import pytest

from apm.campaign_support import inventory, verify_inventory
from apm.compatibility import noise_names, physical_files


@pytest.mark.parametrize('fault', ['changed', 'missing', 'extra', 'symlink'])
def test_raw_inventory_rejects_damage_and_unlisted_files(tmp_path, fault):
    folder = tmp_path / 'raw'
    folder.mkdir()
    file = folder / 'terminal.txt'
    file.write_text('1.0 2.0\n')
    record = tmp_path / 'inventory.json'
    inventory(folder, record)
    assert verify_inventory(record)
    if fault == 'changed':
        file.write_text('1.0 2.1\n')
    elif fault == 'missing':
        file.unlink()
    elif fault == 'extra':
        (folder / 'unlisted.txt').write_text('extra')
    else:
        copy = tmp_path / 'elsewhere'
        copy.write_bytes(file.read_bytes())
        file.unlink()
        file.symlink_to(copy)
    assert not verify_inventory(record)


def test_physical_comparison_keeps_exact_numbers_and_method_model_hashes(tmp_path):
    a, b = tmp_path / 'old', tmp_path / 'new'
    for folder in (a, b):
        folder.mkdir()
        (folder / 'device.csv').write_text('idmag_a,method,model_sha256\n1.0,terminal-fd,abc\n')
    assert physical_files(a, []) == physical_files(b, [])
    (b / 'device.csv').write_text('idmag_a,method,model_sha256\n1.00000000001,terminal-fd,abc\n')
    assert physical_files(a, []) != physical_files(b, [])
    (b / 'device.csv').write_text('idmag_a,method,model_sha256\n1.0,terminal-fd,changed\n')
    assert physical_files(a, []) != physical_files(b, [])


def test_noise_request_identity_excludes_only_code_identity(tmp_path):
    row = {'request_id': 'n2-old', 'request_hash': 'old', 'memberships': [],
           'request': {'implementation_code_sha256': 'old-code', 'model_sha256': 'model',
                       'method_id': 'method', 'seed': 42, 'reference_tool_hashes': {'ngspice': 'tool'}}}
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps({'requests': [row]}))
    _, expected = noise_names(tmp_path)
    row['request']['implementation_code_sha256'] = 'current-code'
    path.write_text(json.dumps({'requests': [row]}))
    assert noise_names(tmp_path)[1] == expected
    for key in ('model_sha256', 'method_id', 'seed', 'reference_tool_hashes'):
        original = row['request'][key]
        row['request'][key] = 'wrong'
        path.write_text(json.dumps({'requests': [row]}))
        assert noise_names(tmp_path)[1] != expected
        row['request'][key] = original
