* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm045_io25_nmos d g s b w=1u l=0.18u
Mapm045_io25_core d g s b apm045_io25_ncore w='w' l='l'
.ends apm045_io25_nmos

.subckt apm045_io25_pmos d g s b w=1u l=0.18u
Mapm045_io25_core d g s b apm045_io25_pcore w='w' l='l'
.ends apm045_io25_pmos
