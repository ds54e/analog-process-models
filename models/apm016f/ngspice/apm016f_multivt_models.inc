* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Independently authored generic 16 nm-class BSIM-CMG family cards.
* LVT and HVT copy the APM-authored SVT basis exactly except for PHIG.
* No value is copied, interpolated, fitted, or otherwise numerically derived
* from an official PTM-MG or ASAP7 model card. See ../parameter_generation.md
* and the family variant-generation records.

.model apm016f_lvt_ncore bsimcmg_va type=1 bulkmod=1 geomod=1 shmod=0
+ l=16n tfin=8n fpitch=48n hfin=32n eot=1n
+ nbody=1.5e24 nsd=1.0e26 ngate=0
+ phig=4.35 u0=0.030 vsat=1.00e5
+ cdsc=7.0e-3 cdscd=7.0e-3 dvt0=0.050 dvt1=0.60
+ eta0=0.20 dsub=1.06 pclm=0.050 pdibl1=1.30 pdibl2=2.0e-4
+ rdsmod=0 rdsw=100 cvmod=0 cgeomod=0
+ igcmod=0 igbmod=0 gidlmod=0 iimod=0 tnom=27

.model apm016f_lvt_pcore bsimcmg_va type=-1 bulkmod=1 geomod=1 shmod=0
+ l=16n tfin=8n fpitch=48n hfin=32n eot=1n
+ nbody=1.5e24 nsd=1.0e26 ngate=0
+ phig=4.85 u0=0.014 vsat=8.00e4
+ cdsc=7.0e-3 cdscd=7.0e-3 dvt0=0.050 dvt1=0.60
+ eta0=0.20 dsub=1.06 pclm=0.050 pdibl1=1.30 pdibl2=2.0e-4
+ rdsmod=0 rdsw=100 cvmod=0 cgeomod=0
+ igcmod=0 igbmod=0 gidlmod=0 iimod=0 tnom=27

.model apm016f_svt_ncore bsimcmg_va type=1 bulkmod=1 geomod=1 shmod=0
+ l=16n tfin=8n fpitch=48n hfin=32n eot=1n
+ nbody=1.5e24 nsd=1.0e26 ngate=0
+ phig=4.45 u0=0.030 vsat=1.00e5
+ cdsc=7.0e-3 cdscd=7.0e-3 dvt0=0.050 dvt1=0.60
+ eta0=0.20 dsub=1.06 pclm=0.050 pdibl1=1.30 pdibl2=2.0e-4
+ rdsmod=0 rdsw=100 cvmod=0 cgeomod=0
+ igcmod=0 igbmod=0 gidlmod=0 iimod=0 tnom=27

.model apm016f_svt_pcore bsimcmg_va type=-1 bulkmod=1 geomod=1 shmod=0
+ l=16n tfin=8n fpitch=48n hfin=32n eot=1n
+ nbody=1.5e24 nsd=1.0e26 ngate=0
+ phig=4.75 u0=0.014 vsat=8.00e4
+ cdsc=7.0e-3 cdscd=7.0e-3 dvt0=0.050 dvt1=0.60
+ eta0=0.20 dsub=1.06 pclm=0.050 pdibl1=1.30 pdibl2=2.0e-4
+ rdsmod=0 rdsw=100 cvmod=0 cgeomod=0
+ igcmod=0 igbmod=0 gidlmod=0 iimod=0 tnom=27

.model apm016f_hvt_ncore bsimcmg_va type=1 bulkmod=1 geomod=1 shmod=0
+ l=16n tfin=8n fpitch=48n hfin=32n eot=1n
+ nbody=1.5e24 nsd=1.0e26 ngate=0
+ phig=4.55 u0=0.030 vsat=1.00e5
+ cdsc=7.0e-3 cdscd=7.0e-3 dvt0=0.050 dvt1=0.60
+ eta0=0.20 dsub=1.06 pclm=0.050 pdibl1=1.30 pdibl2=2.0e-4
+ rdsmod=0 rdsw=100 cvmod=0 cgeomod=0
+ igcmod=0 igbmod=0 gidlmod=0 iimod=0 tnom=27

.model apm016f_hvt_pcore bsimcmg_va type=-1 bulkmod=1 geomod=1 shmod=0
+ l=16n tfin=8n fpitch=48n hfin=32n eot=1n
+ nbody=1.5e24 nsd=1.0e26 ngate=0
+ phig=4.65 u0=0.014 vsat=8.00e4
+ cdsc=7.0e-3 cdscd=7.0e-3 dvt0=0.050 dvt1=0.60
+ eta0=0.20 dsub=1.06 pclm=0.050 pdibl1=1.30 pdibl2=2.0e-4
+ rdsmod=0 rdsw=100 cvmod=0 cgeomod=0
+ igcmod=0 igbmod=0 gidlmod=0 iimod=0 tnom=27
