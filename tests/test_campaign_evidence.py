# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
import json
import sys

import pytest

from apm.campaign_support import inventory, verify_inventory
from apm.compatibility import noise_names, physical_files


@pytest.mark.parametrize('failed_step', ['clone', 'baseline-checkout'])
def test_comparison_stops_dependent_work_after_failed_process(tmp_path, monkeypatch, failed_step):
    from apm import campaign_support, compatibility

    root = tmp_path / 'source'
    (root / 'tools').mkdir(parents=True)
    (root / 'tools/compatibility_probe.py').write_text('# fixture\n')
    attempted = []

    def execute(root, output, name, command, **kwargs):
        assert failed_step not in attempted, 'Dependent work ran after a failed prerequisite'
        attempted.append(name)
        if name == failed_step:
            return campaign_support.run(root, output, name, [sys.executable, '-c', 'raise SystemExit(7)'])
        (tmp_path / 'comparison/fixed-input-source').mkdir(parents=True)
        return {'returncode': 0, 'status': 'PASS'}

    monkeypatch.setattr(compatibility, 'git_text', lambda *args: 'a' * 40)
    monkeypatch.setattr(compatibility, 'run', execute)
    with pytest.raises(RuntimeError, match='COMPARISON_EXECUTION_FAILED: ' + failed_step):
        compatibility.execute_comparison(root, tmp_path / 'comparison')
    receipt = json.loads((tmp_path / 'comparison/executions' / (failed_step + '.json')).read_text())
    assert receipt['returncode'] == 7 and receipt['status'] == 'FAIL'


def test_comparison_rejects_checkout_with_wrong_observed_commit(tmp_path, monkeypatch):
    from apm import compatibility

    root = tmp_path / 'source'
    (root / 'tools').mkdir(parents=True)
    (root / 'tools/compatibility_probe.py').write_text('# fixture\n')
    attempted = []

    def execute(root, output, name, command, **kwargs):
        attempted.append(name)
        assert name in ('clone', 'baseline-checkout'), 'Installed or executed the wrong source'
        return {'returncode': 0, 'status': 'PASS'}

    monkeypatch.setattr(compatibility, 'git_text', lambda *args: 'a' * 40)
    monkeypatch.setattr(compatibility, 'run', execute)
    with pytest.raises(RuntimeError, match='COMPARISON_SOURCE_IDENTITY_DRIFT'):
        compatibility.execute_comparison(root, tmp_path / 'comparison')
    assert attempted == ['clone', 'baseline-checkout']


@pytest.mark.parametrize('status', ['validated', 'FAIL', 'NOT_VERIFIED'])
def test_equal_partial_regressions_cannot_pass_comparison(tmp_path, monkeypatch, status):
    from apm import compatibility
    from apm.compiler_provenance import digest

    for name in ('baseline', 'current'):
        stage = tmp_path / name / 'electrical'
        stage.mkdir(parents=True)
        (stage / 'report.json').write_text(json.dumps({'status': status}))
        (stage / 'terminal.csv').write_text('current_a\n1.0\n')
        research = tmp_path / name / 'research'
        research.mkdir()
        (research / 'realization.json').write_text(json.dumps({'devices': []}))
    legacy = tmp_path / 'baseline/research/realization.json'
    record = {'status': 'PASS', 'profile_sha256': 'same-profile', 'imported_modules': {},
              'runs': [{'arrays': [1.0], 'subject': {'tool': 'same-tool'}}] * 3,
              'saved_original_path': str(legacy), 'saved_original_sha256': digest(legacy),
              'saved_original_unchanged': True}
    for name in ('baseline', 'current'):
        (tmp_path / name / 'research/report.json').write_text(json.dumps(record))
    (tmp_path / 'source-identities.json').write_text(json.dumps({'current': 'a' * 40}))
    monkeypatch.setattr(compatibility, 'REGRESSIONS', {'electrical': 'characterization-check'})
    monkeypatch.setattr(compatibility, 'noise_names', lambda folder: ([('old-id', 'physical-id')], []))
    monkeypatch.setattr(compatibility.np, 'load', lambda path: [1.0])
    report = compatibility.compare_outputs(tmp_path)
    assert report['status'] == ('PASS' if status == 'validated' else 'FAIL')
    assert report['records'][0]['checks']['exact_physical_files'] is True


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
