# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Source-aware local realizations. All public geometry and coefficients use SI."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

from .compiler_provenance import digest
from .paths import repository_root
from .research_numerics import MG_METHOD, ResearchError, canonical_hash, normal_draw

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

SCHEMAS = {x: f'apm.research-{x}.v1' for x in
           ('profile', 'request', 'realization', 'run', 'report', 'map')}
EXCLUDED = ['global', 'spatial', 'SS', 'noise', 'passives', 'yield', 'calibrated-temperature']


def save(path: Path, value: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')
    return value


def seal(value: dict) -> dict:
    return {**value, 'content_id': canonical_hash(value)}


def verify(value: dict, schema: str) -> dict:
    data = dict(value)
    key = data.pop('content_id', None)
    if data.get('schema') != schema or canonical_hash(data) != key:
        raise ResearchError('CORRUPT_OR_UNVERSIONED_RECORD')
    return value


def describe(root: Path | None = None) -> dict:
    root = root or repository_root()
    registry = tomllib.loads((root/'variation/research/apm045/sources.toml').read_text())
    return {'schema': SCHEMAS['report'], 'origin': 'research',
            'approved_profiles': registry['approved_runtime_profiles'],
            'quantitative_vtg': 'AVAILABLE' if registry['approved_runtime_profiles'] else 'SOURCE_PROFILE_UNRESOLVED',
            'artificial': 'Explicit software experiments only; acknowledgement required',
            'io18_io25': 'ASSESSMENT_ONLY; beta unknown',
            'other_families': 'UNSUPPORTED', 'included_effects': ['VTH_MG', 'beta_MG'],
            'excluded_effects': EXCLUDED, 'extraction': MG_METHOD,
            'reference': {'temperature_k': 300, 'vds_magnitude_v': .05, 'vbs_v': 0},
            'geometry': {'w_m': [1e-6,4e-6], 'l_m': [1.2e-7,4e-7]},
            'claim': 'Software statistics and transfer hypotheses are separate from measured calibration.'}


def load_profile(path: Path, *, allow_artificial: bool = False, root: Path | None = None) -> dict:
    profile = json.loads(path.read_text())
    if profile.get('schema') != SCHEMAS['profile']:
        raise ResearchError('PROFILE_SCHEMA_INVALID')
    if profile.get('tier') == 'ARTIFICIAL':
        if not allow_artificial:
            raise ResearchError('ARTIFICIAL_ACKNOWLEDGEMENT_REQUIRED')
    else:
        root = root or repository_root()
        registry = tomllib.loads((root/'variation/research/apm045/sources.toml').read_text())
        approvals=[x for x in registry['approved_runtime_profiles'] if isinstance(x,dict)
                   and x.get('sha256')==digest(path) and x.get('id')==profile.get('id')]
        if not approvals:
            raise ResearchError('SOURCE_PROFILE_UNAPPROVED')
        if digest(root/profile['source_decision']) != approvals[0]['decision_sha256']:
            raise ResearchError('SOURCE_DECISION_DRIFT')
        if digest(path.parent/'hart_tsmc40_reanalysis.json') != profile['source_dataset_sha256']:
            raise ResearchError('SOURCE_DATASET_DRIFT')
    if profile.get('rho_assumption') != 'independent-Croon' or profile.get('rho') != 0:
        raise ResearchError('UNSUPPORTED_COVARIANCE')
    if profile.get('interpolation') != 'linear-log-L@1' or set(profile['coefficients']) != {'n','p'}:
        raise ResearchError('PROFILE_COORDINATES_INVALID')
    for records in profile['coefficients'].values():
        a = np.array([[r[k] for k in ('l_m','a_vt_v_m','a_beta_m')] for r in records])
        if a.ndim != 2 or a.shape[0] < 2 or not np.all(np.isfinite(a)) or np.any(a <= 0) or np.any(np.diff(a[:,0]) <= 0):
            raise ResearchError('PROFILE_COEFFICIENT_INVALID')
        if a[0,0] > 1.2e-7 or a[-1,0] < 4e-7:
            raise ResearchError('REQUIRED_DOMAIN_UNSUPPORTED')
    return profile


def validate_devices(devices: list[dict]) -> list[dict]:
    if not isinstance(devices,list) or not devices:
        raise ResearchError('EMPTY_OR_INVALID_INSTANCE_MAP')
    uids, leaves = set(), set()
    for device in devices:
        if not isinstance(device,dict) or not {'uid','path','family','polarity','w_m','l_m'}<=device.keys():
            raise ResearchError('INCOMPLETE_INSTANCE_MAP')
        if device.get('family') != 'apm045/vtg' or device.get('polarity') not in ('n','p'):
            raise ResearchError('UNSUPPORTED_RESEARCH_DEVICE')
        uid = device.get('uid')
        if not isinstance(uid, str) or not uid or len(uid) > 256 or uid in uids:
            raise ResearchError('UID_COLLISION_OR_INVALID')
        segments = device.get('path')
        if not isinstance(segments, list) or not segments or not all(
                isinstance(s, str) and re.fullmatch(r'[xX][a-zA-Z0-9_]+', s) for s in segments):
            raise ResearchError('UNSAFE_HIERARCHY')
        leaf = '.'.join(segments).lower()
        if leaf in leaves:
            raise ResearchError('DUPLICATE_LEAF')
        uids.add(uid); leaves.add(leaf)
        w,l = device['w_m'],device['l_m']
        if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in (w,l)) or not (1e-6 <= w <= 4e-6 and 1.2e-7 <= l <= 4e-7):
            raise ResearchError('GEOMETRY_OUT_OF_SCOPE')
    return devices


