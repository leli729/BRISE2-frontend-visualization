import pandas as pd
import pytest

from configuration_selection.model.value_transformer.tpe_ei import TpeEi
from configuration_selection.model.value_transformer.weighted_sum import WeightedSum
from core_entities.objectives import Objectives


def _objectives(*minimizations) -> Objectives:
    return Objectives.from_description({
        f"Y{i + 1}": {"Name": f"Y{i + 1}", "DataType": "float", "Minimization": m,
                      "MinExpectedValue": 0, "MaxExpectedValue": float("inf")} for i, m in enumerate(minimizations)})


def _weighted_sum(objectives: Objectives, weights: list) -> WeightedSum:
    return WeightedSum({"WeightedSum": {"Type": "weighted_sum", "Weights": weights}}, objectives)


def _directions(criteria) -> list:
    return [(criterion.name, criterion.minimization) for criterion in criteria]


class TestWeightedSum:

    @pytest.mark.parametrize("minimizations, expected", [
        ((True, True), [12.0, 3.0]),  # the objectives are summed as they are
        ((True, False), [-8.0, -1.0]),  # a maximized objective is subtracted: Y1 - 2 * Y2
        ((False, True), [8.0, 1.0]),  # -Y1 + 2 * Y2
        ((False, False), [-12.0, -3.0]),  # the weighted sum of two maximized objectives is negated: Y is minimized
    ])
    def test_a_maximized_objective_is_weighted_by_its_negation(self, minimizations, expected):
        objectives = _objectives(*minimizations)
        predictions = pd.DataFrame({"Y1": [2.0, 1.0], "Y2": [5.0, 1.0]})

        transformed = _weighted_sum(objectives, [1, 2]).transform(predictions)

        assert transformed["weighted_sum(Y1,Y2)"].tolist() == pytest.approx(expected)

    @pytest.mark.parametrize("minimizations", [(True, True), (True, False), (False, False)])
    def test_the_weighted_sum_is_declared_minimized_whatever_the_directions_of_the_objectives(self, minimizations):
        objectives = _objectives(*minimizations)

        criteria = _weighted_sum(objectives, [1, 2]).transform_criteria(tuple(objectives))

        assert _directions(criteria) == [("weighted_sum(Y1,Y2)", True)]


class TestTpeEi:

    @pytest.mark.parametrize("minimization", [True, False])
    def test_the_ratio_is_declared_maximized_whatever_the_direction_of_the_objective(self, minimization):
        objectives = _objectives(minimization)
        acquisition_function = TpeEi({"TPE_EI": {"Type": "tpe_ei"}}, objectives)

        criteria = acquisition_function.transform_criteria(None)  # a TPE declares no rankable value of its own

        assert _directions(criteria) == [("ratio(Y1)", False)]
