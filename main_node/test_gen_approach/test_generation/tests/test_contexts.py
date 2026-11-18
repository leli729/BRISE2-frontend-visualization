import re

import pytest

from generator_paths import MODELS
from pairwise_generator import CONTEXT_VARIANTS
from selenium_validator import CONTEXT_REQUIRED_TRANSFORMERS

MULTI_OBJECTIVE = [name for name in CONTEXT_VARIANTS if name.endswith(("-2-mo", "-5-mo"))]


def _model(name):
    return (MODELS / f"{name}.wfl").read_text()


def _directions(name):
    """{objective: minimized?} in the order of the objectives block."""
    text = _model(name)
    objectives = text[text.index("Objectives {"):]
    return {match.group(1): match.group(2) == "true"
            for match in re.finditer(r'\[Name = "(Y\d)"\][^\[]*(?:\[DataType[^\]]*\][^\[]*)?\[Minimization = (true|false)\]', objectives)}


def test_there_are_ten_contexts_and_each_has_a_model():
    assert len(CONTEXT_VARIANTS) == 10
    for name in CONTEXT_VARIANTS:
        assert (MODELS / f"{name}.wfl").is_file(), name


# D7: maximized objectives

@pytest.mark.parametrize("name", MULTI_OBJECTIVE)
def test_y2_is_maximized_and_the_other_objectives_are_minimized_in_a_multi_objective_context(name):
    directions = _directions(name)

    assert len(directions) == (2 if name.endswith("-2-mo") else 5)
    assert directions["Y2"] is False
    assert all(minimized for objective, minimized in directions.items() if objective != "Y2")


def test_y1_is_maximized_in_the_single_objective_float_context():
    assert _directions("2-float-so") == {"Y1": False}


@pytest.mark.parametrize("name", ["float-nom-so", "all-types-so", "int-cat-so"])
def test_the_other_single_objective_contexts_minimize(name):
    assert _directions(name) == {"Y1": True}


# D8: a search space without floats

def test_the_int_cat_context_has_integer_and_categorical_parameters_but_no_float():
    text = _model("int-cat-so")
    search_space = text[text.index("SearchSpace {"):text.index("xor Structure {")]

    assert "FloatHyperparameter" not in search_space
    assert search_space.count("IntegerHyperparameter") >= 2
    assert "NominalHyperparameter" in search_space and "OrdinalHyperparameter" in search_space


def test_the_int_cat_context_is_hierarchical_with_two_levels_like_all_types():
    text = _model("int-cat-so")
    search_space = text[text.index("SearchSpace {"):text.index("xor Structure {")]

    # a category holding a parameter that holds categories: N0 > N01 > N1 > N11
    assert re.search(r"N0 : NominalHyperparameter \{.*N01 : Category \{.*N1 : \w+Hyperparameter \{.*N11 : Category", search_space, re.DOTALL)


def test_the_int_cat_context_requires_the_transformers_of_its_parameter_types():
    assert set(CONTEXT_REQUIRED_TRANSFORMERS["int-cat"]) == {"NominalTransformer", "OrdinalTransformer"}
