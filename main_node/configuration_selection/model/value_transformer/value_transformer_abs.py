import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, Optional, Sequence, Tuple
from core_entities.objectives import Criterion, Objectives


class ValueTransformer(ABC):
    def __init__(self, value_transformer_description: Dict, objectives: Objectives):
        self.value_transformer_description = value_transformer_description
        self.feature_name = list(value_transformer_description.keys())[0]
        self.objectives = objectives

    @abstractmethod
    def transform(self, objective_function_values: pd.DataFrame) -> pd.DataFrame:
        pass

    @abstractmethod
    def transform_criteria(self, criteria: Optional[Sequence[Criterion]]) -> Tuple[Criterion, ...]:
        """
        Declares the columns `transform` produces and the direction each is ranked in. It describes the output and
        never checks the input, so that it doesn't depend on how many columns arrive.
        :param criteria: the declarations of the incoming columns, None if they have no rankable direction.
        :return: the declarations of the transformed columns.
        """
        pass
