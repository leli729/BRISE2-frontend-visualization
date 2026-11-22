from copy import deepcopy

from selenium_validator import patch_product, set_quality_threshold, set_stop_condition_expression, set_tpe_parameters

STOP_CONDITION = {
    "Instance": {
        "BadConfigurationBasedSC": {"Parameters": {"MaxBadConfigurations": 5}, "Type": "bad_configuration_based", "Name": "SC1"},
        "GuaranteedSC": {"Type": "guaranteed", "Name": "SC2"},
        "QuantityBasedSC": {"Parameters": {"MaxConfigs": 10}, "Type": "quantity_based", "Name": "SC3"},
    },
    "StopConditionTriggerLogic": {
        "Expression": "StopCondition1",
        "InspectionParameters": {"RepetitionPeriod": 5, "TimeUnit": "seconds"},
    },
}


def _validators(quality_threshold_by_region):
    """A Predictor with one Model per region, each with a QualityValidator as its external and its internal validator."""
    predictor = {"WindowSize": 1.0}
    for region, threshold in enumerate(quality_threshold_by_region):
        predictor[f"Model_{region}"] = {
            "Validator": {
                "ExternalValidator": {"QualityValidator": {"QualityThreshold": threshold, "Type": "quality_validator"}},
                "InternalValidator": {"QualityValidator": {"QualityThreshold": threshold, "Type": "quality_validator"}},
            }
        }
    return {"ConfigurationSelection": {"Predictor": predictor}}


# the quality threshold

def test_every_quality_threshold_of_every_model_accepts_every_finite_score():
    product = _validators([1.0, 0.5])

    set_quality_threshold(product)

    for model in ("Model_0", "Model_1"):
        validator = product["ConfigurationSelection"]["Predictor"][model]["Validator"]
        assert validator["ExternalValidator"]["QualityValidator"]["QualityThreshold"] == -1e9
        assert validator["InternalValidator"]["QualityValidator"]["QualityThreshold"] == -1e9


def test_the_quality_threshold_patch_changes_nothing_else():
    product = _validators([1.0])
    product["StopCondition"] = deepcopy(STOP_CONDITION)
    expected = deepcopy(product)
    expected["ConfigurationSelection"]["Predictor"]["Model_0"]["Validator"]["ExternalValidator"]["QualityValidator"]["QualityThreshold"] = -1e9
    expected["ConfigurationSelection"]["Predictor"]["Model_0"]["Validator"]["InternalValidator"]["QualityValidator"]["QualityThreshold"] = -1e9

    set_quality_threshold(product)

    assert product == expected


def test_a_product_without_a_quality_validator_is_left_as_it_is():
    product = {"ConfigurationSelection": {"Predictor": {"Model_0": {"Validator": {"ExternalValidator": {"MockValidator": {"Type": "mock_validator"}}}}}}}
    expected = deepcopy(product)

    set_quality_threshold(product)

    assert product == expected


# the stop-condition expression

def test_the_expression_is_the_or_of_every_stop_condition_name_in_the_order_of_the_instances():
    product = {"StopCondition": deepcopy(STOP_CONDITION)}

    set_stop_condition_expression(product)

    assert product["StopCondition"]["StopConditionTriggerLogic"]["Expression"] == "SC1 or SC2 or SC3"


def test_the_expression_of_a_single_stop_condition_is_its_name():
    product = {"StopCondition": deepcopy(STOP_CONDITION)}
    product["StopCondition"]["Instance"] = {"GuaranteedSC": {"Type": "guaranteed", "Name": "SC2"}}

    set_stop_condition_expression(product)

    assert product["StopCondition"]["StopConditionTriggerLogic"]["Expression"] == "SC2"


