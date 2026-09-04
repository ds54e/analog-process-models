* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm045_io18_nmos d g s b w=1u l=0.08u
Mapm045_io18_core d g s b apm045_io18_ncore w='w' l='l'
.ends apm045_io18_nmos

.subckt apm045_io18_pmos d g s b w=1u l=0.08u
Mapm045_io18_core d g s b apm045_io18_pcore w='w' l='l'
.ends apm045_io18_pmos
