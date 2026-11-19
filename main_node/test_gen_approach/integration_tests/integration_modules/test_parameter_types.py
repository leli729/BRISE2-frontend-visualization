import os

os.environ["TEST_MODE"] = "UNIT_TEST"

import pytest

from core_entities.experiment import Experiment
from tools.initial_config import load_experiment_setup

from test_gen_approach.integration_tests.helpers.experiment_utils import (
    PHASE1_OUTPUT_DIR,
    get_parameter_types,
    load_phase1_config,
)

TEST_CASES = "./Resources/tests/test_cases_product_configurations/test_case_{}.json"

_phase1_configs = sorted(f.name for f in PHASE1_OUTPUT_DIR.glob("*.json"))

# the fixture each context uses; int-cat has an ordinal parameter, so it takes the all-types one
FIXTURE_BY_CONTEXT = {"2-float": "2_float", "float-nom": "float_nom", "all-types": "all_types", "int-cat": "all_types"}


class TestParameterTypes:

    @pytest.mark.parametrize("test_case, expected", [
        (0, "2_float"),
        (4, "float_nom"),
        (2, "all_types"),
    ])
    def test_the_fixture_matches_the_types_of_the_search_space(self, test_case, expected):
        description, search_space = load_experiment_setup(TEST_CASES.format(test_case))
        experiment = Experiment(description, search_space)

        assert get_parameter_types(experiment) == expected

    @pytest.mark.parametrize("config_file", _phase1_configs)
    def test_the_fixture_of_a_generated_configuration_matches_its_context(self, config_file):
        # config_<index>_<context>.json: the context, not the search space, says which parameter types to expect
        context = config_file.split("_", 2)[2].removesuffix(".json")
        expected = next(fixture for prefix, fixture in FIXTURE_BY_CONTEXT.items() if context.startswith(prefix))
        description, search_space = load_phase1_config(config_file)

        assert get_parameter_types(Experiment(description, search_space)) == expected
