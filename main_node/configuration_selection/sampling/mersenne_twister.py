import random
import pandas as pd
import numpy as np
from typing import Mapping, Tuple

from configuration_selection.sampling.selection_algorithm_abs import SamplingStrategy
from core_entities.search_space import Hyperparameter


class MersenneTwister(SamplingStrategy):
    def __init__(self, parameters: Mapping, region: Tuple[Hyperparameter]):
        """
        Selection algorithm that uses Mersenne Twister pseudo-random generator. <https://docs.python.org/3/library/random.html>
        With a "Seed" it draws from a generator of its own; without one it draws from the global generator of `random`.
        """
        super().__init__(parameters, region)
        self.generator = None
        if "Seed" in parameters:
            self.generator = random.Random(parameters["Seed"])

    def sample(self) -> pd.DataFrame:

        sampled_values = []
        for i in range(len(self.region)):
            if self.generator is None:
                sampled_values.append(random.random())
            else:
                sampled_values.append(self.generator.random())
        sampled_values = np.array(sampled_values).reshape(1, len(self.region))

        result = self.transform(sampled_values)
        return result
