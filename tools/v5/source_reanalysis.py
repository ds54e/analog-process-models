#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Auditable vector reanalysis of the pinned Hart companion; no APM fit inputs.

Requires PyMuPDF. The PDF and detailed output stay ignored. Numeric adaptations
are not author-issued data or corrections. Page indices below are zero-based.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import fitz
import numpy as np

PIN='0f1a691225d51db40440d5e71081bda819a34fda8bda4b08099f5830418e7f5a'


def segments(drawing):
    groups=[];g=[]
    for item in drawing['items']:
        if item[0]!='l':continue
        a,b=list(item[1]),list(item[2])
        if g and np.linalg.norm(np.array(g[-1])-a)>.01:
            groups.append(np.array(g));g=[]
        if not g:g.append(a)
        g.append(b)
    if g:groups.append(np.array(g))
    return groups


def analyze(pdf):
    assert hashlib.sha256(pdf.read_bytes()).hexdigest()==PIN
    doc=fitz.open(pdf);p=doc[5].get_drawings()
    records=[]
    # Error-bar halves meet at the estimate; endpoints preserve reported 95% CI.
    # Axes read visually: Vth 0..12 mV um, beta 0..5 percent um; T=300 K.
    for pol,y0,y1,indices in [('p',383.05,473.73,[(1037,1039),(1041,1043),(1045,1047)]),
                             ('n',534.385,625.065,[(1445,1447),(1449,1451),(1453,1455)])]:
        for length,(i,j) in zip([40,120,400],indices):
            v0,v,v1=p[i]['rect'].y0,p[i]['rect'].y1,p[j]['rect'].y1
            # Corresponding beta error bars occupy the same series order.
            x=342.31; ys=[]
            for k,d in enumerate(p):
                r=d['rect']
                if r.width<.01 and abs(r.x0-x)<.01 and y0+10<r.y0<r.y1<y1-5:
                    ys.append((k,r.y0,r.y1))
            center_candidates=[]
            for a in ys:
                for b in ys:
                    if abs(a[2]-b[1])<.002:
                        center_candidates.append((a[0],b[0],a[1],a[2],b[2]))
            centers=sorted(center_candidates,key=lambda t:t[3],reverse=True)
            # p beta series ordering at RT: square lowest, circle middle, triangle highest.
            index=([40,400,120] if pol=='p' else [40,120,400]).index(length)
            bi,bj,b0,b,b1=centers[index]
            conv=lambda y,top,y0=y0,y1=y1: (y1-y)/(y1-y0)*top
            records.append({'polarity':pol,'length_nm':length,'vth_mV_um':conv(v,12),
                'vth_95ci':[conv(v1,12),conv(v0,12)],'beta_percent_um':conv(b,5),
                'beta_95ci':[conv(b1,5),conv(b0,5)],'pdf_vector_indices':[i,j,bi,bj],
                'axes_pdf_points':{'y0':y0,'y1':y1,'vth_range':[0,12],'beta_range':[0,5]},
                'digitization_absolute_bound':{'vth_mV_um':.5/(y1-y0)*12,'beta_percent_um':.5/(y1-y0)*5},
                'long_length_decision':'400nm is inferred from Fig2 and Figs5/7/12 inventories and p802-803 prose; printed legend says 1.2um, which is the large-device width' if length==400 else 'unambiguous'})
    slopes=[]
    for pol,indices in [('p',(95,257)),('n',(571,733))]:
        values=[]
        for index,top in zip(indices,(80,20)):
            rect=p[index]['rect']
            values.append(rect.height/90.68*top*np.sqrt(.12*.04))
        match=next(x for x in records if x['polarity']==pol and x['length_nm']==40)
        slopes.append({'polarity':pol,'pdf_vector_indices':list(indices),
                       'vth_mV_um':values[0],'beta_percent_um':values[1],
                       'relative_difference':[values[0]/match['vth_mV_um']-1,
                                              values[1]/match['beta_percent_um']-1]})
    # Independent ID-VG traces in Fig5: all red curves, 48 N and 48 P per geometry.
    curves=[]
    for size,index,x0,x1 in [('S',73,77.61,195.303),('M',280,248.30,365.996),('L',444,418.99,536.686)]:
        groups=[g for g in segments(doc[4].get_drawings()[index]) if len(g)>50]
        for pol in ('n','p'):
            selected=[g for g in groups if (g[-1,0]>g[0,0])==(pol=='n')]
            curves.append({'size':size,'polarity':pol,'count':len(selected),'index':index,
                           'axis':[x0,x1,64.772,157.300],'curves':[g.tolist() for g in selected]})
    current=[]
    # Fig12(a,c) measured curves, no fitting to its Croon overlays.
    drawings=doc[6].get_drawings()
    for pol,indices in [('n',[81,84,87]),('p',[1953,1956,1959])]:
        for size,index in zip(('S','M','L'),indices):
            current.append({'polarity':pol,'size':size,'index':index,
                            'segments':[g.tolist() for g in segments(drawings[index])]})
    checks=[]
    dimensions={'S':(.12,.04),'M':(.36,.12),'L':(1.2,.4)}
    for item in current:
        pol,size=item['polarity'],item['size']
        trace=next(c for c in curves if c['polarity']==pol and c['size']==size)
        coeff=next(c for c in records if c['polarity']==pol and c['length_nm']==round(dimensions[size][1]*1000))
        cx0,cx1,cy0,cy1=trace['axis']
        mx0,mx1=(66.861,158.894) if pol=='n' else (318.780,410.813)
        my0,my1=63.245,135.597
        data=np.array(item['segments'][0])
        mx=(data[:,0]-mx0)/(mx1-mx0)*1.1
        my=(my1-data[:,1])/(my1-my0)*(.7 if pol=='n' else .6)
        order=np.argsort(mx); mx=mx[order]; my=my[order]
        for vg in ([.75,.8,.9,.95,1.0] if pol=='n' else [.1,.15,.25,.3,.4]):
            sensitivity=[]
            for width in (.025,.05):
                values=[]
                for g in trace['curves']:
                    g=np.array(g);x=(g[:,0]-cx0)/(cx1-cx0)*1.1
                    y=-14+(cy1-g[:,1])/(cy1-cy0)*10
                    order=np.argsort(x);x=x[order];y=y[order]
                    # Log slope gives gm/Id without assuming the source is APM.
                    values.append(abs((np.interp(vg+width,x,y)-np.interp(vg-width,x,y))/(2*width))*np.log(10))
                sensitivity.append(float(np.mean(values)))
            area=math.prod(dimensions[size])
            av=coeff['vth_mV_um']*.001;ab=coeff['beta_percent_um']*.01
            predicted=math.sqrt((ab*ab+(np.mean(sensitivity)*av)**2)/area)/np.log(10)
            observed=float(np.interp(vg,mx,my))
            # Source finite-population interval (72 independent normal pairs),
            # plus an explicit 0.5 PDF-point display uncertainty. No APM data.
            display=.5/(my1-my0)*(.7 if pol=='n' else .6)
            checks.append({'polarity':pol,'size':size,'vg_v':vg,'gm_over_id_per_v':sensitivity,
                'predicted_sigma_log10_i':predicted,'observed_sigma_log10_i':observed,
                'ratio':predicted/observed,'display_bound_decades':display,
                'development_or_confirmation':'confirmation' if vg in (.8,.95,.15,.3) else 'development',
                'predicted_parameter_interval':[math.sqrt(((coeff['beta_95ci'][k]+(-1 if k==0 else 1)*coeff['digitization_absolute_bound']['beta_percent_um'])*.01)**2+((coeff['vth_95ci'][k]+(-1 if k==0 else 1)*coeff['digitization_absolute_bound']['vth_mV_um'])*.001*sensitivity[k])**2)/math.sqrt(area)/math.log(10) for k in (0,1)],
                'observed_interval':[max(0,observed*.86-display),observed*1.20+display]})
    return {'fixed_length_slope_checks':slopes,'independent_current_checks':checks,
'pdf_sha256':PIN,'coefficients':records,'fig5':curves,'fig12':current,
            'method':'PDF vector path/errorbar reanalysis; manual visual axes verification required',
            'status':'SOURCE_CANDIDATE_REANALYSIS_NOT_RUNTIME_APPROVAL',
            'normalization':'Companion p800 overline is population average over matched pairs; do not import original-ST pair-mean convention',
            'rho':'Zero is a named independent-Croon approximation justified by companion Eq7, not a measured covariance',
            'extraction':'2002 review Sec2.2 adds D/2; APM subtracts D/2. Common offset D cancels equal-bias pair differences. Author smoothing and beta-code unavailable.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pdf',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();a.output.write_text(json.dumps(analyze(a.pdf),indent=2)+'\n')
