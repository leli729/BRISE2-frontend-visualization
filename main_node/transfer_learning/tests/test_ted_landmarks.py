import pytest

from tools.restore_db import RestoreDB
from transfer_learning.transfer_expediency_determination.sampling_landmark_based import SamplingLandmarkBased

# A source is similar to the target only if the first MinNumberOfSamples configurations the two measured are the same (the
# landmarks): the same sampler on the same search space draws them first. Two search spaces that merely share one
# configuration are not the same space.

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


def _description(comparator, similar_experiments):
    return {"SamplingLandmarkBased": {
        "MinNumberOfSamples": LANDMARKS,
        "Type": "sampling_landmark_based",
        "Comparator": {comparator: {"Type": COMPARATORS[comparator]}},
        "ExperimentsQuantity": {"FixedQuantity": {"NumberOfSimilarExperiments": similar_experiments}}}}


def _source(name, parameters_and_results):
    return {"Exp_unique_ID": name,
            "Samples": [{"type": 2, "parameters": parameters, "results": {"Y1": result}, "prediction_info": {}}
                        for parameters, result in parameters_and_results]}


def _write_target(database, parameters_and_results):
    for parameters, result in parameters_and_results:
        database.write_one_record("Configuration", {"Exp_unique_ID": TARGET, "Parameters": parameters, "Results": {"Y1": result}})


@pytest.fixture(params=list(COMPARATORS))
def make_ted(request):
    """TED of a target that measured its landmarks A, B and C, taking up to the given number of similar experiments."""
    rdb.cleanup()

    def make(similar_experiments=3):
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
