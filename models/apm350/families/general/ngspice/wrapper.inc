* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm350_general_nmos d g s b w=1u l=0.4u
Mapm350_general_core d g s b apm350_ncore w='w' l='l'
+ ad='w*0.4u' as='w*0.4u' pd='2*w+0.8u' ps='2*w+0.8u'
.ends apm350_general_nmos

.subckt apm350_general_pmos d g s b w=1u l=0.4u
Mapm350_general_core d g s b apm350_pcore w='w' l='l'
+ ad='w*0.4u' as='w*0.4u' pd='2*w+0.8u' ps='2*w+0.8u'
.ends apm350_general_pmos
