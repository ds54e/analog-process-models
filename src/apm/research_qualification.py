# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Executable v5 engineering confirmation. Numerical success is not source accuracy."""
from __future__ import annotations

import copy
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.stats import chi2, kstest

from .compiler_provenance import digest
from .research import SCHEMAS, load_profile, sample, save, seal, sigma
from .research_mapping import ReferenceMapper, observable
from .research_numerics import ResearchError, aggregate_tail_risk, normal_draw, pair_relative
from .research_spice import curve, execute, measure, pair_request, raw_realization

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def geometries(plan):
    return [(w,l) for w in plan['w_um'] for l in plan['l_um']]+[tuple(x) for x in plan['holdouts_um']]


def sigma_interval(values,alpha):
    n=len(values);s=np.std(values,ddof=1)
    return (s*np.sqrt((n-1)/chi2.ppf([1-alpha/2,alpha/2],n-1))).tolist()


def bootstrap_sigma(values,seed,n):
    rng=np.random.Generator(np.random.PCG64(seed));stats=[]
    for start in range(0,n,64):
        x=values[rng.integers(len(values),size=(min(64,n-start),len(values)))]
        stats.extend(x.std(axis=1,ddof=1))
    return np.quantile(stats,[.025,.975]).tolist()


def pure_sampler(plan,profile,output):
    n=plan['pure_pairs'];seed=plan['sampler_seed']
    z=np.array([[[normal_draw(seed,i,u,c) for c in ('vth','beta')] for u in ('a','b')] for i in range(n)])
    np.savez_compressed(output/'draws.npz',z=z)
    checks={};records=[]
    a={'polarity':'n','w_m':1e-6,'l_m':1.2e-7}
    for label,b in [('equal',a),('unequal_width',{**a,'w_m':4e-6}),('unequal_length',{**a,'l_m':4e-7})]:
        sa,sb=sigma(profile,a),sigma(profile,b)
        q=z[:,0]*sa-z[:,1]*sb;expected=np.sqrt(sa*sa+sb*sb)
        ci=np.array([sigma_interval(q[:,k],.05/16) for k in (0,1)])/expected[:,None]
        checks[label]=bool(np.all(ci>=.98) and np.all(ci<=1.02)
            and np.max(np.abs(q.mean(axis=0))/expected)<.02 and abs(np.corrcoef(q.T)[0,1])<.02)
        records.append({'case':label,'sigma_ratio_ci':ci.tolist(),'means_over_sigma':(q.mean(axis=0)/expected).tolist()})
    checks['normal_marginals']=all(kstest(z[:,i,j],'norm').pvalue>.05/16 for i in (0,1) for j in (0,1))
    checks['independent_devices']=all(abs(np.corrcoef(z[:,0,j],z[:,1,j])[0,1])<.02 for j in (0,1))
    checks['width_law']=bool(np.array_equal(sigma(profile,{**a,'w_m':4e-6}),sigma(profile,a)/2))
    keys=[('a','vth'),('b','beta'),('added','vth')]
    one={k:normal_draw(seed,3,*k) for k in keys[:2]}
    with ThreadPoolExecutor(4) as pool:
        reordered=dict(zip(reversed(keys),pool.map(lambda k:normal_draw(seed,3,*k),reversed(keys))))
    checks['reorder_insert_workers']=all(one[k]==reordered[k] for k in one)
    return {'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,
            'requested_pairs':n,'executed_pairs':n,'failed_pairs':0,'records':records,
            'draws_sha256':digest(output/'draws.npz'),'tier':'ARTIFICIAL_ONLY'}


