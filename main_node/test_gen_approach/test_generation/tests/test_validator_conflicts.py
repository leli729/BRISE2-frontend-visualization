import pytest

from pairwise_generator import CONTEXT_VARIANTS, PairwiseConfig
from selenium_validator import MODEL_PATH, WaffleSeleniumValidator

# The validator treats every Model_N alike, so one surrogate stands for all the models of a product. Every context has a
# numeric parameter, and MultiArmedBandit.create refuses a region with one, so the model of that region never builds and
# a product with the bandit never predicts a whole configuration.

BANDIT = f"{MODEL_PATH}.Surrogate.Instance.MultiArmedBandit"
OTHER_SURROGATES = [
    "LinearRegression", "SupportVectorRegression", "GradientBoostingRegressor", "BayesianRidgeRegression",
    "TreeParzenEstimator", "MultiLayerPerceptronRegressor", "GaussianProcessRegressor", "ModelMock",
]
STRUCTURES = ["Flat", "Hierarchical"]


@pytest.fixture(scope="module")
def validator():
    # the decisions under test read the row only; the constructor would parse the feature model and open the log file
    return WaffleSeleniumValidator.__new__(WaffleSeleniumValidator)


def _row(context, structure, *selections):
    return PairwiseConfig(index=0, context_variant=context, selections=[f"Context.SearchSpace.Structure.{structure}", *selections])


def test_the_bandit_conflicts_in_every_row_the_generator_produces(validator, configurations):
    not_conflicting = [row.index for row in configurations if not validator._is_conflicting("MultiArmedBandit", row)]

    assert not_conflicting == []


@pytest.mark.parametrize("structure", STRUCTURES)
@pytest.mark.parametrize("context", CONTEXT_VARIANTS)
def test_the_bandit_conflicts_in_every_context_and_structure(validator, context, structure):
    row = _row(context, structure, BANDIT)

    assert validator._is_conflicting("MultiArmedBandit", row)


@pytest.mark.parametrize("surrogate", OTHER_SURROGATES)
def test_no_other_surrogate_conflicts_because_of_the_context(validator, surrogate):
    row = _row("float-nom-so", "Hierarchical", f"{MODEL_PATH}.Surrogate.Instance.{surrogate}")

    assert not validator._is_conflicting(surrogate, row)


def test_a_row_that_selects_the_bandit_keeps_the_transformers_of_its_context(validator):
    # a bandit that conflicts itself empties nothing: the surrogate that replaces it needs them
    row = _row("all-types-so", "Hierarchical", BANDIT)

    assert {"NominalTransformer", "OrdinalTransformer"} <= validator._transformers_on(row, "Surrogate")


def test_a_row_that_selects_the_bandit_is_not_forced_to_the_mock_validator(validator):
    # the bandit excludes the quality validator, the surrogate that replaces it doesn't
    row = _row("float-nom-so", "Hierarchical", BANDIT)

    assert not validator._is_mock_validator_needed(row)


def test_a_row_that_selects_the_bandit_does_not_rule_out_the_pure_surrogate_type(validator):
    # Pure excludes the bandit, so it is skipped while the bandit is selected; a bandit that conflicts itself triggers nothing
    row = _row("float-nom-2-mo", "Hierarchical", BANDIT)

    assert not validator._is_conflicting("Pure", row)
