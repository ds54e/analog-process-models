* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Stable public APM350 devices. Public sizing is only w and l.

.subckt apm350_nmos d g s b w=1u l=0.4u
Mapm350_core d g s b apm350_ncore w='w' l='l'
+ ad='w*0.4u' as='w*0.4u' pd='2*w+0.8u' ps='2*w+0.8u'
.ends apm350_nmos

.subckt apm350_pmos d g s b w=1u l=0.4u
Mapm350_core d g s b apm350_pcore w='w' l='l'
+ ad='w*0.4u' as='w*0.4u' pd='2*w+0.8u' ps='2*w+0.8u'
.ends apm350_pmos
