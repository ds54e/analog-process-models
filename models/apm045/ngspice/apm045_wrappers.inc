* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Public APM045 devices. The stable v1 public parameters are only w and l.

.subckt apm045_nmos d g s b w=1u l=0.05u
Mapm045_core d g s b NMOS_VTG w='w' l='l'
.ends apm045_nmos

.subckt apm045_pmos d g s b w=1u l=0.05u
Mapm045_core d g s b PMOS_VTG w='w' l='l'
.ends apm045_pmos
