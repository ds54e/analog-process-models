# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Bounded circuit, replay and IO-transfer experiments for the v5 contract."""
from __future__ import annotations

import json
import math
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline

from .compiler_provenance import digest
from .research import SCHEMAS, sample, save, sigma
from .research_numerics import ResearchError, extract_mg, pair_relative
from .research_spice import DIAGNOSTIC, curve, execute, pair_request, raw_realization, spice_context


def circuit_request(folder,pol,kind,gate,current):
    w,l=1e-6,2.4e-7
    model=f'apm045_vtg_{"nmos" if pol=="n" else "pmos"}'
    rail=0 if pol=='n' else 1
    lines=['Vdd vdd 0 1',f'Vs s 0 {rail}']; devices=[]
    def mos(name,drain,gate_node,source,width=w):
        lines.append(f'X{name} {drain} {gate_node} {source} {source} {model} w={width:.17g} l={l:.17g}')
        devices.append({'uid':f'{pol}/{kind}/{name}','path':['xtop','x'+name],
            'family':'apm045/vtg','polarity':pol,'w_m':width,'l_m':l})
    if kind.startswith('mirror'):
        factor=int(kind[6:])
        lines += [f'Iref vdd ref {current}' if pol=='n' else f'Iref ref 0 {current}',
                  'Vout out 0 .5','.subckt circuit ref out s']
        mos('ref','ref','ref','s');mos('out','out','ref','s',w*factor)
        lines+=['.ends circuit','Xtop ref out s circuit']
        recipe={'kind':'op','vectors':['v(ref)','i(Vout)']}
    elif kind.startswith('bank'):
        units=int(kind[4:]);u=gate if pol=='n' else 1-gate
        lines += [f'Vgate g 0 {u}','Va a 0 .5','Vb b 0 .5','.subckt circuit a b g s']
        for i in range(units):
            mos(f'a{i}','a','g','s');mos(f'b{i}','b','g','s')
        lines+=['.ends circuit','Xtop a b g s circuit']
        recipe={'kind':'op','vectors':['i(Va)','i(Vb)']}
    else:
        lines=['Vdd vdd 0 1',f'Itail {"s 0" if pol=="n" else "vdd s"} {2*current}',
               f'Vcommon cm 0 {0.7 if pol=="n" else .3}','Vdiff dv 0 0',
               'Ega ga cm dv 0 .5','Egb gb cm dv 0 -.5',
               f'Va a 0 {0.8 if pol=="n" else .2}',f'Vb b 0 {0.8 if pol=="n" else .2}',
               '.subckt circuit a b ga gb s']
        mos('a','a','ga','s');mos('b','b','gb','s')
        lines+=['.ends circuit','Xtop a b ga gb s circuit']
        recipe={'kind':'dc','source':'Vdiff','start':-.15,'stop':.15,'step':.001,
                'vectors':['i(Va)','i(Vb)','v(s)','v(ga)','v(gb)']}
    path=folder/'circuit.cir';path.write_text('\n'.join(lines)+'\n')
    return {'schema':SCHEMAS['request'],'circuit':str(path),'devices':devices,'analyses':[recipe]}


def circuit_observable(report,kind,current):
    if report['status']!='PASS':raise ResearchError('CIRCUIT_APPLICATION_FAILED: '+str(report['errors']))
    data=np.loadtxt(Path(report['directory'])/'analysis0.txt',skiprows=1,ndmin=2)
    if kind.startswith('mirror'):return float(abs(data[0,2])/current)
    if kind.startswith('bank'):return float(pair_relative(np.abs(data[:,1]),np.abs(data[:,2]))[0])
    diff=np.abs(data[:,1])-np.abs(data[:,2]);indices=np.flatnonzero(diff[:-1]*diff[1:]<=0)
    if len(indices)!=1:raise ResearchError('OFFSET_NOT_UNIQUELY_BRACKETED')
    i=indices[0]
    if not np.all((data[:,3:]>=-1e-9)&(data[:,3:]<=1+1e-9)):
        raise ResearchError('CIRCUIT_VOLTAGE_DOMAIN_EXCEEDED')
    return float(data[i,0]-diff[i]*(data[i+1,0]-data[i,0])/(diff[i+1]-diff[i]))


