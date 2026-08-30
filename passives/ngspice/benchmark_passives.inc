* SPDX-FileCopyrightText: APM contributors
* SPDX-License-Identifier: Apache-2.0
*
* Technology-neutral benchmark passives. Python resolves Global/Local/All into
* the concrete value passed here; match_size remains explicit result identity.

.subckt Rbench p n value=1k tc1=0 match_size=1
Rbench_core p n r='value' tc1='tc1'
.ends Rbench

.subckt Cbench p n value=1p tc1=0 match_size=1
Cbench_core p n c='value' tc1='tc1'
.ends Cbench
