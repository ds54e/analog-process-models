* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Native-IHP-mismatch counterparts to apm130_wrappers.inc. Include this file
* instead of the nominal wrapper file with the upstream mos_*_mismatch section.
* Public names and public sizing stay d,g,s,b plus w,l; mm_ok is fixed internally.

.subckt apm130_nmos d g s b w=1u l=0.13u
Xapm130_core d g s b sg13_lv_nmos w='w' l='l' mm_ok=1
.ends apm130_nmos

.subckt apm130_pmos d g s b w=1u l=0.13u
Xapm130_core d g s b sg13_lv_pmos w='w' l='l' mm_ok=1
.ends apm130_pmos
