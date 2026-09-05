# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from apm import history

ROOT = Path(__file__).resolve().parents[1]


def test_baseline_scope_and_history_are_independently_exact():
    result = history.verify_history(ROOT)
    assert result['status'] == 'PASS', result
    inv = history.inventory(ROOT)
    assert {k: len(v['entries']) for k, v in inv['frozen_scopes'].items()} == {
        'preflight': 13, 'released_inputs': 161, 'v4': 52, 'v5': 30}
    assert history.verify_assets(ROOT)['status'] == 'PASS'
    retained = {a['path'] for a in inv['artifacts'] if a['action'] == 'retain_exact'}
    assert {'validation/evidence/v5_source_decision.md',
            'variation/research/apm045/derived/hart_tsmc40_profile.json',
            'LICENSES/CC-BY-4.0.txt'} <= retained


@pytest.mark.parametrize('fault', ['missing', 'moved_tag', 'wrong_tree', 'shallow', 'grafts'])
def test_history_failure_is_not_pass(monkeypatch, fault):
    original = history.git_text

    def altered(root, *args):
        if fault == 'missing' and args[:1] == ('cat-file',):
            raise history.HistoryError('MISSING_HISTORY: missing object')
        if fault == 'moved_tag' and args == ('rev-parse', 'refs/tags/v5.0.0'):
            return '0' * 40
        if fault == 'wrong_tree' and args == ('rev-parse', history.BASELINE + '^{tree}'):
            return '0' * 40
        if fault == 'shallow' and args == ('rev-parse', '--is-shallow-repository'):
            return 'true'
        if fault == 'grafts' and args == ('rev-parse', '--git-path', 'info/grafts'):
            return str(ROOT / 'README.md')
        return original(root, *args)

    monkeypatch.setattr(history, 'git_text', altered)
    result = history.verify_history(ROOT)
    assert result['status'] != 'PASS', result
    if fault in ('missing', 'shallow', 'grafts'):
        assert 'MISSING_HISTORY' in result.get('error', '') or 'GRAFTS_UNSUPPORTED' in result.get('error', '')


def test_no_git_does_not_discover_parent_checkout(tmp_path):
    result = history.verify_history(tmp_path)
    assert result['status'] == 'NOT_VERIFIED'
    assert 'MISSING_HISTORY' in result['error']


@pytest.mark.parametrize('field', ['tag_object', 'source', 'evidence'])
def test_registry_cannot_reanchor_to_observed_drift(tmp_path, field):
    (tmp_path / 'releases').mkdir()
    text = (ROOT / 'releases/index.toml').read_text()
    old = history.load_index(ROOT)['legacy'][-1]
    value = old[field] if field == 'tag_object' else old[field]['commit']
    (tmp_path / 'releases/index.toml').write_text(text.replace(value, '0' * 40))
    with pytest.raises(history.HistoryError, match='REGISTRY_DRIFT'):
        history.load_index(tmp_path)


def test_tampered_inventory_cannot_be_resealed(tmp_path):
    (tmp_path / 'releases').mkdir()
    (tmp_path / 'releases/index.toml').write_bytes((ROOT / 'releases/index.toml').read_bytes())
    inv = copy.deepcopy(history.inventory(ROOT))
    inv['artifacts'].pop()
    (tmp_path / 'releases/migration-v6.json').write_text(json.dumps(inv))
    with pytest.raises(history.HistoryError, match='INVENTORY_DRIFT'):
        history.inventory(tmp_path)


@pytest.mark.parametrize('path', ['../escape', '/absolute', '.git/config', 'a/../../escape',
                                'a\\escape', './file', 'a//file'])
def test_unsafe_export_paths_rejected_before_writing(path):
    with pytest.raises(history.HistoryError, match='UNSAFE_EXPORT_PATH'):
        history.safe_inventory({path: {'mode': '100644', 'kind': 'blob', 'blob': '0' * 40}})


def test_symlink_child_export_rejected():
    with pytest.raises(history.HistoryError, match='UNSAFE_EXPORT_PATH'):
        history.safe_inventory({'link': {'mode': '120000', 'kind': 'blob'},
                                'link/file': {'mode': '100644', 'kind': 'blob'}})


def test_export_collision_does_not_touch_destination(tmp_path):
    sentinel = tmp_path / 'sentinel'
    sentinel.write_text('preserve')
    with pytest.raises(history.HistoryError, match='DESTINATION_OCCUPIED'):
        history.export_tree(ROOT, 'v5.0.0', 'source', tmp_path)
    assert sentinel.read_text() == 'preserve'


def test_export_is_exact_and_detects_byte_mode_inventory_tampering(tmp_path):
    destination = tmp_path / 'v5'
    result = history.export_tree(ROOT, 'v5.0.0', 'source', destination)
    assert result['status'] == 'PASS'
    assert not (destination / '.git').exists()
    source = result['commit']
    file = destination / 'README.md'
    original = file.read_bytes()
    file.write_bytes(original + b'\n')
    assert 'README.md' in history.verify_export(ROOT, source, destination)['mismatches']
    file.write_bytes(original)
    file.chmod(0o755)
    assert 'README.md' in history.verify_export(ROOT, source, destination)['mismatches']
    file.chmod(0o644)
    (destination / 'extra').write_text('unexpected')
    assert 'extra' in history.verify_export(ROOT, source, destination)['mismatches']


def test_retained_asset_hash_and_mode_drift_fail(monkeypatch):
    original = history.worktree_bytes
    target = ROOT / 'validation/evidence/v5_source_decision.md'
    monkeypatch.setattr(history, 'worktree_bytes',
                        lambda p: b'changed decision' if p == target else original(p))
    result = history.verify_assets(ROOT)
    assert result['status'] == 'FAIL'
    assert 'validation/evidence/v5_source_decision.md' in result['mismatches']
