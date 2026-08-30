* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0

.subckt apm016f_svt_nfet d g s b l=16n nfin=1
Napm016f_svt_core d g s b apm016f_svt_ncore l='l' nfin='nfin'
.ends apm016f_svt_nfet

.subckt apm016f_svt_pfet d g s b l=16n nfin=1
Napm016f_svt_core d g s b apm016f_svt_pcore l='l' nfin='nfin'
.ends apm016f_svt_pfet