def mapping_checks(root,binary,plan,profile,mapper,output):
    records=[];rng=np.random.Generator(np.random.PCG64(plan['mapping_seed']))
    targets=[(0,0),(-6,0),(6,0),(0,-6),(0,6),(-6,-6),(-6,6),(6,-6),(6,6)]
    targets+=list(map(tuple,rng.uniform(-5.8,5.8,(17,2))))
    for pol in plan['polarity']:
        for w,l in geometries(plan):
            name=f'{pol}-{w:g}-{l:g}'; folder=output/name;folder.mkdir(exist_ok=True)
            d={'family':'apm045/vtg','polarity':pol,'w_m':w*1e-6,'l_m':l*1e-6}
            item={'polarity':pol,'w_um':w,'l_um':l,'requested':len(targets),'cases':[]}
            try:
                mapping=mapper.calibrate(d);scales=np.array(mapping['sigma'])
                fine=pair_request(folder/'fine.cir',pol,d['w_m'],d['l_m'],plan['mapping_fine_step_v'])
                base,bref=measure(root,binary,folder/'runs',fine,[[0,0],[0,0]])
                _,_,twin=curve(bref)
                grid=np.abs(observable(base[0],np.array(mapping['nominal'])))/scales
                item.update(condition=mapping['condition'],half_step=mapping['half_step_relative_change'],
                            extraction_error_over_sigma=grid.tolist(),mapping_id=mapping['content_id'])
                for latent in targets:
                    target=scales*latent;raw,_=mapper.predict(d,target)
                    actual,report=measure(root,binary,folder/'runs',fine,[raw,[0,0]])
                    error=np.abs(observable(actual[0],np.array(mapping['nominal']))-target)/scales
                    same=bool(np.array_equal(curve(report)[2],twin))
                    item['cases'].append({'z':list(latent),'raw':raw.tolist(),'error_over_sigma':error.tolist(),
                        'twin_equal':same,'run':report['run_id'],'report_sha256':digest(Path(report['directory'])/'run.json'),
                        'status':'PASS' if np.max(error)<=.02 and same else 'FAIL'})
                item['status']='PASS' if np.max(grid)<=.005 and all(x['status']=='PASS' for x in item['cases']) else 'FAIL'
            except (ResearchError,OSError,ValueError) as error:
                item.update(status='FAIL',error=str(error))
            records.append(item);save(folder/'summary.json',item)
            print(f'mapping {name}: {item["status"]}',flush=True)
    controls=application_controls(root,binary,output/'controls')
    risk=aggregate_tail_risk(plan['campaign_scalar_draws'],plan['latent_limit'])
    return {'status':'PASS' if records and all(x['status']=='PASS' for x in records)
            and controls['status']=='PASS' and risk['expected_count']<=plan['campaign_risk_max'] else 'FAIL',
            'records':records,'controls':controls,'tail_risk':risk,'source_tier':profile['tier']}


def two_bias_request(folder,pol,w,l,step):
    request=pair_request(folder/'pair.cir',pol,w,l,step)
    request['analyses'].append(copy.deepcopy(request['analyses'][0]))
    sign=1 if pol=='n' else -1
    request['analyses'][1]['set_sources']={'Vda':sign*.5,'Vdb':sign*.5}
    return request


