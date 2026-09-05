# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Small typed ngspice recipe runner with explicit leaf readback and sealed caches."""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
from pathlib import Path

import numpy as np

from .compiler_provenance import digest
from .research import SCHEMAS, save, seal, validate_devices, verify
from .research_numerics import ResearchError, canonical_hash, extract_mg

MODELS = ('models/apm045/vendor/freepdk45/NMOS_VTG.inc',
          'models/apm045/vendor/freepdk45/PMOS_VTG.inc',
          'models/apm045/families/vtg/ngspice/wrapper.inc')
IDENT = r'[a-zA-Z][a-zA-Z0-9_]*'
VECTOR = re.compile(r'(?:i\('+IDENT+r'\)|v\('+IDENT+r'(?:,'+IDENT+r')?\))', re.IGNORECASE)
DIAGNOSTIC = re.compile(r'^\s*(?:error\b|fatal\b|warning:|.*simulation interrupted)[^\n]*', re.IGNORECASE|re.MULTILINE)
PARAMS = ('w','l','delvto','mulu0','m','nf')


def leaf(device: dict) -> str:
    return 'm.'+'.'.join(device['path']).lower()+'.mapm045_vtg_core'


def flatten(path: Path, manifest: dict, stack: tuple = ()) -> str:
    path = path.resolve()
    if path in stack or not path.is_file() or any(c in str(path) for c in '\n\r"'):
        raise ResearchError('INVALID_INCLUDE')
    manifest[str(path)] = digest(path)
    result = []
    for line in path.read_text().splitlines():
        include = re.fullmatch(r'\s*\.include\s+["\']?([^"\']+?)["\']?\s*',line,re.IGNORECASE)
        if include:
            result.append(flatten(path.parent/include[1],manifest,(*stack,path)))
        elif re.match(r'\s*\.(control|endc|end|lib)\b',line,re.IGNORECASE):
            raise ResearchError('CIRCUIT_REQUIRES_BODY_ONLY_AND_EXPLICIT_INCLUDES')
        else:
            result.append(line)
    return '\n'.join(result)


def analysis_command(recipe: dict) -> str:
    kind = recipe['kind']
    if kind == 'dc':
        if not re.fullmatch(IDENT,recipe['source']):
            raise ResearchError('UNSAFE_SOURCE_NAME')
        a,b,h = [float(recipe[k]) for k in ('start','stop','step')]
        if not all(math.isfinite(v) for v in (a,b,h)) or h == 0 or (b-a)/h <= 0 or (b-a)/h > 100000:
            raise ResearchError('INVALID_DC_GRID')
        return f'dc {recipe["source"]} {a:.17g} {b:.17g} {h:.17g}'
    if kind == 'ac':
        a,b = float(recipe['start']),float(recipe['stop']); n=recipe['points_per_decade']
        if not (0 < a < b <= 1e12 and isinstance(n,int) and 1 <= n <= 1000):
            raise ResearchError('INVALID_AC_GRID')
        return f'ac dec {n} {a:.17g} {b:.17g}'
    if kind == 'tran':
        h,b = float(recipe['step']),float(recipe['stop'])
        if not 0 < h < b or b/h > 100000:
            raise ResearchError('INVALID_TRANSIENT_GRID')
        return f'tran {h:.17g} {b:.17g}'
    if kind == 'op':
        return 'op'
    raise ResearchError('UNSUPPORTED_ANALYSIS')


def read_commands(devices, prefix):
    commands = []
    for i,d in enumerate(devices):
        for k in PARAMS:
            commands += [f'let {prefix}_{i}_{k} = @{leaf(d)}[{k}]',f'print {prefix}_{i}_{k}']
    return commands


