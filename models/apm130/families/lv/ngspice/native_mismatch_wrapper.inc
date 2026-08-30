* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Family-qualified counterpart to wrapper.inc for IHP's mos_tt_mismatch
* section. mm_ok is deliberately fixed internally; the APM public geometry
* remains d,g,s,b plus w,l.

.subckt apm130_lv_nmos d g s b w=1u l=0.13u
Xapm130_lv_core d g s b sg13_lv_nmos w='w' l='l' mm_ok=1
.ends apm130_lv_nmos

.subckt apm130_lv_pmos d g s b w=1u l=0.13u
Xapm130_lv_core d g s b sg13_lv_pmos w='w' l='l' mm_ok=1
.ends apm130_lv_pmos