def circuit_family(root,binary,plan,profile,mapper,folder,pol,kind,gate,current):
    folder.mkdir(parents=True,exist_ok=True);req=circuit_request(folder,pol,kind,gate,current)
    devices=req['devices'];maps=[mapper.calibrate(d) for d in devices]
    raw=np.zeros((len(devices),2))
    def observed(x,realization=None):
        report=execute(root,binary,folder/'runs',req,realization or raw_realization(req,x))
        try:
            return circuit_observable(report,kind,current),report
        except (ResearchError,OSError,ValueError) as error:
            error.run_report=report
            raise
    nominal,_=observed(raw);scale=nominal if kind.startswith('mirror') else 1
    predicted_variance=0
    # Units of the same bank have identical topology. Verify one unit in each
    # branch, then sum the independent physical-unit covariances, not m=N.
    representatives=list(range(len(devices))) if not kind.startswith('bank') else [0,1]
    sensitivities=[]
    for i in representatives:
        derivatives=[]
        for k,h in enumerate((.001,.01)):
            lo=raw.copy();hi=raw.copy();lo[i,k]=-h;hi[i,k]=h
            derivatives.append((observed(hi)[0]-observed(lo)[0])/(2*h*scale))
        s=np.array(derivatives)@np.linalg.inv(np.array(maps[i]['jacobian']))
        count=int(kind[4:]) if kind.startswith('bank') else 1
        predicted_variance+=count*float(np.sum((s*sigma(profile,devices[i]))**2))
        sensitivities.append(s.tolist())
    def run(index):
        try:
            def resolve(d,q):
                raw,mp=mapper.predict(d,q)
                return raw,mp['content_id']
            realized=sample(profile,req,plan['circuits_seed'],index+plan['sample_index_start'],resolve)
            if realized['status']!='RESOLVED':return {'index':index,'status':'OUT_OF_SCOPE','realization':realized}
            raw=[x['raw'] for x in realized['devices']]
            value,report=observed(raw,realized)
            return {'index':index,'status':'PASS','value':(value-nominal)/scale,
                    'run':report['run_id'],'report_sha256':digest(Path(report['directory'])/'run.json')}
        except (ResearchError,OSError,ValueError) as error:
            failed_report=getattr(error,'run_report',None)
            binding={'run':failed_report['run_id'],
                     'report_sha256':digest(Path(failed_report['directory'])/'run.json')} if failed_report else {}
            return {'index':index,'status':'FAIL','error':str(error),**binding}
    n=plan['circuit_realizations_per_family']
    with ThreadPoolExecutor(plan['workers']) as pool:rows=list(pool.map(run,range(n)))
    save(folder/'cohort.json',{'requested':n,'rows':rows})
    failures=[r for r in rows if r['status']!='PASS']
    result={'polarity':pol,'family':kind,'requested':n,'attempted':len(rows),
            'executed':sum('run' in r for r in rows),'failed':len(failures),
            'physical_units':len(devices),'nominal_observable':nominal,'sensitivity_q':sensitivities,
            'cohort_sha256':digest(folder/'cohort.json'),'exclusions':['ideal supply','ideal output clamps','ideal reference/tail currents','global mismatch']}
    if failures:return {**result,'status':'FAIL','failures':failures[:10]}
    values=np.array([r['value'] for r in rows]);observed_sigma=float(values.std(ddof=1));prediction=math.sqrt(predicted_variance)
    result.update(observed_sigma=observed_sigma,predicted_sigma=prediction,sigma_ratio=observed_sigma/prediction,
                  mean_over_sigma=float(values.mean()/prediction))
    result['status']='PASS' if .8<=observed_sigma/prediction<=1.2 and abs(values.mean()/prediction)<.15 else 'FAIL'
    return result


