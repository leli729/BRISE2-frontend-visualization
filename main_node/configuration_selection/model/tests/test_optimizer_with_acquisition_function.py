import numpy as np
import pandas as pd
import pytest

from core_entities.objectives import Objectives
from core_entities.search_space import FloatHyperparameter
from configuration_selection.model.optimizer.random_search import RandomSearch
from configuration_selection.model.surrogate.tree_parzen_estimator import TreeParzenEstimator

X = FloatHyperparameter("x", 0, 0.0, 1.0)


def _objectives(minimization):
    return Objectives.from_description({"Y1": {"Name": "Y1", "DataType": "float", "Minimization": minimization,
                                               "MinExpectedValue": 0, "MaxExpectedValue": float("inf")}})


class TestRandomSearchWithTreeParzenEstimator:
    """
    A Tree Parzen Estimator predicts probabilities, which only the acquisition function of the optimizer turns into
    a score per candidate.
    """

    @staticmethod
    def _trained_surrogate(objectives):
        description = {
            "ConfigurationTransformers": {
                "FloatTransformer": {"SklearnFloatMinMaxScaler": {"Type": "sklearn_float_transformer"}}},
            "Instance": {"TreeParzenEstimator": {"MultiObjective": False, "Parameters": {
                "top_n_percent": 25, "random_fraction": 0.0, "bandwidth_factor": 3, "min_bandwidth": 0.001}}},
        }
        surrogate = TreeParzenEstimator(description, (X,), objectives)
        values = np.linspace(0, 1, 60)
        assert surrogate.create(pd.DataFrame({"x": values}), pd.DataFrame({"Y1": values}))
        return surrogate

    @staticmethod
    def _optimized(minimization: bool):
        objectives = _objectives(minimization)
        description = {"Instance": {"RandomSearch": {"SamplingSize": 60}},
                       "ValueTransformers": {"AcquisitionFunction": {"TPE_EI": {"Type": "tpe_ei"}}}}
        optimizer = RandomSearch(description, (X,), objectives)
        return optimizer.optimize(TestRandomSearchWithTreeParzenEstimator._trained_surrogate(objectives))

    @pytest.mark.parametrize("minimization", [True, False])
    def test_candidates_are_scored_by_the_acquisition_function_and_returned_best_first(self, minimization):
        result = self._optimized(minimization)

        assert "ratio(Y1)" in result.columns  # the score is reported as the ratio it is, where the model reads it
        assert "Y1" not in result.columns  # not as a value of the objective
        assert "Y1_probability_good" not in result.columns
        assert result["ratio(Y1)"].is_monotonic_decreasing  # the score is the ratio of good to bad, the highest first

    def test_the_best_candidate_has_a_small_x_when_the_objective_is_minimized(self):
        # the observations are x = 0..1 with Y1 = x, so the best ones are at the low end
        assert self._optimized(minimization=True).iloc[0]["x"] < 0.15

    def test_the_best_candidate_has_a_large_x_when_the_objective_is_maximized(self):
        assert self._optimized(minimization=False).iloc[0]["x"] > 0.85
