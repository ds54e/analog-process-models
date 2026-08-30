* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm045_vtg_nmos d g s b w=1u l=0.05u
Mapm045_vtg_core d g s b NMOS_VTG w='w' l='l'
.ends apm045_vtg_nmos

.subckt apm045_vtg_pmos d g s b w=1u l=0.05u
Mapm045_vtg_core d g s b PMOS_VTG w='w' l='l'
.ends apm045_vtg_pmos
