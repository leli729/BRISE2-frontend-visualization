import pandas as pd
from typing import Dict, Optional, Sequence, Tuple

from configuration_selection.model.value_transformer.value_scalarizator_abs import ValueScalarizator
from core_entities.objectives import Criterion, Objectives


class WeightedSum(ValueScalarizator):
    def __init__(self, value_transformer_description: Dict, objectives: Objectives):
        super().__init__(value_transformer_description, objectives)
        self.weights = value_transformer_description[self.feature_name]["Weights"]
        # a maximized objective is weighted by its negation, so that the sum is to be minimized
        self.signed_weights = [weight * objective.sign for weight, objective in zip(self.weights, objectives)]

    def transform_criteria(self, criteria: Optional[Sequence[Criterion]]) -> Tuple[Criterion, ...]:
        return (Criterion("Y", minimization=True),)

    def transform(self, objective_function_values: pd.DataFrame) -> pd.DataFrame:
        assert len(objective_function_values.columns) == len(self.weights) == len(self.signed_weights)
        transformed_objective_function_values = objective_function_values.dot(self.signed_weights)
        temp_df = pd.DataFrame()
        if type(transformed_objective_function_values) is pd.Series:
            transformed_objective_function_values = pd.concat([temp_df, transformed_objective_function_values])
            transformed_objective_function_values.rename(columns={0: "Y"}, inplace=True)
        else:
            transformed_objective_function_values.rename(columns={"<unnamed>": "Y"}, inplace=True)

        return transformed_objective_function_values
