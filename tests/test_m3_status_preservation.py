import numpy as np
import pandas as pd

from thermal_twin.identification import FittedTopology, evaluate_topology
from thermal_twin.topologies import reference_model_bank


def test_metrics_are_preserved_when_optimizer_status_is_unsuccessful() -> None:
    topology = reference_model_bank()[0]
    theta = np.log([0.2, 1e7, 1e-4])
    fitted = FittedTopology(
        topology=topology,
        parameters_log=theta,
        resistances=np.exp(theta[:1]),
        capacitances=np.exp(theta[1:2]),
        alpha=float(np.exp(theta[-1])),
        n_parameters=3,
        success=False,
        status=1,
        message="deliberate test status",
        nfev=0,
        nit=0,
        objective_mse=0.0,
    )
    frame = pd.DataFrame({"Tin": [20.0, 21.0, 20.5], "Tout": [5.0, 5.0, 5.0], "Qhvac_W_A": [1000.0, 1000.0, 1000.0]})
    evaluation = evaluate_topology(fitted, frame)
    assert fitted.success is False
    assert evaluation.metrics.n_observations == 3
    assert np.isfinite(evaluation.metrics.rmse)
    assert np.isfinite(evaluation.metrics.bic)
