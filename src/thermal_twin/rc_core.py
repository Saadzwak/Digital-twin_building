"""Testable RC graph kernel implementing notebook cell 55 exactly.

Node zero is always the measured indoor-air node.  The outdoor temperature is
a boundary input, never a state.  The kernel uses exact ZOH discretisation of
the continuous graph and open-loop rollout after its initial state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.linalg import expm


Array = np.ndarray


@dataclass(frozen=True)
class RCTopology:
    """An RC topology with internal and outdoor-boundary resistances."""

    name: str
    n_nodes: int
    n_resistances: int
    n_capacitances: int
    edges: tuple[tuple[int, int, int], ...]
    outdoor_edges: tuple[tuple[int, int], ...]
    node_names: tuple[str, ...]
    duplicate_of: str | None = None

    def validate(self) -> None:
        if self.n_nodes <= 0 or self.n_capacitances != self.n_nodes:
            raise ValueError(f"{self.name}: one positive capacity is required per state node.")
        if len(self.node_names) != self.n_nodes or self.node_names[0] != "air":
            raise ValueError(f"{self.name}: node 0 must be named air.")
        resistance_indices = [index for _, _, index in self.edges]
        resistance_indices.extend(index for _, index in self.outdoor_edges)
        if sorted(resistance_indices) != list(range(self.n_resistances)):
            raise ValueError(f"{self.name}: every resistance index must appear exactly once.")
        for left, right, _ in self.edges:
            if not (0 <= left < self.n_nodes and 0 <= right < self.n_nodes):
                raise ValueError(f"{self.name}: internal edge endpoint is out of range.")
            if left == right:
                raise ValueError(f"{self.name}: an internal edge cannot be a self-loop.")
        for node, _ in self.outdoor_edges:
            if not 0 <= node < self.n_nodes:
                raise ValueError(f"{self.name}: outdoor edge endpoint is out of range.")


@dataclass(frozen=True)
class ContinuousMatrices:
    """Continuous graph matrices and explicit heat-input vector."""

    K: Array
    k_out: Array
    A: Array
    b_out: Array
    b_q: Array


@dataclass(frozen=True)
class DiscreteMatrices:
    """Exact zero-order-hold state transition matrices."""

    Ad: Array
    Bd_out: Array
    Bd_q: Array


def _positive_vector(values: Iterable[float], expected_size: int, label: str) -> Array:
    vector = np.asarray(tuple(values), dtype=float)
    if vector.shape != (expected_size,):
        raise ValueError(f"{label} must have shape ({expected_size},), got {vector.shape}.")
    if not np.isfinite(vector).all() or (vector <= 0.0).any():
        raise ValueError(f"{label} must contain only finite strictly positive values.")
    return vector


def build_continuous_matrices(
    topology: RCTopology,
    resistances: Iterable[float],
    capacitances: Iterable[float],
    alpha: float,
) -> ContinuousMatrices:
    """Assemble the notebook's continuous ``A``, ``b_out`` and ``b_q``.

    ``alpha * Q`` is injected at the indoor-air node only.  The vector order
    is topology order, including the numeric order used by the notebook; it is
    intentionally not reordered to make the 4R3C figure more intuitive.
    """

    topology.validate()
    R = _positive_vector(resistances, topology.n_resistances, "resistances")
    C = _positive_vector(capacitances, topology.n_capacitances, "capacitances")
    if not np.isfinite(alpha) or alpha <= 0.0:
        raise ValueError("alpha must be finite and strictly positive.")

    K = np.zeros((topology.n_nodes, topology.n_nodes), dtype=float)
    k_out = np.zeros(topology.n_nodes, dtype=float)
    for left, right, resistance_index in topology.edges:
        conductance = 1.0 / R[resistance_index]
        K[left, left] += conductance
        K[right, right] += conductance
        K[left, right] -= conductance
        K[right, left] -= conductance
    for node, resistance_index in topology.outdoor_edges:
        conductance = 1.0 / R[resistance_index]
        K[node, node] += conductance
        k_out[node] += conductance
    inverse_capacitances = np.diag(1.0 / C)
    A = -inverse_capacitances @ K
    b_out = inverse_capacitances @ k_out
    b_q = np.zeros(topology.n_nodes, dtype=float)
    b_q[0] = alpha / C[0]
    return ContinuousMatrices(K=K, k_out=k_out, A=A, b_out=b_out, b_q=b_q)


def discretize_exact(matrices: ContinuousMatrices, dt_seconds: float) -> DiscreteMatrices:
    """Discretise with the augmented exponential used in notebook cell 55."""

    if not np.isfinite(dt_seconds) or dt_seconds <= 0.0:
        raise ValueError("dt_seconds must be finite and strictly positive.")
    n_nodes = matrices.A.shape[0]
    augmented = np.zeros((n_nodes + 2, n_nodes + 2), dtype=float)
    augmented[:n_nodes, :n_nodes] = matrices.A
    augmented[:n_nodes, n_nodes] = matrices.b_out
    augmented[:n_nodes, n_nodes + 1] = matrices.b_q
    discrete = expm(augmented * dt_seconds)
    return DiscreteMatrices(
        Ad=discrete[:n_nodes, :n_nodes],
        Bd_out=discrete[:n_nodes, n_nodes],
        Bd_q=discrete[:n_nodes, n_nodes + 1],
    )


def simulate_open_loop(
    topology: RCTopology,
    tout: Iterable[float],
    q_hvac: Iterable[float],
    dt_seconds: float,
    parameters_log: Iterable[float],
    tin_initial: float,
) -> Array:
    """Roll out the fixed open-loop ZOH model from a measured initial Tin.

    Inputs at index ``k`` control the transition from ``k`` to ``k + 1``;
    after initialization, measured Tin is never fed back into the state.
    """

    topology.validate()
    tout_values = np.asarray(tuple(tout), dtype=float)
    q_values = np.asarray(tuple(q_hvac), dtype=float)
    if tout_values.ndim != 1 or q_values.ndim != 1 or len(tout_values) != len(q_values):
        raise ValueError("tout and q_hvac must be one-dimensional arrays of equal length.")
    if len(tout_values) == 0:
        raise ValueError("tout and q_hvac cannot be empty.")
    if not np.isfinite(tout_values).all() or not np.isfinite(q_values).all() or not np.isfinite(tin_initial):
        raise ValueError("simulation inputs and initial Tin must be finite.")
    theta = np.asarray(tuple(parameters_log), dtype=float)
    expected = topology.n_resistances + topology.n_capacitances + 1
    if theta.shape != (expected,) or not np.isfinite(theta).all():
        raise ValueError(f"parameters_log must have shape ({expected},) and finite values.")
    physical = np.exp(theta)
    matrices = build_continuous_matrices(
        topology,
        physical[: topology.n_resistances],
        physical[topology.n_resistances : -1],
        float(physical[-1]),
    )
    discrete = discretize_exact(matrices, dt_seconds)
    state = np.empty((len(tout_values), topology.n_nodes), dtype=float)
    state[0, :] = tin_initial
    for index in range(len(tout_values) - 1):
        state[index + 1] = (
            discrete.Ad @ state[index]
            + discrete.Bd_out * tout_values[index]
            + discrete.Bd_q * q_values[index]
        )
    return state[:, 0]