def read_values(log,devices,prefix,raws):
    errors=[]
    for i,(d,raw) in enumerate(zip(devices,raws)):
        expected = [d['w_m'],d['l_m'],raw[0],math.exp(raw[1]),1,1]
        for k,value in zip(PARAMS,expected):
            matches=re.findall(r'^'+prefix+'_'+str(i)+'_'+k+r'\s*=\s*(\S+)',log,re.MULTILINE)
            if len(matches)!=1:
                errors.append(f'{prefix}/{i}/{k}: missing or repeated readback')
            else:
                try:
                    if not math.isclose(float(matches[0]),value,rel_tol=2e-11,abs_tol=1e-18):
                        errors.append(f'{prefix}/{i}/{k}: expected {value}, observed {matches[0]}')
                except ValueError:
                    errors.append(f'{prefix}/{i}/{k}: nonnumeric')
    return errors


def execute(root: Path, binary: Path, output: Path, request: dict, realization: dict,
            *, temperature_c: float = 26.85, timeout: float = 60) -> dict:
    verify(realization,SCHEMAS['realization'])
    if realization['request_id'] != canonical_hash(request) or realization['status'] != 'RESOLVED':
        raise ResearchError('REALIZATION_REQUEST_MISMATCH_OR_FAILED')
    devices=validate_devices(request['devices'])
    if len(devices)!=len(realization['devices']):
        raise ResearchError('REALIZATION_INSTANCE_COUNT')
    realized = {d['uid']:d for d in realization['devices']}
    if len(realized)!=len(devices) or set(realized)!={d['uid'] for d in devices}:
        raise ResearchError('REALIZATION_UID_MISMATCH')
    for d in devices:
        if any(realized[d['uid']][k]!=v for k,v in d.items()):
            raise ResearchError('REALIZATION_DEVICE_MISMATCH')
    raw=[realized[d['uid']]['raw'] for d in devices]
    if np.shape(raw)!=(len(devices),2) or not np.all(np.isfinite(raw)):
        raise ResearchError('INVALID_RAW_PARAMETERS')
    if not -40 <= temperature_c <= 125 or not 0 < timeout <= 600:
        raise ResearchError('RUN_CONDITION_OUT_OF_SCOPE')
    manifest={}
    body=flatten(Path(request['circuit']),manifest)
    if re.search(r'^\s*\.model\s+(nmos_vtg|pmos_vtg)\b',body,re.IGNORECASE|re.MULTILINE):
        raise ResearchError('NOMINAL_MODEL_REDEFINITION')
    model_text='\n'.join(flatten(root/p,manifest) for p in MODELS)
    if 'input_binding' in realization and realization['input_binding']!=manifest:
        raise ResearchError('CIRCUIT_OR_INCLUDE_CHANGED_SINCE_SAMPLING')
    recipes=request['analyses']
    if not recipes:
        raise ResearchError('EMPTY_ANALYSIS_RECIPE')
    commands=['set num_threads=1','set noaskquit','set numdgt=17',
              'set wr_singlescale','set wr_vecnames','op']
    for i,d in enumerate(devices):
        commands += [f'echo model_{i}_begin',f'show {leaf(d)}',f'echo model_{i}_end']
    commands += read_commands(devices,'before')
    for d,x in zip(devices,raw):
        commands += [f'alter @{leaf(d)}[delvto] = {x[0]:.17g}',
                     f'alter @{leaf(d)}[mulu0] = {math.exp(x[1]):.17g}']
    for i,recipe in enumerate(recipes):
        vectors=recipe['vectors']
        if not vectors or not all(VECTOR.fullmatch(v) for v in vectors):
            raise ResearchError('UNSAFE_OUTPUT_VECTOR')
        for name,value in recipe.get('set_sources',{}).items():
            if not re.fullmatch(IDENT,name) or not np.isfinite(value) or abs(value)>1:
                raise ResearchError('INVALID_ANALYSIS_SOURCE_SETTING')
            commands += [f'alter {name} = {value:.17g}']
        commands += ['op',*read_commands(devices,f'applied{i}'),analysis_command(recipe),
                     *read_commands(devices,f'after{i}'),f'wrdata analysis{i}.txt '+' '.join(vectors)]
    deck='\n'.join(['* APM research-local typed recipe',model_text,body,
         f'.temp {temperature_c:.17g}', '.options reltol=1e-7 abstol=1e-15 vntol=1e-9',
         '.control',*commands,'quit','.endc','.end',''])
    spinit=binary.resolve().parent.parent/'share/ngspice/scripts/spinit'
    tool={'binary':str(binary.resolve()),'sha256':digest(binary),
          'version':subprocess.check_output([str(binary),'--version'],text=True).strip(),
          'system_spinit':{'path':str(spinit),'sha256':digest(spinit) if spinit.is_file() else None},
          'num_threads':1,'environment':{'LC_ALL':'C','OMP_NUM_THREADS':'1'},
          'openvaf':'NOT_USED_NATIVE_BSIM4'}
    if not re.search(r'ngspice-47\b',tool['version']):
        raise ResearchError('REFERENCE_NGSPICE_47_REQUIRED')
    subject={'realization_id':realization['content_id'],'request':request,'input_files':manifest,
             'tool':tool,'temperature_c':temperature_c,'deck_sha256':canonical_hash(deck),
             'runner_sha256':digest(Path(__file__)), 'timeout_seconds':timeout}
    run_id=canonical_hash(subject); path=output/run_id
    if path.exists():
        try:
            report=verify(json.loads((path/'run.json').read_text()),SCHEMAS['run'])
            if report['run_id']!=run_id or report['subject']!=subject or report['status']!='PASS':
                raise ResearchError('INVALID_CACHED_STATUS_OR_IDENTITY')
            if {p.name for p in path.iterdir()} != set(report['files']) | {'run.json'}:
                raise ResearchError('CACHE_INVENTORY_MISMATCH')
            if not report['files'] or any(digest(path/f)!=h for f,h in report['files'].items()):
                raise ResearchError('CACHE_ARTIFACT_TAMPER')
            return report
        except (OSError,KeyError,ValueError) as error:
            raise ResearchError(f'CACHE_REJECTED: {error}') from error
    path.mkdir(parents=True,exist_ok=False)
    (path/'input.cir').write_text(deck)
    save(path/'realization.json',realization); save(path/'request.json',request)
    timed_out=False
    try:
        proc=subprocess.run([str(binary),'-n','-b','input.cir'],cwd=path,text=True,
            capture_output=True,timeout=timeout,check=False,
            env={**os.environ,**tool['environment']})
        stdout,stderr,code=proc.stdout,proc.stderr,proc.returncode
    except subprocess.TimeoutExpired as error:
        stdout,stderr,code=error.stdout or b'',error.stderr or b'',None
        stdout=stdout.decode(errors='replace') if isinstance(stdout,bytes) else stdout
        stderr=stderr.decode(errors='replace') if isinstance(stderr,bytes) else stderr
        timed_out=True
    (path/'stdout.txt').write_text(stdout); (path/'stderr.txt').write_text(stderr)
    log=stdout+'\n'+stderr
    errors=[m.group(0) for m in DIAGNOSTIC.finditer(log)]
    if code!=0 or timed_out or 'Using SPARSE 1.3' not in log:
        errors.append('PROCESS_TIMEOUT_EXIT_OR_SOLVER')
    errors+=read_values(log,devices,'before',np.zeros((len(devices),2)))
    for i,d in enumerate(devices):
        block=re.search(f'model_{i}_begin(.*?)model_{i}_end',log,re.DOTALL)
        if block is None or not re.search(r'\bmodel\s+'+('nmos_vtg' if d['polarity']=='n' else 'pmos_vtg')+r'\b',block[1]):
            errors.append(f'MODEL_IDENTITY/{i}')
    rows=[]
    for i,recipe in enumerate(recipes):
        errors+=read_values(log,devices,f'applied{i}',raw)+read_values(log,devices,f'after{i}',raw)
        try:
            data=np.loadtxt(path/f'analysis{i}.txt',skiprows=1,ndmin=2)
            columns=1+len(recipe['vectors'])*(2 if recipe['kind']=='ac' else 1)
            if data.shape[1]!=columns or not np.all(np.isfinite(data)) or not len(data):
                raise ResearchError('INVALID_OUTPUT_SHAPE')
            if recipe['kind']=='dc':
                axis=np.arange(round((recipe['stop']-recipe['start'])/recipe['step'])+1)*recipe['step']+recipe['start']
                if data.shape[0]!=len(axis) or not np.allclose(data[:,0],axis,rtol=0,atol=1e-10):
                    raise ResearchError('TRUNCATED_OR_INVALID_DC_AXIS')
            if recipe['kind'] in ('ac','tran') and (len(data)<2 or not np.all(np.diff(data[:,0])>0)):
                raise ResearchError('INVALID_TIME_OR_FREQUENCY_AXIS')
            rows.append(len(data))
        except (OSError,ValueError) as error:
            errors.append(str(error))
    report=seal({'schema':SCHEMAS['run'],'run_id':run_id,'subject':subject,
        'status':'FAIL' if errors else 'PASS','errors':errors,'returncode':code,
        'timed_out':timed_out,'rows':rows,'directory':str(path),
        'files':{f.name:digest(f) for f in sorted(path.iterdir()) if f.is_file()}})
    return save(path/'run.json',report)


