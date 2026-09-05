#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Identical probe executed by separately installed baseline/current packages.

The outer driver keeps absolute circuit/model paths fixed. This file only uses
preserved public scientific primitives; it never edits or reseals a realization.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from apm.compiler_provenance import digest
from apm.research import load_profile, sample, save
from apm.research_cli import read_request
from apm.research_mapping import ReferenceMapper
from apm.research_numerics import normal_draw
from apm.research_spice import execute
from apm.toolchain import resolve_toolchain

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('root', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--legacy', type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
root = args.root
tool = resolve_toolchain(root)
request = read_request(root / 'examples/research/request.json')
profile = load_profile(root / 'variation/research/apm045/derived/hart_tsmc40_profile.json', root=root)
mapper = ReferenceMapper(root, tool.ngspice, args.output / 'maps', profile)
realized = sample(profile, request, 1001, 0, mapper)
save(args.output / 'realization.json', realized)
z = np.array([[[normal_draw(9041, i, u, c) for c in ('vth', 'beta')]
              for u in ('a', 'b')] for i in range(65536)])
np.save(args.output / 'latents.npy', z)
saved = args.legacy or args.output / 'realization.json'
before = digest(saved)
old = json.loads(saved.read_text())
runs = []
for temperature, path in ((26.85, 'request.json'), (85, 'request.json'), (26.85, 'request-op.json')):
    recipe = read_request(root / 'examples/research' / path) if path == 'request.json' else {
        **request, 'analyses': [{'kind': 'op', 'vectors': ['v(ref)', 'i(Vout)']}]}
    r = execute(root, tool.ngspice, args.output / 'runs', recipe, old, temperature_c=temperature)
    runs.append({'run_id': r['run_id'], 'status': r['status'], 'directory': r['directory'],
                 'subject': r['subject'], 'rows': r['rows'],
                 'arrays': {f: np.loadtxt(Path(r['directory']) / f, skiprows=1).tolist()
                            for f in r['files'] if f.startswith('analysis') and f.endswith('.txt')}})
save(args.output / 'report.json', {'status': 'PASS' if realized['status'] == 'RESOLVED'
     and all(r['status'] == 'PASS' for r in runs) and digest(saved) == before else 'FAIL',
     'saved_original_path': str(saved), 'saved_original_sha256': before,
     'saved_original_unchanged': digest(saved) == before,
     'runs': runs, 'profile_sha256': digest(root / 'variation/research/apm045/derived/hart_tsmc40_profile.json'),
     'imported_modules': {n: digest(Path(__import__('apm.' + n, fromlist=['x']).__file__))
                          for n in ('research', 'research_numerics', 'research_mapping', 'research_spice')}})
