# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""N/P-specific reference mapping; no remapping at a circuit operating point."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .compiler_provenance import digest
from .research import SCHEMAS, save, seal, sigma, verify
from .research_numerics import (
    MAPPING_METHOD,
    MG_METHOD,
    ResearchError,
    canonical_hash,
    local_jacobian,
)
from .research_spice import MODELS, measure, pair_request, spice_context

POWERS = [(i,j) for i in range(6) for j in range(6-i)]


def features(q):
    return np.array([q[0]**i*q[1]**j for i,j in POWERS])


def observable(values, nominal):
    return np.array([values[0]-nominal[0],values[1]/nominal[1]-1])


class ReferenceMapper:
    def __init__(self, root: Path, binary: Path, output: Path, profile: dict):
        self.root,self.binary,self.output,self.profile=root,binary,output,profile
        self.maps={}
        self.tool=spice_context(binary)

    def calibrate(self, device):
        geometry={k:device[k] for k in ('polarity','w_m','l_m','family')}
        if str(self.binary.resolve())!=self.tool['binary'] or digest(self.binary)!=self.tool['sha256'] or digest(Path(self.tool['system_spinit']['path']))!=self.tool['system_spinit']['sha256']:
            raise ResearchError('SIMULATOR_CHANGED_DURING_MAPPING')
        subject={'geometry':geometry,'profile':self.profile,'method':MAPPING_METHOD,
            'extractor':MG_METHOD,'tool':self.tool,
            'model_hashes':{p:digest(self.root/p) for p in MODELS},
            'implementation':{p:digest(Path(__file__).parent/p) for p in
                              ('research.py','research_mapping.py','research_numerics.py','research_spice.py')}}
        key=canonical_hash(subject)
        if key in self.maps:
            return self.maps[key]
        folder=self.output/key; cache=folder/'map.json'
        if folder.exists():
            try:
                mapping=verify(json.loads(cache.read_text()),SCHEMAS['map'])
                if mapping['subject']!=subject or mapping['status']!='PASS':
                    raise ResearchError('MAPPING_CACHE_IDENTITY')
                # The acquisition receipts are part of calibration, not optional logs.
                if any(digest(Path(p))!=h for p,h in mapping['evidence'].items()):
                    raise ResearchError('MAPPING_CACHE_EVIDENCE')
                for p in mapping['evidence']:
                    acquisition=json.loads(Path(p).read_text())
                    if any(digest(Path(p).parent/f)!=h for f,h in acquisition['files'].items()):
                        raise ResearchError('MAPPING_RAW_EVIDENCE_TAMPER')
                self.maps[key]=mapping
                return mapping
            except (ValueError,KeyError,OSError) as error:
                raise ResearchError(f'MAPPING_CACHE_REJECTED: {error}') from error
        folder.mkdir(parents=True)
        request=pair_request(folder/'reference.cir',device['polarity'],device['w_m'],device['l_m'])
        values,report=measure(self.root,self.binary,folder/'runs',request,[[0,0],[0,0]])
        nominal=values[0]; twin_nominal=values[1]; scales=sigma(self.profile,device)
        evidence={str(Path(report['directory'])/'run.json'):digest(Path(report['directory'])/'run.json')}
        def forward(x):
            values,r=measure(self.root,self.binary,folder/'runs',request,[x,[0,0]])
            evidence[str(Path(r['directory'])/'run.json')]=digest(Path(r['directory'])/'run.json')
            if not np.array_equal(values[1],twin_nominal):
                raise ResearchError('UNTOUCHED_TWIN_CHANGED')
            return observable(values[0],nominal)
        h=np.array([.001,.01])
        jac,cond=local_jacobian(forward,h,scales)
        half,_=local_jacobian(forward,h/2,scales)
        delta=float(np.linalg.norm((jac-half)*h/scales[:,None])/np.linalg.norm(jac*h/scales[:,None]))
        if cond>100 or delta>.02:
            raise ResearchError('MAPPING_ILL_CONDITIONED_OR_STEP_UNSTABLE')
        bounds=1.15*np.abs(np.linalg.inv(jac))@(6*scales)
        if bounds[0]>.15 or bounds[1]>.5:
            raise ResearchError('TAIL_RAW_BOUND_EXCEEDED')
        train=[]; raws=[]
        for a in np.linspace(-1,1,7):
            for b in np.linspace(-1,1,7):
                x=bounds*np.array([a,b]); q=forward(x)
                train.append(features(q/(6*scales)));raws.append(x)
        coefficients=np.linalg.lstsq(train,raws,rcond=None)[0]
        # Remove a tiny intercept so the nominal device is exactly nominal.
        coefficients[0]=0
        mapping=seal({'schema':SCHEMAS['map'],'subject':subject,'status':'PASS',
            'nominal':nominal.tolist(),'sigma':scales.tolist(),'raw_bounds':bounds.tolist(),
            'jacobian':jac.tolist(),'half_step_relative_change':delta,'condition':cond,
            'coefficients':coefficients.tolist(),'evidence':evidence,
            'qualification':'DEVELOPMENT_MAP; held-out and source qualification are separate'})
        save(cache,mapping);self.maps[key]=mapping
        return mapping

    def predict(self, device, q):
        mapping=self.calibrate(device)
        scales=np.array(mapping['sigma'])
        if np.shape(q)!=(2,) or not np.all(np.isfinite(q)) or q[1]<=-1 or np.max(np.abs(q/scales))>6+1e-12:
            raise ResearchError('TARGET_OUT_OF_DECLARED_DOMAIN')
        raw=features(q/(6*scales))@np.array(mapping['coefficients'])
        if np.any(np.abs(raw)>np.array(mapping['raw_bounds'])):
            raise ResearchError('RAW_OUT_OF_MAPPING_DOMAIN')
        return raw,mapping

    def __call__(self, device, q):
        raw,mapping=self.predict(device,q)
        folder=self.output/mapping['content_id']/'verification'
        request=pair_request(folder/'reference.cir',device['polarity'],device['w_m'],device['l_m'],.0005)
        for _ in range(3):
            values,_=measure(self.root,self.binary,folder/'runs',request,[raw,[0,0]])
            actual=observable(values[0],np.array(mapping['nominal']))
            residual=actual-q
            if np.max(np.abs(residual)/np.array(mapping['sigma']))<=.02:
                return raw,mapping['content_id']
            raw=raw-np.linalg.solve(np.array(mapping['jacobian']),residual)
            if np.any(np.abs(raw)>np.array(mapping['raw_bounds'])):
                raise ResearchError('RAW_CORRECTION_OUT_OF_DOMAIN')
        raise ResearchError('MAPPING_RESIDUAL_EXCEEDED')
