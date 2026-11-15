import math
import random

import pandas as pd
from typing import Dict, Optional, Tuple

from configuration_selection.model.surrogate.surrogate_abs import Surrogate
from core_entities.objectives import Criterion, Objectives


class ModelMock(Surrogate):
    """
    The stand-in for a run without a surrogate. It predicts random values, which only rank candidates at random: each
    objective is drawn in its expected range, and the draws go through the value transformers of the surrogate, as the
    labels of the other surrogates do. An objective whose range is not finite is not scaled: it is drawn between 0
    and 1, and an integer objective is rounded to 0 or 1.
    """

    def __init__(self, surrogate_description: Dict, region: Tuple, objectives: Objectives):
        super().__init__(surrogate_description, region, objectives)
        self.multi_objective = surrogate_description['Instance']['ModelMock']['MultiObjective']

    def output_criteria(self) -> Optional[Tuple[Criterion, ...]]:
        # not a prediction of the objectives, so not named as them
        return tuple(Criterion.derived("random", [label], label.minimization) for label in self._label_criteria())

    def create(self, features: pd.DataFrame, labels: pd.DataFrame) -> bool:
        return True

    def predict(self, cfg: pd.Series, transform: bool = True) -> pd.DataFrame:
        mapping_predicted_objective: Dict[float, str] = {}
        for o in self.objectives.names:
            mapping_predicted_objective[random.random()] = o
        drawn = self._transform(mapping_predicted_objective)
        predicted = self._transform_values(drawn)
        predicted.columns = [criterion.name for criterion in self.output_criteria()]

        return predicted

    def predict_batch(self, configurations: pd.DataFrame, transform: bool = True) -> pd.DataFrame:
        # each row's mock value is independently random, so there is nothing to vectorize; each row is
        # predicted on its own, same as predict(), just collected into a single result Dataframe
        predicted = pd.DataFrame()
        for _, cfg in configurations.reset_index(drop=True).iterrows():
            prediction = self.predict(cfg, transform)
            predicted = pd.concat([predicted, prediction], ignore_index=True)
        return predicted

    def _transform(self, mapping_predicted_objective: Dict[float, str]) -> pd.DataFrame:
        """
        Transform a floating point value between 0 and 1 into a DataFrame according to the Objective type.
        :param df: Floating-point value to be transformed.
        :return: Transformed DataFrame.
        """
        transformed_values = pd.DataFrame()  # transform based on the Objective type
        for value, name in mapping_predicted_objective.items():
            objective = self.objectives.by_name(name)
            lower, upper = objective.expected_range
            if not (math.isfinite(lower) and math.isfinite(upper)):
                lower, upper = 0, 1  # there is no range to scale to: the draw itself, rounded for an integer
            if objective.data_type == "float":
                transformed_value = lower + value * (upper - lower)
            elif objective.data_type == "int":
                transformed_value = round(lower + value * (upper - lower))
            else:
                raise NotImplementedError  # Objective function types except of numeric are not supported!

            if transformed_values.empty:
                transformed_values = pd.DataFrame(columns=[objective.name])
                transformed_values.loc[0] = transformed_value
            else:
                temp = pd.DataFrame(columns=[objective.name])
                temp.loc[0] = transformed_value
                transformed_values = transformed_values.join(temp)

        return transformed_values
