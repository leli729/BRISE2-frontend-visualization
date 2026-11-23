import pytest

from tools.restore_db import RestoreDB
from transfer_learning.transfer_expediency_determination.sampling_landmark_based import SamplingLandmarkBased

# A source is similar to the target only if it has identical landmarks and objective functions.

rdb = RestoreDB()

TARGET = "target"
LANDMARKS = 3
COMPARATORS = {"NormDifference": "norm_difference_comparator", "RGPE": "rgpe_comparator"}


def _configuration(i):
    return {"Context.SearchSpace.X1": float(i), "Context.SearchSpace.X2": float(i)}


# the target's landmarks are A, B and C
A, B, C, D, X, Y, Z = (_configuration(i) for i in range(7))

# the results of the landmarks (one for each) as the target measured them and as a source measured them
TARGET_RESULTS = [1.0, 2.0, 3.0]
SOURCE_RESULTS = [3.0, 2.0, 1.0]


def _objectives(name="Y1", data_type="float", minimization=True, max_expected_value=100):
    """Context.TaskConfiguration.Objectives of one objective."""
    return {name: {"Name": name, "DataType": data_type, "Minimization": minimization,
                   "MinExpectedValue": 0, "MaxExpectedValue": max_expected_value}}


MINIMIZED_Y1 = _objectives()


def _description(comparator, similar_experiments):
    return {"SamplingLandmarkBased": {
        "MinNumberOfSamples": LANDMARKS,
        "Type": "sampling_landmark_based",
        "Comparator": {comparator: {"Type": COMPARATORS[comparator]}},
        "ExperimentsQuantity": {"FixedQuantity": {"NumberOfSimilarExperiments": similar_experiments}}}}


def _source(name, parameters_and_results, objectives=MINIMIZED_Y1):
    source = {"Exp_unique_ID": name,
              "Samples": [{"type": 2, "parameters": parameters, "results": {"Y1": result}, "prediction_info": {}}
                          for parameters, result in parameters_and_results]}
    if objectives is not None:
        source["Objectives"] = objectives
    return source


def _write_target(database, parameters_and_results):
    for parameters, result in parameters_and_results:
        database.write_one_record("Configuration", {"Exp_unique_ID": TARGET, "Parameters": parameters, "Results": {"Y1": result}})


@pytest.fixture(params=list(COMPARATORS))
def make_ted(request):
    """
    TED of a target that measured its landmarks A, B and C, taking up to the given number of similar experiments. The
    target has the given objectives in its description, none if they are None.
    """
    rdb.cleanup()

    def make(similar_experiments=3, objectives=MINIMIZED_Y1):
        if objectives is not None:
            rdb.database.write_one_record("Experiment_description", {
                "Exp_unique_ID": TARGET, "Context": {"TaskConfiguration": {"Objectives": objectives}}})
        ted = SamplingLandmarkBased(_description(request.param, similar_experiments), TARGET)
        _write_target(ted.database, list(zip([A, B, C], TARGET_RESULTS)))
        ted.database.write_one_record("Experiment_state", {"Exp_unique_ID": TARGET, "Number_of_measured_configs": LANDMARKS})
        return ted

    yield make
    rdb.cleanup()


@pytest.fixture
def ted(make_ted):
    return make_ted()


def _taken(ted, *sources):
    """The sources TED takes among the given ones."""
    for source in sources:
        ted.database.write_one_record("Transfer_learning_info", source)
    return sorted(source["Exp_unique_ID"] for source in ted.analyse_experiments_similarity())


class TestSimilarSources:

    def test_a_source_that_began_with_the_landmarks_is_taken(self, ted):
        source = _source("same", list(zip([A, B, C], SOURCE_RESULTS)))

        assert _taken(ted, source) == ["same"]

    def test_a_source_that_measured_the_landmarks_in_another_order_is_taken(self, ted):
        # parallel workers finish in any order
        source = _source("reordered", list(zip([C, A, B], [SOURCE_RESULTS[2], SOURCE_RESULTS[0], SOURCE_RESULTS[1]])))

        assert _taken(ted, source) == ["reordered"]

    def test_a_source_with_more_samples_after_the_landmarks_is_taken(self, ted):
        source = _source("longer", list(zip([A, B, C, D, X, Y], SOURCE_RESULTS + [0.0] * 3)))

        assert _taken(ted, source) == ["longer"]

    def test_several_sources_that_began_with_the_landmarks_are_all_taken(self, ted):
        sources = [_source(name, list(zip([A, B, C], SOURCE_RESULTS))) for name in ("first", "second")]

        assert _taken(ted, *sources) == ["first", "second"]


