* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm022_lvt_nmos d g s b w=1u l=25n
Mapm022_lvt_core d g s b apm022_lvt_ncore w='w' l='l'
.ends apm022_lvt_nmos

.subckt apm022_lvt_pmos d g s b w=1u l=25n
Mapm022_lvt_core d g s b apm022_lvt_pcore w='w' l='l'
.ends apm022_lvt_pmos
