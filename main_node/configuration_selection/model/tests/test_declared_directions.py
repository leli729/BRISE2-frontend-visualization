import copy

import numpy as np
import pandas as pd
import pytest

from configuration_selection.model.optimizer.moea import MOEA
from configuration_selection.model.optimizer.random_search import RandomSearch
from configuration_selection.model.surrogate.composite_surrogate import CompositeSurrogate
from configuration_selection.model.surrogate.surrogate_abs import Surrogate
from configuration_selection.model.surrogate.surrogate_orchestrator import SurrogateOrchestrator
from configuration_selection.model.surrogate.tree_parzen_estimator import TreeParzenEstimator
from core_entities.objectives import Objectives
from core_entities.search_space import FloatHyperparameter

X = FloatHyperparameter("x", 0, 0.0, 1.0)
WEIGHTED_SUM = {"ValueTransformers": {"ValueScalarizator": {"WeightedSum": {"Type": "weighted_sum", "Weights": [1, 2]}}}}
TPE_EI = {"ValueTransformers": {"AcquisitionFunction": {"TPE_EI": {"Type": "tpe_ei"}}}}


class ObjectivePredictor(Surrogate):
    """Predicts Y1 = x and Y2 = 1 - x, scalarized by its value transformers if it has any."""

    def create(self, features, labels) -> bool:
        return True

    def predict(self, cfg: pd.Series, transform: bool = True) -> pd.DataFrame:
        return self.predict_batch(pd.DataFrame({"x": [cfg["x"]]}))

    def predict_batch(self, configurations: pd.DataFrame, transform: bool = True) -> pd.DataFrame:
        x = configurations["x"].reset_index(drop=True)
        predicted = pd.DataFrame({name: x if name == "Y1" else 1.0 - x for name in self.objectives.names})
        return self._transform_values(predicted) if self.scalarized else predicted


class ProbabilityPredictor(Surrogate):
    """Predicts the densities of a Tree Parzen Estimator, whose ratio of good to bad is x + 0.01."""

    def create(self, features, labels) -> bool:
        return True

    def output_criteria(self):
        return None

    def predict(self, cfg: pd.Series, transform: bool = True) -> pd.DataFrame:
        return self.predict_batch(pd.DataFrame({"x": [cfg["x"]]}))

    def predict_batch(self, configurations: pd.DataFrame, transform: bool = True) -> pd.DataFrame:
        x = configurations["x"].reset_index(drop=True)
        return pd.DataFrame({"Y1_probability_good": x + 0.01, "Y1_probability_bad": 1.0})


def _named_objectives(**minimizations) -> Objectives:
    return Objectives.from_description({
        name: {"Name": name, "DataType": "float", "Minimization": m, "MinExpectedValue": 0,
               "MaxExpectedValue": float("inf")} for name, m in minimizations.items()})


def _objectives(*minimizations) -> Objectives:
    return _named_objectives(**{f"Y{i + 1}": m for i, m in enumerate(minimizations)})


def _directions(criteria) -> list:
    return [(criterion.name, criterion.minimization) for criterion in criteria]


def _random_search(description: dict, objectives: Objectives) -> RandomSearch:
    return RandomSearch({"Instance": {"RandomSearch": {"SamplingSize": 300}}} | description, (X,), objectives)


def _moea(description: dict, objectives: Objectives) -> MOEA:
    instance = {"Instance": {"MOEA": {"Generations": 40, "PopulationSize": 24, "Algorithms": ["de"]}}}
    return MOEA(instance | description, (X,), objectives)


def _from_case(get_experiment, test_case: int, key: str, surrogate_key: str = "Surrogate"):
    """The surrogate of a model of a test case, and the description, the search space and the objectives around it."""
    description, search_space = get_experiment(test_case)
    model = copy.deepcopy(description["ConfigurationSelection"]["Predictor"][key])
    objectives = Objectives.from_description(description["Context"]["TaskConfiguration"]["Objectives"])
    region = search_space.regions[0]
    surrogate = SurrogateOrchestrator().get_surrogate(model[surrogate_key], region, objectives)
    return surrogate, model, region, objectives


