# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Execute only explicitly reviewed, named public examples and inspect real outputs."""
from __future__ import annotations

import csv
import re
import shutil
import sys
from pathlib import Path

import numpy as np

from .campaign_support import read, run
from .compiler_provenance import digest
from .lifecycle import write_report
from .research import SCHEMAS, seal, verify
from .research_spice import read_values

BLOCKS = {
    'discover': 'README.md', 'cold': 'docs/getting-started.md',
    'warm': 'docs/getting-started.md', 'nominal': 'docs/using-models.md',
    'characterize': 'docs/characterization.md', 'noise': 'docs/noise.md',
    'benchmark': 'docs/benchmark-variation.md', 'native': 'docs/native-variation.md',
    'research': 'docs/research-local.md', 'history': 'docs/history.md',
    'snapshot': 'docs/source-snapshot.md',
}


def command_block(root, name):
    source = root / BLOCKS[name]
    matches = re.findall(r'<!-- apm-journey: ' + re.escape(name) + r' -->\s*```bash\n(.*?)\n```',
                         source.read_text(), re.DOTALL)
    if len(matches) != 1:
        raise ValueError('REVIEWED_BLOCK_MISSING_OR_DUPLICATE: ' + name)
    return matches[0]


def execute_block(root, output, name):
    code = command_block(root, name)
    receipt = run(root, output, name, ['bash', '-euo', 'pipefail', '-c', code])
    receipt.update(document=BLOCKS[name], document_sha256=digest(root / BLOCKS[name]),
                   block=name, executed_block=code)
    write_report(output / (name + '.json'), receipt)
    return receipt


