from pathlib import Path

import numpy as np
import pandas as pd

from thermal_twin.identification import FittedTopology, evaluate_topology
from thermal_twin.reference_ingestion import split_reference_months
from thermal_twin.topologies import STD_4R3C


def test_notebook_four_r_three_c_parameters_reproduce_the_three_reference_metrics() -> None:
    root = Path(__file__).resolve().parents[1]
    hourly = pd.read_csv(root / "data" / "processed" / "hourly_reference.csv", parse_dates=["Date"]).set_index("Date")
    # Values printed by the notebook; they are intentionally only the available
    # displayed precision, so the assertion tolerance reflects truncation.
    physical = np.array(
        [
            5.13956342e-04,
            2.87774378,
            1.10887673e-01,
            4.51489350e-03,
            1.74260153e10,
            2.98095799e3,
            6.34499651e10,
            3.6386052387,
        ]
    )
    theta = np.log(physical)
    fitted = FittedTopology(
        topology=STD_4R3C,
        parameters_log=theta,
        resistances=physical[:4],
        capacitances=physical[4:7],
        alpha=float(physical[-1]),
        n_parameters=8,
        success=True,
        status=0,
        message="notebook printed parameter oracle",
        nfev=None,
        nit=None,
        objective_mse=0.0,
    )
    splits = split_reference_months(hourly)
    validation = evaluate_topology(fitted, splits["validation"]).metrics
    testing = evaluate_topology(fitted, splits["test"]).metrics
    assert np.isclose(validation.rmse, 4.682382, atol=5e-7)
    assert np.isclose(validation.bic, 4578.578337, atol=3e-6)
    assert np.isclose(testing.rmse, 0.857599, atol=5e-7)
