import pandas as pd
import pytest

from configuration_selection.model.value_transformer.tpe_ei import TpeEi
from core_entities.objectives import Objectives

# rows of (probability_good, probability_bad); the last one has no good density; the ratio is good / bad
PROBABILITIES = pd.DataFrame({"Y1_probability_good": [0.5, 0.2, 0.0], "Y1_probability_bad": [0.1, 0.4, 0.3]})


def _acquisition_function(minimization):
    objectives = Objectives.from_description({"Y1": {"Name": "Y1", "DataType": "float", "Minimization": minimization,
                                                      "MinExpectedValue": 0, "MaxExpectedValue": float("inf")}})
    return TpeEi({"TPE_EI": {"Type": "tpe_ei"}}, objectives)


class TestTpeEi:

    @pytest.mark.parametrize("minimization", [True, False])
    def test_each_row_of_a_batch_gets_its_own_ratio_of_good_to_bad_whatever_the_direction(self, minimization):
        acquisition_function = _acquisition_function(minimization)

        batch = acquisition_function.transform(PROBABILITIES)["ratio(Y1)"].tolist()
        rows = []
        for i in range(len(PROBABILITIES)):
            row = acquisition_function.transform(PROBABILITIES.iloc[[i]].reset_index(drop=True))
            rows.append(row["ratio(Y1)"].iloc[0])

        assert batch == pytest.approx([5.0, 0.5, 0.0])
        assert rows == pytest.approx([5.0, 0.5, 0.0])

    @pytest.mark.parametrize("minimization", [True, False])
    def test_a_row_without_a_finite_ratio_gets_its_good_density_whatever_the_direction(self, minimization):
        # no observation of the bad group has this value: the ratio is infinite, and a higher value ranks better; a TPE never
        # produces this, since it floors both densities at 1e-32, so it checks TpeEi as a unit
        probabilities = pd.DataFrame({"Y1_probability_good": [0.5], "Y1_probability_bad": [0.0]})

        ratio = _acquisition_function(minimization).transform(probabilities)["ratio(Y1)"].tolist()

        assert ratio == pytest.approx([0.5])
