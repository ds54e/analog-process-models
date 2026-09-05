# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import pytest

from apm import paths

ROOT = Path(__file__).resolve().parents[1]


def fixture_root(path):
    (path / 'src/apm').mkdir(parents=True)
    (path / 'src/apm/__init__.py').write_text('')
    (path / 'pyproject.toml').write_text('[project]\nname="analog-process-models"\n')
    (path / 'models/example').mkdir(parents=True)
    (path / 'models/example/technology.toml').write_text('')
    (path / 'variation').mkdir()
    (path / 'variation/benchmark_v2.toml').write_text('')
    return path


def test_explicit_root_precedes_cwd_and_installed_source(tmp_path, monkeypatch):
    selected = fixture_root(tmp_path / 'chosen')
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv('APM_REPO_ROOT', str(selected))
    assert paths.repository_root() == selected
    assert not (selected / '.git').exists()
    assert paths.state_directory() == selected / '.apm'
    monkeypatch.setenv('APM_STATE_DIR', str(tmp_path / 'selected-state'))
    assert paths.state_directory() == tmp_path / 'selected-state'


@pytest.mark.parametrize('value', ['', 'missing', 'wrong-project'])
def test_invalid_explicit_root_never_falls_back(tmp_path, monkeypatch, value):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv('APM_REPO_ROOT', str(tmp_path / value) if value else '')
    with pytest.raises(RuntimeError, match='APM_REPO_ROOT is not an APM checkout'):
        paths.repository_root()


def test_cwd_ancestry_then_installed_source_without_historical_markers(tmp_path, monkeypatch):
    selected = fixture_root(tmp_path / 'selected')
    child = selected / 'examples/nested'
    child.mkdir(parents=True)
    monkeypatch.delenv('APM_REPO_ROOT', raising=False)
    monkeypatch.chdir(child)
    assert paths.repository_root() == selected
    monkeypatch.chdir(tmp_path)
    assert paths.repository_root() == ROOT