class TestDissimilarSources:

    def test_a_source_that_shares_one_landmark_only_is_not_taken(self, ted):
        # the same names and one sampled value do not make the same search space
        source = _source("one-in-common", list(zip([A, X, Y, Z], SOURCE_RESULTS + [0.0])))

        assert _taken(ted, source) == []

    def test_a_source_that_has_the_landmarks_only_after_its_first_samples_is_not_taken(self, ted):
        # a long run of another search space can contain the landmarks by chance
        source = _source("later", list(zip([X, Y, Z, A, B, C], [0.0] * 3 + SOURCE_RESULTS)))

        assert _taken(ted, source) == []

    def test_a_source_that_began_with_later_configurations_of_the_target_is_not_taken(self, ted):
        # the landmarks are the first configurations the target measured, not any of them
        _write_target(ted.database, [(D, 100.0)])
        source = _source("later-ones", list(zip([B, C, D], SOURCE_RESULTS)))

        assert _taken(ted, source) == []

    def test_a_source_with_fewer_samples_than_landmarks_is_not_taken(self, ted):
        source = _source("short", list(zip([A, B], SOURCE_RESULTS[:2])))

        assert _taken(ted, source) == []

    def test_only_the_source_with_the_landmarks_is_taken_among_several(self, ted):
        sources = [_source("one-in-common", list(zip([A, X, Y], SOURCE_RESULTS))),
                   _source("same", list(zip([A, B, C], SOURCE_RESULTS)))]

        assert _taken(ted, *sources) == ["same"]


class TestObjectives:
    """The landmarks of all these sources are the target's, so only the objectives tell them from the similar ones."""

    SAME_LANDMARKS = list(zip([A, B, C], SOURCE_RESULTS))

    @pytest.mark.parametrize("objectives", [
        pytest.param(_objectives(minimization=False), id="the other direction"),
        pytest.param(_objectives(max_expected_value=1000), id="another expected range"),
        pytest.param(_objectives(data_type="integer"), id="another data type"),
        pytest.param(_objectives(name="Y2"), id="another name"),
        pytest.param({**MINIMIZED_Y1, **_objectives(name="Y2")}, id="one more objective"),
    ])
    def test_a_source_with_other_objectives_is_not_taken(self, ted, objectives):
        assert _taken(ted, _source("other", self.SAME_LANDMARKS, objectives)) == []

    def test_a_source_with_no_objectives_on_record_is_not_taken(self, ted):
        # nothing proves the direction it was optimized in
        assert _taken(ted, _source("unknown", self.SAME_LANDMARKS, objectives=None)) == []

    def test_only_the_source_with_the_objectives_of_the_target_is_taken_among_several(self, ted):
        sources = [_source("maximized", self.SAME_LANDMARKS, _objectives(minimization=False)),
                   _source("minimized", self.SAME_LANDMARKS),
                   _source("unknown", self.SAME_LANDMARKS, objectives=None)]

        assert _taken(ted, *sources) == ["minimized"]

    def test_a_maximizing_target_takes_the_source_that_maximized(self, make_ted):
        ted = make_ted(objectives=_objectives(minimization=False))
        sources = [_source("maximized", self.SAME_LANDMARKS, _objectives(minimization=False)),
                   _source("minimized", self.SAME_LANDMARKS)]

        assert _taken(ted, *sources) == ["maximized"]

    def test_a_target_with_no_description_takes_no_source(self, make_ted):
        ted = make_ted(objectives=None)

        assert _taken(ted, _source("same", self.SAME_LANDMARKS)) == []


class TestRanking:

    def test_the_most_similar_source_is_judged_by_the_landmarks_only(self, make_ted):
        # the target goes on after the landmarks: D with 100. "landmarks-right" measured the landmarks as the target did
        # and D very differently, "landmarks-off" got B and C the other way round and D right. Over all four common
        # configurations "landmarks-off" would look closer; over the landmarks "landmarks-right" is.
        ted = make_ted(similar_experiments=1)
        _write_target(ted.database, [(D, 100.0)])
        sources = [_source("landmarks-right", list(zip([A, B, C, D], [1.0, 2.0, 3.0, 0.0]))),
                   _source("landmarks-off", list(zip([A, B, C, D], [1.0, 3.0, 2.0, 100.0])))]

        assert _taken(ted, *sources) == ["landmarks-right"]


class TestSamplingLandmarkBased:

    def test_banning_one_of_two_similar_sources_keeps_the_other_without_comparing_again(self, ted):
        for name in ("first", "second"):
            ted.database.write_one_record("Transfer_learning_info", _source(name, list(zip([A, B, C], SOURCE_RESULTS))))
        assert [source["Exp_unique_ID"] for source in ted.analyse_experiments_similarity()] == ["first", "second"]
        comparisons = []
        compare = ted.comparator.get_similar_experiments
        ted.comparator.get_similar_experiments = lambda sources: comparisons.append(sources) or compare(sources)

        ted.ban_experiments(["first"])

        assert [source["Exp_unique_ID"] for source in ted.similar_experiments] == ["second"]
        assert [source["Exp_unique_ID"] for source in ted.analyse_experiments_similarity()] == ["second"]
        assert comparisons == []
