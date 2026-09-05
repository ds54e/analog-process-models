# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Concrete current qualification. Independent failures remain visible and do not skip peers."""
from __future__ import annotations

import hashlib
import platform
import shutil
import sys
import traceback
from pathlib import Path

from .campaign_audits import docs_audit, migration_audit, original_execution
from .campaign_support import inventory, pytest_coverage, read, run, verify_inventory
from .candidate import audit_clone
from .catalog import load_catalog
from .compatibility import REGRESSIONS, execute_comparison
from .compiler_provenance import digest, observe_compiler
from .confirmation import audit_confirmation, audit_plan
from .history import load_index, tomllib, verify_assets, verify_history
from .journeys import execute_block, observations
from .lifecycle import load_contract, package_identity, source_identity, write_report
from .maintenance_validate import audit_architecture
from .release import record_check
from .research_charge import qualify_charge
from .toolchain import resolve_toolchain


def remote_identity(root, output):
    logs = output / 'remote'
    tags = run(root, logs, 'tags', ['git', 'ls-remote', '--tags', load_contract(root)['remote']])
    actual = {ref: obj for obj, ref in (line.split() for line in Path(tags['stdout']).read_text().splitlines())}
    expected = load_index(root)['legacy']
    objects = all(actual.get('refs/tags/' + r['tag']) == r['tag_object']
                  and actual.get('refs/tags/' + r['tag'] + '^{}') == r['source']['commit'] for r in expected)
    releases = run(root, logs, 'releases', ['gh', 'api', 'repos/ds54e/analog-process-models/releases'])
    projected = []
    for r in read(Path(releases['stdout'])):
        # Future releases do not redefine the pinned legacy release objects.
        if r['tag_name'] not in {x['tag'] for x in expected}:
            continue
        value = {k: r[k] for k in ('id', 'tag_name', 'target_commitish', 'name', 'draft', 'prerelease', 'created_at', 'published_at')}
        value['body_sha256'] = hashlib.sha256((r['body'] or '').encode()).hexdigest()
        value['assets'] = [{k: a[k] for k in ('id', 'name', 'size', 'created_at', 'updated_at', 'digest')} for a in r['assets']]
        projected.append(value)
    old = read(root / 'releases/remote-v6-baseline.json')['releases']
    checks = {'remote_tag_objects_and_commits': tags['returncode'] == 0 and objects,
              'legacy_release_objects_unchanged': releases['returncode'] == 0 and projected == old}
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'tag_objects': actual, 'release_objects': projected}


def tool_snapshot(root):
    tool = resolve_toolchain(root)
    return {'ngspice': {'path': str(tool.ngspice), 'sha256': digest(tool.ngspice)},
            'compiler': observe_compiler(tool.openvaf, environment=tool.environment())}