def circuit_checks(root,binary,plan,profile,mapper,output):
    records=[]
    for pol in plan['polarity']:
        folder=output/pol;folder.mkdir(exist_ok=True)
        req=pair_request(folder/'bias.cir',pol,1e-6,2.4e-7,.002,.5)
        nominal=execute(root,binary,folder/'bias',req,raw_realization(req,[[0,0],[0,0]]))
        u,a,_=curve(nominal);sp=CubicSpline(u,a);gm=sp.derivative()(u)/np.maximum(a,1e-30)
        k=np.flatnonzero((gm[:-1]>10)&(gm[1:]<=10))[-1]
        gate=float(np.interp(10,gm[k:k+2][::-1],u[k:k+2][::-1]));current=float(sp(gate))
        for kind in plan['circuit_families']:
            try:result=circuit_family(root,binary,plan,profile,mapper,folder/kind,pol,kind,gate,current)
            except (ResearchError,OSError,ValueError) as error:result={'polarity':pol,'family':kind,'status':'FAIL','error':str(error)}
            records.append(result);save(folder/kind/'summary.json',result)
            print(f'circuit {pol}/{kind}: {result["status"]}',flush=True)
    scaling=[]
    for pol in plan['polarity']:
        byname={r['family']:r for r in records if r['polarity']==pol and 'observed_sigma' in r}
        if 'bank1' in byname:
            for n in (4,16):
                if f'bank{n}' in byname:
                    scaling.append({'polarity':pol,'units':n,'ratio_to_inverse_sqrt_n':
                        byname[f'bank{n}']['observed_sigma']*math.sqrt(n)/byname['bank1']['observed_sigma']})
    valid=records and all(r['status']=='PASS' for r in records) and len(scaling)==4 and all(.8<=s['ratio_to_inverse_sqrt_n']<=1.2 for s in scaling)
    return {'status':'PASS' if valid else 'FAIL','records':records,'unit_bank_scaling':scaling}


def logged_deck(binary,folder,deck):
    tool=spice_context(binary)
    if folder.exists():
        try:
            record=json.loads((folder/'run.json').read_text())
            if (folder/'input.cir').read_text()!=deck or record.get('tool')!=tool or record['binary_sha256']!=digest(binary) or any(digest(folder/p)!=h for p,h in record['files'].items()):
                raise ResearchError('ASSESSMENT_CACHE_TAMPER')
            return record
        except (OSError,KeyError,ValueError) as error:
            raise ResearchError(f'ASSESSMENT_CACHE_REJECTED: {error}') from error
    folder.mkdir(parents=True,exist_ok=False);(folder/'input.cir').write_text(deck)
    try:
        r=subprocess.run([str(binary),'-n','-b','input.cir'],cwd=folder,text=True,capture_output=True,
                         timeout=60,check=False,env={**os.environ,**tool['environment']})
        stdout,stderr,code=r.stdout,r.stderr,r.returncode
    except subprocess.TimeoutExpired as error:
        stdout=error.stdout or b'';stderr=error.stderr or b'';code=None
        stdout=stdout.decode(errors='replace') if isinstance(stdout,bytes) else stdout
        stderr=stderr.decode(errors='replace') if isinstance(stderr,bytes) else stderr
    (folder/'stdout.txt').write_text(stdout);(folder/'stderr.txt').write_text(stderr)
    valid=code==0 and not DIAGNOSTIC.search(stdout+'\n'+stderr) and 'Using SPARSE 1.3' in stdout+stderr
    result={'status':'PASS' if valid else 'FAIL','returncode':code,'binary_sha256':digest(binary),'tool':tool,
            'files':{p.name:digest(p) for p in folder.iterdir() if p.is_file()}}
    save(folder/'run.json',result)
    return result