class TestDeclaredOutput:
    """A surrogate declares the direction of each column it predicts."""

    def test_a_surrogate_declares_the_objectives_it_predicts(self):
        surrogate = ObjectivePredictor({}, (X,), _objectives(True, False))

        assert _directions(surrogate.output_criteria()) == [("Y1", True), ("Y2", False)]

    def test_a_scalarizing_surrogate_declares_the_minimized_weighted_sum(self):
        surrogate = ObjectivePredictor(WEIGHTED_SUM, (X,), _objectives(True, False))

        assert _directions(surrogate.output_criteria()) == [("Y", True)]

    def test_a_composite_surrogate_declares_the_declarations_of_its_surrogates(self):
        first = ObjectivePredictor({}, (X,), _objectives(True))
        second = ObjectivePredictor({}, (X,), _named_objectives(Y2=False))

        composite = CompositeSurrogate((first, second), (X,))

        assert _directions(composite.output_criteria()) == [("Y1", True), ("Y2", False)]

    def test_a_regression_surrogate_declares_the_objective(self, get_experiment):
        surrogate, _, _, _ = _from_case(get_experiment, 13, "Model")  # Y1 minimized

        assert _directions(surrogate.output_criteria()) == [("Y1", True)]

    def test_a_multi_armed_bandit_declares_its_upper_confidence_bound_maximized(self, get_experiment):
        surrogate, _, _, _ = _from_case(get_experiment, 11, "Model_0")  # Y1 maximized

        assert _directions(surrogate.output_criteria()) == [("Y1", False)]

    def test_a_scalarizing_multi_armed_bandit_declares_its_upper_confidence_bound_maximized(self, get_experiment):
        surrogate, _, _, _ = _from_case(get_experiment, 8, "Model_0")  # Y1 and Y2 maximized, a weighted sum

        assert _directions(surrogate.output_criteria()) == [("Y", False)]

    def test_a_tree_parzen_estimator_declares_no_rankable_value(self, get_experiment):
        surrogate, _, _, _ = _from_case(get_experiment, 12, "Model_1")

        assert surrogate.output_criteria() is None


class TestResolvedCriteria:
    """The optimizer resolves the direction of every column it ranks."""

    def test_the_objectives_a_surrogate_predicts_keep_their_directions(self):
        objectives = _objectives(True, False)

        resolved = _random_search({}, objectives).resolve_criteria(ObjectivePredictor({}, (X,), objectives))

        assert _directions(resolved) == [("Y1", True), ("Y2", False)]

    def test_a_weighted_sum_is_ranked_minimized(self):
        objectives = _objectives(True, False)

        resolved = _random_search({}, objectives).resolve_criteria(ObjectivePredictor(WEIGHTED_SUM, (X,), objectives))

        assert _directions(resolved) == [("Y", True)]

    def test_a_weighted_sum_of_the_optimizer_is_ranked_minimized(self):
        objectives = _objectives(True, False)

        resolved = _random_search(WEIGHTED_SUM, objectives).resolve_criteria(ObjectivePredictor({}, (X,), objectives))

        assert _directions(resolved) == [("Y", True)]

    @pytest.mark.parametrize("minimization", [True, False])
    def test_an_acquisition_function_ranks_its_score_maximized_under_the_name_of_the_objective(self, minimization):
        objectives = _objectives(minimization)

        resolved = _random_search(TPE_EI, objectives).resolve_criteria(ProbabilityPredictor({}, (X,), objectives))

        assert _directions(resolved) == [("Y1", False)]

    def test_an_upper_confidence_bound_is_ranked_maximized(self, get_experiment):
        surrogate, _, _, objectives = _from_case(get_experiment, 11, "Model_0")

        resolved = _random_search({}, objectives).resolve_criteria(surrogate)

        assert _directions(resolved) == [("Y1", False)]

    def test_densities_without_an_acquisition_function_have_no_direction_to_rank_by(self):
        objectives = _objectives(True)

        with pytest.raises(ValueError):
            _random_search({}, objectives).resolve_criteria(ProbabilityPredictor({}, (X,), objectives))


class TestRankingWithoutADeclaredDirection:

    def test_densities_without_an_acquisition_function_are_not_ranked_by_a_guessed_direction(self):
        # a TPE's densities have no direction until an acquisition function turns them into a score
        objectives = _objectives(True)

        with pytest.raises(ValueError):
            _random_search({}, objectives).optimize(ProbabilityPredictor({}, (X,), objectives))


