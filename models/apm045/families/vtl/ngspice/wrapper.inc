* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm045_vtl_nmos d g s b w=1u l=0.05u
Mapm045_vtl_core d g s b NMOS_VTL w='w' l='l'
.ends apm045_vtl_nmos

.subckt apm045_vtl_pmos d g s b w=1u l=0.05u
Mapm045_vtl_core d g s b PMOS_VTL w='w' l='l'
.ends apm045_vtl_pmos
