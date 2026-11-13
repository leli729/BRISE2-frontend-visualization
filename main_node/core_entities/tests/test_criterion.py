import pytest

from core_entities.objectives import Criterion, Objective


class TestCriterion:

    @pytest.mark.parametrize("minimization, sign", [(True, 1), (False, -1)])
    def test_a_minimized_criterion_has_the_sign_plus_one_and_a_maximized_one_minus_one(self, minimization, sign):
        assert Criterion("Y", minimization).sign == sign

    def test_criteria_with_the_same_name_and_direction_are_equal(self):
        assert Criterion("Y", True) == Criterion("Y", True)
        assert Criterion("Y", True) != Criterion("Y", False)
        assert Criterion("Y", True) != Criterion("ratio", True)

    def test_an_objective_is_a_criterion_with_its_own_name_and_direction(self):
        objective = Objective("Y1", False, "float", 0, 10)

        assert isinstance(objective, Criterion)
        assert objective.name == "Y1"
        assert objective.minimization is False
        assert objective.sign == -1
