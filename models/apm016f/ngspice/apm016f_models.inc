* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Independently authored APM016F generic BSIM-CMG cards.
* These parameters are not copied, interpolated, fitted, or otherwise derived
* from an official PTM-MG model card. See ../parameter_generation.md.
*
* Geometry and electrostatic inputs are shared by the N/P cards. Carrier
* transport and gate work function are independently selected per polarity.
* Self-heating is explicitly disabled for the v1 public model.

.model apm016f_cmg_n bsimcmg_va type=1 bulkmod=1 geomod=1 shmod=0
+ l=16n tfin=8n fpitch=48n hfin=32n eot=1n
+ nbody=1.5e24 nsd=1.0e26 ngate=0
+ phig=4.45 u0=0.030 vsat=1.00e5
+ cdsc=7.0e-3 cdscd=7.0e-3 dvt0=0.050 dvt1=0.60
+ eta0=0.20 dsub=1.06 pclm=0.050 pdibl1=1.30 pdibl2=2.0e-4
+ rdsmod=0 rdsw=100 cvmod=0 cgeomod=0
+ igcmod=0 igbmod=0 gidlmod=0 iimod=0 tnom=27

.model apm016f_cmg_p bsimcmg_va type=-1 bulkmod=1 geomod=1 shmod=0
+ l=16n tfin=8n fpitch=48n hfin=32n eot=1n
+ nbody=1.5e24 nsd=1.0e26 ngate=0
+ phig=4.75 u0=0.014 vsat=8.00e4
+ cdsc=7.0e-3 cdscd=7.0e-3 dvt0=0.050 dvt1=0.60
+ eta0=0.20 dsub=1.06 pclm=0.050 pdibl1=1.30 pdibl2=2.0e-4
+ rdsmod=0 rdsw=100 cvmod=0 cgeomod=0
+ igcmod=0 igbmod=0 gidlmod=0 iimod=0 tnom=27
