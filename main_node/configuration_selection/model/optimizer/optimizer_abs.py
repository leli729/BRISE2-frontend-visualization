import numpy as np
import pandas as pd
import pygmo as pg
from typing import Dict, Sequence, Tuple, Mapping
from abc import ABC, abstractmethod

from configuration_selection.model.value_transformer.value_transformer_orchestrator import ValueTransformerOrchestrator
from configuration_selection.model.configuration_transformer.configuration_transformer_abs import ConfigurationTransformer
from configuration_selection.model.surrogate.surrogate_abs import Surrogate
from configuration_selection.model import configuration_transformation
from core_entities.search_space import Hyperparameter
from core_entities.objectives import Criterion, Objectives


class Optimizer(ABC):
    def __init__(self, optimizer_description: Dict, region: Tuple, objectives: Objectives):
        self.region = region
        self.objectives = objectives
        self.feature_name = list(optimizer_description['Instance'].keys())[0]
        self.optimizer_description = optimizer_description

        # Configuration Transformers
        self.mapping_config_transformer_parameter: Mapping[ConfigurationTransformer, Tuple[Hyperparameter]] = (
            configuration_transformation.build_transformers(optimizer_description, region))

        # Value Transformers
        self.value_transformers = []
        self.scalarized = False
        self.value_transformer_orchestrator = ValueTransformerOrchestrator()
        for i in optimizer_description.items():
            if "ValueTransformer" in i[0]:
                for vt in i[1].items():
                    if vt[0] == "ValueScalarizator":
                        self.scalarized = True
                    value_transformer = self.value_transformer_orchestrator.get_value_transformer(vt, objectives)
                    self.value_transformers.append(value_transformer)

    @abstractmethod
    def optimize(self, surrogate: Surrogate) -> pd.DataFrame:
        """
        :param surrogate: surrogate used for evaluation.
        :return: a list of evaluated configurations, sorted by their quality, the best first.
        """
        pass

    def resolve_criteria(self, surrogate: Surrogate) -> Tuple[Criterion, ...]:
        """
        Resolves the direction of every column the candidates are ranked by: what the surrogate declares, mapped by the
        value transformers of the optimizer. A column of a value transformer is reported under the name of the objective
        (or "Y" if the surrogate scalarizes), keeping its direction.
        :param surrogate: the surrogate that predicts the candidates.
        :return: one criterion per ranked column, named as the column.
        :raises ValueError: if the surrogate predicts columns without a direction that no value transformer gives one.
        """
        criteria = surrogate.output_criteria()
        for value_transformer in self.value_transformers:
            criteria = value_transformer.transform_criteria(criteria)
        if criteria is None:
            raise ValueError(f"The columns {type(surrogate).__name__} predicts have no direction to rank candidates by: "
                             f"an acquisition function has to turn them into a score.")
        if self.value_transformers:
            names = ["Y"] if surrogate.scalarized else self.objectives.names
            if len(names) == len(criteria):
                criteria = tuple(Criterion(name, criterion.minimization) for name, criterion in zip(names, criteria))
        return tuple(criteria)

    def _rank_candidates(self, candidates: pd.DataFrame, criteria: Sequence[Criterion]) -> pd.DataFrame:
        """
        Sorts candidates by their predicted quality, the best first, each column in its own direction.
        :param candidates: parameter values of candidates, followed by their predictions.
        :param criteria: the columns that hold the predictions to rank, with their directions.
        :return: the same candidates, reordered, with a default index.
        """
        if candidates.empty:
            return candidates
        label_columns = [criterion.name for criterion in criteria]
        values_to_minimize = candidates[label_columns].to_numpy(dtype=float) * np.array([c.sign for c in criteria])
        if len(label_columns) == 1:
            order = np.argsort(values_to_minimize[:, 0], kind="stable")
        else:
            order = pg.sort_population_mo(values_to_minimize.tolist())
        return candidates.iloc[order].reset_index(drop=True)

    def _transform_configuration(self, features: pd.DataFrame) -> pd.DataFrame:
        return configuration_transformation.transform(features, self.mapping_config_transformer_parameter)

    def _inverse_transform_configuration(self, optimized_features: pd.DataFrame) -> pd.DataFrame:
        return configuration_transformation.inverse_transform(optimized_features, self.mapping_config_transformer_parameter)

    def _transform_values(self, labels: pd.DataFrame) -> pd.DataFrame:
        transformed_labels = pd.DataFrame()
        if len(self.value_transformers) > 0:
            for vt in self.value_transformers:
                if transformed_labels.empty:
                    transformed_labels = vt.transform(labels)
                else:
                    transformed_labels = vt.transform(transformed_labels)
        else:
            transformed_labels = labels
        return transformed_labels
