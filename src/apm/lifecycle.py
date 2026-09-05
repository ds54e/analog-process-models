# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Current package phase and release contract; no historical validator imports."""
from __future__ import annotations

import json
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from . import __version__
from .history import HistoryError, digest, git_text, tomllib

GROUPS = {
    'identity.lifecycle': ['identity.package', 'identity.phase', 'identity.source'],
    'preservation.history': ['history.remote', 'history.objects', 'history.selector_coverage',
                             'history.exports', 'history.bundle', 'history.original_execution'],
    'preservation.current_assets': ['assets.bytes_modes', 'assets.provenance', 'assets.notice_closure'],
    'architecture.dependencies': ['architecture.imports', 'architecture.discovery',
                                  'architecture.io_closure', 'architecture.check_mapping'],
    'docs.usability': ['docs.links_claims'] + [f'journey.J{i}' for i in range(1, 11)],
    'compatibility.science': ['compat.baseline_physical', 'compat.latents_replay',
                              'electrical.all_families', 'variation.benchmark', 'variation.native',
                              'noise.method', 'noise.catalog', 'research.plan', 'research.sampler',
                              'research.mapping', 'research.statistics', 'research.circuits',
                              'research.replay_charge', 'research.io'],
    'validation.fail_closed': ['negative.history', 'negative.reconstruction', 'negative.lifecycle',
                               'negative.evidence', 'negative.runtime'],
    'environment.reproducibility': ['environment.cold', 'environment.warm', 'environment.tools'],
    'quality.current': ['quality.pytest', 'quality.ruff', 'quality.reuse',
                        'quality.public_hygiene', 'quality.install'],
    'release.clean_candidate': ['release.clone', 'release.clean_tree', 'release.evidence_binding'],
}
EXACT_CHECKS = ['tag.annotated_identity', 'tag.approved_candidate', 'tag.fresh_full_rerun']


class ValidationError(RuntimeError):
    """A requested current check could not be completed successfully."""


def load_contract(root):
    data = tomllib.loads((root / 'validation/acceptance.toml').read_text())
    definitions = data.get('gate', [])
    expected = {**GROUPS, 'release.exact_tag_requalification': EXACT_CHECKS}
    actual = {g['id']: g for g in definitions}
    if (data.get('schema') != 'apm.acceptance.v1' or len(actual) != len(definitions)
            or set(actual) != set(expected)
            or any(g.get('required') is not True or g.get('checks') != expected[k]
                   or g.get('phase') != ('exact-tag' if k.startswith('release.exact') else 'candidate')
                   for k, g in actual.items())):
        raise ValidationError('REQUIRED_CHECK_INVENTORY_DRIFT')
    if data.get('phase') not in ('implementation', 'candidate', 'published'):
        raise ValidationError('INVALID_LIFECYCLE_PHASE')
    return data


def package_identity(root):
    try:
        contract = load_contract(root)
        phase = contract['phase']
        expected = contract[{'implementation': 'implementation_version',
                             'candidate': 'candidate_version',
                             'published': 'maintenance_version'}[phase]]
        project = tomllib.loads((root / 'pyproject.toml').read_text())['project']
        installed = metadata.version('analog-process-models')
        cli = subprocess.run([sys.executable, '-m', 'apm.cli', '--version'], cwd=root,
                             text=True, capture_output=True, check=False)
        checks = {
            'phase_version': expected == project['version'] == __version__ == installed,
            'cli_version': cli.returncode == 0 and cli.stdout.strip() == 'APM ' + expected,
            'selected_source': Path(__file__).resolve() == (root / 'src/apm/lifecycle.py').resolve(),
            'project_identity': project['name'] == 'analog-process-models',
        }
        return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
                'phase': phase, 'version': project['version'], 'runtime_version': __version__,
                'installed_version': installed, 'cli_version': cli.stdout.strip(),
                'acceptance_sha256': digest((root / 'validation/acceptance.toml').read_bytes())}
    except (OSError, KeyError, ValueError, metadata.PackageNotFoundError, ValidationError) as error:
        return {'status': 'FAIL', 'error': str(error)}


def source_identity(root):
    try:
        if not (root / '.git').exists():
            raise HistoryError('MISSING_HISTORY')
        return {'status': 'PASS', 'commit': git_text(root, 'rev-parse', 'HEAD'),
                'tree': git_text(root, 'rev-parse', 'HEAD^{tree}'),
                'clean': not git_text(root, 'status', '--porcelain', '--untracked-files=all')}
    except HistoryError as error:
        return {'status': 'NOT_VERIFIED', 'error': str(error)}


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return {**report, 'report_path': str(path)}
