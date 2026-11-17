import pandas as pd
from typing import Dict, Optional, Sequence, Tuple

from configuration_selection.model.value_transformer.value_scalarizator_abs import ValueScalarizator
from core_entities.objectives import Criterion, Objectives


class NormalizedWeightedSum(ValueScalarizator):
    def __init__(self, value_transformer_description: Dict, objectives: Objectives):
        super().__init__(value_transformer_description, objectives)
        self.weights = value_transformer_description[self.feature_name]["Weights"]

    def transform_criteria(self, criteria: Optional[Sequence[Criterion]]) -> Tuple[Criterion, ...]:
        # the inputs are named when known; a declaration never checks them
        inputs = self.objectives if criteria is None else criteria
        return (Criterion.derived("normalized_weighted_sum", inputs, minimization=True),)

    def transform(self, objective_function_values: pd.DataFrame) -> pd.DataFrame:
        assert len(objective_function_values.columns) == len(self.weights)
        # every objective on one scale by its expected range: 0 is the best value it is expected to take, 1 the worst;
        # a value outside the range lands outside [0, 1], it is not clipped
        normalized = pd.DataFrame(index=objective_function_values.index)
        for column, objective in zip(objective_function_values.columns, self.objectives):
            lowest, highest = objective.expected_range
            best, worst = (lowest, highest) if objective.minimization else (highest, lowest)
            normalized[column] = (objective_function_values[column] - best) / (worst - best)
        normalized_weighted_sum = Criterion.derived("normalized_weighted_sum", self.objectives, minimization=True)
        return normalized.dot(self.weights).to_frame(normalized_weighted_sum.name)
