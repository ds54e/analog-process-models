# SPDX-FileCopyrightText: 2026 APM preflight contributors
# SPDX-License-Identifier: Apache-2.0

import math
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pytest
from scipy.special import erf
from numerical_core import PreflightError, aggregate_tail_risk, canonical_hash, covariance_from_pair_coefficients, extract_mg, inverse_mapping, local_jacobian, normal_draw, pair_coefficient_to_device_sigma, pair_relative

def analytic_curve(u, x0=0.55, width=0.08, amplitude=0.0001):
    return 1e-12 + amplitude * width * math.sqrt(math.pi) / 2 * (1 + erf((u - x0) / width))

def test_key_replay():
    assert normal_draw(53, 2, 'ea.left', 'vth') == normal_draw(53, 2, 'ea.left', 'vth')

def test_key_insertion_and_order():
    ids = ['ea.left', 'ea.right', 'bias.ref']
    expected = {i: normal_draw(53, 2, i, 'vth') for i in ids}
    actual = {i: normal_draw(53, 2, i, 'vth') for i in reversed(ids + ['unused'])}
    assert all((expected[i] == actual[i] for i in ids))

def test_key_workers():
    args = [(53, i, 'ea.left', 'vth') for i in range(64)]
    expected = [normal_draw(*a) for a in args]
    with ThreadPoolExecutor(max_workers=4) as executor:
        actual = list(executor.map(lambda a: normal_draw(*a), args))
    assert actual == expected

@pytest.mark.parametrize('bad', [-1, True, 3.5])
def test_bad_seed(bad):
    with pytest.raises(PreflightError):
        normal_draw(bad, 0, 'a', 'vth')

def test_pair_sqrt2():
    sigma = pair_coefficient_to_device_sigma(0.004, 1, 0.25)
    assert math.sqrt(2) * sigma == pytest.approx(0.008)

def test_width_scaling():
    s1 = pair_coefficient_to_device_sigma(0.004, 1, 0.12)
    s4 = pair_coefficient_to_device_sigma(0.004, 4, 0.12)
    assert s4 == s1 / 2

def test_length_scaling_has_coefficient():
    s1 = pair_coefficient_to_device_sigma(0.004, 1, 0.1)
    s4 = pair_coefficient_to_device_sigma(0.006, 1, 0.4)
    assert s4 / s1 == pytest.approx(0.75)

def test_pair_unequal_sizes():
    s1 = pair_coefficient_to_device_sigma(0.004, 1, 0.25)
    s2 = pair_coefficient_to_device_sigma(0.004, 4, 0.25)
    expected = math.sqrt(s1 * s1 + s2 * s2)
    assert expected == pytest.approx(math.sqrt(4e-05))

def test_relative_definition():
    assert pair_relative(np.array([1.1]), np.array([0.9]))[0] == pytest.approx(0.2)

def test_relative_bad_value():
    with pytest.raises(PreflightError):
        pair_relative(np.array([-1.0]), np.array([1.0]))

def test_covariance():
    c = covariance_from_pair_coefficients(0.004, 0.006, 1, 0.25, 0.3)
    assert c[0, 1] / math.sqrt(c[0, 0] * c[1, 1]) == pytest.approx(0.3)
    assert np.linalg.eigvalsh(c).min() > 0

def test_latent_population():
    rng = np.random.Generator(np.random.PCG64(50905))
    z = rng.standard_normal((65536, 2, 2))
    sigma = np.array([0.004, 0.006]) / math.sqrt(2 * 0.25)
    diff = (z[:, 0] - z[:, 1]) * sigma
    expected = np.array([0.004, 0.006]) / math.sqrt(0.25)
    assert np.all(np.abs(diff.std(axis=0, ddof=1) / expected - 1) < 0.02)
    assert np.all(np.abs(diff.mean(axis=0) / expected) < 0.02)
    assert abs(np.corrcoef(diff.T)[0, 1]) < 0.02

def test_tail():
    r = aggregate_tail_risk(204800, 6)
    assert r['expected_count'] == pytest.approx(0.0004041063, rel=2e-05)
    assert 0 < r['probability_at_least_one'] < 0.001

def test_extraction_analytic():
    u = np.linspace(0, 1, 1001)
    r = extract_mg(u, analytic_curve(u))
    expected_vth = 0.55 - float(analytic_curve(np.array(0.55))) / 0.0001 - 0.025
    assert r.u_star_v == pytest.approx(0.55, abs=2e-05)
    assert r.beta_mg_a_per_v2 == pytest.approx(0.002, rel=2e-05)
    assert r.vth_mg_v == pytest.approx(expected_vth, abs=2e-06)

def test_extraction_refinement():
    values = []
    for n in (201, 501, 1001):
        u = np.linspace(0, 1, n)
        values.append(extract_mg(u, analytic_curve(u)))
    assert max((x.vth_mg_v for x in values)) - min((x.vth_mg_v for x in values)) < 1e-05

def test_extraction_endpoint():
    u = np.linspace(0, 1, 501)
    with pytest.raises(PreflightError, match='ENDPOINT'):
        extract_mg(u, np.exp(u) * 1e-06)

def test_extraction_duplicate_axis():
    with pytest.raises(PreflightError, match='AXIS'):
        extract_mg(np.ones(20), np.ones(20))

def test_extraction_nonfinite():
    u = np.linspace(0, 1, 20)
    j = np.ones(20)
    j[4] = np.nan
    with pytest.raises(PreflightError, match='NONFINITE'):
        extract_mg(u, j)

def test_extraction_two_peaks():
    u = np.linspace(0, 1, 1001)
    j = analytic_curve(u, 0.35, 0.03) + analytic_curve(u, 0.7, 0.03)
    with pytest.raises(PreflightError, match='AMBIGUOUS'):
        extract_mg(u, j)

def test_mapping_inversion():

    def f(x):
        a, b = x
        return np.array([a + 0.02 * b + 0.005 * a * b, np.expm1(b) + 0.2 * a])
    target = np.array([0.01, 0.02])
    jac, condition = local_jacobian(f, np.array([0.001, 0.01]), np.array([0.01, 0.02]))
    assert np.isfinite(condition) and condition < 20
    assert jac[0, 1] != 0 and jac[1, 0] != 0
    raw = inverse_mapping(f, target, np.array([0.01, 0.02]), (np.array([-0.2, -0.5]), np.array([0.2, 0.5])))
    assert np.allclose(f(raw), target, atol=1e-08)

def test_mapping_no_resample_or_clip():
    with pytest.raises(PreflightError, match='OUT_OF_SCOPE'):
        inverse_mapping(lambda x: x, np.array([0.0, -1.0]), np.ones(2), (-np.ones(2), np.ones(2)))

def test_mapping_impossible_target():
    with pytest.raises(PreflightError, match='NOT_REACHED'):
        inverse_mapping(lambda x: x, np.array([5.0, 0.2]), np.ones(2), (-np.ones(2), np.ones(2)))

def test_hash_no_nan():
    with pytest.raises(ValueError):
        canonical_hash({'nan': float('nan')})
