from collections import Counter

import pytest

from generator_paths import BASE, GRAMMAR
from dimension_blacklist import BLACKLIST, apply_blacklist, feature_dimensions
from pairwise_generator import CONTEXT_VARIANTS, PairwiseConfig
from quant_metrics import get_parser_features
from wfl_parser_textx import WflParserTextX

SURROGATE = "ConfigurationSelection.Predictor.Model.Surrogate"
OPTIMIZER = "ConfigurationSelection.Predictor.Model.Optimizer"
ON_OFF_GROUPS = (
    [f"{owner}.ConfigurationTransformers.{name}" for owner in (SURROGATE, OPTIMIZER)
     for name in ("OrdinalTransformer", "NominalTransformer", "IntegerTransformer", "FloatTransformer")]
    + [f"{SURROGATE}.ValueTransformers.ValueScalarizator",
       f"{OPTIMIZER}.ValueTransformers.ValueScalarizator",
       f"{OPTIMIZER}.ValueTransformers.AcquisitionFunction"]
)
EXTERNAL_VALIDATOR = "ConfigurationSelection.Predictor.Model.Validator.ExternalValidator"
ENERGY_VALIDATOR = f"{EXTERNAL_VALIDATOR}.EnergyValidator"
ENUM_ATTRIBUTES = {"TimeUnit", "kernel", "GammaType", "CType", "activation", "solver", "BandwidthType", "ThresholdType"}


def _options(dimensions):
    return {option for dimension in dimensions for option in dimension}


# the parser reads every feature, the blacklist is applied afterwards (D2)

def test_the_parser_reads_the_features_that_phase_2_does_not_run(parser):
    options = _options(parser.parse_features())

    assert "PlotSelection.Plot.Heatmap" in options
    assert "DistributionMode.BatchedDistribution" in options
    assert "RepetitionManager.Instance.QuantityBased" in options
    assert ENERGY_VALIDATOR in options


# D9: the children of an `or` group that are groups themselves

@pytest.mark.parametrize("group", ON_OFF_GROUPS)
def test_a_group_inside_an_or_group_is_an_on_off_dimension(parser, group):
    assert [group, f"{group}.None"] in parser.parse_features()


@pytest.mark.parametrize("group", [f"{owner}.{name}" for owner in (SURROGATE, OPTIMIZER)
                                   for name in ("ConfigurationTransformers", "ValueTransformers")])
def test_an_or_group_adds_no_dimension_of_its_own_only_its_children_do(parser, group):
    assert group not in _options(parser.parse_features())


def test_the_choices_inside_those_groups_stay_as_before(parser):
    dimensions = parser.parse_features()

    assert [f"{SURROGATE}.ConfigurationTransformers.NominalTransformer.BinaryEncoder",
            f"{SURROGATE}.ConfigurationTransformers.NominalTransformer.SklearnBinaryEncoder"] in dimensions
    assert [f"{SURROGATE}.ValueTransformers.ValueScalarizator.WeightedSum",
            f"{SURROGATE}.ValueTransformers.ValueScalarizator.NormalizedWeightedSum"] in dimensions


def test_the_children_of_an_or_group_that_are_plain_features_stay_on_off_dimensions(parser):
    nsga2 = f"{OPTIMIZER}.Instance.MOEA.Algorithms.NSGA2"

    assert [nsga2, f"{nsga2}.None"] in parser.parse_features()


# D10: every enum attribute is a dimension

def test_every_enum_attribute_is_one_dimension_with_all_its_values(parser):
    dimensions = parser.parse_enum_dimensions()

    attributes = [dimension[0].split("=")[0] for dimension in dimensions]
    assert sorted(attributes) == sorted(f"enum.{name}" for name in ENUM_ATTRIBUTES)
    kernel = next(dimension for dimension in dimensions if dimension[0].startswith("enum.kernel="))
    assert kernel == [f"enum.kernel={value}" for value in ("linear", "poly", "rbf", "sigmoid", "precomputed")]


def test_an_attribute_declared_several_times_is_one_dimension(parser):
    # TimeUnit is declared in the task block and in three stop conditions
    time_units = [dimension for dimension in parser.parse_enum_dimensions() if dimension[0].startswith("enum.TimeUnit=")]

    assert time_units == [[f"enum.TimeUnit={value}" for value in ("seconds", "minutes", "hours", "days")]]


def test_an_attribute_declared_with_different_values_is_an_error(tmp_path):
    declaration = '[TimeUnit in {"seconds", "minutes", "hours", "days"}]'
    text = BASE.read_text()
    second = text.index(declaration, text.index(declaration) + 1)
    changed = tmp_path / "changed.wfl"
    changed.write_text(text[:second] + '[TimeUnit in {"seconds", "minutes"}]' + text[second + len(declaration):])

    with pytest.raises(ValueError, match="TimeUnit"):
        WflParserTextX(str(GRAMMAR), str(changed)).parse_enum_dimensions()


def test_a_configuration_returns_the_value_it_selected_for_an_enum_attribute():
    configuration = PairwiseConfig(index=0, context_variant="2-float-so",
                                   selections=["StopCondition.Instance.AdaptiveSC", "enum.kernel=linear", "enum.GammaType=auto"])

    assert configuration.get_enum("kernel") == "linear"
    assert configuration.get_enum("GammaType") == "auto"


