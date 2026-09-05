# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

from apm import research as r
from apm.research_spice import execute, pair_request, raw_realization

ROOT=Path(__file__).resolve().parents[1]


def fixture():
    return r.load_profile(ROOT/'tests/fixtures/research/artificial.json',allow_artificial=True)


def device():
    return {'uid':'physical/one','path':['xtop','xa'],'family':'apm045/vtg',
            'polarity':'n','w_m':1e-6,'l_m':1.2e-7}


def test_profiles_require_explicit_adoption(tmp_path):
    with pytest.raises(r.ResearchError,match='ACKNOWLEDGEMENT'):
        r.load_profile(ROOT/'tests/fixtures/research/artificial.json')
    p=fixture();p['tier']='APPROVED';f=tmp_path/'forged.json';r.save(f,p)
    with pytest.raises(r.ResearchError,match='UNAPPROVED'):r.load_profile(f)


@pytest.mark.parametrize('case',['uid','leaf','syntax','geometry','family'])
def test_invalid_instance_maps_fail(case):
    a=device();b=copy.deepcopy(a);b['uid']='second';b['path']=['xtop','xb']
    if case=='uid':b['uid']=a['uid']
    if case=='leaf':b['path']=['XTOP','XA']
    if case=='syntax':b['path']=['xtop','xa\nreset']
    if case=='geometry':b['l_m']=float('nan')
    if case=='family':b['family']='apm045/io18'
    with pytest.raises(r.ResearchError):r.validate_devices([a,b])


def test_length_interpolation_and_width_law():
    a=device();b={**a,'w_m':4e-6}
    assert np.array_equal(r.sigma(fixture(),a)/2,r.sigma(fixture(),b))
    b={**a,'l_m':np.sqrt(1.2e-7*4e-7)}
    assert r.sigma(fixture(),b)[0]*np.sqrt(2*b['w_m']*b['l_m'])==pytest.approx(5e-9)


def test_draw_identity_ignores_geometry_and_source_but_realization_changes():
    a=device();b={**a,'w_m':2e-6}
    x,y=[r.draw_device(fixture(),d,99,2) for d in (a,b)]
    assert x['z']==y['z'] and x['latent_draw_id']==y['latent_draw_id']
    assert x['target']!=y['target']


def test_failed_draw_is_persisted_without_mapping_or_redraw(monkeypatch):
    monkeypatch.setattr(r,'normal_draw',lambda *args:7.0)
    q={'schema':r.SCHEMAS['request'],'devices':[device()],'circuit':str(ROOT/'examples/research/mirror.cir')}
    result=r.sample(fixture(),q,1,0,lambda *args:pytest.fail('out of domain reached mapper'))
    assert result['status']=='FAILED' and result['devices'][0]['z']==[7,7]
    assert result['devices'][0]['status']=='OUT_OF_SCOPE'


def test_double_counting_and_corrupt_sample_rejected():
    q={'schema':r.SCHEMAS['request'],'devices':[device()],'other_variation_leaves':['xtop.xa']}
    with pytest.raises(r.ResearchError,match='DOUBLE_COUNTING'):r.sample(fixture(),q,1,0,None)
    value=r.seal({'schema':r.SCHEMAS['realization'],'raw':[0,0]});value['raw'][0]=.1
    with pytest.raises(r.ResearchError,match='CORRUPT'):r.verify(value,r.SCHEMAS['realization'])


def test_typed_recipe_executes_and_cache_tamper_fails(tmp_path):
    q=pair_request(tmp_path/'pair.cir','n',1e-6,1.2e-7,.01)
    v=raw_realization(q,[[.01,.02],[0,0]])
    report=execute(ROOT,Path('/usr/local/bin/ngspice'),tmp_path/'runs',q,v)
    assert report['status']=='PASS',report['errors']
    assert execute(ROOT,Path('/usr/local/bin/ngspice'),tmp_path/'runs',q,v)==report
    (Path(report['directory'])/'analysis0.txt').write_text('tamper')
    with pytest.raises(r.ResearchError,match='CACHE_REJECTED'):
        execute(ROOT,Path('/usr/local/bin/ngspice'),tmp_path/'runs',q,v)


def test_bad_path_zero_exit_is_not_success(tmp_path):
    q=pair_request(tmp_path/'pair.cir','n',1e-6,1.2e-7,.01)
    q['devices'][0]['path']=['xtop','xmissing']
    report=execute(ROOT,Path('/usr/local/bin/ngspice'),tmp_path/'runs',q,
                   raw_realization(q,[[.01,.02],[0,0]]))
    assert report['returncode']==0
    assert report['status']=='FAIL' and 'MODEL_IDENTITY/0' in report['errors']
    assert any('no such' in e.lower() for e in report['errors'])