def table(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def observations(root):
    """Measurements for the published prose; unavailable files fail in the caller."""
    state = root / '.apm'
    electrical = table(state / 'tutorial-characterization/derived.csv')
    noise = table(state / 'tutorial-noise/noise_spectrum.csv')
    spectrum = np.array([[float(r[k]) for k in ('frequency_hz', 's_idrain_terminal_a2_per_hz',
                        's_vgate_equivalent_v2_per_hz', 'y_dg_real_s', 'y_dg_imag_s')] for r in noise])
    nominal = {name: np.loadtxt(state / f'tutorial-nominal/{name}-idvg.txt', skiprows=1)
               for name in ('apm045', 'apm130')}
    saved = state / 'tutorial-research/realization.json'
    realized = verify(read(saved), SCHEMAS['realization'])
    replays = []
    for path in sorted((state / 'tutorial-research/runs').glob('*/run.json')):
        r = verify(read(path), SCHEMAS['run'])
        same = read(path.parent / 'realization.json') == realized
        log = (path.parent / 'stdout.txt').read_text() + (path.parent / 'stderr.txt').read_text()
        devices = r['subject']['request']['devices']
        raw = [d['raw'] for d in realized['devices']]
        stable = all(not read_values(log, devices, f'{p}{i}', raw)
                     for p in ('applied', 'after') for i in range(len(r['subject']['request']['analyses'])))
        replays.append({'run_id': r['run_id'], 'status': r['status'],
                        'temperature_c': r['subject']['temperature_c'],
                        'analyses': [a['kind'] for a in r['subject']['request']['analyses']],
                        'same_saved_realization': same, 'stable_readback': stable,
                        'raw_receipts': all(digest(path.parent / f) == h for f, h in r['files'].items())})
    return {
        'electrical': {'rows': len(electrical), 'fields': list(electrical[0]),
                       'finite_difference_gm': all(float(r['gm_step_v']) > 0 for r in electrical),
                       'y_matrices': len(read(state / 'tutorial-characterization/y_matrix.json')),
                       'comparison_status': read(state / 'tutorial-threshold/report.json')['status']},
        'noise': {'rows': len(noise), 'first_frequency_hz': spectrum[0, 0],
                  'last_frequency_hz': spectrum[-1, 0], 'first_drain_psd_a2_per_hz': spectrum[0, 1],
                  'first_gate_psd_v2_per_hz': spectrum[0, 2],
                  'positive_psd': bool(np.all(spectrum[:, 1:3] >= 0)),
                  'complex_transfer_identity': bool(np.allclose(spectrum[:, 1] / np.sum(spectrum[:, 3:]**2, axis=1),
                                                                spectrum[:, 2], rtol=1e-12, atol=0)),
                  'effective_parameters_present': (state / 'tutorial-noise/noise_model_snapshot.json').is_file(),
                  'fit_statuses': [{k: v for k, v in r.items() if 'status' in k}
                                   for r in table(state / 'tutorial-noise/noise_metrics.csv')]},
        'nominal': {k: {'points': len(v), 'finite': bool(np.all(np.isfinite(v))),
                        'last_row': v[-1].tolist()} for k, v in nominal.items()},
        'variation': {'benchmark': read(state / 'tutorial-benchmark/report.json')['status'],
                      'native': read(state / 'tutorial-native/report.json')['status'],
                      'research': realized['status'], 'profile_tier': realized['profile_tier']},
        'replay': {'saved_sha256': digest(saved), 'devices': realized['devices'], 'runs': replays,
                   'all_same_and_stable': len(replays) == 3 and all(r['status'] == 'PASS'
                       and r['same_saved_realization'] and r['stable_readback'] and r['raw_receipts'] for r in replays)
                       and {r['temperature_c'] for r in replays} == {26.85, 85}
                       and {a for r in replays for a in r['analyses']} == {'dc', 'op'}},
    }


def negative_journey(root, output):
    output.mkdir(parents=True, exist_ok=False)
    cli = [sys.executable, '-m', 'apm.cli']
    source = root / '.apm/tutorial-research'
    original = source / 'realization.json'
    before = digest(original)
    request = read(root / 'examples/research/request.json')
    request['circuit'] = str(root / 'examples/research/mirror.cir')
    request['devices'][0]['family'] = 'apm045/io18'
    write_report(output / 'unsupported-request.json', request)
    corrupt = read(original)
    corrupt['devices'][0]['raw'][0] += .1  # deliberately do not reseal a physical record
    write_report(output / 'corrupt-realization.json', corrupt)
    cached = next((source / 'runs').glob('*/run.json'))
    shutil.copytree(cached.parent, output / 'stale' / cached.parent.name)
    stale = read(cached)
    stale.pop('content_id')
    stale['subject']['temperature_c'] = 77
    # This reseals a deliberately false RUN CACHE, never a saved physical device.
    write_report(output / 'stale' / cached.parent.name / 'run.json', seal(stale))
    sample_args = ['research', 'sample', '--profile', 'variation/research/apm045/derived/hart_tsmc40_profile.json',
                   '--seed', '1001', '--index', '0', '--state', str(output / 'maps')]
    run_args = ['research', 'run', '--request', 'examples/research/request.json']
    cases = [
        ('unsupported', sample_args + ['--request', str(output / 'unsupported-request.json'),
                                      '--output', str(output / 'unsupported.json')], 'UNSUPPORTED_RESEARCH_DEVICE', {}),
        ('corrupt', run_args + ['--realization', str(output / 'corrupt-realization.json'),
                                '--output', str(output / 'corrupt-runs')], 'CORRUPT_OR_UNVERSIONED_RECORD', {}),
        ('stale', ['research', 'run', '--request', str(cached.parent / 'request.json'),
                   '--realization', str(original), '--temperature-c', str(read(cached)['subject']['temperature_c']),
                   '--output', str(output / 'stale')], 'CACHE_REJECTED', {}),
        ('wrong-root', ['list', 'technologies'], 'APM_REPO_ROOT is not an APM checkout',
         {'APM_REPO_ROOT': str(output / 'missing-root')}),
        ('occupied', sample_args + ['--request', 'examples/research/request.json', '--output', str(original)],
         'REALIZATION_OUTPUT_OCCUPIED', {}),
        ('missing-history', ['history', 'verify'], 'MISSING_HISTORY',
         {'APM_REPO_ROOT': str(root / '.apm/tutorial-snapshot')}),
    ]
    records = []
    for name, args, expected, env in cases:
        receipt = run(root, output, name, cli + args, env=env, timeout=120)
        diagnostic = Path(receipt['stdout']).read_text() + Path(receipt['stderr']).read_text()
        observed = receipt['returncode'] not in (None, 0) and expected in diagnostic
        records.append({'case': name, 'expected': expected, 'mechanism_observed': observed,
                        'execution': str(output / (name + '.json'))})
    checks = {'six_specific_mechanisms': len(records) == 6 and all(r['mechanism_observed'] for r in records),
              'saved_physical_file_untouched': digest(original) == before,
              'no_failed_realization_written': not (output / 'unsupported.json').exists(),
              'no_corrupt_simulation_started': not (output / 'corrupt-runs').exists()}
    return write_report(output / 'report.json', {'status': 'PASS' if all(checks.values()) else 'FAIL',
                                                'checks': checks, 'records': records})
