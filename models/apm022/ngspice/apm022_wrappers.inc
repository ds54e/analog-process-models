* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Stable public APM022 devices. Public sizing is only w and l.

.subckt apm022_nmos d g s b w=1u l=25n
Mapm022_core d g s b apm022_ncore w='w' l='l'
.ends apm022_nmos

.subckt apm022_pmos d g s b w=1u l=25n
Mapm022_core d g s b apm022_pcore w='w' l='l'
.ends apm022_pmos
