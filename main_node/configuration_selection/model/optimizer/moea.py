from typing import Tuple, Dict, List
import pandas as pd
import numpy as np
import pygmo as pg

from core_entities.search_space import CategoricalHyperparameter, IntegerHyperparameter, NumericHyperparameter

from configuration_selection.model.optimizer.optimizer_abs import Optimizer
from configuration_selection.model.surrogate.surrogate_abs import Surrogate
from core_entities.objectives import Objectives

# these algorithms may leave the bounds of the problem unless explicitly forced to respect them
FORCE_BOUNDS_ALGORITHMS = frozenset({"cmaes", "xnes"})


class MOEA(Optimizer):
    def __init__(self, optimizer_description: Dict, region: Tuple, objectives: Objectives):
        super().__init__(optimizer_description, region, objectives)
        self.generations = optimizer_description["Instance"][self.feature_name]["Generations"]
        self.pop_size = optimizer_description["Instance"][self.feature_name]["PopulationSize"]
        self.algorithms = []
        for a in optimizer_description["Instance"][self.feature_name]["Algorithms"]:
            self.algorithms.append(a.lower())

        # transform and get boundaries
        self.bounds: Tuple[List, List] = ([], [])
        self.params: List[str] = []
        self.masked_params: Dict[str: Tuple[float, int]] = {}  # if lower bound == upper bound nsga2 and moead don't work
        # bounds/params/masked_params are (re)built per optimize() call

    def _has_own_transformer(self, hp) -> bool:
        return any(hp in params for params in self.mapping_config_transformer_parameter.values())

    def _build_bounds_params_masked(self) -> None:
        bounds: Tuple[List, List] = ([], [])
        params: List[str] = []
        masked_params: Dict[str: Tuple[float, int]] = {}

        i = 0  # number of masked parameters within the region influencing indexing of subsequent masked parameters
        for hp in self.region:
            if isinstance(hp, (CategoricalHyperparameter, IntegerHyperparameter)) and not self._has_own_transformer(hp):
                # MOEA searches every parameter as a real number, and only its own transformers cast it back
                raise ValueError(
                    f"MOEA needs ConfigurationTransformers of its own for {type(hp).__name__} '{hp.name}': it searches "
                    f"the parameter as a real number and only a transformer casts the proposal back.")
            if issubclass(type(hp), NumericHyperparameter):
                lower = hp.transform(0)
                lower_hp = pd.DataFrame([lower], columns=[hp.name])
                upper = hp.transform(1)
                upper_hp = pd.DataFrame([upper], columns=[hp.name])
                hps = pd.merge(lower_hp, upper_hp, how='outer')

                transformed_hps = self._transform_configuration(hps)

                transformed_name = transformed_hps.columns[0]
                bounds[0].append(transformed_hps.loc[0][transformed_name])
                bounds[1].append(transformed_hps.loc[1][transformed_name])
                params.append(transformed_name)

            if issubclass(type(hp), CategoricalHyperparameter):
                transformed_variants = pd.DataFrame()
                for category in hp.categories:
                    variant = pd.DataFrame([category], columns=[hp.name])
                    transformed_variant = self._transform_configuration(variant)
                    if transformed_variants.empty:
                        transformed_variants = transformed_variant
                    else:
                        transformed_variants = pd.concat([transformed_variants, transformed_variant])
                for c in transformed_variants.columns:
                    if min(transformed_variants[c]) == max(transformed_variants[c]):
                        masked_params[c] = tuple([min(transformed_variants[c]), len(params) + i])
                        i += 1
                        continue
                    bounds[0].append(min(transformed_variants[c]))
                    bounds[1].append(max(transformed_variants[c]))
                    params.append(c)

        self.bounds, self.params, self.masked_params = bounds, params, masked_params

    def optimize(self, surrogate: Surrogate) -> pd.DataFrame:
        self._build_bounds_params_masked()
        problem = self._PygmoProblem(optimizer=self, surrogate=surrogate)
        population = pg.population(problem, self.pop_size, b=pg.default_bfe())  # the initial population in one batch
        for algo_name in self.algorithms:
            algo_parameters = {"gen": self.generations}
            if algo_name in FORCE_BOUNDS_ALGORITHMS:
                algo_parameters["force_bounds"] = True
            algorithm = getattr(pg, algo_name)(**algo_parameters)
            if hasattr(algorithm, "set_bfe"):  # not every algorithm can evaluate a population in one batch
                algorithm.set_bfe(pg.bfe())
            population = pg.algorithm(algorithm).evolve(population)

        optimized_features = pd.DataFrame(population.get_x(), columns=self.params)
        # pygmo minimizes, so the fitness of a maximized column is negated; restore the predicted values
        optimized_labels = pd.DataFrame(population.get_f() * problem.signs, columns=[c.name for c in problem.criteria])

        for p, val_ind in self.masked_params.items():
            optimized_features.insert(loc=val_ind[1], column=p, value=val_ind[0])

        optimized_features = self._inverse_transform_configuration(optimized_features)  # inverse transform

        result = optimized_features.join(optimized_labels)
        return self._rank_candidates(result, problem.criteria)

    class _PygmoProblem:
        """
        A custom Pygmo problem, where the surrogate is utilized to evaluate the objective function.
        """
        def __init__(self,
                     optimizer,
                     surrogate: Surrogate):
            self._surrogate = surrogate
            self._optimizer: MOEA = optimizer
            self._bounds = self._optimizer.bounds
            self.criteria = self._optimizer.resolve_criteria(surrogate)
            self.signs = np.array([criterion.sign for criterion in self.criteria])
            self._params = self._optimizer.params

        def fitness(self, x):
            return self.batch_fitness(np.asarray(x)).tolist()

        def batch_fitness(self, dvs):
            """
            :param dvs: the decision vectors of a population, one after another.
            :return: the fitness of every individual of the population, one after another.
            """
            configurations = pd.DataFrame(np.asarray(dvs).reshape(-1, len(self._params)), columns=self._params)
            for p, val_ind in self._optimizer.masked_params.items():
                configurations.insert(loc=val_ind[1], column=p, value=val_ind[0])

            # the surrogate scores the configurations the individuals stand for, which are the ones that get measured
            configurations = self._optimizer._inverse_transform_configuration(configurations)

            result = self._surrogate.predict_batch(configurations)

            transformed_result = self._optimizer._transform_values(result)
            return (transformed_result.values * self.signs).flatten()

        def get_nobj(self):
            return len(self.criteria)

        def get_bounds(self):
            return self._bounds
