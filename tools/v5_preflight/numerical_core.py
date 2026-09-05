# SPDX-FileCopyrightText: 2026 APM preflight contributors
# SPDX-License-Identifier: Apache-2.0

"""Exploratory v5 helpers. Not a released APM statistical model.

All coefficients used by the tests are artificial numerical test inputs.
A beta coefficient for a public measurement profile is deliberately absent.
"""
from __future__ import annotations
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Callable
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import least_squares, minimize_scalar
from scipy.signal import find_peaks
from scipy.special import ndtr

class PreflightError(ValueError):
    pass

def canonical_hash(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    return hashlib.sha256(data).hexdigest()

def normal_draw(seed: int, sample_index: int, device_uid: str, channel: str) -> float:
    """Keyed stream; no temperature, geometry, profile, worker or list position.

    Reusing this draw with different geometry is common-random-number coupling,
    NOT a claim that the two resulting devices are the same physical specimen.
    Persist returned draws; the RNG call is not a cross-version replay promise.
    """
    for name, value in (('seed', seed), ('sample_index', sample_index)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PreflightError(f'{name} must be a nonnegative integer')
    if not device_uid or not channel:
        raise PreflightError('UID and channel must be nonempty')
    key = {'method': 'apm-v5-preflight-keyed-normal@1', 'seed': seed, 'sample_index': sample_index, 'device_uid': device_uid, 'channel': channel}
    words = np.frombuffer(bytes.fromhex(canonical_hash(key)), dtype='<u4').tolist()
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(words)))
    return float(rng.standard_normal())

def pair_coefficient_to_device_sigma(a_pair: float, w_um: float, l_um: float) -> float:
    """a_pair must already be normalized to quantity*micrometre.

    Independent, identical devices are assumed. No percent-to-fraction guess.
    """
    values = (a_pair, w_um, l_um)
    if not all((math.isfinite(x) for x in values)) or a_pair < 0 or min(w_um, l_um) <= 0:
        raise PreflightError('invalid coefficient or geometry')
    return a_pair / math.sqrt(2.0 * w_um * l_um)

def covariance_from_pair_coefficients(avt: float, abeta: float, w_um: float, l_um: float, rho: float=0.0) -> np.ndarray:
    if not math.isfinite(rho) or abs(rho) > 1.0:
        raise PreflightError('rho must be in [-1,1]')
    sv = pair_coefficient_to_device_sigma(avt, w_um, l_um)
    sb = pair_coefficient_to_device_sigma(abeta, w_um, l_um)
    return np.array([[sv * sv, rho * sv * sb], [rho * sv * sb, sb * sb]])