# the objectives' directions, and whether the best candidate of Y1 = x, Y2 = 1 - x, scalarized as 1 * Y1 + 2 * Y2 (each
# in its own direction), has the largest x: both objectives prefer a small x when Y1 is minimized and Y2 maximized,
# and a large one when Y1 is maximized and Y2 minimized; when both share a direction they conflict, and the weight of
# Y2 decides: Y = 2 - x is minimized (a large x) when both are minimized, and maximized (a small x) when both are
# maximized
WEIGHTED_SUMS = [
    pytest.param((True, True), True, id="both_minimized"),
    pytest.param((False, False), False, id="both_maximized"),
    pytest.param((True, False), False, id="y1_minimized_y2_maximized"),
    pytest.param((False, True), True, id="y1_maximized_y2_minimized"),
]


class TestRankingByDeclaredDirection:

    @pytest.mark.parametrize("minimizations, prefers_large_x", WEIGHTED_SUMS)
    def test_random_search_ranks_a_weighted_sum_of_objectives_in_their_own_directions(self, minimizations, prefers_large_x):
        objectives = _objectives(*minimizations)

        result = _random_search({}, objectives).optimize(ObjectivePredictor(WEIGHTED_SUM, (X,), objectives))

        best = result["x"].max() if prefers_large_x else result["x"].min()
        assert result.iloc[0]["x"] == best

    @pytest.mark.parametrize("minimizations, prefers_large_x", WEIGHTED_SUMS)
    def test_moea_searches_a_weighted_sum_of_objectives_in_their_own_directions(self, minimizations, prefers_large_x):
        objectives = _objectives(*minimizations)

        result = _moea({}, objectives).optimize(ObjectivePredictor(WEIGHTED_SUM, (X,), objectives))

        assert (result.iloc[0]["x"] > 0.95) == prefers_large_x
        assert (result.iloc[0]["x"] < 0.05) != prefers_large_x

    @pytest.mark.parametrize("minimization", [True, False])
    def test_moea_searches_the_ratio_of_good_to_bad_towards_its_maximum_whatever_the_direction_of_the_objective(
            self, minimization):
        objectives = _objectives(minimization)

        result = _moea(TPE_EI, objectives).optimize(ProbabilityPredictor({}, (X,), objectives))

        assert result["Y1"].is_monotonic_decreasing
        assert result.iloc[0]["x"] > 0.95


class TestSurrogatesUnderAScalarizer:

    def test_a_tree_parzen_estimator_splits_good_from_bad_by_the_direction_of_the_weighted_sum(self):
        # Y1 = x maximized and Y2 = 1 - x minimized, weights [1, 2]: Y = -x + 2 * (1 - x) = 2 - 3x is minimized, so the good
        # observations have a large x (the first objective's direction, maximized, would take the small ones)
        objectives = _objectives(False, True)
        description = {
            "ConfigurationTransformers": {
                "FloatTransformer": {"SklearnFloatMinMaxScaler": {"Type": "sklearn_float_transformer"}}},
            "Instance": {"TreeParzenEstimator": {"MultiObjective": False, "Parameters": {
                "top_n_percent": 25, "random_fraction": 0.0, "bandwidth_factor": 3, "min_bandwidth": 0.001}}},
        } | WEIGHTED_SUM
        surrogate = TreeParzenEstimator(description, (X,), objectives)
        values = np.linspace(0, 1, 60)

        assert surrogate.create(pd.DataFrame({"x": values}), pd.DataFrame({"Y1": values, "Y2": 1.0 - values}))

        densities = surrogate.predict_batch(pd.DataFrame({"x": [0.05, 0.95]}))
        ratio = (densities["Y1_probability_good"] / densities["Y1_probability_bad"]).tolist()
        assert ratio[1] > ratio[0]

    def test_a_multi_armed_bandit_prefers_the_categories_of_better_objectives(self, get_experiment):
        # test_case_8: Y1 and Y2 are maximized, scalarized by a weighted sum
        surrogate, _, region, objectives = _from_case(get_experiment, 8, "Model_0")
        rng = np.random.default_rng(0)
        features = pd.DataFrame({hp.name: [hp.categories[rng.integers(len(hp.categories))] for _ in range(60)]
                                 for hp in region})
        first = region[0]
        quality = features[first.name].map({category: index for index, category in enumerate(first.categories)})
        labels = pd.DataFrame({name: quality.astype(float) for name in objectives.names})
        assert surrogate.create(features, labels)

        def upper_confidence_bound(category):
            configuration = pd.Series({hp.name: hp.categories[0] for hp in region})
            configuration[first.name] = category
            return surrogate.predict(configuration)["Y"].iloc[0]

        assert upper_confidence_bound(first.categories[-1]) > upper_confidence_bound(first.categories[0])
