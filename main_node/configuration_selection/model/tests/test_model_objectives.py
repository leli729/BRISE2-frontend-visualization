import copy

import numpy as np
import pytest

from configuration_selection.model.model import Model
from core_entities.configuration import Configuration
from core_entities.objectives import Objectives

# test case and key of its model, by how the model handles several objectives
CASES = {
    "compositional": (3, "Model"),  # 5 objectives, a surrogate and an optimizer for each of them
    "pure": (2, "Model_0"),  # 5 objectives, one surrogate and one optimizer for all of them
    "dynamic_compositional": (5, "Model"),  # 2 objectives
    "portfolio": (6, "Model"),  # 5 objectives
}
# the models whose surrogates are replaced one to one by those of a source experiment
TRANSFERABLE_CASES = ["compositional", "pure"]


class Setup:
    def __init__(self, description: dict, search_space, key: str, model: Model):
        self.description = description
        self.search_space = search_space
        self.key = key
        self.model = model
        self.objectives_description = description["Context"]["TaskConfiguration"]["Objectives"]


def _model(description: dict, search_space, key: str) -> Model:
    model_description = copy.deepcopy(description["ConfigurationSelection"]["Predictor"][key])
    for name, part in model_description.items():
        if name.startswith("Optimizer"):  # a short search is enough here
            if "MOEA" in part["Instance"]:
                part["Instance"]["MOEA"]["Generations"] = 2  # GACO needs a population as large as its archive
            else:
                part["Instance"]["RandomSearch"]["SamplingSize"] = 100
    objectives = Objectives.from_description(description["Context"]["TaskConfiguration"]["Objectives"])
    return Model((key, model_description), search_space.regions[0], objectives)


def _measured_configurations(region, objectives_description: dict) -> list:
    rng = np.random.default_rng(0)
    configurations = []
    for _ in range(30):
        configuration = Configuration({hp.name: hp.transform(rng.uniform()) for hp in region},
                                      Configuration.Type.TEST, "experiment")
        configuration.results = {name: float(rng.uniform()) for name in objectives_description}
        configuration.status["measured"] = True
        configurations.append(configuration)
    return configurations


def _predicted(get_experiment, case: str) -> Setup:
    """A model that proposed candidates for measured configurations, so that it holds its prediction information."""
    test_case, key = CASES[case]
    description, search_space = get_experiment(test_case)
    setup = Setup(description, search_space, key, _model(description, search_space, key))

    candidates = setup.model.predict(list(setup.model.region),
                                     _measured_configurations(setup.model.region, setup.objectives_description))

    assert not candidates.empty
    return setup


@pytest.fixture(params=list(CASES))
def predicted(request, get_experiment) -> Setup:
    return _predicted(get_experiment, request.param)


@pytest.fixture(params=TRANSFERABLE_CASES)
def predicted_transferable(request, get_experiment) -> Setup:
    return _predicted(get_experiment, request.param)


class TestPredictionInfo:
    """
    The prediction information of a model is stored with the proposed configurations in MongoDB and read back by
    transfer learning, so it holds the objectives as the Experiment Description does.
    """

    def test_the_objectives_of_a_prediction_are_stored_as_in_the_experiment_description(self, predicted):
        stored = predicted.model.created_surrogates_descriptions_and_objectives_and_optimizer_descriptions

        for entry in stored:
            for key in ("Objectives_surrogate", "Objectives_optimizer"):
                assert isinstance(entry[key], dict) and entry[key]
                assert entry[key] == {name: predicted.objectives_description[name] for name in entry[key]}

    def test_the_stored_objectives_of_the_surrogates_cover_all_objectives(self, predicted):
        stored = predicted.model.created_surrogates_descriptions_and_objectives_and_optimizer_descriptions

        assert {name for entry in stored for name in entry["Objectives_surrogate"]} == set(predicted.objectives_description)


class TestCandidateColumns:
    """
    The candidates a model proposes are ranked by the values its optimizers rank them by; each is named by the criterion
    it is a value of, so that a ratio or an upper confidence bound is not mistaken for a prediction of an objective.
    """

    @pytest.mark.parametrize("test_case, key, ranked", [
        (10, "Model", ["Y1"]),  # a regression surrogate predicts the objective
        (1, "Model", ["weighted_sum(Y1,Y2)"]),  # a regression surrogate with a weighted sum
        (3, "Model", [f"ratio(Y{i})" for i in range(1, 6)]),  # tree Parzen estimators with an acquisition function
        (2, "Model_0", ["Y1", "Y2", "Y3", "Y4", "Y5"]),  # one regression surrogate for 5 objectives
    ], ids=["regression", "weighted_sum", "compositional_acquisition_functions", "pure_objectives"])
    def test_a_model_proposes_candidates_with_the_values_they_are_ranked_by(
            self, get_experiment, test_case, key, ranked):
        description, search_space = get_experiment(test_case)
        model = _model(description, search_space, key)
        objectives = description["Context"]["TaskConfiguration"]["Objectives"]

        candidates = model.predict(list(model.region), _measured_configurations(model.region, objectives))

        assert candidates.columns.tolist() == [hp.name for hp in model.region] + ranked


class TestTransferredModels:
    """Transfer learning rebuilds the surrogates and optimizers of a source experiment from the stored information."""

    @staticmethod
    def _names(mapping) -> list:
        return sorted(objectives.names for objectives in mapping.values())

    def test_surrogates_and_optimizers_rebuilt_from_the_stored_information_replace_those_with_the_same_objectives(
            self, predicted_transferable):
        predicted = predicted_transferable
        stored = predicted.model.created_surrogates_descriptions_and_objectives_and_optimizer_descriptions
        target = _model(predicted.description, predicted.search_space, predicted.key)
        surrogates_before = self._names(target.mapping_surrogate_objective)
        optimizers_before = self._names(target.mapping_optimizer_objective)

        target.update_surrogates_and_optimizers(stored)

        # nothing is added next to the replaced ones, if the objectives are not equal
        assert self._names(target.mapping_surrogate_objective) == surrogates_before
        assert self._names(target.mapping_optimizer_objective) == optimizers_before
        assert all(isinstance(surrogate.objectives, Objectives) for surrogate in target.mapping_surrogate_objective)
