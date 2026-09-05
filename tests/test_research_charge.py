# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest

from apm.research_charge import charge_metrics
from apm.research_numerics import ResearchError


def test_conserved_dynamic_charges_and_fault_injection():
    t = np.linspace(0, 1, 101)
    qg = (1 + np.sin(t)) * 1e-15
    data = np.column_stack((t, qg, -0.2 * qg, -0.3 * qg, -0.5 * qg))
    assert charge_metrics(data)["status"] == "PASS"
    data[:, 4] += 1e-18
    assert charge_metrics(data)["status"] == "FAIL"
    data[:, 1:] = 0
    assert charge_metrics(data)["status"] == "FAIL"
    with pytest.raises(ResearchError, match="INCOMPLETE"):
        charge_metrics(data[:, :4])
