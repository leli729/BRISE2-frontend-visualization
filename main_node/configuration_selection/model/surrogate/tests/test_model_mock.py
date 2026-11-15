import random

import numpy as np
import pandas as pd
import pytest

from configuration_selection.model.surrogate.model_mock import ModelMock
from core_entities.objectives import Objectives
from core_entities.search_space import FloatHyperparameter

X = FloatHyperparameter("x", 0, 0.0, 1.0)
DESCRIPTION = {"Instance": {"ModelMock": {"MultiObjective": False}}}
WEIGHTED_SUM = {"ValueTransformers": {"ValueScalarizator": {
    "WeightedSum": {"Type": "weighted_sum", "Weights": [1, 2]}}}}


def _ranged_objectives(*ranges, data_type="float") -> Objectives:
    """Objectives Y1, Y2, … of the given (minimized, lowest expected value, highest expected value)."""
    return Objectives.from_description({
        f"Y{i + 1}": {"Name": f"Y{i + 1}", "DataType": data_type, "Minimization": minimization,
                      "MinExpectedValue": lowest, "MaxExpectedValue": highest}
        for i, (minimization, lowest, highest) in enumerate(ranges)})


def _predictions(objectives: Objectives):
    """The random values of a stub without and with a weighted sum of [1, 2], for 300 candidates."""
    features = pd.DataFrame({"x": np.linspace(0, 1, 300)})
    random.seed(0)
    plain = ModelMock(DESCRIPTION, (X,), objectives)
    scalarizing = ModelMock(DESCRIPTION | WEIGHTED_SUM, (X,), objectives)
    return plain.predict_batch(features), scalarizing.predict_batch(features).iloc[:, 0]


class TestModelMockValues:
    """The values rank candidates at random; they are drawn for each objective in its expected range."""

    def test_each_objective_is_drawn_in_its_range_and_the_weighted_sum_is_taken_of_the_draws(self):
        # Y1 in [0, 10] minimized and Y2 in [0, 10] maximized, weights [1, 2]: Y1 - 2 * Y2 lies in [-20, 10]
        drawn, weighted = _predictions(_ranged_objectives((True, 0, 10), (False, 0, 10)))

        assert drawn.min().min() >= 0 and drawn.max().max() <= 10
        assert weighted.min() >= -20 and weighted.max() <= 10
        assert weighted.min() < -5 and weighted.max() > 0  # the draws are spread over the range, not constant

    @pytest.mark.parametrize("range_of_y2", [(0, float("inf")), (float("-inf"), 0), (float("-inf"), float("inf"))])
    def test_an_objective_with_an_infinite_range_is_drawn_unscaled_between_0_and_1(self, range_of_y2):
        # the draws only rank candidates, so an infinite range needs no scale, and gives no inf or nan
        drawn, weighted = _predictions(_ranged_objectives((True, 0, 10), (False, *range_of_y2)))

        assert drawn["random(Y1)"].between(0, 10).all()  # a finite range is scaled as before
        assert drawn["random(Y2)"].between(0, 1).all() and drawn["random(Y2)"].nunique() > 1
        assert weighted.between(-2, 10).all()  # Y1 - 2 * Y2 with Y2 in [0, 1]

    def test_an_integer_objective_with_an_infinite_range_is_drawn_as_0_or_1(self):
        drawn, _ = _predictions(_ranged_objectives((True, 0, float("inf")), (False, 0, 10), data_type="int"))

        assert set(drawn["random(Y1)"]) == {0, 1}
        # a finite range is scaled
        assert drawn["random(Y2)"].between(0, 10).all() and drawn["random(Y2)"].nunique() > 2
