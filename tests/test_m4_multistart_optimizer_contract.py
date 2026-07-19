from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

import thermal_twin.multistart_impl as implementation
from thermal_twin.multistart import fit_from_initial_parameters
from thermal_twin.topologies import reference_model_bank


def test_multistart_only_changes_x0_not_l_bfgs_b_options_or_bounds(monkeypatch) -> None:
    captured = {}

    def fake_minimize(function, x0, **kwargs):
        captured["x0"] = x0.copy()
        captured["kwargs"] = kwargs
        return SimpleNamespace(x=x0, success=True, status=0, message="ok", nfev=1, nit=0, fun=function(x0))

    monkeypatch.setattr(implementation, "minimize", fake_minimize)
    topology = reference_model_bank()[0]
    frame = pd.DataFrame({"Tin": [20.0, 20.0], "Tout": [10.0, 10.0], "Qhvac_W_A": [0.0, 0.0]})
    initial = np.array([-2.0, 16.0, -9.0])
    fit_from_initial_parameters(topology, frame, initial)
    assert np.array_equal(captured["x0"], initial)
    assert captured["kwargs"]["method"] == "L-BFGS-B"
    assert set(captured["kwargs"]) == {"bounds", "method"}