def pair_relative(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a, b = (np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    if a.shape != b.shape or not np.all(np.isfinite(a)) or (not np.all(np.isfinite(b))):
        raise PreflightError('invalid pair arrays')
    if np.any(a <= 0) or np.any(b <= 0):
        raise PreflightError('relative pair observable requires positive magnitudes')
    return 2.0 * (a - b) / (a + b)

def aggregate_tail_risk(n_draws: int, sigma_limit: float) -> dict[str, float]:
    """Independent scalar normal draws and a rectangular domain only."""
    if isinstance(n_draws, bool) or not isinstance(n_draws, int) or n_draws <= 0:
        raise PreflightError('n_draws must be a positive integer')
    if not math.isfinite(sigma_limit) or sigma_limit <= 0:
        raise PreflightError('sigma_limit must be positive')
    p = float(2.0 * ndtr(-sigma_limit))
    any_failure = -math.expm1(n_draws * math.log1p(-p))
    return {'single_draw_probability': p, 'expected_count': n_draws * p, 'probability_at_least_one': any_failure}

@dataclass(frozen=True)
class MGResult:
    u_star_v: float
    gm_max_s: float
    vth_mg_v: float
    beta_mg_a_per_v2: float
    peak_kind: str

def extract_mg(u: np.ndarray, current_magnitude: np.ndarray, vds: float=0.05) -> MGResult:
    """Exploratory deterministic maximum-gm extraction for smooth DC data.

    Cubic-spline differentiation, no smoothing/fitted physical compact model.
    Grid refinement remains a separate mandatory test. Does not infer VTH0.
    """
    u, j = (np.asarray(u, dtype=float), np.asarray(current_magnitude, dtype=float))
    if u.ndim != 1 or j.shape != u.shape or len(u) < 9:
        raise PreflightError('CURVE_SHAPE_INVALID')
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(j)):
        raise PreflightError('NONFINITE_CURVE')
    if np.any(np.diff(u) <= 0) or vds <= 0:
        raise PreflightError('CURVE_AXIS_INVALID')
    if np.any(j < 0):
        raise PreflightError('CURRENT_MAGNITUDE_NEGATIVE')
    spline = CubicSpline(u, j)
    deriv = spline.derivative()
    gm = deriv(u)
    k = int(np.argmax(gm))
    if gm[k] <= 0:
        raise PreflightError('NONPOSITIVE_GM')
    if k < 2 or k > len(u) - 3:
        raise PreflightError('EXTRACTION_ENDPOINT_LIMITED')
    candidates, _ = find_peaks(gm)
    competitors = [int(i) for i in candidates if gm[i] >= 0.995 * gm[k] and abs(u[i] - u[k]) > 0.02]
    if competitors:
        raise PreflightError('EXTRACTION_PEAK_AMBIGUOUS')
    result = minimize_scalar(lambda x: -float(deriv(x)), bounds=(u[k - 1], u[k + 1]), method='bounded', options={'xatol': 1e-12})
    if not result.success:
        raise PreflightError('EXTRACTION_SOLVER_FAILED')
    x = float(result.x)
    g = float(deriv(x))
    return MGResult(x, g, x - float(spline(x)) / g - abs(vds) / 2, g / abs(vds), 'interior_peak')

def local_jacobian(function: Callable[[np.ndarray], np.ndarray], raw_steps: np.ndarray, output_scales: np.ndarray) -> tuple[np.ndarray, float]:
    h, s = (np.asarray(raw_steps, float), np.asarray(output_scales, float))
    if h.shape != (2,) or s.shape != (2,) or np.any(h <= 0) or np.any(s <= 0):
        raise PreflightError('invalid scales')
    jac = np.column_stack([(np.asarray(function(np.eye(2)[i] * h[i])) - np.asarray(function(-np.eye(2)[i] * h[i]))) / (2 * h[i]) for i in range(2)])
    scaled = np.diag(1 / s) @ jac @ np.diag(h)
    if not np.all(np.isfinite(scaled)):
        raise PreflightError('LOCAL_VARIATION_MAPPING_NONFINITE')
    return (jac, float(np.linalg.cond(scaled)))

def inverse_mapping(function: Callable[[np.ndarray], np.ndarray], target: np.ndarray, scales: np.ndarray, bounds: tuple[np.ndarray, np.ndarray], initial: np.ndarray | None=None) -> np.ndarray:
    target, scales = (np.asarray(target, float), np.asarray(scales, float))
    if target.shape != (2,) or scales.shape != (2,) or np.any(scales <= 0):
        raise PreflightError('invalid target/scales')
    if not np.all(np.isfinite(target)) or not np.all(np.isfinite(scales)):
        raise PreflightError('nonfinite target/scales')
    if target[1] <= -1:
        raise PreflightError('LOCAL_BETA_LINEAR_MODEL_OUT_OF_SCOPE')
    x0 = np.zeros(2) if initial is None else np.asarray(initial, float)
    lower, upper = map(lambda a: np.asarray(a, float), bounds)

    def residual(x):
        return (np.asarray(function(x)) - target) / scales

    def jacobian(x):
        columns = []
        for i, step in enumerate((0.0001, 0.001)):
            lo, hi = (x.copy(), x.copy())
            lo[i] = max(lower[i], x[i] - step)
            hi[i] = min(upper[i], x[i] + step)
            if hi[i] <= lo[i]:
                raise PreflightError('MAPPING_DIFFERENCE_DOMAIN_EMPTY')
            columns.append((residual(hi) - residual(lo)) / (hi[i] - lo[i]))
        return np.column_stack(columns)
    result = least_squares(residual, x0, jac=jacobian, bounds=(lower, upper), xtol=1e-11, ftol=1e-11, gtol=1e-11, max_nfev=50)
    if not result.success or np.max(np.abs(result.fun)) > 0.01:
        raise PreflightError('MAPPING_TARGET_NOT_REACHED')
    return result.x
