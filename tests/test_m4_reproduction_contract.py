from thermal_twin.reproduction import NOTEBOOK_REFERENCE, ReproductionRow, primary_validation
from thermal_twin.topologies import reference_model_bank


def _row(name: str, rmse: float, bic: float, test: float) -> ReproductionRow:
    topology = next(item for item in reference_model_bank() if item.name == name)
    reference = NOTEBOOK_REFERENCE[name]
    return ReproductionRow(
        model=name,
        n_nodes=topology.n_nodes,
        n_resistances=topology.n_resistances,
        n_capacitances=topology.n_capacitances,
        n_parameters=topology.n_resistances + topology.n_capacitances + 1,
        duplicate_of=topology.duplicate_of,
        fit_success=True,
        fit_status=0,
        fit_message="test",
        fit_nfev=1,
        validation_rmse=rmse,
        validation_mae=0.0,
        validation_bic=bic,
        test_rmse=test,
        test_mae=0.0,
        expected_validation_rmse=reference.validation_rmse,
        expected_validation_bic=reference.validation_bic,
        expected_test_rmse=reference.test_rmse,
        expected_success=reference.success,
        delta_validation_rmse=rmse - reference.validation_rmse,
        delta_validation_bic=bic - reference.validation_bic,
        delta_test_rmse=test - reference.test_rmse,
    )


def test_reference_bank_and_primary_contract_are_frozen() -> None:
    assert len(NOTEBOOK_REFERENCE) == 19
    rows = []
    for topology in reference_model_bank():
        reference = NOTEBOOK_REFERENCE[topology.name]
        value = 4.682382 if topology.name == "STD_4R3C_two_masses_plus_air_shunt" else 5.0
        rows.append(_row(topology.name, value, reference.validation_bic, reference.test_rmse))
    verdict = primary_validation(rows)
    assert verdict["passed"] is True
    assert verdict["eighteen_in_4_98_5_02"] == 18


def test_primary_contract_rejects_a_plausible_but_wrong_four_r_three_c() -> None:
    rows = []
    for topology in reference_model_bank():
        reference = NOTEBOOK_REFERENCE[topology.name]
        value = 4.70 if topology.name == "STD_4R3C_two_masses_plus_air_shunt" else 5.0
        rows.append(_row(topology.name, value, reference.validation_bic, reference.test_rmse))
    verdict = primary_validation(rows)
    assert verdict["passed"] is False
    assert verdict["std_4r3c_exact"] is False
