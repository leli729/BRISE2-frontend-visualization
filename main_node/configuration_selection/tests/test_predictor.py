from types import SimpleNamespace

import pandas as pd
import pytest

from configuration_selection.model.model import Model
from configuration_selection.model.predictor import Predictor
from core_entities.configuration import Configuration
from core_entities.objectives import Criterion
from tools.restore_db import RestoreDB

rdb = RestoreDB()
Y1_MINIMIZED = Criterion("Y1", minimization=True)


def _make_config(parameters):
    return Configuration(parameters, Configuration.Type.TEST, "experiment_id")


def _make_region(parent_name, activation_category, hp_names):
    parent = SimpleNamespace(name=parent_name)
    return tuple(SimpleNamespace(parent=parent, activation_category=activation_category, name=hp_name)
                 for hp_name in hp_names)


class TestUpdatePrediction:

    def test_updating_prediction_with_colliding_objective_columns(self):
        """
        Each hierarchical region's model predicts the same objective column names, so merging several regions'
        predictions must rename those columns.
        """
        region_names = [f"hp{i}" for i in range(4)]
        predicted = pd.DataFrame()
        for i, hp_name in enumerate(region_names):
            partial_configuration = pd.DataFrame({hp_name: [i], "Y1": [float(i)]})
            predicted = Predictor._update_prediction(None, predicted, partial_configuration, str(i), [hp_name])

        assert len(predicted) == 1
        assert set(region_names).issubset(predicted.columns)

        objective_columns = [c for c in predicted.columns if c not in region_names]
        assert len(objective_columns) == len(region_names)
        assert len(set(objective_columns)) == len(objective_columns)
        assert sorted(predicted[objective_columns].iloc[0].tolist()) == [0.0, 1.0, 2.0, 3.0]

    def test_updating_prediction_with_no_prior_predictions_returns_partial_configuration_unchanged(self):
        partial_configuration = pd.DataFrame({"hp0": [1], "Y1": [0.5]})
        merged = Predictor._update_prediction(None, pd.DataFrame(), partial_configuration, "0", ["hp0"])

        pd.testing.assert_frame_equal(merged, partial_configuration)


class TestConsideredConfigsForRegion:

    def test_sibling_regions_are_scoped_independently(self):
        """
        Two sibling regions (same parent, different activation categories) must each be scoped from the
        full base window, not from whatever the other sibling's filtering left behind.
        """
        base_considered_configs = [
            _make_config({"algorithm": "A", "A.param": 1}),
            _make_config({"algorithm": "B", "B.param": 2}),
        ]
        region_a = _make_region("algorithm", "A", ["A.param"])
        region_b = _make_region("algorithm", "B", ["B.param"])

        configs_for_a = Predictor._considered_configs_for_region(None, base_considered_configs, region_a, ["A.param"])
        configs_for_b = Predictor._considered_configs_for_region(None, base_considered_configs, region_b, ["B.param"])

        assert [c.parameters["algorithm"] for c in configs_for_a] == ["A"]
        assert [c.parameters["algorithm"] for c in configs_for_b] == ["B"]

    def test_root_level_region_skips_activation_category_filter(self):
        base_considered_configs = [_make_config({"algorithm": "A"})]
        root_region = _make_region("root", "root", ["algorithm"])

        configs = Predictor._considered_configs_for_region(None, base_considered_configs, root_region, ["algorithm"])

        assert configs == base_considered_configs

    def test_configs_from_an_unrelated_branch_lacking_the_parent_key_are_excluded_not_erroring(self):
        """
        A deeper region's parent hyperparameter (e.g. under branch N01) is absent from configs
        measured along a different branch: those configs must be filtered out.
        """
        base_considered_configs = [
            _make_config({"branch": "N01", "N01.O1": "N01.O1.X", "N01.O1.X.param": 1}),
            _make_config({"branch": "N02", "N02.param": 2}),
        ]
        deeper_region = _make_region("N01.O1", "N01.O1.X", ["N01.O1.X.param"])

        configs = Predictor._considered_configs_for_region(None, base_considered_configs, deeper_region,
                                                            ["N01.O1.X.param"])

        assert [c.parameters["branch"] for c in configs] == ["N01"]

    def test_base_considered_configs_is_not_mutated(self):
        base_considered_configs = [
            _make_config({"algorithm": "A", "A.param": 1}),
            _make_config({"algorithm": "B", "B.param": 2}),
        ]
        original = list(base_considered_configs)
        region_a = _make_region("algorithm", "A", ["A.param"])

        Predictor._considered_configs_for_region(None, base_considered_configs, region_a, ["A.param"])

        assert base_considered_configs == original


