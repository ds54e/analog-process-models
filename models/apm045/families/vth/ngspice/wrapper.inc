* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm045_vth_nmos d g s b w=1u l=0.05u
Mapm045_vth_core d g s b NMOS_VTH w='w' l='l'
.ends apm045_vth_nmos

.subckt apm045_vth_pmos d g s b w=1u l=0.05u
Mapm045_vth_core d g s b PMOS_VTH w='w' l='l'
.ends apm045_vth_pmos