def replay_checks(root,binary,plan,profile,mapper,output):
    records=[]
    for pol in plan['polarity']:
        folder=output/pol;folder.mkdir(exist_ok=True)
        rail=0 if pol=='n' else 1;gate=.6 if pol=='n' else .4;drain=.5
        body=f'''Vd d 0 {drain}
Vg g 0 DC {gate} AC 1 SIN({gate} .001 1meg)
Vs s 0 {rail}
Vb b 0 {rail}
Xtop d g s b stage
.subckt stage d g s b
Xa d g s b apm045_vtg_{'nmos' if pol=='n' else 'pmos'} w=2u l=.24u
.ends stage
'''
        circuit=folder/'replay.cir';circuit.write_text(body)
        d={'uid':f'{pol}/replay','path':['xtop','xa'],'family':'apm045/vtg','polarity':pol,'w_m':2e-6,'l_m':2.4e-7}
        req={'schema':SCHEMAS['request'],'circuit':str(circuit),'devices':[d],
             'analyses':[{'kind':'dc','source':'Vg','start':.3,'stop':.7,'step':.002,'vectors':['i(Vd)','v(g)']},
                         {'kind':'ac','start':1e5,'stop':1e7,'points_per_decade':1,'vectors':['i(Vd)','i(Vg)','i(Vs)','i(Vb)']},
                         {'kind':'tran','step':1e-8,'stop':5e-6,'vectors':['i(Vd)','v(g)']}]}
        realization=sample(profile,req,plan['circuits_seed'],plan['sample_index_start']+999,mapper)
        raw=np.array(realization['devices'][0]['raw']);save(folder/'realization.json',realization)
        for temp in plan['replay_temperature_c']:
            r=execute(root,binary,folder/'runs',req,realization,temperature_c=temp)
            item={'polarity':pol,'temperature_c':temp,'realization_id':realization['content_id'],
                  'raw':raw.tolist(),'run':r['run_id'],'status':r['status']}
            if r['status']=='PASS':
                path=Path(r['directory']);ac=np.loadtxt(path/'analysis1.txt',skiprows=1);tran=np.loadtxt(path/'analysis2.txt',skiprows=1)
                currents=ac[:,1::2]+1j*ac[:,2::2];k=int(np.argmin(abs(ac[:,0]-1e6)))
                t=tran[:,0];selection=t>=3e-6;t=t[selection]
                matrix=np.column_stack((np.ones(len(t)),np.sin(2*np.pi*1e6*t),np.cos(2*np.pi*1e6*t)))
                coefficients=np.linalg.lstsq(matrix,tran[selection,1],rcond=None)[0]
                transfer=(coefficients[1]+1j*coefficients[2])/.001
                amp=abs(transfer)/abs(currents[k,0]);phase=float(np.angle(transfer/currents[k,0]))
                kcl=float(np.max(abs(currents.sum(axis=1)))/np.max(abs(currents)))
                item.update(ac_tran_amplitude_ratio=amp,ac_tran_phase_difference=phase,terminal_kcl_relative=kcl,
                    report_sha256=digest(path/'run.json'))
                item['status']='PASS' if abs(amp-1)<=.02 and abs(phase)<=.03 and kcl<1e-8 else 'FAIL'
            records.append(item)
    return {'status':'PASS' if records and all(r['status']=='PASS' for r in records) else 'FAIL','records':records,
            'scope':'Same raw parameters; temperature response uncalibrated; terminal AC current/charge continuity, no noise MC'}