class TestAveragePredictionsPerObjective:

    def test_predictions_of_one_objective_from_several_regions_are_averaged(self):
        predicted_values = pd.Series({"Y1": 1.0, "Y1__region2": 2.0, "Y1__region3": 6.0})
        averaged = Predictor._average_predictions_per_objective(None, predicted_values)

        assert averaged == {"Y1": 3.0}

    def test_every_objective_keeps_its_own_average(self):
        predicted_values = pd.Series(
            {"Y1": 1.0, "Y2": 10.0, "Y1__region2": 3.0, "Y2__region2": 20.0}
        )
        averaged = Predictor._average_predictions_per_objective(None, predicted_values)

        assert averaged == {"Y1": 2.0, "Y2": 15.0}
        assert list(averaged.keys()) == ["Y1", "Y2"]

    def test_single_region_prediction_is_returned_as_is(self):
        predicted_values = pd.Series({"Y1": 0.5})
        averaged = Predictor._average_predictions_per_objective(None, predicted_values)

        assert averaged == {"Y1": 0.5}


class TestPredictedConfigurationsHoldOnlyActiveParameters:
    """
    'test_case_13' is flat, 'test_case_11' is hierarchical; both have the branches N01 {F1, N1} and N02 {I1, O1}
    below N0. A configuration leaves the predictor in its measured form: the active parameters only.
    """

    N0 = "Context.SearchSpace.N0"
    BRANCH_PARAMETERS = {
        f"{N0}.N01": {N0, f"{N0}.N01.F1", f"{N0}.N01.N1"},
        f"{N0}.N02": {N0, f"{N0}.N02.I1", f"{N0}.N02.O1"},
    }

    @pytest.fixture(autouse=True)
    def _database(self):
        rdb.cleanup()
        rdb.restore()

    @staticmethod
    def _predictor(get_experiment, test_case):
        description, search_space = get_experiment(test_case)
        return Predictor("experiment_id", description, search_space)

    @pytest.mark.parametrize("test_case", [13, 11])
    def test_sampled_configurations_hold_the_parameters_of_their_branch(self, get_experiment, test_case):
        predictor = self._predictor(get_experiment, test_case)

        configurations = [c for _ in range(20) for c in predictor.predict([], True)]

        assert all(set(c.parameters) == self.BRANCH_PARAMETERS[c.parameters[self.N0]] for c in configurations)

    def test_flat_predictions_hold_the_parameters_of_their_branch(self, get_experiment):
        predictor = self._predictor(get_experiment, 13)
        region = predictor.search_space.regions[0]
        n1, o1 = f"{self.N0}.N01.N1.N11", f"{self.N0}.N02.O1.O11"
        # the model proposes a value for every parameter, also for the ones the branch doesn't activate
        proposals = pd.DataFrame([
            {self.N0: f"{self.N0}.N01", f"{self.N0}.N01.F1": 1.0, f"{self.N0}.N01.N1": n1,
             f"{self.N0}.N02.I1": 11, f"{self.N0}.N02.O1": o1, "Y1": 0.5},
            {self.N0: f"{self.N0}.N02", f"{self.N0}.N01.F1": 2.0, f"{self.N0}.N01.N1": n1,
             f"{self.N0}.N02.I1": 22, f"{self.N0}.N02.O1": o1, "Y1": 0.6},
        ])
        predictor.mapping_region_model[region].predict = lambda parameters, configurations: proposals
        predictor.mapping_region_model[region].ranked_criteria = [Y1_MINIMIZED]

        configurations = predictor.predict([_make_config({})])

        assert [set(c.parameters) for c in configurations] == [
            self.BRANCH_PARAMETERS[f"{self.N0}.N01"], self.BRANCH_PARAMETERS[f"{self.N0}.N02"]]
        assert [c.parameters[f"{self.N0}.N01.F1"] for c in configurations[:1]] == [1.0]
        assert [c.predicted_result for c in configurations] == [
            {"Y1": {"Minimization": True, "Value": 0.5}}, {"Y1": {"Minimization": True, "Value": 0.6}}]