def test_a_configuration_has_no_value_for_an_attribute_it_did_not_select():
    configuration = PairwiseConfig(index=0, context_variant="2-float-so", selections=["enum.GammaType=auto"])

    assert configuration.get_enum("kernel") is None
    assert configuration.get_enum("Gamma") is None  # whole attribute names only


# D2: the blacklist

def test_a_dimension_whose_options_all_lie_under_an_entry_is_dropped():
    dimensions = [["PlotSelection.Plot.Heatmap", "PlotSelection.Plot.Heatmap.None"],
                  ["StopCondition.Instance.AdaptiveSC", "StopCondition.Instance.AdaptiveSC.None"]]

    assert apply_blacklist(dimensions) == [dimensions[1]]


def test_a_blacklisted_option_leaves_the_rest_of_its_dimension():
    quality, mock = f"{EXTERNAL_VALIDATOR}.QualityValidator", f"{EXTERNAL_VALIDATOR}.MockValidator"
    assert ENERGY_VALIDATOR in BLACKLIST

    assert apply_blacklist([[quality, ENERGY_VALIDATOR, mock]]) == [[quality, mock]]


def test_a_dimension_left_with_one_option_is_dropped():
    assert apply_blacklist([[f"{EXTERNAL_VALIDATOR}.MockValidator", ENERGY_VALIDATOR]]) == []


def test_an_entry_matches_whole_path_segments_only():
    dimensions = [["PlotSelectionExtra", "PlotSelectionExtra.None"]]

    assert apply_blacklist(dimensions) == dimensions


def test_every_entry_has_a_reason_and_matches_something_the_parser_finds(parser):
    found = _options(parser.parse_features()) | _options(parser.parse_enum_dimensions())

    for entry, reason in BLACKLIST.items():
        assert reason.strip(), f"{entry} has no reason"
        assert any(option == entry or option.startswith(entry + ".") for option in found), f"{entry} matches no feature (stale?)"


def test_the_feature_dimensions_leave_out_what_phase_2_does_not_run(parser):
    options = _options(feature_dimensions(parser))

    assert not [option for option in options if option.split(".")[0] in ("PlotSelection", "DistributionMode", "RepetitionManager")]
    assert not [option for option in options if option.endswith("EnergyValidator")]
    assert not {"enum.kernel=precomputed", "enum.GammaType=float", "enum.CType=float"} & options
    assert {"enum.kernel=rbf", "enum.kernel=linear"} <= options
    assert [f"{EXTERNAL_VALIDATOR}.QualityValidator", f"{EXTERNAL_VALIDATOR}.MockValidator"] in feature_dimensions(parser)


def test_the_feature_dimensions_hold_the_on_off_groups_and_the_enums(parser):
    dimensions = feature_dimensions(parser)

    for group in ON_OFF_GROUPS:
        assert [group, f"{group}.None"] in dimensions
    # CType keeps one value ("std") after the blacklist, so it is no dimension and the validator uses its preference
    for attribute in ENUM_ATTRIBUTES - {"CType"}:
        assert any(dimension[0].startswith(f"enum.{attribute}=") for dimension in dimensions)


def test_the_metrics_count_the_dimensions_the_generator_samples(parser):
    assert get_parser_features(str(GRAMMAR), str(BASE)) == feature_dimensions(parser)


# the pairwise set samples exactly the filtered dimensions

def test_every_configuration_selects_one_option_of_each_dimension_in_order(parser, configurations):
    dimensions = feature_dimensions(parser)

    for configuration in configurations:
        assert len(configuration.selections) == len(dimensions)
        for selection, dimension in zip(configuration.selections, dimensions):
            assert selection in dimension


def test_the_pairwise_set_covers_every_context(configurations):
    assert {configuration.context_variant for configuration in configurations} == set(CONTEXT_VARIANTS)


# an enum attribute is owned by the feature that declares it (a place); the generator's dimension has no place

def test_an_enum_attribute_is_declared_in_as_many_places_as_the_model_has(parser):
    places = Counter(attribute for _, attribute in parser.parse_enum_places())

    assert places == Counter({"TimeUnit": 4, "kernel": 1, "GammaType": 1, "CType": 1, "activation": 1, "solver": 1,
                              "BandwidthType": 1, "ThresholdType": 1})


def test_an_enum_attribute_is_owned_by_the_feature_that_declares_it(parser):
    places = {(attribute, place) for place, attribute in parser.parse_enum_places()}

    assert {("TimeUnit", place) for place in (
        "Context.TaskConfiguration",
        "StopCondition.Instance.TimeBasedSC.Parameters",
        "StopCondition.StopConditionTriggerLogic.InspectionParameters",
        "TransferLearning.ModelRecommendation.DynamicModelsRecommendation",
    )} <= places
    assert ("kernel", f"{SURROGATE}.Instance.SupportVectorRegression.Parameters") in places
    assert ("GammaType", f"{SURROGATE}.Instance.SupportVectorRegression") in places