def execute_campaign(root, output, subject):
    results, outcomes = [], {}
    logs = output / 'executions'
    cli = [sys.executable, '-m', 'apm.cli']
    # Runs are deliberately sequential at the outer level; the preserved research
    # evaluator uses its declared bounded four workers and single-thread simulators.
    def attempt(name, function):
        try:
            result = function()
        except Exception as error:  # noqa: BLE001 - retain failure, continue independent work
            result = {'status': 'FAIL', 'error': str(error), 'traceback': traceback.format_exc()}
        if not isinstance(result, dict):
            result = {'status': 'FAIL', 'error': 'UNTYPED_COMPONENT_RESULT'}
        path = output / 'components' / (name + '.json')
        write_report(path, result)
        outcomes[name] = result
        return result

    def emit(identifier, checks, names, *, extra=()):
        paths = [output / 'components' / (n + '.json') for n in names]
        paths += list(extra)
        results.append(record_check(output, identifier, subject, checks, paths))

    def passed(name):
        return outcomes.get(name, {}).get('status') in ('PASS', 'pass', 'validated')

    attempt('identity', lambda: package_identity(root))
    attempt('source-start', lambda: source_identity(root))
    attempt('clone', lambda: audit_clone(root))
    attempt('history', lambda: verify_history(root))
    attempt('remote', lambda: remote_identity(root, output))
    attempt('assets', lambda: verify_assets(root))
    attempt('architecture', lambda: audit_architecture(root))
    attempt('migration', lambda: migration_audit(root, output / 'migration-detail.json'))
    attempt('docs', lambda: docs_audit(root))
    attempt('tools-before', lambda: tool_snapshot(root))
    prerequisites = {x: shutil.which(x) for x in ('git', 'python3', 'gcc', 'g++', 'autoconf',
                     'automake', 'bison', 'flex', 'make', 'curl', 'tar', 'cpio', 'rpm2cpio', 'sha256sum')}
    cold_absent = all(not (root / '.apm' / p).exists() for p in ('tutorial-cold', 'tutorial-python', 'tutorial-first-result'))
    os_release = Path('/etc/os-release').read_text()
    reference_host = platform.machine() == 'x86_64' and 'microsoft-standard-WSL2' in platform.release()
    reference_host &= any(line.startswith('VERSION_ID="9') for line in os_release.splitlines())
    reference_host &= any(word in os_release.lower() for word in ('rhel', 'almalinux', 'rocky', 'centos'))
    attempt('environment', lambda: {'status': 'PASS' if all(prerequisites.values()) and cold_absent and reference_host else 'FAIL',
                                   'prerequisites': prerequisites, 'cold_prefixes_absent': cold_absent,
                                   'reference_host': reference_host,
                                   'machine': platform.machine(), 'kernel': platform.release(),
                                   'os_release': os_release, 'python': sys.version})
    for name in ('discover', 'cold'):
        attempt(name, lambda name=name: execute_block(root, output / 'journeys', name)
                if name != 'cold' or cold_absent else {'status': 'FAIL', 'error': 'COLD_DESTINATION_OCCUPIED'})
    attempt('cold-doctor', lambda: read(root / '.apm/tutorial-cold/doctor/report.json'))
    attempt('build', lambda: run(root, logs, 'build', cli + ['build-models']))
    attempt('warm', lambda: execute_block(root, output / 'journeys', 'warm'))
    attempt('tools-after', lambda: tool_snapshot(root))
    # All named blocks are individually attempted even if a sibling fails.
    for name in ('nominal', 'characterize', 'noise', 'benchmark', 'native', 'research', 'history-example', 'snapshot'):
        block = 'history' if name == 'history-example' else name
        key = name + '-example' if name in ('benchmark', 'native') else name
        attempt(key, lambda block=block: execute_block(root, output / 'journeys', block))
    attempt('observations', lambda: {'status': 'PASS', **observations(root)})
    attempt('failures', lambda: execute_block(root, output / 'journeys', 'failures'))
    attempt('negative-runtime', lambda: read(root / '.apm/tutorial-failures/report.json'))
    attempt('current', lambda: read(root / '.apm/tutorial-current-validation/report.json'))
    attempt('pytest-coverage', lambda: pytest_coverage(root / '.apm/tutorial-current-validation/pytest.xml'))
    attempt('install', lambda: run(root, logs, 'pip-check', [sys.executable, '-m', 'pip', 'check']))
    attempt('doctor', lambda: run(root, logs, 'doctor', cli + ['doctor']))
    attempt('doctor-detail', lambda: read(root / '.apm/doctor/report.json'))
    attempt('history-campaign', lambda: run(root, logs, 'history-campaign',
            [sys.executable, str(root / 'tools/verify_history_migration.py'), '--output', str(output / 'archive')]))
    attempt('archive', lambda: read(output / 'archive/report.json'))
    attempt('original-execution', lambda: original_execution(root, output / 'original-execution'))

    for name, command in REGRESSIONS.items():
        attempt(name + '-execution', lambda name=name, command=command: run(root, logs, name,
            [sys.executable, str(root / 'tools/trace_current_command.py'), str(output / 'traces' / (name + '.json')),
             command, '--output', str(output / 'regressions' / name)]))
        attempt(name, lambda name=name: read(output / 'regressions' / name / 'report.json'))
    attempt('compatibility', lambda: execute_comparison(root, output / 'compatibility'))
    plan = tomllib.loads((root / 'validation/v5_confirmation_plan.toml').read_text())
    attempt('research-plan', lambda: audit_plan(plan))
    for stage in ('sampler', 'mapping', 'statistics', 'circuits', 'replay', 'io'):
        attempt('research-' + stage + '-execution', lambda stage=stage: run(root, logs, 'research-' + stage,
            cli + ['research', 'check', '--suite', stage, '--output', str(output / 'research')]))
        attempt('research-' + stage, lambda stage=stage: read(output / 'research' / stage / 'report.json'))
    attempt('charge', lambda: qualify_charge(resolve_toolchain(root).ngspice, output / 'research/replay', output / 'charge'))
    attempt('confirmation', lambda: audit_confirmation(root, output / 'research', plan, subject['subject_commit']))
    attempt('source-end', lambda: source_identity(root))

    emit('identity.package', {'coherent': passed('identity')}, ['identity'])
    emit('identity.phase', {'candidate': outcomes['identity'].get('phase') == 'candidate'}, ['identity'], extra=[root / 'validation/acceptance.toml'])
    emit('identity.source', {'exact_clean_source': passed('source-start') and outcomes['source-start'].get('clean') is True
                             and outcomes['source-start'].get('commit') == subject['subject_commit']
                             and outcomes['source-start'].get('tree') == subject['subject_tree']}, ['source-start'])
    emit('history.remote', {'immutable_remote': passed('remote')}, ['remote'], extra=[root / 'releases/remote-v6-baseline.json'])
    for identifier in ('history.objects', 'history.selector_coverage'):
        emit(identifier, {'exact_objects_scopes': passed('history')}, ['history'], extra=[root / 'releases/index.toml', root / 'releases/migration-v6.json'])
    emit('history.exports', {'all_13_exact_exports': passed('archive') and len(outcomes['archive'].get('exports', [])) == 13}, ['archive'])
    emit('history.bundle', {'self_contained_offline_restore': passed('archive') and outcomes['archive'].get('self_contained') is True}, ['archive'])
    emit('history.original_execution', {'original_packages_and_checks': passed('original-execution')}, ['original-execution'])
    current = outcomes['current'].get('results', {})
    for identifier, checks in (
        ('assets.bytes_modes', {'pinned_local_assets': passed('assets')}),
        ('assets.provenance', {'full_current_provenance': current.get('provenance', {}).get('status') in ('pass', 'validated')}),
        ('assets.notice_closure', {'distribution': current.get('distribution', {}).get('status') == 'pass',
                                 'reuse': current.get('reuse', {}).get('status') == 'pass'}),
    ):
        emit(identifier, checks, ['assets', 'current'])
    emit('architecture.imports', {'no_historical_dependency': passed('architecture')}, ['architecture'])
    emit('architecture.discovery', {'configured_no_git_use': passed('snapshot'), 'specific_wrong_root_failure': passed('negative-runtime')}, ['snapshot', 'negative-runtime'])
    def closure():
        traces = [read(output / 'traces' / (n + '.json')) for n in REGRESSIONS]
        retired = {r['path'] for r in read(root / 'releases/retired-v6.json')['artifacts']}
        reads = sorted({p for t in traces for p in t['reads']})
        checks = {'no_retired_file_reads': not set(reads) & retired,
                  'all_reads_locally_present': bool(reads) and all((root / p).is_file() for p in reads),
                  'local_current_imports': all(Path(p).is_relative_to(root / 'src/apm') for t in traces for p in t['modules'].values())}
        return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'read_paths': reads, 'traces': traces}
    attempt('closure', closure)
    emit('architecture.io_closure', {'runtime_closure': passed('closure'), 'source_notice_closure': current.get('provenance', {}).get('status') in ('pass', 'validated')}, ['closure', 'current'])
    emit('architecture.check_mapping', {'complete_mapping_and_helper_equivalence': passed('migration')}, ['migration'], extra=[root / 'releases/check-migration.json', root / 'releases/helper-migration.json'])
    emit('docs.links_claims', {'reviewed_links_claims': passed('docs')}, ['docs'], extra=[root / 'docs/maintainers/v6-editorial-review.md'])
    obs = outcomes['observations']
    j = {
        1: (['discover', 'docs'], {'catalog_and_review': passed('discover') and passed('docs') and len(load_catalog(root).technologies) == 5}),
        2: (['cold', 'environment', 'cold-doctor'], {'cold_executed': passed('cold') and passed('environment'),
                                                  'observed_cold_compiler': outcomes['cold-doctor'].get('reference_toolchain_status') == 'VERIFIED'}),
        3: (['warm', 'tools-before', 'tools-after', 'current'], {'warm_safe': passed('warm') and passed('current') and outcomes['tools-before'] == outcomes['tools-after']}),
        4: (['nominal', 'observations'], {'both_nominal_circuits': passed('nominal') and len(obs.get('nominal', {})) == 2
                                      and all(r['finite'] and r['points'] >= 100 for r in obs.get('nominal', {}).values())}),
        5: (['characterize', 'noise', 'observations'], {'commands': passed('characterize') and passed('noise'),
             'physical_interpretation': obs.get('electrical', {}).get('finite_difference_gm') is True
                and obs.get('noise', {}).get('complex_transfer_identity') is True}),
        6: (['benchmark-example', 'native-example', 'research', 'observations'], {'three_distinct_flows': all(passed(n) for n in ('benchmark-example', 'native-example', 'research'))
                                                              and obs.get('variation', {}).get('research') == 'RESOLVED'}),
        7: (['observations', 'compatibility'], {'same_physical_device': obs.get('replay', {}).get('all_same_and_stable') is True
                                              and outcomes['compatibility'].get('replay_status') == 'PASS'}),
        8: (['negative-runtime'], {'six_specific_failures_safe': passed('negative-runtime')}),
        9: (['history-example', 'history', 'source-end'], {'verified_export_clean': passed('history-example') and passed('history')
                                                       and outcomes['source-end'].get('clean') is True}),
        10: (['snapshot'], {'ordinary_no_git_use_and_missing_history': passed('snapshot')}),
    }
    for number, (names, checks) in j.items():
        emit(f'journey.J{number}', checks, names)
    for identifier, name in (('compat.baseline_physical', 'physical_status'), ('compat.latents_replay', 'replay_status')):
        emit(identifier, {'exact_comparison': outcomes['compatibility'].get(name) == 'PASS'}, ['compatibility'])
    for identifier, name in (('electrical.all_families', 'electrical'), ('variation.benchmark', 'benchmark'),
                             ('variation.native', 'native'), ('noise.method', 'noise_method'), ('noise.catalog', 'noise_catalog')):
        emit(identifier, {'executed_required_coverage': passed(name) and passed(name + '-execution')}, [name, name + '-execution'])
    emit('research.plan', {'preserved_declared_plan': passed('research-plan') and passed('assets')}, ['research-plan', 'assets'], extra=[root / 'validation/v5_confirmation_plan.toml'])
    audit = outcomes['confirmation'].get('checks', {})
    for identifier, name, predicates in (
        ('research.sampler', 'sampler', ('sampling', 'sampler_raw_integrity')),
        ('research.mapping', 'mapping', ('mapping', 'methods', 'tail', 'application', 'mapping_raw_integrity')),
        ('research.statistics', 'statistics', ('statistics', 'statistics_raw_integrity', 'cross_bias_regions')),
        ('research.circuits', 'circuits', ('circuits', 'circuits_raw_integrity')),
        ('research.replay_charge', 'replay', ('replay', 'replay_raw_integrity')),
        ('research.io', 'io', ('io', 'io_raw_integrity')),
    ):
        checks = {k: audit.get(k) is True for k in predicates}
        checks['actual_stage_execution'] = passed('research-' + name + '-execution') and passed('research-' + name)
        if name == 'replay':
            checks['terminal_charge'] = passed('charge')
        emit(identifier, checks, ['confirmation', 'research-' + name, 'research-' + name + '-execution', 'charge'] if name == 'replay'
             else ['confirmation', 'research-' + name, 'research-' + name + '-execution'])
    coverage = outcomes['pytest-coverage']
    for identifier, module in (('negative.history', 'test_history'), ('negative.reconstruction', 'test_history'),
                               ('negative.lifecycle', 'test_lifecycle'), ('negative.evidence', 'test_lifecycle'),
                               ('negative.runtime', 'test_research')):
        cases = [c for c in coverage.get('cases', []) if c['classname'].endswith(module)]
        emit(identifier, {'no_skips_or_failures': passed('pytest-coverage'), 'executed_negative_suite': len(cases) >= 10,
                          'runtime_failures_observed': passed('negative-runtime')}, ['pytest-coverage', 'negative-runtime'])
    emit('environment.cold', {'empty_prefix_actual_bootstrap': passed('cold') and passed('environment'),
                              'fresh_compiler_verified': outcomes['cold-doctor'].get('reference_toolchain_status') == 'VERIFIED',
                              'fresh_ngspice': str(root / '.apm/tutorial-cold/') in outcomes['cold-doctor'].get('ngspice_path', '')},
         ['cold', 'environment', 'cold-doctor'])
    emit('environment.warm', {'actual_reuse': passed('warm'), 'unchanged_observed_compiler': outcomes['tools-before'] == outcomes['tools-after']}, ['warm', 'tools-before', 'tools-after'])
    emit('environment.tools', {'actual_smoke': passed('doctor') and passed('doctor-detail'),
                               'compiler_verified': outcomes['doctor-detail'].get('reference_toolchain_status') == 'VERIFIED'}, ['doctor', 'doctor-detail', 'tools-after'])
    emit('quality.pytest', {'current_tests_no_skips': passed('pytest-coverage')}, ['current', 'pytest-coverage'])
    for name in ('ruff', 'reuse'):
        emit('quality.' + name, {'actual_check': current.get(name, {}).get('status') == 'pass'}, ['current'])
    emit('quality.public_hygiene', {'distribution_audit': current.get('distribution', {}).get('status') == 'pass'}, ['current'])
    emit('quality.install', {'fresh_install_and_dependency_check': passed('install') and passed('identity') and passed('warm')}, ['install', 'identity', 'warm'])
    emit('release.clone', {'independently_fresh_authoritative_clone': passed('clone')}, ['clone'])
    emit('release.clean_tree', {'same_clean_commit_tree': outcomes['source-start'] == outcomes['source-end']
                               and outcomes['source-end'].get('clean') is True}, ['source-start', 'source-end'])
    # Bind raw execution evidence after all writers finish, excluding the exact
    # source copies/tool installations (separately hashed by history/build checks).
    manifests = []
    for name in ('research', 'charge', 'regressions', 'journeys', 'executions', 'negative-runtime', 'traces',
                 'archive', 'original-execution', 'compatibility'):
        folder = output / name
        if folder.is_dir():
            path = output / ('raw-' + name + '.json')
            inventory(folder, path)
            manifests.append(path)
    for folder in sorted((root / '.apm').glob('tutorial-*')):
        if folder.is_dir() and folder.name not in ('tutorial-cold', 'tutorial-python'):
            path = output / ('raw-' + folder.name + '.json')
            inventory(folder, path)
            manifests.append(path)
    raw_valid = bool(manifests) and all(verify_inventory(p) for p in manifests)
    links_valid = all(digest(Path(r['path'])) == r['sha256']
                      and all(digest(Path(a['path'])) == a['sha256'] for a in read(r['path'])['artifacts']) for r in results)
    emit('release.evidence_binding', {'all_required_preceding_results_bound': len(results) == 56 and links_valid,
                                     'raw_inventory_verified': raw_valid}, ['source-end'], extra=manifests)
    return results
