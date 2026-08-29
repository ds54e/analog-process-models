* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Public APM016F devices. The stable v1 parameters are only l and nfin.
* nfin is a positive integer in the APM public contract.

.subckt apm016f_nfet d g s b l=16n nfin=1
Napm016f_core d g s b apm016f_cmg_n l='l' nfin='nfin'
.ends apm016f_nfet

.subckt apm016f_pfet d g s b l=16n nfin=1
Napm016f_core d g s b apm016f_cmg_p l='l' nfin='nfin'
.ends apm016f_pfet
