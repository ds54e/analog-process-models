# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Same-input old/current comparison with explicit physical projections.

Exact numeric/string arrays, signed complex Y, saved raw parameters, failures,
method/source/model/tool identities are compared. Only listed output identities
are normalized; this is not a general metadata-stripping comparator.
"""
from __future__ import annotations

import csv
import re
import sys

import numpy as np

from .campaign_support import read, run
from .compiler_provenance import digest
from .history import BASELINE, canonical, git_text
from .lifecycle import write_report

REGRESSIONS = {'electrical': 'characterization-check', 'benchmark': 'benchmark-check',
               'native': 'apm130-native-check', 'noise_method': 'noise-method-check',
               'noise_catalog': 'noise-catalog-check'}
# The excluded CSV field is an artifact receipt, not a model/source hash.
# Every underlying artifact is retained and independently inventoried/audited.
CSV_IDENTITIES = {'result_content_sha256'}
JSON_PHYSICAL = {'y_matrix.json', 'noise_model_snapshot.json', 'source_breakdown.json'}
BENCHMARK_FIELDS = ('schema', 'status', 'benchmark_configuration', 'checks', 'validation_seed',
                    'validated_devices', 'validated_families', 'variation_origin', 'samples',
                    'mos_simulations', 'replay_simulations', 'passive_simulations',
                    'passive_noise_simulation', 'adapter_calibrations')


def normalize(value, replacements):
    if isinstance(value, str):
        if callable(replacements):
            return replacements(value)
        for a, b in replacements:
            value = value.replace(a, b)
        return value
    if isinstance(value, list):
        return [normalize(v, replacements) for v in value]
    if isinstance(value, dict):
        return {normalize(k, replacements): normalize(v, replacements) for k, v in value.items()}
    return value


def compiled_replacements(replacements):
    """Match declared path/identity strings once, without scanning every CSV cell 660 times."""
    mapping = dict(replacements)
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)))
    minimum = min(map(len, mapping))
    return lambda value: value if len(value) < minimum else pattern.sub(lambda m: mapping[m[0]], value)


def noise_names(folder):
    plan = read(folder / 'plan.json')
    replacements = []
    requests = []
    for row in plan['requests']:
        request = dict(row['request'])
        request.pop('implementation_code_sha256')
        import hashlib
        physical = hashlib.sha256(canonical(request)).hexdigest()
        replacements += [(row['request_id'], 'physical-' + physical), (row['request_hash'], physical)]
        requests.append({'request': request, 'memberships': row['memberships']})
    return replacements, sorted(requests, key=canonical)


def physical_index(folder, replacements):
    result = {}
    for path in sorted(folder.rglob('*')):
        if path.suffix != '.csv' and path.name not in JSON_PHYSICAL:
            continue
        # Resume fault-injection creates intentionally corrupt outputs. Compare
        # that mechanism through its validator; use ordinary outputs here.
        if 'resume_qualification' in path.parts:
            continue
        name = normalize(str(path.relative_to(folder)), replacements)
        if name in result:
            raise ValueError('DUPLICATE_PHYSICAL_FILE_IDENTITY')
        result[name] = path
    return result


def physical_file(path, replacements):
    if path.suffix == '.csv':
        with path.open() as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            rows = [{k: normalize(v, replacements) for k, v in r.items() if k not in CSV_IDENTITIES}
                    for r in reader]
        return {'fields': fields, 'rows': sorted(rows, key=canonical)}
    return normalize(read(path), replacements)


def physical_files(folder, replacements):
    return {name: physical_file(path, replacements) for name, path in physical_index(folder, replacements).items()}


def compare_outputs(output):
    base, current = output / 'baseline', output / 'current'
    records, failures = [], []
    replacements = {}
    for name, folder in (('baseline', base), ('current', current)):
        repl = [(str(folder), '<OUTPUT>')]
        noise_repl, requests = noise_names(folder / 'noise_catalog')
        replacements[name] = compiled_replacements(repl + noise_repl)
        write_report(folder / 'comparison-noise-requests.json', {'requests': requests})
    for stage in REGRESSIONS:
        a = physical_index(base / stage, replacements['baseline'])
        b = physical_index(current / stage, replacements['current'])
        shared = set(a) & set(b)
        mismatches = [k for k in sorted(shared) if digest(a[k]) != digest(b[k])
                      and physical_file(a[k], replacements['baseline']) != physical_file(b[k], replacements['current'])]
        missing = sorted(set(a) ^ set(b))
        old_status = read(base / stage / 'report.json')['status']
        new_status = read(current / stage / 'report.json')['status']
        stage_checks = {'exact_physical_files': bool(shared) and not missing and not mismatches,
                        'both_regressions_passed': old_status in ('PASS', 'pass', 'validated')
                            and new_status in ('PASS', 'pass', 'validated'),
                        'same_failure_classification': old_status == new_status}
        if stage == 'benchmark':
            old, new = read(base / stage / 'report.json'), read(current / stage / 'report.json')
            a = normalize({k: old[k] for k in BENCHMARK_FIELDS}, replacements['baseline'])
            b = normalize({k: new[k] for k in BENCHMARK_FIELDS}, replacements['current'])
            samples = {str(p.relative_to(base / stage)): read(p) for p in (base / stage / 'samples').glob('*.json')}
            other_samples = {str(p.relative_to(current / stage)): read(p) for p in (current / stage / 'samples').glob('*.json')}
            stage_checks['exact_physical_files'] = bool(samples) and samples == other_samples
            stage_checks['benchmark_full_science_and_provenance'] = a == b
            write_report(output / 'benchmark-projections.json', {'baseline': a, 'current': b})
        if stage == 'noise_catalog':
            old, new = read(base / stage / 'plan.json'), read(current / stage / 'plan.json')
            stage_checks['same_requests_models_methods_tools'] = read(base / 'comparison-noise-requests.json') == read(current / 'comparison-noise-requests.json')
            stage_checks['same_family_model_and_tool_bindings'] = all(old[k] == new[k] for k in
                ('family_bindings', 'frozen_methods', 'reference_tools', 'logical_request_counts', 'unique_request_count'))
            stage_checks['same_terminal_status_counts'] = read(base / stage / 'report.json')['terminal_status_counts'] == read(current / stage / 'report.json')['terminal_status_counts']
        records.append({'stage': stage, 'checks': stage_checks, 'compared_files': len(shared),
                        'mismatches': mismatches, 'missing': missing})
        if not all(stage_checks.values()):
            failures.append(stage)
    a, b = read(base / 'research/report.json'), read(current / 'research/report.json')
    old, new = read(base / 'research/realization.json'), read(current / 'research/realization.json')
    physical_keys = ('uid', 'path', 'family', 'polarity', 'w_m', 'l_m', 'z', 'target', 'raw')
    draws = lambda r: [{k: d[k] for k in physical_keys} for d in r['devices']]
    replay_checks = {
        '65536_exact_latent_pairs': bool(np.array_equal(np.load(base / 'research/latents.npy'), np.load(current / 'research/latents.npy'))),
        'same_targets_and_raw': draws(old) == draws(new),
        'exact_legacy_file_reused': b['saved_original_path'] == str(base / 'research/realization.json')
            and b['saved_original_sha256'] == digest(base / 'research/realization.json') and b['saved_original_unchanged'],
        'same_replay_physical_arrays': [r['arrays'] for r in a['runs']] == [r['arrays'] for r in b['runs']],
        'same_tools_methods_sources': a['profile_sha256'] == b['profile_sha256']
            and a['imported_modules'] == b['imported_modules']
            and [r['subject']['tool'] for r in a['runs']] == [r['subject']['tool'] for r in b['runs']],
        'three_successful_replays_each': a['status'] == b['status'] == 'PASS' and len(a['runs']) == len(b['runs']) == 3,
    }
    return write_report(output / 'report.json', {'status': 'PASS' if not failures and all(replay_checks.values()) else 'FAIL',
            'physical_status': 'PASS' if not failures else 'FAIL', 'replay_status': 'PASS' if all(replay_checks.values()) else 'FAIL',
            'records': records, 'replay_checks': replay_checks, 'failed_stages': failures,
            'comparison': 'exact deterministic arrays and named scientific/provenance projections; zero numerical tolerance',
            'excluded_csv_identity_fields': sorted(CSV_IDENTITIES),
            'request_id_normalization': 'request minus implementation_code_sha256; all model/method/seed/tool fields retained',
            'baseline_commit': BASELINE, 'current_commit': read(output / 'source-identities.json')['current']})


def execute_comparison(root, output):
    output.mkdir(parents=True, exist_ok=False)
    clone = output / 'fixed-input-source'
    logs = output / 'executions'
    current = git_text(root, 'rev-parse', 'HEAD')

    def checked_run(cwd, name, command, **kwargs):
        receipt = run(cwd, logs, name, command, **kwargs)
        if receipt['returncode'] != 0 or receipt['status'] != 'PASS':
            raise RuntimeError('COMPARISON_EXECUTION_FAILED: ' + name)
        return receipt

    checked_run(root, 'clone', ['git', 'clone', '--no-hardlinks', str(root), str(clone)])
    write_report(output / 'source-identities.json', {'baseline': BASELINE, 'current': current,
                 'method': 'Separate installed packages; sequential exact Git checkouts at identical absolute input paths',
                 'probe_sha256': digest(root / 'tools/compatibility_probe.py')})
    for name, commit in (('baseline', BASELINE), ('current', current)):
        checked_run(clone, name + '-checkout', ['git', 'checkout', '--detach', commit])
        observed_commit = git_text(clone, 'rev-parse', 'HEAD')
        write_report(logs / (name + '-source.json'), {'expected_commit': commit, 'observed_commit': observed_commit})
        if observed_commit != commit:
            raise RuntimeError('COMPARISON_SOURCE_IDENTITY_DRIFT: ' + name)
        folder, site = output / name, output / (name + '-site')
        folder.mkdir()
        checked_run(clone, name + '-install', [sys.executable, '-m', 'pip', 'install', '--no-deps', '--target', str(site), str(clone)])
        env = {'APM_REPO_ROOT': str(clone), 'APM_STATE_DIR': str(folder / 'state'),
               'PYTHONPATH': str(site), 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}
        identity = checked_run(clone, name + '-identity', [sys.executable, '-c',
            'import apm,importlib.metadata,json; print(json.dumps({"runtime":apm.__version__,"installed":importlib.metadata.version("analog-process-models"),"module":apm.__file__}))'], env=env)
        observed = read(identity['stdout'])
        from pathlib import Path

        from .history import tomllib
        expected = tomllib.loads((clone / 'pyproject.toml').read_text())['project']['version']
        if observed['runtime'] != expected or observed['installed'] != expected or not Path(observed['module']).is_relative_to(site):
            raise ValueError('COMPARISON_PACKAGE_ISOLATION_FAILED')
        checked_run(clone, name + '-build', [sys.executable, '-m', 'apm.cli', 'build-models'], env=env)
        for stage, command in REGRESSIONS.items():
            checked_run(clone, name + '-' + stage, [sys.executable, '-m', 'apm.cli', command, '--output', str(folder / stage)], env=env)
        args = [sys.executable, str(root / 'tools/compatibility_probe.py'), str(clone), str(folder / 'research')]
        if name == 'current':
            args += ['--legacy', str(output / 'baseline/research/realization.json')]
        checked_run(clone, name + '-research', args, env=env)
    return compare_outputs(output)
