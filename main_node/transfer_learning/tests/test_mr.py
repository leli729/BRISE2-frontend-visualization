from typing import Dict, Tuple
from copy import deepcopy
from types import SimpleNamespace

import numpy as np

from core_entities.configuration import Configuration
from core_entities.experiment import Experiment
from core_entities.search_space import SearchSpace, get_search_space_record
from configuration_selection.configuration_selection import ConfigurationSelection
from configuration_selection.model.surrogate.tree_parzen_estimator import TreeParzenEstimator
from transfer_learning.transfer_learning_module import TransferLearningOrchestrator
from transfer_learning.model_recommendation.dynamic_model_recommendation import DynamicModelRecommendation
from sklearn.gaussian_process import GaussianProcessRegressor
from tools.initial_config import load_experiment_setup
from tools.restore_db import RestoreDB


experiment_description_file = "./Resources/tests/test_cases_product_configurations/test_case_0.json"
rdb = RestoreDB()

TIME_THRESHOLD = 0.5
FAST = 0.01
SLOW = 2.0
OBJECTIVE = {"Y1": {"Name": "Y1", "DataType": "float", "Minimization": True, "MinExpectedValue": 0, "MaxExpectedValue": 100}}

# a source's samples: the first three were sampled, the rest predicted by a model
SAMPLED = 3
SAMPLES = 12