class TestPredictionInfoNamesTheModelsThatPredictedTheConfiguration:
    """
    A configuration's prediction information holds the models that predicted it, with their build time, and a model
    combination is dumped only when every level's model predicted. Before each test, every model gets the description
    and build time that an earlier successful call leaves behind (EARLIER_CALL).
    'test_case_13' is flat (one region), 'test_case_11' hierarchical: region 0 is the root (N0), region 1 the branch N01
    (F1, N1), region 2 the branch N02 (I1, O1).
    """

    N0 = "Context.SearchSpace.N0"
    NO_MODEL = {"Model": [], "time_to_build": 0}
    EARLIER_CALL = {"Model": [{"Surrogate": "built in an earlier call"}], "time_to_build": 1.0}
    BUILT = {"Model": [{"Surrogate": "built in this call"}], "time_to_build": 2.0}

    @pytest.fixture(autouse=True)
    def _database(self):
        rdb.cleanup()
        rdb.restore()

    @classmethod
    def _predictor_with_models_built_earlier(cls, get_experiment, test_case):
        description, search_space = get_experiment(test_case)
        predictor = Predictor("experiment_id", description, search_space)
        for model in predictor.mapping_region_model.values():
            descriptions = list(cls.EARLIER_CALL["Model"])
            model.created_surrogates_descriptions_and_objectives_and_optimizer_descriptions = descriptions
            model.time_to_build = cls.EARLIER_CALL["time_to_build"]
            model.ranked_criteria = [Y1_MINIMIZED]
        return predictor

    @classmethod
    def _predict_as_built_in_this_call(cls, proposal):
        """A model's predict that builds and proposes, setting its per-call attributes as the real one does."""
        def predict(model, parameters, configurations):
            model.created_surrogates_descriptions_and_objectives_and_optimizer_descriptions = list(cls.BUILT["Model"])
            model.time_to_build = cls.BUILT["time_to_build"]
            model.ranked_criteria = [Y1_MINIMIZED]
            return proposal
        return predict

    def _proposal(self):
        n0 = self.N0
        return pd.DataFrame([{n0: f"{n0}.N01", f"{n0}.N01.F1": 1.0, f"{n0}.N01.N1": f"{n0}.N01.N1.N11",
                              f"{n0}.N02.I1": 11, f"{n0}.N02.O1": f"{n0}.N02.O1.O11", "Y1": 0.5}])

    def _hierarchical_predict(self, predictor, branch_proposes):
        """The root's model proposes the branch N01; the branch's model proposes too, or fails."""
        n0 = self.N0
        root = predictor.search_space.regions[0]
        predict_root = self._predict_as_built_in_this_call(pd.DataFrame([{n0: f"{n0}.N01", "Y1": 0.5}]))
        predict_branch = self._predict_as_built_in_this_call(
            pd.DataFrame([{f"{n0}.N01.F1": 1.0, f"{n0}.N01.N1": f"{n0}.N01.N1.N11", "Y1": 0.6}]))

        def predict(model, parameters, configurations):
            if model.region == root:
                return predict_root(model, parameters, configurations)
            if branch_proposes:
                return predict_branch(model, parameters, configurations)
            return pd.DataFrame()

        return predict

    def test_a_region_whose_model_proposes_nothing_reports_no_model_and_adds_no_dump(self, get_experiment, monkeypatch):
        predictor = self._predictor_with_models_built_earlier(get_experiment, 13)
        # patched on the class: the predictor pickles the model into the dumps, which an instance attribute would break;
        # unlike the real predict, the fake keeps the earlier build's attributes: the predictor must not rely on a reset
        monkeypatch.setattr(Model, "predict", lambda model, parameters, configurations: pd.DataFrame())

        configurations = predictor.predict([_make_config({})])

        assert [c.type for c in configurations] == [Configuration.Type.FROM_SELECTOR]
        assert configurations[0].prediction_info == {"0": self.NO_MODEL}
        assert predictor.hierarchical_models_dumps == []

    @pytest.mark.parametrize("test_case", [13, 11])
    def test_a_sampled_configuration_reports_no_model_and_adds_no_dump(self, get_experiment, test_case):
        predictor = self._predictor_with_models_built_earlier(get_experiment, test_case)

        configurations = predictor.predict([], True)

        prediction_info = configurations[0].prediction_info
        assert len(prediction_info) == predictor.search_space.number_of_levels  # one region per level is sampled
        assert prediction_info == {region_index: self.NO_MODEL for region_index in prediction_info}
        assert predictor.hierarchical_models_dumps == []

    def test_a_predicting_model_reports_its_description_and_build_time_and_adds_its_dump(
            self, get_experiment, monkeypatch):
        predictor = self._predictor_with_models_built_earlier(get_experiment, 13)
        monkeypatch.setattr(Model, "predict", self._predict_as_built_in_this_call(self._proposal()))

        configurations = predictor.predict([_make_config({})])

        assert [c.type for c in configurations] == [Configuration.Type.PREDICTED]
        assert configurations[0].prediction_info == {"0": self.BUILT}
        assert [len(dump) for dump in predictor.hierarchical_models_dumps] == [1]

    def test_a_sampled_branch_reports_no_model_next_to_a_predicting_root_and_adds_no_dump(
            self, get_experiment, monkeypatch):
        predictor = self._predictor_with_models_built_earlier(get_experiment, 11)
        monkeypatch.setattr(Model, "predict", self._hierarchical_predict(predictor, branch_proposes=False))

        configurations = predictor.predict([_make_config({})])

        assert [c.type for c in configurations] == [Configuration.Type.FROM_SELECTOR]
        # the root's proposal is kept; the branch's parameters, which its model did not propose, come from the sampler
        n0 = self.N0
        assert configurations[0].parameters[n0] == f"{n0}.N01"
        assert {f"{n0}.N01.F1", f"{n0}.N01.N1"} <= set(configurations[0].parameters)
        assert configurations[0].prediction_info == {"0": self.BUILT, "1": self.NO_MODEL}
        # a dump holds a model for every level, and the branch's model was not built in this call
        assert predictor.hierarchical_models_dumps == []

    def test_a_configuration_predicted_on_every_level_adds_one_dump_of_all_levels(
            self, get_experiment, monkeypatch):
        predictor = self._predictor_with_models_built_earlier(get_experiment, 11)
        monkeypatch.setattr(Model, "predict", self._hierarchical_predict(predictor, branch_proposes=True))

        configurations = predictor.predict([_make_config({})])

        assert [c.type for c in configurations] == [Configuration.Type.PREDICTED]
        assert configurations[0].prediction_info == {"0": self.BUILT, "1": self.BUILT}
        assert [len(dump) for dump in predictor.hierarchical_models_dumps] == [2]

    def test_a_model_that_builds_nothing_holds_nothing_of_an_earlier_call(self, get_experiment):
        predictor = self._predictor_with_models_built_earlier(get_experiment, 13)
        region, model = next(iter(predictor.mapping_region_model.items()))

        candidates = model.predict(list(region), [])

        assert candidates.empty
        assert model.created_surrogates_descriptions_and_objectives_and_optimizer_descriptions == []
        assert model.time_to_build is None
        assert model.ranked_criteria == []


