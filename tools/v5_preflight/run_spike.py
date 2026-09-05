# SPDX-FileCopyrightText: 2026 APM preflight contributors
# SPDX-License-Identifier: Apache-2.0

"""Unqualified ngspice-47 preflight runner; do NOT treat it as a v5 release gate.

Uses existing immutable APM VTG files; never rewrites a model or repository file.
Default investigation: W=1um, L=.12um, N/P, 300K, |VDS|=50mV.
No measured beta-mismatch coefficient is used anywhere in this runner.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import numpy as np
from numerical_core import PreflightError, extract_mg, inverse_mapping, local_jacobian
BASE_REF = 'b09d104759296e6dd59c6f08e6cd30fa716d6461'
MODEL_FILES = {'models/apm045/vendor/freepdk45/NMOS_VTG.inc': 'd98a9f5103d4248f46fdf4086d19fe64c9e3eded', 'models/apm045/vendor/freepdk45/PMOS_VTG.inc': '5d3fcca1b06d81685713ec4dd90beadb4051f5e1', 'models/apm045/families/vtg/ngspice/wrapper.inc': '62cc2ef43146224a2dc0b06398139b2d1ece2ada'}
LEAF_A = '@m.xtop.xea.xa.mapm045_vtg_core'
LEAF_B = '@m.xtop.xea.xb.mapm045_vtg_core'

def write_json(path: Path, value: object):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')

def git_blob_hash(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\x00' + data).hexdigest()

def verify_models(root: Path) -> dict:
    observed = {}
    for relative, expected in MODEL_FILES.items():
        path = root / relative
        if not path.is_file():
            raise PreflightError(f'MODEL_MISSING: {relative}')
        raw = path.read_bytes()
        observed[relative] = {'git_blob_sha1': git_blob_hash(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        if observed[relative]['git_blob_sha1'] != expected:
            raise PreflightError(f'MODEL_IDENTITY_MISMATCH: {relative}')
    return observed

def render_deck(root: Path, polarity: str, w_um: float, l_um: float, step: float, delvto: float, ln_mulu0: float, temperature_c: float=26.85, vds: float=0.05, invalid_target: bool=False, reset_after_apply: bool=False) -> str:
    if polarity not in ('n', 'p'):
        raise PreflightError('invalid polarity')
    if not all((math.isfinite(x) for x in (w_um, l_um, step, delvto, ln_mulu0, temperature_c, vds))):
        raise PreflightError('nonfinite deck parameter')
    if min(w_um, l_um, step, vds) <= 0 or vds > 1:
        raise PreflightError('invalid deck parameter')
    includes = []
    for relative in MODEL_FILES:
        path = str((root / relative).resolve())
        if any((c in path for c in ('"', '\n', '\r'))):
            raise PreflightError('unsafe include path')
        includes.append(f'.include "{path}"')
    source, drain, stop, increment = (0.0, vds, 1.0, step) if polarity == 'n' else (1.0, 1.0 - vds, -1.0, -step)
    wrapper = f"apm045_vtg_{('nmos' if polarity == 'n' else 'pmos')}"
    target = LEAF_A if not invalid_target else '@m.xtop.xea.xmissing.mapm045_vtg_core'
    apply = [f'alter {LEAF_A}[delvto] = 0', f'alter {LEAF_A}[mulu0] = 1', f'alter {LEAF_B}[delvto] = 0', f'alter {LEAF_B}[mulu0] = 1', f'alter {target}[delvto] = {delvto:.17g}', f'alter {target}[mulu0] = {math.exp(ln_mulu0):.17g}']
    if reset_after_apply:
        apply.append('reset')
    readback = []
    for label, leaf in [('a', LEAF_A), ('b', LEAF_B)]:
        for parameter in ('w', 'l', 'delvto', 'mulu0'):
            key = f'{label}_{parameter}'
            readback += [f'let {key} = {leaf}[{parameter}]', f'print {key}']
    return '\n'.join(['* APM v5 exploratory hierarchy/MG probe; no statistical calibration claim', *includes, f'.temp {temperature_c:.17g}', '.options reltol=1e-7 abstol=1e-15 vntol=1e-9', f'Vs s 0 {source:.17g}', 'Vb b s 0', f'Vda da 0 {drain:.17g}', f'Vdb db 0 {drain:.17g}', 'Vctrl g s 0', f'Xtop da db g s b stage1 w={w_um:.17g}u l={l_um:.17g}u', '.subckt stage1 da db g s b w=1u l=.12u', "Xea da db g s b stage2 w='w' l='l'", '.ends stage1', '.subckt stage2 da db g s b w=1u l=.12u', f"Xa da g s b {wrapper} w='w' l='l'", f"Xb db g s b {wrapper} w='w' l='l'", '.ends stage2', '.control', 'set noaskquit', 'set numdgt=17', 'set wr_singlescale', 'set wr_vecnames', *apply, 'op', *readback, f'dc Vctrl 0 {stop:.17g} {increment:.17g}', 'let u = abs(v(g)-v(s))', 'wrdata sweep.txt u i(Vda) i(Vdb)', 'quit', '.endc', '.end', ''])

def readback_scalars(log: str) -> dict:
    result = {}
    for key in ('a_w', 'a_l', 'a_delvto', 'a_mulu0', 'b_w', 'b_l', 'b_delvto', 'b_mulu0'):
        found = re.findall('(?m)^\\s*' + key + '\\s*=\\s*([-+0-9.eE]+)\\s*$', log)
        if len(found) != 1:
            raise PreflightError(f'READBACK_MISSING_OR_DUPLICATE: {key}')
        result[key] = float(found[0])
        if not math.isfinite(result[key]):
            raise PreflightError('READBACK_NONFINITE')
    return result

def expected_negative_failure(name: str, error: Exception, log: str='') -> bool:
    """Accept only the intended target failure, not an unrelated simulator error."""
    message = str(error)
    if name not in ('bad_path', 'reset_loses_perturbation'):
        return False
    if message.startswith(('READBACK_MISMATCH: a_delvto ', 'READBACK_MISMATCH: a_mulu0 ')):
        return True
    if name != 'bad_path' or not message.startswith('SIMULATION_FAILED:'):
        return False
    return any(('xmissing' in line.lower() and re.search("no such|not found|can't find|does not exist|unknown|no matching", line, re.I) for line in log.splitlines()))

class SpiceProbe:

    def __init__(self, root: Path, binary: str, output: Path, polarity: str, w_um: float, l_um: float):
        self.root, self.binary, self.output = (root, binary, output)
        self.polarity, self.w_um, self.l_um = (polarity, w_um, l_um)
        self.counter = 0
        self.cache = {}

    def run(self, raw=(0.0, 0.0), step=0.001, temperature_c=26.85, vds=0.05, invalid_target=False, reset_after_apply=False):
        key = tuple(map(float, raw)) + (step, temperature_c, vds, invalid_target, reset_after_apply)
        if key in self.cache:
            return self.cache[key]
        path = self.output / f'{self.counter:05d}'
        self.counter += 1
        path.mkdir(parents=True, exist_ok=False)
        deck = render_deck(self.root, self.polarity, self.w_um, self.l_um, step, *raw, temperature_c, vds, invalid_target, reset_after_apply)
        (path / 'input.cir').write_text(deck, encoding='utf-8')
        command = [self.binary, '-n', '-b', 'input.cir']
        proc = subprocess.run(command, cwd=path, text=True, capture_output=True, timeout=60, env={**__import__('os').environ, 'OMP_NUM_THREADS': '1', 'LC_ALL': 'C'})
        log = proc.stdout + '\n' + proc.stderr
        (path / 'stdout.txt').write_text(proc.stdout, encoding='utf-8')
        (path / 'stderr.txt').write_text(proc.stderr, encoding='utf-8')
        write_json(path / 'request.json', {'command': command, 'raw': list(map(float, raw)), 'step_v': step, 'temperature_c': temperature_c, 'vds_magnitude_v': vds, 'returncode': proc.returncode, 'source_calibration': False})
        if proc.returncode or re.search('(?im)^\\s*(?:fatal error|error(?:\\s|:))', log):
            raise PreflightError(f'SIMULATION_FAILED: {path}')
        rb = readback_scalars(log)
        expected = {'a_w': self.w_um * 1e-06, 'a_l': self.l_um * 1e-06, 'a_delvto': float(raw[0]), 'a_mulu0': math.exp(float(raw[1])), 'b_w': self.w_um * 1e-06, 'b_l': self.l_um * 1e-06, 'b_delvto': 0.0, 'b_mulu0': 1.0}
        for name, value in expected.items():
            if not math.isclose(rb[name], value, rel_tol=1e-08, abs_tol=1e-16):
                raise PreflightError(f'READBACK_MISMATCH: {name} at {path}')
        data = np.loadtxt(path / 'sweep.txt', skiprows=1)
        if data.ndim != 2 or data.shape[1] != 4 or (not np.all(np.isfinite(data))):
            raise PreflightError(f'OUTPUT_SHAPE_INVALID: {path}')
        u, ia, ib = (data[:, 1], data[:, 2], data[:, 3])
        a = extract_mg(u, np.abs(ia), vds)
        b = extract_mg(u, np.abs(ib), vds)
        record = {'a': asdict(a), 'b': asdict(b), 'readback': rb, 'run_directory': str(path), 'u': u, 'ia': ia, 'ib': ib}
        write_json(path / 'extraction.json', {k: v for k, v in record.items() if k not in ('u', 'ia', 'ib')})
        self.cache[key] = record
        return record

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--ngspice', default='ngspice')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--w-um', type=float, default=1.0)
    parser.add_argument('--l-um', type=float, default=0.12)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    binary = shutil.which(args.ngspice)
    report = {'kind': 'exploratory_preflight', 'base_ref': BASE_REF, 'source_beta_approved': False, 'release_qualification': False, 'records': {}}
    if not binary:
        report.update(status='NOT_RUN_TOOL_UNAVAILABLE', tool=args.ngspice)
        write_json(out / 'report.json', report)
        return 2
    version = subprocess.run([binary, '--version'], text=True, capture_output=True, timeout=10)
    text = version.stdout + '\n' + version.stderr
    (out / 'ngspice-version.txt').write_text(text, encoding='utf-8')
    if not re.search('ngspice\\s*-?\\s*47\\b', text, re.I):
        report.update(status='NOT_RUN_WRONG_TOOL_VERSION')
        write_json(out / 'report.json', report)
        return 2
    try:
        root = args.repo.resolve()
        report['models'] = verify_models(root)
        report['simulator_sha256'] = hashlib.sha256(Path(binary).read_bytes()).hexdigest()
        for polarity in ('n', 'p'):
            probe = SpiceProbe(root, binary, out / polarity, polarity, args.w_um, args.l_um)
            coarse = [probe.run(step=h) for h in (0.005, 0.002, 0.001)]
            base = coarse[-1]
            vths = [r['a']['vth_mg_v'] for r in coarse]
            betas = [r['a']['beta_mg_a_per_v2'] for r in coarse]
            if max(vths) - min(vths) > 5e-05 or (max(betas) - min(betas)) / betas[-1] > 0.001:
                raise PreflightError(f'EXTRACTION_NOT_CONVERGED: {polarity}')

            def f(raw):
                r = probe.run(raw)
                if not np.allclose(r['ib'], base['ib'], rtol=1e-08, atol=1e-15):
                    raise PreflightError('UNTOUCHED_TWIN_CHANGED')
                return np.array([r['a']['vth_mg_v'] - vths[-1], r['a']['beta_mg_a_per_v2'] / betas[-1] - 1.0])
            scales = np.array([0.01, 0.02])
            jac, condition = local_jacobian(f, np.array([0.001, 0.01]), scales)
            if not np.isfinite(condition) or condition > 100:
                raise PreflightError('MAPPING_ILL_CONDITIONED')
            targets = [(0.01, 0.02), (0.01, -0.02), (-0.01, 0.02), (-0.01, -0.02)]
            mapped = []
            for target in targets:
                raw = inverse_mapping(f, np.array(target), scales, (np.array([-0.1, math.log(0.5)]), np.array([0.1, math.log(1.5)])))
                fine = probe.run(raw, step=0.0005)
                fine0 = probe.run(step=0.0005)
                recovered = np.array([fine['a']['vth_mg_v'] - fine0['a']['vth_mg_v'], fine['a']['beta_mg_a_per_v2'] / fine0['a']['beta_mg_a_per_v2'] - 1])
                if np.max(np.abs((recovered - np.array(target)) / scales)) > 0.01:
                    raise PreflightError('MAPPING_REFINEMENT_CHECK_FAILED')
                mapped.append({'target': target, 'raw': raw.tolist(), 'recovered': recovered.tolist()})
            negatives = {}
            for name, kwargs in [('bad_path', {'invalid_target': True}), ('reset_loses_perturbation', {'reset_after_apply': True})]:
                try:
                    probe.run((0.02, math.log(1.05)), **kwargs)
                except PreflightError as error:
                    diagnostic_log = ''
                    if probe.counter:
                        last_run = probe.output / f'{probe.counter - 1:05d}'
                        for filename in ('stdout.txt', 'stderr.txt'):
                            log_path = last_run / filename
                            if log_path.is_file():
                                diagnostic_log += log_path.read_text() + '\n'
                    if not expected_negative_failure(name, error, diagnostic_log):
                        raise PreflightError(f'NEGATIVE_CONTROL_INCONCLUSIVE: {name}: {error}') from error
                    negatives[name] = {'detected': True, 'reason': str(error)}
                else:
                    raise PreflightError(f'NEGATIVE_CONTROL_NOT_DETECTED: {name}')
            report['records'][polarity] = {'extraction': base['a'], 'raw_jacobian': jac.tolist(), 'normalized_condition_number': condition, 'artificial_target_mapping': mapped, 'negative_controls': negatives, 'ngspice_processes': probe.counter}
        report['status'] = 'EXPLORATORY_PREFLIGHT_PASSED_NOT_RELEASE_QUALIFICATION'
    except (PreflightError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        report.update(status='EXPLORATORY_PREFLIGHT_FAILED', error=str(error))
    write_json(out / 'report.json', report)
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}, indent=2))
    return 0 if report['status'] == 'EXPLORATORY_PREFLIGHT_PASSED_NOT_RELEASE_QUALIFICATION' else 1
if __name__ == '__main__':
    sys.exit(main())