def statistics_geometry(root,binary,plan,profile,mapper,output,pol,w,l):
    output.mkdir(parents=True,exist_ok=True)
    d={'family':'apm045/vtg','polarity':pol,'w_m':w*1e-6,'l_m':l*1e-6}
    mp=mapper.calibrate(d); nominal=np.array(mp['nominal']);scales=np.array(mp['sigma'])
    req=two_bias_request(output,pol,d['w_m'],d['l_m'],plan['statistics_step_v'])
    for x in req['devices']:x['uid']=f'{pol}/{w}/{l}/{x["uid"]}'
    baseline=execute(root,binary,output/'runs',req,raw_realization(req,[[0,0],[0,0]]))
    biases=[];nomcurves=[]
    for index in (0,1):
        u,a,b=curve(baseline,index);sp=CubicSpline(u,a);gmid=sp.derivative()(u)/np.maximum(a,1e-30)
        nomcurves.append((u,a))
        for value in plan['cross_bias_gm_id']:
            candidates=np.flatnonzero((gmid[:-1]>=value)&(gmid[1:]<value))
            if not len(candidates):
                biases.append({'vds_index':index,'gm_id':value,'status':'UNREACHABLE'});continue
            k=candidates[-1]; gate=float(np.interp(value,gmid[k:k+2][::-1],u[k:k+2][::-1]))
            biases.append({'vds_index':index,'gm_id':value,'gate':gate,'nominal_current':float(sp(gate)),'status':'REACHABLE'})
    sensitivities=[]
    for axis,h in enumerate((.001,.01)):
        hs=[]
        for sign in (-1,1):
            raw=np.zeros(2);raw[axis]=sign*h
            r=execute(root,binary,output/'runs',req,raw_realization(req,[raw,[0,0]]))
            hs.append([float(CubicSpline(*curve(r,b['vds_index'])[:2])(b['gate'])) if b['status']=='REACHABLE' else 0 for b in biases])
        sensitivities.append((np.array(hs[1])-hs[0])/(2*h))
    sensitivity=np.array(sensitivities).T@np.linalg.inv(np.array(mp['jacobian']))
    seed=plan['statistics_seed'];n=plan['spice_pairs_per_geometry_polarity']
    def run(index):
        try:
            def resolve(d,q):
                raw,mp=mapper.predict(d,q)
                return raw,mp['content_id']
            realized=sample(profile,req,seed,index+plan['sample_index_start'],resolve)
            draws=realized['devices']
            if realized['status']!='RESOLVED':
                return {'index':index,'status':'OUT_OF_SCOPE','realization':realized}
            raws=[x['raw'] for x in draws]
            values,report=measure(root,binary,output/'runs',req,raws,realization=realized)
            q=np.array([observable(v,nominal) for v in values]);target=np.array([x['target'] for x in draws])
            currents=[]
            for b in biases:
                if b['status']!='REACHABLE':currents.append([0,0]);continue
                u,a,c=curve(report,b['vds_index'])
                currents.append([float(CubicSpline(u,j)(b['gate'])) for j in (a,c)])
            return {'index':index,'status':'PASS' if np.max(np.abs(q-target)/scales)<=.02 else 'MAPPING_RESIDUAL',
                    'q':q.tolist(),'target':target.tolist(),'currents':currents,'run':report['run_id'],
                    'report_sha256':digest(Path(report['directory'])/'run.json')}
        except (ResearchError,OSError,ValueError) as error:
            failed_report=getattr(error,'run_report',None)
            binding={'run':failed_report['run_id'],
                     'report_sha256':digest(Path(failed_report['directory'])/'run.json')} if failed_report else {}
            return {'index':index,'status':'FAIL','error':str(error),**binding}
    with ThreadPoolExecutor(plan['workers']) as pool:rows=list(pool.map(run,range(n)))
    save(output/'cohort.json',{'requested':n,'rows':rows})
    failed=[x for x in rows if x['status']!='PASS']
    result={'polarity':pol,'w_um':w,'l_um':l,'requested_pairs':n,'executed_pairs':sum('run' in x for x in rows),'attempted_pairs':len(rows),
            'failed_pairs':len(failed),'cohort_sha256':digest(output/'cohort.json')}
    if failed:
        return {**result,'status':'FAIL','failures':failed[:10]}
    q=np.array([x['q'] for x in rows]);target=np.array([x['target'] for x in rows]); currents=np.array([x['currents'] for x in rows])
    diff=q[:,0]-q[:,1];expected=scales*np.sqrt(2)
    alpha=plan['simultaneous_alpha']/(2*len(geometries(plan))*2)
    ci=np.array([sigma_interval(diff[:,k],alpha) for k in (0,1)])/expected[:,None]
    ratio=pair_relative(1+q[:,0,1],1+q[:,1,1]);target_ratio=pair_relative(1+target[:,0,1],1+target[:,1,1])
    ratio_ci=bootstrap_sigma(ratio,plan['bootstrap_seed'],plan['ratio_bootstrap_replicates'])
    for i,b in enumerate(biases):
        if b['status']!='REACHABLE':continue
        obs=pair_relative(currents[:,i,0],currents[:,i,1]);s=sensitivity[i]/b['nominal_current']
        actual_prediction=float(np.sqrt(np.sum((s*expected)**2)))
        croon=float(np.hypot(expected[1],b['gm_id']*expected[0]))
        measured=float(np.std(obs,ddof=1))
        b.update(sensitivity=s.tolist(),observed_sigma=measured,sensitivity_sigma=actual_prediction,
                 croon_sigma=croon,sensitivity_ratio=measured/actual_prediction,croon_ratio=measured/croon,
                 valid_sensitivity_region=.8<=measured/actual_prediction<=1.2)
    checks={'simultaneous_sigma_equivalence':bool(np.all(ci>=.9) and np.all(ci<=1.1)),
            'means':bool(np.max(np.abs(diff.mean(axis=0))/expected)<.1),
            'covariance':abs(float(np.corrcoef(diff.T)[0,1]))<.1,
            'nonlinear_ratio_recovery':abs(float(np.std(ratio)/np.std(target_ratio))-1)<.02}
    result.update(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,
        sigma_ratio_ci=ci.tolist(),mean_over_sigma=(diff.mean(axis=0)/expected).tolist(),
        nonlinear_ratio_sigma=float(np.std(ratio,ddof=1)),nonlinear_ratio_95ci=ratio_ci,
        nonlinear_over_linear_sigma=float(np.std(ratio,ddof=1)/expected[1]),cross_bias=biases)
    return result


