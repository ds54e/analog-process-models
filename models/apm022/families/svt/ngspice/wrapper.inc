* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm022_svt_nmos d g s b w=1u l=25n
Mapm022_svt_core d g s b apm022_svt_ncore w='w' l='l'
.ends apm022_svt_nmos

.subckt apm022_svt_pmos d g s b w=1u l=25n
Mapm022_svt_core d g s b apm022_svt_pcore w='w' l='l'
.ends apm022_svt_pmos