def curve(report: dict, index: int = 0) -> tuple[np.ndarray,np.ndarray,np.ndarray]:
    if report['status']!='PASS':
        raise ResearchError('SPICE_RUN_FAILED: '+str(report['errors']))
    data=np.loadtxt(Path(report['directory'])/f'analysis{index}.txt',skiprows=1)
    return np.abs(data[:,1]),np.abs(data[:,2]),np.abs(data[:,3])


def pair_request(path: Path, polarity: str, w: float, l: float, step: float = .001,
                 vds: float = .05) -> dict:
    sign=1 if polarity=='n' else -1
    body=f'''Vs s 0 {0 if polarity=='n' else 1}
Vda da s {sign*vds}
Vdb db s {sign*vds}
Vgate g s 0
Xtop da db g s pair
.subckt pair da db g s
Xa da g s s apm045_vtg_{'nmos' if polarity=='n' else 'pmos'} w={w:.17g} l={l:.17g}
Xb db g s s apm045_vtg_{'nmos' if polarity=='n' else 'pmos'} w={w:.17g} l={l:.17g}
.ends pair
'''
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or path.read_text()!=body:
        path.write_text(body)
    devices=[{'uid':s,'path':['xtop','x'+s], 'family':'apm045/vtg','polarity':polarity,
              'w_m':w,'l_m':l} for s in ('a','b')]
    return {'schema':SCHEMAS['request'],'circuit':str(path.resolve()),'devices':devices,
        'analyses':[{'kind':'dc','source':'Vgate','start':0,'stop':sign,'step':sign*step,
                     'vectors':['v(g,s)','i(Vda)','i(Vdb)']}]}


def raw_realization(request: dict, raws) -> dict:
    return seal({'schema':SCHEMAS['realization'],'request_id':canonical_hash(request),
                 'status':'RESOLVED','origin':'research','profile_tier':'ARTIFICIAL',
                 'devices':[{**d,'raw':list(map(float,x))} for d,x in zip(request['devices'],raws)]})


def measure(root, binary, output, request, raws, *, realization=None):
    report=execute(root,binary,output,request,realization or raw_realization(request,raws))
    u,a,b=curve(report)
    return np.array([[m.vth_mg_v,m.beta_mg_a_per_v2]
                     for m in (extract_mg(u,a),extract_mg(u,b))]),report