def statistics_checks(root,binary,plan,profile,mapper,output):
    records=[]
    for pol in plan['polarity']:
        for w,l in geometries(plan):
            name=f'{pol}-{w:g}-{l:g}'
            try:
                result=statistics_geometry(root,binary,plan,profile,mapper,output/name,pol,w,l)
            except (ResearchError,OSError,ValueError) as error:
                result={'polarity':pol,'w_um':w,'l_um':l,'status':'FAIL','error':str(error)}
            records.append(result);save(output/name/'summary.json',result)
            print(f'statistics {name}: {result["status"]}',flush=True)
    return {'status':'PASS' if records and all(r['status']=='PASS' for r in records) else 'FAIL','records':records}


def qualify(root,binary,output,suite):
    planpath=root/'validation/v5_confirmation_plan.toml'
    plan=tomllib.loads(planpath.read_text());head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    committed=subprocess.check_output(['git','show',head+':validation/v5_confirmation_plan.toml'],cwd=root)
    if committed!=planpath.read_bytes():raise ResearchError('COMMITTED_CONFIRMATION_PLAN_REQUIRED')
    profile=load_profile(root/plan['profile']);artificial=load_profile(root/plan['artificial_profile'],allow_artificial=True)
    output.mkdir(parents=True,exist_ok=True)
    mapper=ReferenceMapper(root,binary,output/'maps',profile)
    stages=('sampler','mapping','statistics','circuits','replay','io') if suite=='all' else (suite,)
    results={}
    for stage in stages:
        folder=output/stage;folder.mkdir(exist_ok=True)
        if stage=='sampler':result=pure_sampler(plan,artificial,folder)
        elif stage=='mapping':result=mapping_checks(root,binary,plan,profile,mapper,folder)
        elif stage=='statistics':result=statistics_checks(root,binary,plan,profile,mapper,folder)
        else:
            from .research_circuits import circuit_checks, io_assessment, replay_checks
            function={'circuits':circuit_checks,'io':io_assessment,'replay':replay_checks}[stage]
            result=function(root,binary,plan,profile,mapper,folder)
        result.update(schema=SCHEMAS['report'],subject_commit=head,plan_sha256=digest(planpath),
                      profile_sha256=digest(root/plan['profile']),stage=stage)
        save(folder/'report.json',seal(result));results[stage]={'status':result['status'],'report':str(folder/'report.json'),'sha256':digest(folder/'report.json')}
    return save(output/f'{suite}-index.json',{'schema':SCHEMAS['report'],'subject_commit':head,
        'status':'PASS' if results and all(r['status']=='PASS' for r in results.values()) else 'FAIL','stages':results})