def test_the_inspection_parameters_survive_the_expression_patch():
    product = {"StopCondition": deepcopy(STOP_CONDITION)}

    set_stop_condition_expression(product)

    assert product["StopCondition"]["StopConditionTriggerLogic"]["InspectionParameters"] == {"RepetitionPeriod": 5, "TimeUnit": "seconds"}
    assert product["StopCondition"]["Instance"] == STOP_CONDITION["Instance"]


# the parameters of the Tree-Parzen Estimator

def _tpe(top_n_percent=99, random_fraction=1.0):
    """The Instance of a Tree-Parzen Estimator surrogate, with the maxima the validator enters for a bounded attribute."""
    return {"TreeParzenEstimator": {
        "MultiObjective": False,
        "Parameters": {"top_n_percent": top_n_percent, "random_fraction": random_fraction, "bandwidth_factor": 5.0, "min_bandwidth": 0.1},
        "Type": "tree_parzen_estimator"}}


def _tpe_parameters(surrogate):
    parameters = surrogate["Instance"]["TreeParzenEstimator"]["Parameters"]
    return parameters["top_n_percent"], parameters["random_fraction"]


def test_every_tree_parzen_estimator_of_every_model_gets_a_fraction_of_good_observations_and_never_skips_its_build():
    product = {"ConfigurationSelection": {"Predictor": {
        "Model_0": {"Surrogate": {"Instance": _tpe()}},
        "Model_1": {"Surrogate_0": {"Instance": _tpe(50, 0.5)}, "Surrogate_1": {"Instance": _tpe(10, 0.1)}},
    }}}

    set_tpe_parameters(product)

    predictor = product["ConfigurationSelection"]["Predictor"]
    assert _tpe_parameters(predictor["Model_0"]["Surrogate"]) == (30, 0.0)
    assert _tpe_parameters(predictor["Model_1"]["Surrogate_0"]) == (30, 0.0)
    assert _tpe_parameters(predictor["Model_1"]["Surrogate_1"]) == (30, 0.0)


def test_the_tpe_patch_changes_nothing_else_of_the_estimator():
    product = {"ConfigurationSelection": {"Predictor": {"Model": {"Surrogate": {"Instance": _tpe()}}}}}
    expected = deepcopy(product)
    expected_parameters = expected["ConfigurationSelection"]["Predictor"]["Model"]["Surrogate"]["Instance"]["TreeParzenEstimator"]["Parameters"]
    expected_parameters.update({"top_n_percent": 30, "random_fraction": 0.0})

    set_tpe_parameters(product)

    assert product == expected


def test_a_product_without_a_tree_parzen_estimator_is_left_as_it_is():
    # a surrogate of another type that carries a top_n_percent (SVR has none in reality; it is here to catch a patch that
    # matches the key anywhere), and the TPE_EI acquisition function of an optimizer, which is not an estimator
    product = {"ConfigurationSelection": {"Predictor": {"Model": {
        "Surrogate": {"Instance": {"SupportVectorRegression": {"Parameters": {"kernel": "rbf", "C": 10.0, "top_n_percent": 99}, "Type": "sklearn"}}},
        "Optimizer": {"ValueTransformers": {"AcquisitionFunction": {"TPE_EI": {"Type": "tpe_ei"}}}},
    }}}}
    expected = deepcopy(product)

    set_tpe_parameters(product)

    assert product == expected


# the patches together

def test_a_product_gets_every_patch_of_the_generator():
    product = _validators([1.0])
    product["ConfigurationSelection"]["Predictor"]["Model_0"]["Surrogate"] = {"Instance": _tpe()}
    product["StopCondition"] = deepcopy(STOP_CONDITION)

    patch_product(product)

    model = product["ConfigurationSelection"]["Predictor"]["Model_0"]
    assert model["Validator"]["ExternalValidator"]["QualityValidator"]["QualityThreshold"] == -1e9
    assert product["StopCondition"]["StopConditionTriggerLogic"]["Expression"] == "SC1 or SC2 or SC3"
    assert _tpe_parameters(model["Surrogate"]) == (30, 0.0)
