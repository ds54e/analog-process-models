* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm130_lv_nmos d g s b w=1u l=0.13u
Xapm130_lv_core d g s b sg13_lv_nmos w='w' l='l'
.ends apm130_lv_nmos

.subckt apm130_lv_pmos d g s b w=1u l=0.13u
Xapm130_lv_core d g s b sg13_lv_pmos w='w' l='l'
.ends apm130_lv_pmos
