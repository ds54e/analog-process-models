* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm022_hvt_nmos d g s b w=1u l=25n
Mapm022_hvt_core d g s b apm022_hvt_ncore w='w' l='l'
.ends apm022_hvt_nmos

.subckt apm022_hvt_pmos d g s b w=1u l=25n
Mapm022_hvt_core d g s b apm022_hvt_pcore w='w' l='l'
.ends apm022_hvt_pmos
