* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm045_thkox_nmos d g s b w=1u l=0.05u
Mapm045_thkox_core d g s b NMOS_THKOX w='w' l='l'
.ends apm045_thkox_nmos

.subckt apm045_thkox_pmos d g s b w=1u l=0.05u
Mapm045_thkox_core d g s b PMOS_THKOX w='w' l='l'
.ends apm045_thkox_pmos
