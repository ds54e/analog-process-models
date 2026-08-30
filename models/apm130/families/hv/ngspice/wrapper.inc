* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm130_hv_nmos d g s b w=1u l=0.45u
Xapm130_hv_core d g s b sg13_hv_nmos w='w' l='l'
.ends apm130_hv_nmos

.subckt apm130_hv_pmos d g s b w=1u l=0.40u
Xapm130_hv_core d g s b sg13_hv_pmos w='w' l='l'
.ends apm130_hv_pmos
