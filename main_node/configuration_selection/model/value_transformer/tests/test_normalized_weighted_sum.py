import pandas as pd
import pytest

from configuration_selection.model.value_transformer.normalized_weighted_sum import NormalizedWeightedSum
from configuration_selection.model.value_transformer.value_transformer_orchestrator import ValueTransformerOrchestrator
from configuration_selection.model.value_transformer.weighted_sum import WeightedSum
from core_entities.objectives import Objectives


def _objectives(*objectives) -> Objectives:
    """:param objectives: one (minimization, expected minimum, expected maximum) per objective, named Y1, Y2, ..."""
    return Objectives.from_description({
        f"Y{i + 1}": {"Name": f"Y{i + 1}", "DataType": "float", "Minimization": minimization,
                      "MinExpectedValue": low, "MaxExpectedValue": high}
        for i, (minimization, low, high) in enumerate(objectives)})


def _description(weights: list) -> dict:
    return {"NormalizedWeightedSum": {"Type": "normalized_weighted_sum", "Weights": weights}}


def _normalized_weighted_sum(objectives: Objectives, weights: list) -> NormalizedWeightedSum:
    return NormalizedWeightedSum(_description(weights), objectives)


def _transform(objectives: Objectives, weights: list, predictions: dict) -> list:
    transformed = _normalized_weighted_sum(objectives, weights).transform(pd.DataFrame(predictions))
    return transformed.iloc[:, 0].tolist()


class TestNormalization:
    """Each objective is put on one scale: 0 is the best value it is expected to take, 1 the worst."""

    @pytest.mark.parametrize("minimization, value, expected", [
        (True, 10.0, 0.0),  # a minimized objective: the expected minimum is the best
        (True, 50.0, 1.0),
        (False, 50.0, 0.0),  # a maximized objective: the expected maximum is the best
        (False, 10.0, 1.0),
    ])
    def test_the_expected_best_value_maps_to_0_and_the_expected_worst_to_1(self, minimization, value, expected):
        # each value alone, so that the bounds are the declared ones and not the extremes of the rows at hand
        objectives = _objectives((minimization, 10.0, 50.0))

        assert _transform(objectives, [1], {"Y1": [value]}) == pytest.approx([expected])

    @pytest.mark.parametrize("minimization, value, expected", [
        (True, 20.0, 0.25),  # a quarter of the way from the minimum to the maximum
        (False, 20.0, 0.75),  # the same value of a maximized objective is closer to the worst
    ])
    def test_a_value_between_the_bounds_is_placed_linearly(self, minimization, value, expected):
        objectives = _objectives((minimization, 10.0, 50.0))

        assert _transform(objectives, [1], {"Y1": [value]}) == pytest.approx([expected])

    @pytest.mark.parametrize("minimization, value, expected", [
        (True, 0.0, -0.25),  # below the expected minimum of a minimized objective: better than the expected best
        (True, 60.0, 1.25),
        (False, 60.0, -0.25),  # above the expected maximum of a maximized objective
        (False, 0.0, 1.25),
    ])
    def test_a_value_outside_the_bounds_is_not_clipped(self, minimization, value, expected):
        objectives = _objectives((minimization, 10.0, 50.0))

        assert _transform(objectives, [1], {"Y1": [value]}) == pytest.approx([expected])

    def test_objectives_of_different_ranges_weigh_alike_at_the_same_relative_value(self):
        # Y1 spans 10 units, Y2 a thousand: both at their middle contribute 0.5 each, whatever the units
        objectives = _objectives((True, 0.0, 10.0), (True, 0.0, 1000.0))

        assert _transform(objectives, [1, 1], {"Y1": [5.0], "Y2": [500.0]}) == pytest.approx([1.0])


