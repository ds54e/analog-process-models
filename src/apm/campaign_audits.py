# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Migration, documentation and isolated original-source campaign checks."""
from __future__ import annotations

import ast
import difflib
import re
import sys
from pathlib import Path

from .campaign_support import pytest_coverage, read, run
from .compiler_provenance import digest
from .history import BASELINE as BASE
from .history import digest as digest_bytes
from .history import git, git_text, load_index, tomllib
from .lifecycle import write_report

CURRENT_DOCUMENTS = ['README.md', 'AGENTS.md', 'GOAL.md', 'STATUS.md', 'ENVIRONMENT.md',
                     'THIRD_PARTY.md', 'CONTRIBUTING.md', 'SECURITY.md',
                     'docs/index.md', 'docs/getting-started.md', 'docs/using-models.md',
                     'docs/characterization.md', 'docs/noise.md', 'docs/variation.md',
                     'docs/benchmark-variation.md', 'docs/native-variation.md',
                     'docs/research-local.md', 'docs/models.md', 'docs/spectre.md',
                     'docs/history.md', 'docs/source-snapshot.md', 'docs/maintainers/index.md',
                     'docs/maintainers/v6-editorial-review.md']


def docs_audit(root):
    links, errors = [], []
    graph = {}
    for name in CURRENT_DOCUMENTS:
        path = root / name
        source = path.read_text()
        graph[name] = set()
        for match in re.finditer(r'(?<!!)\[[^\]\n]+\]\(([^)]+)\)', source):
            target = match[1]
            if re.match(r'[a-z]+:', target):
                continue  # exact upstream references reviewed in the editorial record
            file, _, anchor = target.partition('#')
            destination = (path.parent / file).resolve() if file else path
            valid = destination.is_file()
            if valid and anchor:
                headings = re.findall(r'^#+\s+(.+)$', destination.read_text(), re.MULTILINE)
                anchors = {re.sub(r'[^\w\- ]', '', h.lower()).replace(' ', '-') for h in headings}
                valid = anchor in anchors
            links.append({'source': name, 'target': target, 'valid': valid})
            if not valid:
                errors.append({'source': name, 'target': target})
            if destination.is_relative_to(root):
                graph[name].add(str(destination.relative_to(root)))
    reachable = graph['README.md'] | {x for n in graph['README.md'] for x in graph.get(n, set())}
    tasks = {'docs/getting-started.md', 'docs/using-models.md', 'docs/characterization.md',
             'docs/noise.md', 'docs/variation.md', 'docs/research-local.md', 'docs/models.md',
             'docs/history.md', 'docs/maintainers/index.md', 'docs/source-snapshot.md'}
    review = root / 'docs/maintainers/v6-editorial-review.md'
    checks = {'all_current_links_resolve': bool(links) and not errors,
              'tasks_within_two_links': tasks <= reachable,
              'source_linked_editorial_review': review.is_file(),
              'package_about_proposal': tomllib.loads((root / 'pyproject.toml').read_text())['project']['description']
                  == 'Open compact models and ngspice tools for analog device, noise, and mismatch studies.'}
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'links': links, 'errors': errors, 'unreachable_tasks': sorted(tasks - reachable),
            'editorial_review_sha256': digest(review) if review.is_file() else None,
            'external_about_write': 'UNAPPLIED: requires specific external authorization'}