def application_controls(root,binary,output):
    """A negative control passes only on its specific observed mechanism."""
    from .research import validate_devices, verify
    from .research_circuits import logged_deck
    from .research_spice import read_values
    records=[]
    for pol in ('n','p'):
        folder=output/pol;folder.mkdir(parents=True,exist_ok=True)
        request=pair_request(folder/'pair.cir',pol,1e-6,1.2e-7,.01)
        raw=[[.02,float(np.log(1.05))],[0,0]]
        good=execute(root,binary,folder/'runs',request,raw_realization(request,raw))
        for kind in ('path','geometry','model'):
            q=copy.deepcopy(request)
            if kind=='path':q['devices'][0]['path']=['xtop','xmissing']
            if kind=='geometry':q['devices'][0]['w_m']=2e-6
            if kind=='model':q['devices'][0]['polarity']='p' if pol=='n' else 'n'
            r=execute(root,binary,folder/'runs',q,raw_realization(q,raw))
            mechanism=(any('no such' in x.lower() for x in r['errors']) if kind=='path'
                else any('before/0/w:' in x for x in r['errors']) if kind=='geometry'
                else 'MODEL_IDENTITY/0' in r['errors'])
            records.append({'polarity':pol,'control':kind,'status':'PASS' if r['status']=='FAIL' and mechanism else 'FAIL',
                            'observed_mechanism':r['errors'],'returncode':r['returncode'],'run':r['run_id'],
                            'report_sha256':digest(Path(r['directory'])/'run.json')})
        # Inject reset into a captured valid deck, preserving pre-reset readback.
        source=Path(good['directory'])/'input.cir'
        deck=source.read_text().replace('dc Vgate','reset\ndc Vgate')
        r=logged_deck(binary,folder/'reset',deck)
        log=(folder/'reset/stdout.txt').read_text()+(folder/'reset/stderr.txt').read_text()
        applied=not read_values(log,request['devices'],'applied0',raw)
        lost=bool(read_values(log,request['devices'],'after0',raw))
        restored=not read_values(log,request['devices'],'after0',np.zeros((2,2)))
        records.append({'polarity':pol,'control':'reset','status':'PASS' if applied and lost and restored else 'FAIL',
            'before_reset_applied':applied,'after_reset_requested_values_lost':lost,
            'after_reset_nominal_values_restored':restored,'report_sha256':digest(folder/'reset/run.json')})
        for kind in ('duplicate_uid','duplicate_leaf','corrupt_sample','corrupt_cache','timeout'):
            ok=False;detail=''
            try:
                if kind.startswith('duplicate'):
                    q=copy.deepcopy(request)
                    key='uid' if kind=='duplicate_uid' else 'path'
                    q['devices'][1][key]=q['devices'][0][key]
                    validate_devices(q['devices'])
                elif kind=='corrupt_sample':
                    sample=raw_realization(request,raw);sample['devices'][0]['raw'][0]+=.01
                    verify(sample,SCHEMAS['realization'])
                elif kind=='corrupt_cache':
                    r=execute(root,binary,folder/'tamper',request,raw_realization(request,raw))
                    (Path(r['directory'])/'analysis0.txt').write_text('intentional fault injection\n')
                    execute(root,binary,folder/'tamper',request,raw_realization(request,raw))
                else:
                    r=execute(root,binary,folder/'timeout',request,raw_realization(request,raw),timeout=1e-9)
                    ok=r['timed_out'] and r['status']=='FAIL';detail=str(r['errors'])
            except ResearchError as error:
                detail=str(error)
                expected={'duplicate_uid':'UID_COLLISION','duplicate_leaf':'DUPLICATE_LEAF',
                          'corrupt_sample':'CORRUPT','corrupt_cache':'CACHE_REJECTED','timeout':'NEVER_ACCEPT_EXCEPTION'}
                ok=expected[kind] in detail
            records.append({'polarity':pol,'control':kind,'status':'PASS' if ok else 'FAIL','observed_mechanism':detail})
    return {'status':'PASS' if all(r['status']=='PASS' for r in records) else 'FAIL','records':records}