class TestMR:
    def test_recommends_the_model_of_a_similar_experiment(self, get_workers, get_configurations_2_float):
        rdb.cleanup()
        rdb.restore()
        experiment, search_space = self.initialize_experiment()
        experiment.database.write_one_record(
            "Search_space", get_search_space_record(search_space, experiment.unique_id)
        )

        cs = ConfigurationSelection(experiment)
        tl = TransferLearningOrchestrator(experiment_id=experiment.unique_id,
                                          experiment_description=experiment.description)
        predicted, measured = cs.send_new_configurations_to_measure("", "", "", get_workers)
        results = get_configurations_2_float[0]['Result']
        del results["Y3"]
        del results["Y4"]
        del results["Y5"]
        predicted[0].results = results
        predicted[0].status['measured'] = True
        predicted[0].status['evaluated'] = True
        experiment.default_configuration = predicted[0]

        for i in range(1, 10):
            predicted, measured = cs.send_new_configurations_to_measure("", "", "", get_workers)

            results = get_configurations_2_float[i]['Result']
            del results["Y3"]
            del results["Y4"]
            del results["Y5"]
            predicted[0].results = results
            predicted[0].status['measured'] = True
            predicted[0].status['evaluated'] = True

            experiment.measured_configurations.append(predicted[0])
            experiment.database.write_one_record("Configuration", predicted[0].get_configuration_record())
            experiment.send_state_to_db()

        similar_experiments = tl.ted_module.analyse_experiments_similarity()

        mapping_region_model = tl.transfer_submodules["Model_transfer"].recommend_best_model(similar_experiments)
        region = list(mapping_region_model.keys())[0]
        isinstance(region, Tuple)
        surrogate = list(mapping_region_model[region].mapping_surrogate_objective.keys())[0]
        assert isinstance(surrogate.surrogate_instance, GaussianProcessRegressor)

    def test_soft_threshold_recommends_a_model_that_builds_too_slowly(self, get_workers, get_configurations_2_float):
        rdb.restore()

        soft_constraint_skeleton = {
            "TransferLearning": {
                "TransferExpediencyDetermination": {
                    "SamplingLandmarkBased": {
                        "MinNumberOfSamples": 10,
                        "Type": "sampling_landmark_based",
                        "Comparator": {
                            "NormDifference": {
                                "Type": "norm_difference_comparator"
                            }
                        },
                        "ExperimentsQuantity": {
                            "FixedQuantity": {
                                "NumberOfSimilarExperiments": 1
                            }
                        }
                    }
                },
                "ModelRecommendation": {
                    "DynamicModelsRecommendation": {
                        "RecommendationGranularity": {
                            "Infinite": {
                                "Value": np.inf
                            }
                        },
                        "PerformanceMetric": {
                            "AverageRelativeImprovement": {}
                        },
                        "Type": "dynamic_model_recommendation",
                        "ThresholdType": "Soft",
                        "TimeToBuildModelThreshold": 0.01,
                        "TimeUnit": "seconds"
                    }
                }
            }
        }

        experiment, search_space = self.initialize_experiment(soft_constraint_skeleton)
        experiment.database.write_one_record(
            "Search_space", get_search_space_record(search_space, experiment.unique_id)
        )

        cs = ConfigurationSelection(experiment)
        tl = TransferLearningOrchestrator(experiment_id=experiment.unique_id,
                                          experiment_description=experiment.description)
        predicted, measured = cs.send_new_configurations_to_measure("", "", "", get_workers)
        results = get_configurations_2_float[0]['Result']
        del results["Y3"]
        del results["Y4"]
        del results["Y5"]
        predicted[0].results = results
        predicted[0].status['measured'] = True
        predicted[0].status['evaluated'] = True
        experiment.default_configuration = predicted[0]

        for i in range(1, 10):
            predicted, measured = cs.send_new_configurations_to_measure("", "", "", get_workers)

            results = get_configurations_2_float[i]['Result']
            del results["Y3"]
            del results["Y4"]
            del results["Y5"]
            predicted[0].results = results
            predicted[0].status['measured'] = True
            predicted[0].status['evaluated'] = True

            experiment.measured_configurations.append(predicted[0])
            experiment.database.write_one_record("Configuration", predicted[0].get_configuration_record())
            experiment.send_state_to_db()

        similar_experiments = tl.ted_module.analyse_experiments_similarity()

        mapping_region_model = tl.transfer_submodules["Model_transfer"].recommend_best_model(similar_experiments)
        assert mapping_region_model is not None

    def test_few_shot_transfers_the_model_of_a_similar_experiment(self, get_workers, get_configurations_2_float):
        rdb.restore()

        few_shot_skeleton = {
            "TransferLearning": {
                "TransferExpediencyDetermination": {
                    "SamplingLandmarkBased": {
                        "MinNumberOfSamples": 10,
                        "Type": "sampling_landmark_based",
                        "Comparator": {
                            "NormDifference": {
                                "Type": "norm_difference_comparator"
                            }
                        },
                        "ExperimentsQuantity": {
                            "FixedQuantity": {
                                "NumberOfSimilarExperiments": 1
                            }
                        }
                    }
                },
                "ModelRecommendation": {
                    "FewShotRecommendation": {
                        "Type": "few_shot"
                    }
                }
            }
        }
        experiment, search_space = self.initialize_experiment(few_shot_skeleton)
        cs = ConfigurationSelection(experiment)
        tl = TransferLearningOrchestrator(experiment_id=experiment.unique_id,
                                          experiment_description=experiment.description)
        predicted, measured = cs.send_new_configurations_to_measure("", "", "", get_workers)
        results = get_configurations_2_float[0]['Result']
        del results["Y3"]
        del results["Y4"]
        del results["Y5"]
        predicted[0].results = results
        predicted[0].status['measured'] = True
        predicted[0].status['evaluated'] = True
        experiment.default_configuration = predicted[0]

        for i in range(1, 10):
            predicted, measured = cs.send_new_configurations_to_measure("", "", "", get_workers)

            results = get_configurations_2_float[i]['Result']
            del results["Y3"]
            del results["Y4"]
            del results["Y5"]
            predicted[0].results = results
            predicted[0].status['measured'] = True
            predicted[0].status['evaluated'] = True

            experiment.measured_configurations.append(predicted[0])
            experiment.database.write_one_record("Configuration", predicted[0].get_configuration_record())
            experiment.send_state_to_db()

        similar_experiments = tl.ted_module.analyse_experiments_similarity()

        mapping_region_model = tl.transfer_submodules["Model_transfer"].recommend_best_model(similar_experiments)
        region = list(mapping_region_model.keys())[0]
        isinstance(region, Tuple)
        surrogate = list(mapping_region_model[region].mapping_surrogate_objective.keys())[0]
        assert isinstance(surrogate.surrogate_instance, GaussianProcessRegressor)

    def initialize_experiment(self, skeleton: Dict = None) -> Tuple[Experiment, SearchSpace]:
        experiment_description, search_space = load_experiment_setup(experiment_description_file)

        modified_description = experiment_description
        if skeleton is not None:
            modified_description = deepcopy(experiment_description)
            modified_description.update(deepcopy(skeleton))

        experiment = Experiment(modified_description, search_space)
        # main-node stores the description when it starts; TED reads the objectives of the target from it
        experiment.database.write_one_record("Experiment_description", experiment.get_experiment_description_record())
        return experiment, search_space


