"""Accelerated ZOH rollout for the product demo, equivalence-checked.

The frozen reproduction protocol keeps ``rc_core.simulate_open_loop`` as its
only simulator.  The live product view needs many fits inside one browser
interaction, so this module evaluates the identical discrete recurrence
through modal decomposition and ``scipy.signal.lfilter``.  When the transition
matrix is too ill-conditioned to diagonalise safely, it falls back to the
exact reference loop, so callers never trade correctness for speed.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

from .rc_core import RCTopology, build_continuous_matrices, discretize_exact

# Above this eigenvector condition number the modal path may lose precision;
# the reference loop is used instead.
_MAX_EIGENVECTOR_CONDITION = 1e8


def _reference_rollout(
    Ad: np.ndarray,
    Bd_out: np.ndarray,
    Bd_q: np.ndarray,
    tout: np.ndarray,
    q_hvac: np.ndarray,
    tin_initial: float,
) -> np.ndarray:
    n_steps = len(tout)
    state = np.empty((n_steps, Ad.shape[0]), dtype=float)
    state[0, :] = tin_initial
    for index in range(n_steps - 1):
        state[index + 1] = Ad @ state[index] + Bd_out * tout[index] + Bd_q * q_hvac[index]
    return state[:, 0]


def simulate_open_loop_fast(
    topology: RCTopology,
    tout: np.ndarray,
    q_hvac: np.ndarray,
    dt_seconds: float,
    parameters_log: np.ndarray,
    tin_initial: float,
) -> np.ndarray:
    """Return the same trajectory as ``rc_core.simulate_open_loop``.

    The recurrence x[k+1] = Ad x[k] + u[k] is decomposed as z = V^-1 x with
    Ad = V diag(lam) V^-1, giving one first-order filter per mode.
    """

    tout = np.asarray(tout, dtype=float)
    q_hvac = np.asarray(q_hvac, dtype=float)
    theta = np.asarray(parameters_log, dtype=float)
    physical = np.exp(theta)
    matrices = build_continuous_matrices(
        topology,
        physical[: topology.n_resistances],
        physical[topology.n_resistances : -1],
        float(physical[-1]),
    )
    discrete = discretize_exact(matrices, dt_seconds)
    n_steps = len(tout)
    n_nodes = topology.n_nodes

    if n_nodes == 1:
        a = float(discrete.Ad[0, 0])
        drive = discrete.Bd_out[0] * tout[: n_steps - 1] + discrete.Bd_q[0] * q_hvac[: n_steps - 1]
        output = np.empty(n_steps, dtype=float)
        output[0] = tin_initial
        if n_steps > 1:
            filtered, _ = lfilter([1.0], [1.0, -a], drive, zi=np.array([a * tin_initial]))
            output[1:] = filtered
        return output

    eigenvalues, eigenvectors = np.linalg.eig(discrete.Ad)
    condition = np.linalg.cond(eigenvectors)
    if not np.isfinite(condition) or condition > _MAX_EIGENVECTOR_CONDITION:
        return _reference_rollout(discrete.Ad, discrete.Bd_out, discrete.Bd_q, tout, q_hvac, tin_initial)

    initial_state = np.full(n_nodes, float(tin_initial))
    drive = np.outer(tout[: n_steps - 1], discrete.Bd_out) + np.outer(q_hvac[: n_steps - 1], discrete.Bd_q)
    inverse_eigenvectors = np.linalg.inv(eigenvectors)
    z0 = inverse_eigenvectors @ initial_state.astype(complex)
    w = drive.astype(complex) @ inverse_eigenvectors.T

    output = np.empty(n_steps, dtype=float)
    output[0] = tin_initial
    if n_steps > 1:
        row = eigenvectors[0, :]
        accumulator = np.zeros(n_steps - 1, dtype=complex)
        for mode in range(n_nodes):
            lam = eigenvalues[mode]
            filtered, _ = lfilter(
                np.array([1.0 + 0.0j]),
                np.array([1.0 + 0.0j, -lam]),
                w[:, mode],
                zi=np.array([lam * z0[mode]]),
            )
            accumulator += row[mode] * filtered
        output[1:] = accumulator.real
    return output
