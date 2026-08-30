* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Family-qualified counterpart to wrapper.inc for IHP's mos_tt_mismatch
* section. mm_ok is deliberately fixed internally; the APM public geometry
* remains d,g,s,b plus w,l.

.subckt apm130_hv_nmos d g s b w=1u l=0.45u
Xapm130_hv_core d g s b sg13_hv_nmos w='w' l='l' mm_ok=1
.ends apm130_hv_nmos

.subckt apm130_hv_pmos d g s b w=1u l=0.40u
Xapm130_hv_core d g s b sg13_hv_pmos w='w' l='l' mm_ok=1
.ends apm130_hv_pmos