class TestWeightedSum:
    def test_the_normalized_values_are_added_with_their_weights(self):
        # Y1 minimized in [0, 10] at 5 -> 0.5; Y2 maximized in [0, 100] at 75 -> 0.25; 1 * 0.5 + 2 * 0.25
        objectives = _objectives((True, 0.0, 10.0), (False, 0.0, 100.0))

        assert _transform(objectives, [1, 2], {"Y1": [5.0], "Y2": [75.0]}) == pytest.approx([1.0])

    def test_a_row_is_scalarized_on_its_own(self):
        # inside the bounds, so that scaling by the rows' own minimum and maximum would give other values
        objectives = _objectives((True, 0.0, 10.0), (False, 0.0, 100.0))
        rows = {"Y1": [5.0, 2.0], "Y2": [75.0, 40.0]}

        together = _transform(objectives, [1, 2], rows)
        alone = [_transform(objectives, [1, 2], {"Y1": [y1], "Y2": [y2]})[0] for y1, y2 in zip(rows["Y1"], rows["Y2"])]

        assert together == pytest.approx(alone)
        assert together == pytest.approx([1.0, 1.4])  # 1 * 0.5 + 2 * 0.25, then 1 * 0.2 + 2 * 0.6

    def test_the_rows_keep_their_index(self):
        # the labels of a validator's split are a subset of the measured configurations, not numbered from 0
        objectives = _objectives((True, 0.0, 10.0), (False, 0.0, 100.0))
        predictions = pd.DataFrame({"Y1": [5.0, 0.0], "Y2": [75.0, 100.0]}, index=[4, 9])

        transformed = _normalized_weighted_sum(objectives, [1, 2]).transform(predictions)

        assert transformed.index.tolist() == [4, 9]
        assert transformed.iloc[:, 0].tolist() == pytest.approx([1.0, 0.0])

    def test_a_zero_weight_leaves_its_objective_out(self):
        objectives = _objectives((True, 0.0, 10.0), (True, 0.0, 10.0))

        assert _transform(objectives, [0, 1], {"Y1": [10.0], "Y2": [5.0]}) == pytest.approx([0.5])


class TestDeclaredCriterion:
    @pytest.mark.parametrize("directions", [(True, True), (True, False), (False, False)])
    def test_the_value_is_declared_minimized_whatever_the_directions_of_the_objectives(self, directions):
        objectives = _objectives(*[(minimization, 0.0, 10.0) for minimization in directions])

        criteria = _normalized_weighted_sum(objectives, [1, 1]).transform_criteria(tuple(objectives))

        assert [(criterion.name, criterion.minimization) for criterion in criteria] == [
            ("normalized_weighted_sum(Y1,Y2)", True)]

    def test_the_transformed_column_is_named_as_the_declared_criterion(self):
        objectives = _objectives((True, 0.0, 10.0), (False, 0.0, 10.0))
        scalarizer = _normalized_weighted_sum(objectives, [1, 1])

        transformed = scalarizer.transform(pd.DataFrame({"Y1": [1.0], "Y2": [2.0]}))

        # the optimizer declares its scalarizer's criterion from the surrogate's output: here, the objectives
        declared = scalarizer.transform_criteria(tuple(objectives))
        assert transformed.columns.tolist() == [criterion.name for criterion in declared]


class TestSelectionByType:
    """A value transformer is resolved from its Type by the similarity of file names; the two scalarizers' names overlap."""

    @pytest.mark.parametrize("feature, type_name, expected_class", [
        ("NormalizedWeightedSum", "normalized_weighted_sum", NormalizedWeightedSum),
        ("WeightedSum", "weighted_sum", WeightedSum),
    ])
    def test_each_type_resolves_to_its_own_scalarizer(self, feature, type_name, expected_class):
        objectives = _objectives((True, 0.0, 10.0), (True, 0.0, 10.0))

        scalarizer = ValueTransformerOrchestrator().get_value_transformer(
            ("ValueScalarizator", {feature: {"Type": type_name, "Weights": [1, 1]}}), objectives)

        assert type(scalarizer) is expected_class
