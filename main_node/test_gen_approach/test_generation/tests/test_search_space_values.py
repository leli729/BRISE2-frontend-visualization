import json
import re

import pytest

from generator_paths import FILL_DB, MODELS
from pairwise_generator import CONTEXT_VARIANTS
from selenium_validator import search_space_value

# The generated contexts take the search spaces of the inputs of fill_db (the fixtures' sources), so that a
# transfer-learning product can share its landmarks with a source: every input of a context has the values of the context.
CONTEXTS = ["2-float", "float-nom", "all-types", "int-cat"]
# the single-objective contexts, whose products have transfer learning, and the input a product of each can take its source from
INPUT_OF_SINGLE_OBJECTIVE_CONTEXT = {"2-float-so": "2-float-max-flat", "float-nom-so": "float-nom-min-flat",
                                     "all-types-so": "all-types-min-flat", "int-cat-so": "int-cat-min-flat"}
VARIANT_AND_INPUT = [
    pytest.param(variant, path.stem, id=f"{variant}-{path.stem}")
    for context in CONTEXTS
    for variant in CONTEXT_VARIANTS if variant.startswith(context)
    for path in sorted(FILL_DB.glob("*.json")) if path.stem.startswith(f"{context}-")]


def _input(name):
    return json.loads((FILL_DB / f"{name}.json").read_text())


def _numeric_parameters(search_space, path=""):
    """(path, bounds and default) of every float and integer parameter below search_space, nested ones included."""
    for name, value in search_space.items():
        if not isinstance(value, dict):
            continue
        if "Lower" in value:
            yield path + name, {attribute: value[attribute] for attribute in ("Lower", "Upper", "Default")}
        else:
            yield from _numeric_parameters(value, f"{path}{name}.")


def _numeric_parameter_names_of_the_model(variant):
    text = (MODELS / f"{variant}.wfl").read_text()
    search_space = text[text.index("SearchSpace {"):text.index("xor Structure {")]
    return set(re.findall(r"(\w+)\s*:\s*(?:Float|Integer)Hyperparameter", search_space))


@pytest.mark.parametrize("variant, input_name", VARIANT_AND_INPUT)
def test_the_input_has_the_numeric_parameters_of_the_context_model(variant, input_name):
    parameters = _numeric_parameters(_input(input_name)["Context"]["SearchSpace"])

    assert {path.rsplit(".", 1)[-1] for path, _ in parameters} == _numeric_parameter_names_of_the_model(variant)


@pytest.mark.parametrize("variant, input_name", VARIANT_AND_INPUT)
def test_every_numeric_parameter_gets_the_bounds_and_the_default_of_the_input(variant, input_name):
    for path, values in _numeric_parameters(_input(input_name)["Context"]["SearchSpace"]):
        for attribute, value in values.items():
            assert search_space_value(variant, f"Context.SearchSpace.{path}.{attribute}") == str(value), (path, attribute)


@pytest.mark.parametrize("field", ["Context.SearchSpace.X1.Level",
                                   "StopCondition.Instance.AdaptiveSC.Parameters.SearchSpacePercentage"])
def test_a_field_other_than_a_bound_or_a_default_gets_no_value(field):
    assert search_space_value("2-float-so", field) is None


@pytest.mark.parametrize("variant", INPUT_OF_SINGLE_OBJECTIVE_CONTEXT)
def test_the_objective_of_a_context_has_the_direction_of_its_input(variant):
    # a source of the other direction would hand a model that optimizes the wrong way
    text = (MODELS / f"{variant}.wfl").read_text()
    minimized_in_context = re.search(r"\[Minimization = (true|false)\]", text).group(1) == "true"
    objectives = _input(INPUT_OF_SINGLE_OBJECTIVE_CONTEXT[variant])["Context"]["TaskConfiguration"]["Objectives"]

    assert [objective["Minimization"] for objective in objectives.values()] == [minimized_in_context]
