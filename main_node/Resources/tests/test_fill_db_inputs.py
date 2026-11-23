import json
from pathlib import Path

import pytest

from core_entities.search_space import SearchSpace

TESTS = Path(__file__).parent
TEST_CASES = sorted((TESTS / "test_cases_product_configurations").glob("*.json"))
INPUTS = sorted((TESTS / "db" / "fill_db").glob("*.json"))

# A target finds a source only with the same search space and objective, the sampler's seed (fill_db runs seed 1) and,
# among other things, the same default handler and sampler, which fill_db sets itself.
SEED_OF_FILL_DB = 1
# A source samples this many configurations before its first prediction, the landmarks a target compares with.
SAMPLES_OF_FILL_DB = 10

# A source predicts only if the proposals of its model are new, and a small space gives it few: an int-cat model
# (GACO) proposed a configuration that was not evaluated yet in 5 of 16 proposals in a space of 44 configurations, in 13
# of 16 in a space of 404 and in 16 of 16 in a space of 4004.
MIN_SEARCH_SPACE_SIZE = 1000

# Transfer-learning test cases that have no source on purpose, or that no test reads.
NO_SOURCE = {
    "EnergyExperimentWithTL": "test_ted.py::test_1 asserts that an energy target finds no source among the test experiments",
    "test_case_basic": "no test reads it",
}


def _load(path):
    return json.loads(path.read_text())


def _identity(product):
    return product["Context"]["SearchSpace"], product["Context"]["TaskConfiguration"]["Objectives"]


TRANSFER_LEARNING = [path for path in TEST_CASES if "TransferLearning" in _load(path) and path.stem not in NO_SOURCE]


def test_there_are_transfer_learning_test_cases_to_check():
    assert TRANSFER_LEARNING, "an empty list would skip the parametrized test"


@pytest.mark.parametrize("path", TRANSFER_LEARNING, ids=lambda path: path.stem)
def test_a_test_case_with_transfer_learning_has_a_source_of_the_same_search_space_and_objective(path):
    target = _load(path)

    sources = [source.stem for source in INPUTS if _identity(_load(source)) == _identity(target)]

    assert sources, f"{path.name} has no input in db/fill_db with its search space and objective"


@pytest.mark.parametrize("path", TRANSFER_LEARNING, ids=lambda path: path.stem)
def test_a_test_case_with_transfer_learning_samples_with_the_seed_of_the_sources(path):
    sampler = _load(path)["ConfigurationSelection"]["SamplingStrategy"]

    assert [description["Seed"] for description in sampler.values()] == [SEED_OF_FILL_DB]


@pytest.mark.parametrize("path", TRANSFER_LEARNING, ids=lambda path: path.stem)
def test_a_test_case_with_transfer_learning_needs_no_more_landmarks_than_a_source_samples(path):
    expediency = _load(path)["TransferLearning"]["TransferExpediencyDetermination"]

    assert [description["MinNumberOfSamples"] for description in expediency.values()] <= [SAMPLES_OF_FILL_DB]


@pytest.mark.parametrize("path", INPUTS, ids=lambda path: path.stem)
def test_an_input_has_a_search_space_large_enough_for_new_model_proposals(path):
    # the float parameters make a space infinite
    assert SearchSpace(_load(path)["Context"]["SearchSpace"]).size >= MIN_SEARCH_SPACE_SIZE
