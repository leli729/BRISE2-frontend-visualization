import copy
import re

import pytest

from configuration_selection.model.optimizer.moea import MOEA
from core_entities.objectives import Objectives
from core_entities.search_space import CategoricalHyperparameter, FloatHyperparameter, IntegerHyperparameter

# MOEA searches every parameter as a real number, and only its own ConfigurationTransformers cast an integer or a
# categorical one back, so it needs them.

# test case, key of the model, index of the region, the parameters MOEA searches (the last part of their names) and
# the bounds of the search, as MOEA with its own transformers builds them
BOUNDS = {
    "flat_floats_scaled": (0, "Model", 0, ["X1_MinMaxScaler", "X2_MinMaxScaler"], ([0.0, 0.0], [1.0, 1.0])),
    "flat_floats_scaled_multi_objective": (7, "Model", 0, ["X1_MinMaxScaler", "X2_MinMaxScaler"], ([0.0, 0.0], [1.0, 1.0])),
    "hierarchical_nominal": (11, "Model_0", 0, ["N0_BinaryEncoder"], ([0.0], [1.0])),
    # F1 has no transformer of the optimizer, so its bounds are its own
    "hierarchical_float_without_a_transformer": (11, "Model_1", 1, ["F1", "N1_BinaryEncoder"], ([0.0, 0.0], [123.0, 1.0])),
    "hierarchical_integer_and_ordinal": (11, "Model_1", 2, ["I1_MinMaxScaler", "O1_OrdinalEncoder"], ([0.0, 0.0], [1.0, 1.0])),
    "flat_all_types": (13, "Model", 0, ["F1_MinMaxScaler", "N1_BinaryEncoder", "I1_MinMaxScaler", "O1_OrdinalEncoder", "N0_BinaryEncoder"],
                       ([0.0] * 5, [1.0] * 5)),
}


def _moea(get_experiment, test_case, key="Model", region_index=0, edit=None):
    """The MOEA of a model of a test case and its region, `edit` changing the description of the model first."""
    description, search_space = get_experiment(test_case)
    model = copy.deepcopy(description["ConfigurationSelection"]["Predictor"][key])
    if edit is not None:
        edit(model)
    objectives = Objectives.from_description(description["Context"]["TaskConfiguration"]["Objectives"])
    region = search_space.regions[region_index]
    return MOEA(model["Optimizer"], region, objectives), region


def _without(*transformers):
    def edit(model):
        for transformer in transformers:
            del model["Optimizer"]["ConfigurationTransformers"][transformer]
    return edit


def _names(region, kinds):
    return "|".join(re.escape(hp.name) for hp in region if isinstance(hp, kinds))


class TestMoeaWithItsOwnTransformers:

    @pytest.mark.parametrize("case", list(BOUNDS))
    def test_the_bounds_of_the_search_are_those_the_transformers_of_moea_define(self, get_experiment, case):
        test_case, key, region_index, expected_params, expected_bounds = BOUNDS[case]
        optimizer, _ = _moea(get_experiment, test_case, key, region_index)

        optimizer._build_bounds_params_masked()

        assert [param.split(".")[-1] for param in optimizer.params] == expected_params
        assert [list(bound) for bound in optimizer.bounds] == [list(bound) for bound in expected_bounds]
        assert optimizer.masked_params == {}

    def test_a_float_without_a_transformer_is_searched_in_its_own_bounds(self, get_experiment):
        optimizer, region = _moea(get_experiment, 13, edit=_without("FloatTransformer"))
        float_parameter = next(hp for hp in region if isinstance(hp, FloatHyperparameter))

        optimizer._build_bounds_params_masked()

        position = optimizer.params.index(float_parameter.name)
        assert (optimizer.bounds[0][position], optimizer.bounds[1][position]) == (0.0, 123.0)  # F1 is a float in [0, 123]


class TestMoeaWithoutTransformers:

    def test_a_categorical_parameter_without_a_transformer_of_moea_is_refused(self, get_experiment):
        # test case 4: flat, the surrogate has a transformer for the nominal parameter, which MOEA must not borrow
        optimizer, region = _moea(get_experiment, 4, edit=_without("NominalTransformer"))

        with pytest.raises(ValueError, match=_names(region, CategoricalHyperparameter)):
            optimizer._build_bounds_params_masked()

    def test_an_integer_parameter_without_a_transformer_of_moea_is_refused(self, get_experiment):
        optimizer, region = _moea(get_experiment, 13, edit=_without("IntegerTransformer"))

        with pytest.raises(ValueError, match=_names(region, IntegerHyperparameter)):
            optimizer._build_bounds_params_masked()

    def test_a_moea_without_any_transformer_is_refused(self, get_experiment):
        def remove_all(model):
            del model["Optimizer"]["ConfigurationTransformers"]

        optimizer, region = _moea(get_experiment, 13, edit=remove_all)

        with pytest.raises(ValueError, match=_names(region, (CategoricalHyperparameter, IntegerHyperparameter))):
            optimizer._build_bounds_params_masked()
