* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Public APM130 devices. Upstream geometry/finger parameters are intentionally
* fixed inside these wrappers; the stable v1 public parameters are only w, l.

.subckt apm130_nmos d g s b w=1u l=0.13u
Xapm130_core d g s b sg13_lv_nmos w='w' l='l'
.ends apm130_nmos

.subckt apm130_pmos d g s b w=1u l=0.13u
Xapm130_core d g s b sg13_lv_pmos w='w' l='l'
.ends apm130_pmos