class TestMappingRegionModel:

    def test_model_description_is_taken_from_the_level_of_the_region(self, get_experiment):
        """
        A single model description is shared by all regions on the same level, so a region index
        must not be used to address the list of model descriptions.
        """
        # test_case_15 holds 6 regions spread over 4 levels
        experiment_description, search_space = get_experiment(15)
        recommendation = SimpleNamespace(experiment_description=experiment_description)
        # an empty list of surrogate descriptions keeps the models as they were constructed
        model_combination = {str(index): {"Model": []} for index in range(len(search_space.regions))}

        mapping_region_model = DynamicModelRecommendation._build_mapping_region_model(
            recommendation, model_combination, search_space)

        assert list(mapping_region_model.keys()) == search_space.regions
        for region, model in mapping_region_model.items():
            assert model.model_name == "Model_{}".format(region[0].level)
            assert model.region == region


def _model(n_restarts_optimizer: int) -> dict:
    """The description of the model that predicted a source's configurations; the number of restarts identifies it."""
    float_scaler = {"FloatTransformer": {"SklearnFloatMinMaxScaler": {"Type": "sklearn_float_transformer",
                                                                      "Class": "sklearn.MinMaxScaler"}}}
    return {"Surrogate": {"ConfigurationTransformers": deepcopy(float_scaler),
                          "Instance": {"GaussianProcessRegressor": {
                              "MultiObjective": "True",
                              "Parameters": {"n_restarts_optimizer": n_restarts_optimizer},
                              "Type": "sklearn_model_wrapper",
                              "Class": "sklearn.gaussian_process.GaussianProcessRegressor"}}},
            "Objectives_surrogate": deepcopy(OBJECTIVE),
            "Optimizer": {"ConfigurationTransformers": deepcopy(float_scaler),
                          "Instance": {"MOEA": {"Generations": 10, "PopulationSize": 100,
                                                "Algorithms": {"GACO": {}}, "Type": "moea"}}},
            "Objectives_optimizer": deepcopy(OBJECTIVE)}


def _source(name: str, improvement_per_step: float, time_to_build: float, n_restarts_optimizer: int) -> dict:
    """A source experiment record: its best result improves by `improvement_per_step` of its start value after
    each configuration, and the model that predicted from the fourth configuration on built in `time_to_build`."""
    samples = []
    for index in range(SAMPLES):
        if index < SAMPLED:
            prediction_info = {"0": {"Model": [], "time_to_build": 0}}
        else:
            prediction_info = {"0": {"Model": [_model(n_restarts_optimizer)], "time_to_build": time_to_build}}
        samples.append({"type": 0, "parameters": {}, "results": {"Y1": 1.0}, "prediction_info": prediction_info})
    curve = [{"Y1": 100.0 * (1 - improvement_per_step * index)} for index in range(SAMPLES)]
    return {"Exp_unique_ID": name, "Samples": samples, "Current_best_curve": curve, "Models_dumps": []}


