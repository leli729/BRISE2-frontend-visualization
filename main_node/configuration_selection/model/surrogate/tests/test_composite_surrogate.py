import copy

import numpy as np
import pandas as pd
import pytest

from configuration_selection.model.surrogate.composite_surrogate import CompositeSurrogate
from configuration_selection.model.surrogate.surrogate_orchestrator import SurrogateOrchestrator
from core_entities.objectives import Objectives
from core_entities.search_space import active_mask, find_parameters_activated_within_region


def _configurations(region, count, rng) -> pd.DataFrame:
    """Random configurations of the region, with NaN in the cells of the parameters that are inactive."""
    configurations = pd.DataFrame({hp.name: [hp.transform(share) for share in rng.uniform(0, 1, count)] for hp in region})
    conditional = find_parameters_activated_within_region(region)
    if conditional:
        mask = active_mask(configurations, [hp.activation_condition for hp in conditional])
        for hp in conditional:
            configurations.loc[~mask[hp.name], hp.name] = np.nan
    return configurations


@pytest.fixture
def surrogates_and_features(get_experiment):
    """Test case 13 (flat, all four parameter types): its surrogate, which scales the float, and the same surrogate without
    a float transformer, so the two transform the configurations differently, each trained for one objective."""
    description, search_space = get_experiment(13)
    model = description["ConfigurationSelection"]["Predictor"]["Model"]
    objectives_description = copy.deepcopy(description["Context"]["TaskConfiguration"]["Objectives"])
    objectives_description["Y2"] = {**objectives_description["Y1"], "Name": "Y2"}
    objectives = Objectives.from_description(objectives_description)
    region = search_space.regions[0]
    rng = np.random.default_rng(0)
    features = _configurations(region, 40, rng)
    labels = rng.uniform(0, 1, 40)  # both objectives get the same labels, so only the transformations differ

    unscaled_description = copy.deepcopy(model["Surrogate"])
    del unscaled_description["ConfigurationTransformers"]["FloatTransformer"]
    surrogates = []
    for surrogate_description, name in ((copy.deepcopy(model["Surrogate"]), "Y1"), (unscaled_description, "Y2")):
        surrogate = SurrogateOrchestrator().get_surrogate(surrogate_description, region, Objectives((objectives.by_name(name),)))
        assert surrogate.create(features, pd.DataFrame({name: labels}))
        surrogates.append(surrogate)
    return surrogates, region, features


class TestCompositeSurrogate:

    def test_a_composite_surrogate_has_no_transformers_of_its_own(self, surrogates_and_features):
        (first, second), region, _ = surrogates_and_features

        composite = CompositeSurrogate((first, second), region)

        assert composite.mapping_config_transformer_parameter == {}
        assert first.mapping_config_transformer_parameter and second.mapping_config_transformer_parameter

    def test_a_composite_surrogate_scores_each_objective_as_its_own_surrogate_does(self, surrogates_and_features):
        (first, second), region, features = surrogates_and_features
        composite = CompositeSurrogate((first, second), region)
        configurations = features.iloc[:8]

        scores = composite.predict_batch(configurations)

        for surrogate in (first, second):
            own = surrogate.predict_batch(configurations)
            pd.testing.assert_frame_equal(scores[list(own.columns)], own)
        # the same labels, so a difference between the objectives comes from the transformations alone
        assert not np.allclose(scores["Y1"], scores["Y2"])