def migration_audit(root, output):
    inventory = read(root / 'releases/migration-v6.json')
    # Every baseline test function, including parameterized scientific and
    # historical corruption checks, must have an explicit current disposition.
    original_tests = set()
    for path in git_text(root, 'ls-tree', '-r', '--name-only', BASE, '--', 'tests',
                         'tools/v5_preflight/tests').splitlines():
        if path.endswith('.py'):
            for node in ast.parse(git_text(root, 'show', BASE + ':' + path)).body:
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    original_tests.add(BASE + ':' + path + '::' + node.name)
    mappings = read(root / 'releases/check-migration.json')['checks']
    bad_destinations = []
    for row in mappings:
        if '::' in row['current']:
            path, name = row['current'].split('::')
            if not (root / path).is_file() or name not in {n.name for n in ast.parse((root / path).read_text()).body
                                                          if isinstance(n, ast.FunctionDef)}:
                bad_destinations.append(row)
    helpers = []
    for target, row in read(root / 'releases/helper-migration.json').items():
        target = target.partition('#')[0]
        source = git(root, 'show', row['commit'] + ':' + row['source'])
        if digest_bytes(source) != row['source_sha256']:
            raise ValueError('HELPER_ORIGIN_DRIFT')
        old = ast.parse(source.decode())
        new = ast.parse((root / target).read_text())
        for name in row['names']:
            def find(tree, name=name):
                return next(n for n in tree.body if getattr(n, 'name', None) == name or
                            (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)))
            before, after = ast.dump(find(old), indent=2), ast.dump(find(new), indent=2)
            difference = '\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile=row['source'], tofile=target))
            helpers.append({'name': name, 'origin': row['commit'] + ':' + row['source'],
                            'target': target, 'ast_identical': before == after, 'ast_diff': difference,
                            'declared_delta': row['changes']})
    allowed_changed = {'src/apm/paths.py', 'src/apm/cli.py', 'src/apm/maintenance_validate.py',
                       'src/apm/provenance_validate.py', 'src/apm/research_cli.py', 'src/apm/__init__.py'}
    changes = []
    for path in git_text(root, 'ls-tree', '-r', '--name-only', BASE, '--', 'src/apm').splitlines():
        current = root / path
        if current.is_file() and git(root, 'show', BASE + ':' + path) != current.read_bytes():
            changes.append(path)
    deliberate = {'audit_plan', 'audit_confirmation', 'audit_migration'}
    checks = {'all_original_checks_mapped': len(mappings) == len(original_tests)
                  and {r['original'] for r in mappings} == original_tests,
              'current_equivalents_exist': not bad_destinations,
              'helper_ast_exact_except_reviewed_changes': all(r['ast_identical'] or r['name'] in deliberate for r in helpers),
              'scientific_implementations_byte_exact': set(changes) <= allowed_changed,
              'inventory_precedes_migration': inventory.get('baseline_commit', BASE) == BASE}
    return write_report(output, {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
                                  'baseline_test_functions': len(original_tests), 'helper_comparisons': helpers,
                                  'changed_existing_modules': changes, 'bad_destinations': bad_destinations})


def original_execution(root, output):
    """Explicit outer isolation; normal imports never run historical packages."""
    output.mkdir(parents=True, exist_ok=False)
    records = []
    targets = [(r['tag'], r['source']['commit']) for r in load_index(root)['legacy']]
    targets += [('v6-baseline', BASE)]
    for name, commit in targets:
        folder = output / name
        clone = folder / 'source'
        logs = folder / 'execution'
        run(root, logs, 'clone', ['git', 'clone', '--no-hardlinks', str(root), str(clone)])
        run(clone, logs, 'checkout', ['git', 'checkout', '--detach', commit])
        site = folder / 'site'
        installed = run(clone, logs, 'install', [sys.executable, '-m', 'pip', 'install', '--no-deps',
                                                 '--target', str(site), str(clone)])
        env = {'APM_REPO_ROOT': str(clone), 'APM_STATE_DIR': str(folder / 'state'),
               'PYTHONPATH': str(site), 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}
        identity = run(clone, logs, 'identity', [sys.executable, '-c',
            'import apm,importlib.metadata,json; print(json.dumps({"runtime":apm.__version__,"installed":importlib.metadata.version("analog-process-models"),"module":apm.__file__}))'], env=env)
        observed = read(Path(identity['stdout']))
        expected = tomllib.loads((clone / 'pyproject.toml').read_text())['project']['version']
        xml = logs / 'pytest.xml'
        selections = ['tests'] if name == 'v6-baseline' else ['tests/test_benchmark.py', 'tests/test_native_variation.py']
        tested = run(clone, logs, 'pytest', [sys.executable, '-m', 'pytest', '-q', *selections,
                                            '--junitxml=' + str(xml)], env=env)
        coverage = pytest_coverage(xml)
        checks = {'installed_original': installed['returncode'] == 0 and observed['runtime'] == observed['installed'] == expected,
                  'isolated_import': Path(observed['module']).is_relative_to(site),
                  'original_tests_executed': tested['returncode'] == 0 and coverage['status'] == 'PASS',
                  'exact_original_source': git_text(clone, 'rev-parse', 'HEAD') == commit}
        if name == 'v6-baseline':
            preflight_xml = logs / 'preflight.xml'
            preflight = run(clone, logs, 'preflight', [sys.executable, '-m', 'pytest', '-q',
                            'tools/v5_preflight/tests', '--junitxml=' + str(preflight_xml)],
                            env={**env, 'PYTHONPATH': str(site) + ':' + str(clone / 'tools/v5_preflight')})
            checks['original_preflight'] = preflight['returncode'] == 0 and pytest_coverage(preflight_xml)['status'] == 'PASS'
        records.append({'name': name, 'commit': commit, 'tree': git_text(clone, 'rev-parse', 'HEAD^{tree}'),
                        'checks': checks, 'identity': observed, 'coverage': coverage,
                        'status': 'PASS' if all(checks.values()) else 'FAIL'})
    return write_report(output / 'report.json', {'status': 'PASS' if len(records) == 6
                        and all(r['status'] == 'PASS' for r in records) else 'FAIL', 'records': records,
                        'claim': 'Representative original execution and complete starting-main tests; not full old release requalification'})
