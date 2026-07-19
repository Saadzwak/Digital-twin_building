"""Frozen 19-topology bank from notebook cell 55."""

from __future__ import annotations

from .rc_core import RCTopology


def make_ladder(n_nodes: int) -> RCTopology:
    if not 1 <= n_nodes <= 10:
        raise ValueError("Reference ladder sizes are 1 through 10.")
    return RCTopology(
        name=f"LADDER_{n_nodes}R{n_nodes}C",
        n_nodes=n_nodes,
        n_resistances=n_nodes,
        n_capacitances=n_nodes,
        edges=tuple((node, node + 1, node) for node in range(n_nodes - 1)),
        outdoor_edges=((n_nodes - 1, n_nodes - 1),),
        node_names=("air",) + tuple(f"M{number}" for number in range(1, n_nodes)),
    )


STD_1R1C = RCTopology(
    "STD_1R1C", 1, 1, 1, (), ((0, 0),), ("air",), duplicate_of="LADDER_1R1C"
)
STD_2R1C = RCTopology(
    "STD_2R1C_parallel_losses", 1, 2, 1, (), ((0, 0), (0, 1)), ("air",)
)
STD_2R2C = RCTopology(
    "STD_2R2C_air_mass", 2, 2, 2, ((0, 1, 0),), ((1, 1),), ("air", "M1"), duplicate_of="LADDER_2R2C"
)
STD_3R2C = RCTopology(
    "STD_3R2C_air_shunt", 2, 3, 2, ((0, 1, 0),), ((1, 1), (0, 2)), ("air", "M1")
)
STD_3R3C = RCTopology(
    "STD_3R3C_two_masses_series", 3, 3, 3, ((0, 1, 0), (1, 2, 1)), ((2, 2),), ("air", "M1", "M2"), duplicate_of="LADDER_3R3C"
)
STD_4R3C = RCTopology(
    "STD_4R3C_two_masses_plus_air_shunt", 3, 4, 3, ((0, 1, 0), (1, 2, 1)), ((2, 2), (0, 3)), ("air", "M1", "M2")
)
STD_5R3C = RCTopology(
    "STD_5R3C_air_shunt_mid_shunt", 3, 5, 3, ((0, 1, 0), (1, 2, 1)), ((2, 2), (0, 3), (1, 4)), ("air", "M1", "M2")
)
STD_6R4C = RCTopology(
    "STD_6R4C_three_masses_plus_shunts", 4, 6, 4, ((0, 1, 0), (1, 2, 1), (2, 3, 2)), ((3, 3), (0, 4), (1, 5)), ("air", "M1", "M2", "M3")
)
STD_7R5C = RCTopology(
    "STD_7R5C_four_masses_plus_shunts", 5, 7, 5, ((0, 1, 0), (1, 2, 1), (2, 3, 2), (3, 4, 3)), ((4, 4), (0, 5), (2, 6)), ("air", "M1", "M2", "M3", "M4")
)


def reference_model_bank() -> tuple[RCTopology, ...]:
    """Return all 19 labels in notebook order; no isomorphic label is removed."""

    return tuple(make_ladder(n_nodes) for n_nodes in range(1, 11)) + (
        STD_1R1C,
        STD_2R1C,
        STD_2R2C,
        STD_3R2C,
        STD_3R3C,
        STD_4R3C,
        STD_5R3C,
        STD_6R4C,
        STD_7R5C,
    )


FOUR_R_THREE_C_FIGURE_MAPPING = {
    "notebook_nodes": {"air": "Tair", "M1": "Tm2", "M2": "Tm1"},
    "notebook_capacitances": {"C0": "C_air", "C1": "C2", "C2": "C1"},
    "notebook_resistances": {"R0": "R3", "R1": "R2", "R2": "R1", "R3": "R4_air_outdoor_shunt"},
    "display_rule": "Do not interpret identified capacities as independently physical building elements.",
}