def _recommendation(threshold_type: str) -> DynamicModelRecommendation:
    """A recommendation of a target experiment whose database holds the state and the search space it reads."""
    rdb.cleanup()
    description, search_space = load_experiment_setup(experiment_description_file)
    description = deepcopy(description)
    description["TransferLearning"]["ModelRecommendation"] = {
        "DynamicModelsRecommendation": {
            "RecommendationGranularity": {"Infinite": {"Value": np.inf}},
            "PerformanceMetric": {"AverageRelativeImprovement": {"Type": "average_relative_improvement"}},
            "Type": "dynamic_model_recommendation",
            "ThresholdType": threshold_type,
            "TimeToBuildModelThreshold": TIME_THRESHOLD,
            "TimeUnit": "seconds",
        }
    }
    experiment = Experiment(description, search_space)
    experiment.database.write_one_record("Search_space", get_search_space_record(search_space, experiment.unique_id))
    experiment.send_state_to_db()
    return DynamicModelRecommendation(experiment.description, experiment.unique_id)


def _n_restarts_of_recommended_model(mapping) -> int:
    assert mapping is not None
    (model,) = mapping.values()
    (surrogate,) = model.mapping_surrogate_objective.keys()
    return surrogate.surrogate_instance.n_restarts_optimizer


class TestSoftThreshold:

    def test_recommends_the_best_source_when_every_source_with_a_good_improvement_is_slow(self):
        recommendation = _recommendation("Soft")
        sources = [_source("slow", improvement_per_step=0.05, time_to_build=SLOW, n_restarts_optimizer=1)]

        mapping = recommendation.recommend_best_model(sources)

        assert _n_restarts_of_recommended_model(mapping) == 1

    def test_skips_a_slow_source_for_a_fast_one_that_is_still_above_the_average_improvement(self):
        recommendation = _recommendation("Soft")
        # improvements of about 0.059, 0.052 and 0.010 a step: the average is 0.040
        sources = [_source("slow", improvement_per_step=0.05, time_to_build=SLOW, n_restarts_optimizer=1),
                   _source("fast", improvement_per_step=0.045, time_to_build=FAST, n_restarts_optimizer=2),
                   _source("poor", improvement_per_step=0.01, time_to_build=FAST, n_restarts_optimizer=3)]

        mapping = recommendation.recommend_best_model(sources)

        assert _n_restarts_of_recommended_model(mapping) == 2

    def test_recommends_the_best_source_when_the_improvement_is_not_good_anywhere(self):
        recommendation = _recommendation("Soft")
        sources = [_source("stagnating", improvement_per_step=0.0, time_to_build=SLOW, n_restarts_optimizer=1)]

        mapping = recommendation.recommend_best_model(sources)

        assert _n_restarts_of_recommended_model(mapping) == 1

    def test_recommends_nothing_when_no_source_has_a_metric(self):
        recommendation = _recommendation("Soft")
        source = _source("unpredicted", improvement_per_step=0.05, time_to_build=FAST, n_restarts_optimizer=1)
        for sample in source["Samples"]:
            sample["prediction_info"] = {"0": {"Model": [], "time_to_build": 0}}

        assert recommendation.recommend_best_model([source]) is None


class TestHardThreshold:

    def test_recommends_nothing_when_every_source_is_slow(self):
        recommendation = _recommendation("Hard")
        sources = [_source("slow", improvement_per_step=0.05, time_to_build=SLOW, n_restarts_optimizer=1)]

        assert recommendation.recommend_best_model(sources) is None

    def test_recommends_a_fast_source_after_a_slow_one_with_a_better_improvement(self):
        recommendation = _recommendation("Hard")
        sources = [_source("slow", improvement_per_step=0.05, time_to_build=SLOW, n_restarts_optimizer=1),
                   _source("fast", improvement_per_step=0.02, time_to_build=FAST, n_restarts_optimizer=2)]

        mapping = recommendation.recommend_best_model(sources)

        assert _n_restarts_of_recommended_model(mapping) == 2
