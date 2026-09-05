# SPDX-FileCopyrightText: 2026 APM preflight contributors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import pytest
from numerical_core import PreflightError
from run_spike import expected_negative_failure, render_deck, readback_scalars, LEAF_A, LEAF_B

def test_n_template():
    text = render_deck(Path('/apm'), 'n', 1.0, 0.12, 0.001, 0.01, 0.02)
    assert 'Vda da 0 0.050000000000000003' in text
    assert LEAF_A + '[delvto]' in text
    assert LEAF_B + '[mulu0]' in text
    assert 'altermod' not in text and '\nreset\n' not in text
    assert '.temp 26.850000000000001' in text

def test_p_template():
    text = render_deck(Path('/apm'), 'p', 1.0, 0.12, 0.001, 0.01, 0.02)
    assert 'Vs s 0 1' in text
    assert 'dc Vctrl 0 -1 -0.001' in text
    assert 'apm045_vtg_pmos' in text
    assert 'let u = abs(v(g)-v(s))' in text

def test_negative_templates():
    text = render_deck(Path('/apm'), 'n', 1.0, 0.12, 0.001, 0.01, 0.02, invalid_target=True)
    assert 'xmissing' in text
    text = render_deck(Path('/apm'), 'n', 1.0, 0.12, 0.001, 0.01, 0.02, reset_after_apply=True)
    assert '\nreset\n' in text

def test_path_injection_rejected():
    with pytest.raises(PreflightError):
        render_deck(Path('/apm\nquit'), 'n', 1.0, 0.12, 0.001, 0.01, 0.02)

def test_readback_parse():
    text = '\n'.join((f'{p}_{q} = {v}' for p in ('a', 'b') for q, v in [('w', '1e-6'), ('l', '1.2e-7'), ('delvto', '0'), ('mulu0', '1')]))
    result = readback_scalars(text)
    assert result['a_w'] == 1e-06 and result['b_mulu0'] == 1

def test_readback_missing():
    with pytest.raises(PreflightError):
        readback_scalars('a_w = 1e-6')

def test_unrelated_simulation_failure_is_not_negative_control_success():
    error = PreflightError('SIMULATION_FAILED: /output/001')
    assert not expected_negative_failure('bad_path', error, 'Error: singular matrix')
    assert not expected_negative_failure('reset_loses_perturbation', error, 'no such xmissing')

def test_only_target_readback_mismatch_is_negative_control_success():
    assert expected_negative_failure('bad_path', PreflightError('READBACK_MISMATCH: a_delvto at /run'))
    assert not expected_negative_failure('bad_path', PreflightError('READBACK_MISMATCH: b_w at /run'))

def test_missing_target_diagnostic_is_required_for_simulation_failure():
    error = PreflightError('SIMULATION_FAILED: /run')
    assert expected_negative_failure('bad_path', error, 'Error: no such device xmissing')
    assert not expected_negative_failure('bad_path', error, 'xmissing printed in deck; singular matrix')
