# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Current maintainer and bounded product checks. Historical execution is separate."""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from .catalog import load_catalog
from .history import verify_assets, verify_history
from .lifecycle import (
    ValidationError,
    load_contract,
    package_identity,
    source_identity,
    write_report,
)
from .paths import repository_root, state_directory
from .provenance_validate import validate_provenance
from .spectre_validate import validate_spectre
from .validation_support import _check_map, _run_logged_command, audit_distribution, audit_migration


def audit_current_guidance(root):
    try:
        contract = load_contract(root)
        checks = {
            'selected_mission': 'docs/maintainers/v6-plan.md' in (root / 'GOAL.md').read_text(),
            'history_routing': 'releases/index.toml' in (root / 'AGENTS.md').read_text(),
            'approval_boundary': contract['create_tag_authorized'] is False
                and contract['publish_release_authorized'] is False,
            'current_critical_references': all((root / p).is_file() for p in (
                'README.md', 'ENVIRONMENT.md', 'CONTRIBUTING.md', 'THIRD_PARTY.md',
                'DEVICE_FAMILY_MODEL.md', 'RESULT_CONTRACT.md', 'APM045_POSITIONING.md')),
        }
        return _check_map(checks, context='current routing and designated approval boundary')
    except (OSError, KeyError, ValueError, ValidationError) as error:
        return {'status': 'fail', 'error': str(error)}


def audit_architecture(root):
    import ast
    historical = {'release_validate', 'release_validate_v4', 'release_validate_v5',
                  'clean_clone', 'clean_clone_v4', 'clean_clone_v5'}
    imports = []
    for path in sorted((root / 'src/apm').glob('*.py')):
        if path.stem in historical:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                if set(node.module.split('.')) & historical:
                    imports.append({'path': str(path.relative_to(root)), 'module': node.module})
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if set(alias.name.split('.')) & historical:
                        imports.append({'path': str(path.relative_to(root)), 'module': alias.name})
    discovery = (root / 'src/apm/paths.py').read_text()
    checks = {'no_historical_imports': not imports,
              'project_discovery_uses_current_identity': 'release_gates' not in discovery
                  and 'pyproject.toml' in discovery and 'analog-process-models' in discovery}
    return {**_check_map(checks, context='current imports and root discovery'), 'imports': imports}


def validate_maintenance_repository(output=None, *, root=None, scope='current'):
    root = (root or repository_root()).resolve()
    if scope not in ('current', 'product'):
        raise ValidationError('UNKNOWN_VALIDATION_SCOPE')
    destination = (output or state_directory(root) / 'validation' /
                   datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')).resolve()
    if destination.exists() or destination.is_symlink():
        raise ValidationError('VALIDATION_OUTPUT_OCCUPIED: choose a new directory')
    destination.mkdir(parents=True)
    results = {}

    def component(name, function):
        try:
            result = function()
        except Exception as error:  # noqa: BLE001 - retain failures and finish independent checks
            result = {'status': 'FAIL', 'error': str(error)}
        results[name] = result
        return result

    component('assets', lambda: verify_assets(root))
    component('identity', lambda: package_identity(root))
    catalog = component('catalog', lambda: {'status': 'PASS', 'snapshot': load_catalog(root).snapshot()})
    if catalog.get('status') == 'PASS':
        families = sum(len(t.families) for t in load_catalog(root).technologies)
        devices = sum(len(f.devices) for t in load_catalog(root).technologies for f in t.families)
        catalog['status'] = 'PASS' if families == 15 and devices == 30 else 'FAIL'
        catalog.update(families=families, devices=devices)
    unavailable = []
    if scope == 'current':
        component('history', lambda: verify_history(root))
        component('guidance', lambda: audit_current_guidance(root))
        component('architecture', lambda: audit_architecture(root))
        component('distribution', lambda: audit_distribution(root))
        component('migration', lambda: audit_migration(root))
        component('provenance', lambda: validate_provenance(destination / 'provenance', root=root))
        component('spectre', lambda: validate_spectre(destination / 'spectre', root=root))
        for name, command in (
            ('pytest', [sys.executable, '-m', 'pytest', '-q', '--junitxml=' + str(destination / 'pytest.xml')]),
            ('ruff', [sys.executable, '-m', 'ruff', 'check', '.']),
            ('reuse', [sys.executable, '-m', 'reuse', 'lint']),
        ):
            component(name, lambda name=name, command=command:
                      _run_logged_command(root, destination, name, command))
        # Exit zero with skipped/empty tests does not establish required coverage.
        pytest = results['pytest']
        try:
            import xml.etree.ElementTree as ET
            suites = list(ET.parse(destination / 'pytest.xml').getroot().iter('testsuite'))
            pytest['coverage_complete'] = bool(suites) and sum(int(s.get('tests', '0')) for s in suites) > 0
            pytest['coverage_complete'] &= all(int(s.get(k, '0')) == 0
                                               for s in suites for k in ('skipped', 'errors', 'failures'))
            if not pytest['coverage_complete']:
                pytest['status'] = 'fail'
        except (OSError, ValueError, ET.ParseError) as error:
            pytest.update(status='fail', error=str(error))
        unavailable = [k for k, v in results.items() if v.get('status') == 'NOT_VERIFIED']
    else:
        unavailable = ['history (not requested)', 'maintainer tests/lint/distribution (not requested)',
                       'real-tool simulation (separate command, not requested)']
    accepted = {'PASS', 'pass', 'structurally_checked'}
    passed = bool(results) and all(r.get('status') in accepted for r in results.values())
    report = {'schema': 'apm.current-validation.v1', 'status': 'PASS' if passed else 'FAIL',
              'scope': scope, 'qualification_claim': 'current source checks; no release qualification',
              'results': results, 'unavailable_or_unrequested': unavailable,
              'real_tool_regressions': 'separate explicit checks; not implied by this report',
              'source': source_identity(root), 'output_directory': str(destination)}
    write_report(destination / 'report.json', report)
    if not passed:
        raise ValidationError(f'CURRENT_VALIDATION_FAILED: see {destination / "report.json"}')
    return {**report, 'report_path': str(destination / 'report.json')}
