# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest

from apm import compiler_provenance as cp
from apm.model_build import _cached_build
from apm.toolchain import Toolchain


def receipt_fixture(tmp_path,monkeypatch):
    binary=tmp_path/'bin/openvaf-r';binary.parent.mkdir();binary.write_bytes(b'controlled compiler')
    state={'commit':cp.EXPECTED_COMMIT,'tree':'test-tree','dirty':'','submodules':''}
    monkeypatch.setattr(cp,'source_state',lambda source:state.copy())
    (tmp_path/'configuration.json').write_text('{}')
    (tmp_path/'build.log').write_text('controlled successful build')
    receipt={'schema':cp.SCHEMA,'before':state,'after':state,'source_path':str(tmp_path/'source'),
        'binary_sha256':cp.digest(binary),'configuration':{},
        'configuration_sha256':cp.digest(tmp_path/'configuration.json'),
        'build_log_sha256':cp.digest(tmp_path/'build.log'),'returncode':0}
    path=tmp_path/'receipt.json'
    path.write_text(json.dumps({**receipt,'receipt_id':cp.identity(receipt)}))
    return binary,path,state


def test_missing_receipt_is_unverified(tmp_path):
    p=tmp_path/'binary';p.write_bytes(b'unknown')
    assert cp.observe_compiler(p)['status']=='UNVERIFIED'


@pytest.mark.parametrize('mutation',['binary','source','configuration','log','pin','receipt'])
def test_observed_provenance_rejects_drift(tmp_path,monkeypatch,mutation):
    binary,path,state=receipt_fixture(tmp_path,monkeypatch)
    assert cp.observe_compiler(binary,path)['status']=='VERIFIED'
    if mutation=='binary': binary.write_bytes(b'changed binary')
    if mutation=='source': state['dirty']=' M file'
    if mutation=='configuration': (tmp_path/'configuration.json').write_text('{"flags":"other"}')
    if mutation=='log': (tmp_path/'build.log').write_text('not bound')
    if mutation in ('pin','receipt'):
        r=json.loads(path.read_text());r.pop('receipt_id')
        if mutation=='pin':
            r['before']['commit']=r['after']['commit']='0'*40
            state['commit']='0'*40
        r['receipt_id']=cp.identity(r) if mutation=='pin' else 'false seal'
        path.write_text(json.dumps(r))
    assert cp.observe_compiler(binary,path)['status']=='UNVERIFIED'


def test_legacy_asserted_cache_is_never_reused(tmp_path):
    binary=tmp_path/'openvaf';binary.write_bytes(b'unknown')
    t=Toolchain(tmp_path,tmp_path,tmp_path/'ngspice',binary,())
    t.osdi_directory.mkdir(parents=True)
    (t.osdi_directory/'build.json').write_text(json.dumps({'schema':'apm.model-build.v2'}))
    assert _cached_build(t) is None


def test_bound_cache_rejects_changed_osdi(tmp_path,monkeypatch):
    from apm import model_build as mb
    binary,path,_=receipt_fixture(tmp_path,monkeypatch)
    t=Toolchain(tmp_path,tmp_path,tmp_path/'ngspice',binary,())
    monkeypatch.setattr(mb,'MODEL_SOURCES',{'fixture':Path('model/code.va')})
    source=tmp_path/'model/code.va';source.parent.mkdir();source.write_text('pinned model')
    t.osdi_directory.mkdir(parents=True)
    osdi=t.osdi_directory/'fixture.osdi';osdi.write_bytes(b'compiled source')
    meta={'schema':'apm.model-build.v3','openvaf_sha256':cp.digest(binary),
          'compiler_provenance':cp.observe_compiler(binary,path),
          'artifacts':[{'model_id':'fixture','output':str(osdi),
             'source_manifest_sha256':{'code.va':cp.digest(source)},'output_sha256':cp.digest(osdi)}]}
    (t.osdi_directory/'build.json').write_text(json.dumps(meta))
    assert mb._cached_build(t)['cache_status']=='verified_reuse'
    osdi.write_bytes(b'tampered')
    assert mb._cached_build(t) is None
