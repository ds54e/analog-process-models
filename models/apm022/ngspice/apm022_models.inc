* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Independently authored generic 22 nm-class planar BSIM4 cards.
* These parameters are not copied, interpolated, fitted, or otherwise derived
* from an official PTM/PTM-MG model card. See ../parameter_generation.md.

.model apm022_ncore nmos level=54 version=4.8.2
+ binunit=1 paramchk=1 tnom=27
+ mobmod=1 capmod=2 rdsmod=0 igcmod=0 igbmod=0 gidlmod=0
+ lmin=2.5e-8 lmax=1.0e-7 wmin=1.0e-7 wmax=1.0e-4
+ toxe=9.0e-10 toxp=9.0e-10 toxm=9.0e-10 dtox=0 epsrox=3.9
+ xj=1.0e-8 ndep=2.0e18 nsd=1.0e20 ngate=0
+ vth0=0.62 k1=0.45 k2=-0.04 lpe0=0 lpeb=0 nfactor=1.20 voff=-0.08
+ dvt0=1.50 dvt1=0.30 dvt2=-0.03 eta0=0.11 etab=-0.05 dsub=0.80
+ u0=0.025 ua=1.0e-9 ub=1.0e-18 uc=-1.0e-10 ute=-1.5
+ vsat=1.20e5 a0=1.0 ags=0 keta=0
+ rdsw=20 rdswmin=5 prwg=0 prwb=0 wr=1
+ pclm=1.50 pdiblc1=0 pdiblc2=0 pdiblcb=0 drout=0.40 pvag=0
+ delta=0.01 fprout=0 pdits=0 pditsd=0
+ cgso=1.5e-10 cgdo=1.5e-10 cgbo=0 xpart=0.5
+ ckappas=0.6 ckappad=0.6 acde=1.0 moin=15 noff=1.0 voffcv=0
+ kt1=-0.08 kt1l=0 kt2=0.02 at=3.3e4

.model apm022_pcore pmos level=54 version=4.8.2
+ binunit=1 paramchk=1 tnom=27
+ mobmod=1 capmod=2 rdsmod=0 igcmod=0 igbmod=0 gidlmod=0
+ lmin=2.5e-8 lmax=1.0e-7 wmin=1.0e-7 wmax=1.0e-4
+ toxe=9.0e-10 toxp=9.0e-10 toxm=9.0e-10 dtox=0 epsrox=3.9
+ xj=1.0e-8 ndep=2.0e18 nsd=1.0e20 ngate=0
+ vth0=-0.62 k1=0.48 k2=-0.04 lpe0=0 lpeb=0 nfactor=1.22 voff=-0.08
+ dvt0=1.50 dvt1=0.30 dvt2=-0.03 eta0=0.12 etab=-0.05 dsub=0.80
+ u0=0.015 ua=1.2e-9 ub=1.2e-18 uc=-1.0e-10 ute=-1.5
+ vsat=1.00e5 a0=1.0 ags=0 keta=0
+ rdsw=20 rdswmin=5 prwg=0 prwb=0 wr=1
+ pclm=1.50 pdiblc1=0 pdiblc2=0 pdiblcb=0 drout=0.40 pvag=0
+ delta=0.01 fprout=0 pdits=0 pditsd=0
+ cgso=1.5e-10 cgdo=1.5e-10 cgbo=0 xpart=0.5
+ ckappas=0.6 ckappad=0.6 acde=1.0 moin=15 noff=1.0 voffcv=0
+ kt1=-0.08 kt1l=0 kt2=0.02 at=3.3e4
