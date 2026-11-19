from copy import deepcopy

from selenium_validator import set_quality_threshold, set_stop_condition_expression

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


# D12: the quality threshold

def test_every_quality_threshold_of_every_model_is_set_to_minus_100():
    product = _validators([1.0, 0.5])

    set_quality_threshold(product)

    for model in ("Model_0", "Model_1"):
        validator = product["ConfigurationSelection"]["Predictor"][model]["Validator"]
        assert validator["ExternalValidator"]["QualityValidator"]["QualityThreshold"] == -100
        assert validator["InternalValidator"]["QualityValidator"]["QualityThreshold"] == -100


def test_the_quality_threshold_patch_changes_nothing_else():
    product = _validators([1.0])
    product["StopCondition"] = deepcopy(STOP_CONDITION)
    expected = deepcopy(product)
    expected["ConfigurationSelection"]["Predictor"]["Model_0"]["Validator"]["ExternalValidator"]["QualityValidator"]["QualityThreshold"] = -100
    expected["ConfigurationSelection"]["Predictor"]["Model_0"]["Validator"]["InternalValidator"]["QualityValidator"]["QualityThreshold"] = -100

    set_quality_threshold(product)

    assert product == expected


def test_a_product_without_a_quality_validator_is_left_as_it_is():
    product = {"ConfigurationSelection": {"Predictor": {"Model_0": {"Validator": {"ExternalValidator": {"MockValidator": {"Type": "mock_validator"}}}}}}}
    expected = deepcopy(product)

    set_quality_threshold(product)

    assert product == expected


# D14: the stop-condition expression

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