class TestPredictedResultNamesEachValueWithItsDirection:
    """
    A configuration's predicted result holds, for every value its model ranked the candidates by, the name of the
    criterion, the direction it is ranked in and the value; a region that did not predict adds nothing.
    'test_case_13' is flat (one region), 'test_case_11' hierarchical: region 0 is the root (N0), region 1 the branch N01
    (F1, N1).
    """

    N0 = "Context.SearchSpace.N0"

    @pytest.fixture(autouse=True)
    def _database(self):
        rdb.cleanup()
        rdb.restore()

    @staticmethod
    def _predictor(get_experiment, test_case):
        description, search_space = get_experiment(test_case)
        return Predictor("experiment_id", description, search_space)

    def _flat_proposal(self, **ranked_values):
        n0 = self.N0
        return pd.DataFrame([{n0: f"{n0}.N01", f"{n0}.N01.F1": 1.0, f"{n0}.N01.N1": f"{n0}.N01.N1.N11",
                              f"{n0}.N02.I1": 11, f"{n0}.N02.O1": f"{n0}.N02.O1.O11"} | ranked_values])

    @staticmethod
    def _predicting(proposal, criteria):
        """A model's predict that proposes and records the criteria it ranked by, as the real one does."""
        def predict(model, parameters, configurations):
            model.ranked_criteria = criteria
            return proposal
        return predict

    @pytest.mark.parametrize("criteria, values, expected", [
        # Y2 is not an objective of test case 13: the directions come from the model, not from the experiment
        ([Y1_MINIMIZED, Criterion("Y2", False)], {"Y1": 0.5, "Y2": 0.7},
         {"Y1": {"Minimization": True, "Value": 0.5}, "Y2": {"Minimization": False, "Value": 0.7}}),
        ([Criterion("ratio(Y1)", False)], {"ratio(Y1)": 1.7}, {"ratio(Y1)": {"Minimization": False, "Value": 1.7}}),
    ], ids=["two_criteria_in_their_own_directions", "derived_value"])
    def test_each_ranked_value_is_stored_under_its_name_with_its_direction(
            self, get_experiment, monkeypatch, criteria, values, expected):
        predictor = self._predictor(get_experiment, 13)
        monkeypatch.setattr(Model, "predict", self._predicting(self._flat_proposal(**values), criteria))

        configurations = predictor.predict([_make_config({})])

        assert [c.predicted_result for c in configurations] == [expected]

    @pytest.mark.parametrize("test_case", [13, 11])
    def test_a_sampled_configuration_holds_no_predicted_result(self, get_experiment, test_case):
        predictor = self._predictor(get_experiment, test_case)

        configurations = predictor.predict([], True)

        assert [c.predicted_result for c in configurations] == [{}]

    def test_each_call_holds_the_predicted_result_of_its_own_proposal_only(self, get_experiment, monkeypatch):
        predictor = self._predictor(get_experiment, 13)
        stored = {"Y1": {"Minimization": True, "Value": 0.5}}
        predicting = self._predicting(self._flat_proposal(Y1=0.5), [Y1_MINIMIZED])
        proposing_nothing = lambda model, parameters, configurations: pd.DataFrame()  # keeps the criteria of the call before

        monkeypatch.setattr(Model, "predict", predicting)
        results = [[c.predicted_result for c in predictor.predict([_make_config({})])]]
        results.append([c.predicted_result for c in predictor.predict([], True)])
        monkeypatch.setattr(Model, "predict", proposing_nothing)
        results.append([c.predicted_result for c in predictor.predict([_make_config({})])])

        assert results == [[stored], [{}], [{}]]  # predicted, sampled, the model proposed nothing

    def test_a_sampled_branch_adds_nothing_next_to_the_value_of_a_predicting_root(self, get_experiment, monkeypatch):
        predictor = self._predictor(get_experiment, 11)
        root = predictor.search_space.regions[0]
        for model in predictor.mapping_region_model.values():
            model.ranked_criteria = [Criterion("Y1", minimization=False)]  # an earlier call's, in the other direction
        proposal = pd.DataFrame([{self.N0: f"{self.N0}.N01", "Y1": 0.5}])
        predict_root = self._predicting(proposal, [Y1_MINIMIZED])

        def predict(model, parameters, configurations):
            return predict_root(model, parameters, configurations) if model.region == root else pd.DataFrame()

        monkeypatch.setattr(Model, "predict", predict)

        configurations = predictor.predict([_make_config({})])

        assert [c.type for c in configurations] == [Configuration.Type.FROM_SELECTOR]
        assert [c.predicted_result for c in configurations] == [{"Y1": {"Minimization": True, "Value": 0.5}}]