def io_assessment(root,binary,plan,profile,mapper,output):
    records=[]
    for family,vdd in [('io18',1.8),('io25',2.5)]:
        for pol in ('n','p'):
            folder=output/f'{family}-{pol}';folder.mkdir(exist_ok=True)
            includes=[root/f'models/apm045/families/{family}/ngspice/{name}' for name in
                      ('wrapper.inc',f'apm045_{family}_{pol}.inc')]
            rows=[];failures=[]
            for w in plan['io_widths_um']:
                for l in plan['io_lengths_um']:
                    for fraction in plan['io_bias_fraction']:
                        sign=1 if pol=='n' else -1;path=folder/f'{w}-{l}-{fraction}'
                        deck='\n'.join(['* APM IO terminal-capacitance transfer assessment',
                            *[f'.include "{p}"' for p in includes],'.temp 26.85',
                            f'Vg g 0 {sign*vdd*fraction} AC 1','Vs s 0 0','Vb b 0 0',f'Vd d 0 {sign*.05}',
                            f'Xdev d g s b apm045_{family}_{"nmos" if pol=="n" else "pmos"} w={w}u l={l}u',
                            '.control','set num_threads=1','set numdgt=17','set wr_vecnames','set wr_singlescale',
                            'ac dec 1 1000 1000000','wrdata ac.txt i(Vg) i(Vd) i(Vs) i(Vb)',
                            f'dc Vg 0 {sign*vdd} {sign*vdd/1000}','wrdata dc.txt v(g) i(Vd)','quit','.endc','.end',''])
                        result=logged_deck(binary,path,deck)
                        if result['status']!='PASS':failures.append(str(path));continue
                        a=np.loadtxt(path/'ac.txt',skiprows=1)
                        dc=np.loadtxt(path/'dc.txt',skiprows=1)
                        try:
                            mg=extract_mg(np.abs(dc[:,1]),np.abs(dc[:,2]))
                            threshold={'status':'EXTRACTED','vth_mg_v':mg.vth_mg_v,'beta_mg_a_v2':mg.beta_mg_a_per_v2}
                        except ResearchError as error:
                            threshold={'status':'UNRESOLVED','error':str(error)}
                        for frequency in plan['io_frequency_hz']:
                            v=a[np.argmin(abs(a[:,0]-frequency))]
                            currents=v[1::2]+1j*v[2::2];c=-currents[0].imag/(2*np.pi*frequency)
                            rows.append({'w_um':w,'l_um':l,'bias_fraction':fraction,'frequency':frequency,
                                'threshold_extraction':threshold,'cgg_f':c,'cgg_over_w_f_m':c/(w*1e-6),'terminal_kcl_relative':float(abs(currents.sum())/max(abs(currents))),
                                'run':str(path),'sha256':digest(path/'run.json')})
            fits=[]
            for w in plan['io_widths_um']:
                for f in plan['io_frequency_hz']:
                    for bias in plan['io_bias_fraction']:
                        selected=[x for x in rows if x['w_um']==w and x['frequency']==f and x['bias_fraction']==bias]
                        if len(selected)!=len(plan['io_lengths_um']):continue
                        x=np.array([x['l_um']*1e-6 for x in selected]);y=np.array([x['cgg_over_w_f_m'] for x in selected])
                        slope,intercept=np.polyfit(x,y,1);pred=slope*x+intercept
                        residual=float(np.max(abs(pred-y))/np.max(abs(y)))
                        # Hold out the shortest assessed length to expose fit sensitivity.
                        long_slope=float(np.polyfit(x[1:],y[1:],1)[0])
                        fits.append({'w_um':w,'frequency':f,'bias_fraction':bias,'slope_f_m2':slope,
                            'overlap_intercept_f_m':intercept,'relative_fit_residual':residual,
                            'long_subset_slope_ratio':long_slope/slope,
                            'tcap_proxy_m':8.8541878128e-12*3.9/slope if slope>0 else None})
            result={'family':family,'polarity':pol,'outcome':'UNRESOLVED_WITH_EVIDENCE',
                'status':'PASS' if not failures and len(rows)==48 and len(fits)==12 else 'FAIL',
                'rows':rows,'fits':fits,'failed_runs':failures,'model_hashes':{str(p.relative_to(root)):digest(p) for p in includes},
                'reason':'Terminal Cgg slope is a model-dependent Tcap proxy. Source effective work function/depletion and matched extraction-to-electrostatic transfer are unavailable; a fixed |VTH_MG|+0.1 substitution is not justified. No IO beta or default numeric mismatch profile.',
                'model_sensitivity':'Compare io18/io25 and N/P, W, L-subset, bias and frequency; released cards remain exact.'}
            save(folder/'summary.json',result);records.append(result)
            print(f'IO {family}/{pol}: {result["status"]} {result["outcome"]}',flush=True)
    return {'status':'PASS' if all(r['status']=='PASS' for r in records) else 'FAIL','records':records}
