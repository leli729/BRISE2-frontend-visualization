import random

import pandas as pd
import pytest

from configuration_selection.sampling.mersenne_twister import MersenneTwister
from configuration_selection.sampling.sampling_strategy_orchestrator import SamplingStrategyOrchestrator


SAMPLES = 10
SAMPLERS = {"Sobol": "sobol", "MersenneTwister": "mersenne_twister"}


@pytest.fixture
def region(get_experiment):
    # test case 0: two floats in [0, 1]
    _, search_space = get_experiment(0)
    return search_space.regions[0]


def _sampler(name, seed, region):
    description = {name: {"Seed": seed, "Type": SAMPLERS[name]}}
    return SamplingStrategyOrchestrator().get_sampling_strategy(description, region)


def _draw(sampler, number=SAMPLES):
    return pd.concat([sampler.sample() for _ in range(number)], ignore_index=True)


@pytest.mark.parametrize("name", list(SAMPLERS))
class TestSeed:

    def test_the_same_seed_draws_the_same_samples(self, name, region):
        first = _draw(_sampler(name, 1, region))
        second = _draw(_sampler(name, 1, region))

        pd.testing.assert_frame_equal(first, second)

    def test_the_first_sample_depends_on_the_seed(self, name, region):
        # the first sample is the default configuration of a product with the random default handler
        assert not _draw(_sampler(name, 1, region), 1).equals(_draw(_sampler(name, 2, region), 1))


class TestMersenneTwisterAmongOtherUsersOfRandom:

    def test_with_a_seed_the_samples_do_not_depend_on_what_else_draws_from_the_global_generator(self, region):
        undisturbed = _draw(_sampler("MersenneTwister", 1, region))
        disturbed_sampler = _sampler("MersenneTwister", 1, region)
        disturbed = []
        for _ in range(SAMPLES):
            random.random()
            disturbed.append(disturbed_sampler.sample())

        pd.testing.assert_frame_equal(undisturbed, pd.concat(disturbed, ignore_index=True))

    def test_with_a_seed_sampling_does_not_change_the_global_generator(self, region):
        sampler = _sampler("MersenneTwister", 1, region)
        state = random.getstate()

        _draw(sampler)

        assert random.getstate() == state

    def test_without_a_seed_the_samples_follow_the_global_generator(self, region):
        # the random search optimizer builds one without a seed
        state = random.getstate()
        try:
            random.seed(0)
            first = _draw(MersenneTwister({}, region))
            random.seed(0)
            second = _draw(MersenneTwister({}, region))
        finally:
            random.setstate(state)

        pd.testing.assert_frame_equal(first, second)
