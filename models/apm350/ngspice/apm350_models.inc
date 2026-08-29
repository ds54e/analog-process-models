* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Independently authored open generic 0.35 um-class / 0.4 um-Lmin BSIM3 cards.
* No third-party parameter card is included or numerically transcribed.

.model apm350_ncore nmos level=49 version=3.3.0
+ binunit=1 paramchk=1 tnom=27
+ mobmod=1 capmod=2 nqsmod=0
+ lmin=4.0e-7 lmax=1.0e-5 wmin=6.0e-7 wmax=1.0e-4
+ tox=8.0e-9 xj=1.5e-7 nch=1.5e17
+ vth0=0.55 k1=0.50 k2=-0.02 k3=0 k3b=0 w0=2.0e-6 nlx=1.0e-7
+ dvt0=0.10 dvt1=0.50 dvt2=-0.05 dvt0w=0 dvt1w=5.0e6 dvt2w=-0.02
+ u0=500 ua=2.5e-10 ub=1.5e-18 uc=-5.0e-11 ute=-1.5
+ vsat=1.0e5 a0=1.0 ags=0.10 b0=0 b1=5.0e-6 keta=-0.01
+ rdsw=200 prwg=0 prwb=0 wr=1
+ voff=-0.08 nfactor=1.20 cit=0 cdsc=2.0e-4 cdscd=0 cdscb=0
+ eta0=0.010 etab=0 dsub=0.05 pclm=1.0 pdiblc1=0.02 pdiblc2=0.002
+ pdiblcb=0 drout=0.50 pvag=0.10 delta=0.01
+ cgso=2.0e-10 cgdo=2.0e-10 cgbo=0 xpart=0.5
+ kt1=-0.11 kt1l=0 kt2=0.02 at=3.3e4

.model apm350_pcore pmos level=49 version=3.3.0
+ binunit=1 paramchk=1 tnom=27
+ mobmod=1 capmod=2 nqsmod=0
+ lmin=4.0e-7 lmax=1.0e-5 wmin=6.0e-7 wmax=1.0e-4
+ tox=8.0e-9 xj=1.5e-7 nch=1.5e17
+ vth0=-0.65 k1=0.55 k2=-0.02 k3=0 k3b=0 w0=2.0e-6 nlx=1.0e-7
+ dvt0=0.12 dvt1=0.52 dvt2=-0.05 dvt0w=0 dvt1w=5.0e6 dvt2w=-0.02
+ u0=200 ua=2.0e-10 ub=1.5e-18 uc=-5.0e-11 ute=-1.5
+ vsat=8.0e4 a0=1.0 ags=0.10 b0=0 b1=5.0e-6 keta=-0.01
+ rdsw=300 prwg=0 prwb=0 wr=1
+ voff=-0.10 nfactor=1.30 cit=0 cdsc=2.5e-4 cdscd=0 cdscb=0
+ eta0=0.015 etab=0 dsub=0.08 pclm=1.2 pdiblc1=0.025 pdiblc2=0.002
+ pdiblcb=0 drout=0.50 pvag=0.10 delta=0.01
+ cgso=2.2e-10 cgdo=2.2e-10 cgbo=0 xpart=0.5
+ kt1=-0.11 kt1l=0 kt2=0.02 at=3.3e4