def sigma(profile: dict, device: dict) -> np.ndarray:
    a = np.array([[r[k] for k in ('l_m','a_vt_v_m','a_beta_m')]
                  for r in profile['coefficients'][device['polarity']]])
    l = device['l_m']
    if not a[0,0] <= l <= a[-1,0]:
        raise ResearchError('COEFFICIENT_EXTRAPOLATION')
    return np.array([np.interp(np.log(l),np.log(a[:,0]),a[:,i]) for i in (1,2)]) / math.sqrt(2*device['w_m']*l)


def draw_device(profile: dict, device: dict, seed: int, index: int) -> dict:
    z = np.array([normal_draw(seed,index,device['uid'],channel) for channel in ('vth','beta')])
    q = z*sigma(profile,device)
    return {**device, 'z':z.tolist(), 'target':q.tolist(),
        'latent_draw_id':canonical_hash({'seed':seed,'index':index,'uid':device['uid'],'z':z.tolist()}),
        'status': 'OUT_OF_SCOPE' if np.max(np.abs(z)) > 6 or q[1] <= -1 else 'DRAWN'}


def sample(profile: dict, request: dict, seed: int, index: int, mapper) -> dict:
    if request.get('schema') != SCHEMAS['request']:
        raise ResearchError('REQUEST_SCHEMA_INVALID')
    devices = validate_devices(request['devices'])
    assigned = {'.'.join(d['path']).lower() for d in devices}
    for other in request.get('other_variation_leaves', []):
        if other.lower() in assigned:
            raise ResearchError('VARIATION_DOUBLE_COUNTING')
    from .research_spice import MODELS, flatten
    binding={}
    flatten(Path(request['circuit']),binding)
    for relative in MODELS:
        flatten(repository_root()/relative,binding)
    realized = []
    for device in devices:
        item = draw_device(profile,device,seed,index)
        if item['status'] == 'DRAWN':
            try:
                raw, mapping_id = mapper(device,np.array(item['target']))
                if np.shape(raw) != (2,) or not np.all(np.isfinite(raw)):
                    raise ResearchError('NONFINITE_RAW_MAPPING')
                item.update(raw=list(map(float,raw)), mapping_id=mapping_id, status='RESOLVED')
            except ResearchError as error:
                item.update(status='MAPPING_FAILED',error=str(error))
        item['device_realization_id'] = canonical_hash({'profile':profile,'device':item})
        realized.append(item)
    return seal({'schema':SCHEMAS['realization'], 'profile_id':canonical_hash(profile),
        'profile_tier':profile['tier'],'origin':'research','excluded_effects':EXCLUDED,
        'request_id':canonical_hash(request),'input_binding':binding,'seed':seed,'sample_index':index,
        'devices':realized,'status':'RESOLVED' if all(d['status']=='RESOLVED' for d in realized) else 'FAILED'})
