import json
from collections import Counter

from dimension_blacklist import feature_dimensions
from pairwise_generator import CONTEXT_VARIANTS, PairwiseConfig
from quant_metrics import (configuration_diversity, configuration_space_reduction, covered_by_output, covered_by_pairwise,
                           output_dimensions, tuple_occurrence)


# An option of the feature model is covered when a product holds it: a feature at its place in the product (a
# hierarchical product numbers its models, and the models of several objectives their surrogates and optimizers), an
# enum option as the value of its attribute in the place of the feature that declares it (an attribute declared in
# several places, TimeUnit, has an option in each). The tuple occurrence and the diversity count the options of a
# product the same way.

TASK = "Context.TaskConfiguration"
STOP = "StopCondition.Instance.TimeBasedSC.Parameters"
INSPECTION = "StopCondition.StopConditionTriggerLogic.InspectionParameters"
RECOMMENDATION = "TransferLearning.ModelRecommendation.DynamicModelsRecommendation"
SVR = "ConfigurationSelection.Predictor.Model.Surrogate.Instance.SupportVectorRegression"


def _options(parser):
    return {option for dimension in output_dimensions(parser) for option in dimension}


def _feature_option(parser, suffix):
    matching = [option for option in _options(parser) if option.endswith(suffix) and "=" not in option]
    assert len(matching) == 1, matching
    return matching[0]


def _enum_option(parser, place, attribute, value):
    option = f"{place}.{attribute}={value}"
    assert option in _options(parser), option
    return option


def _product_holding(*options):
    # the product's keys along the path of each option, an enum option with its value at the attribute
    product = {}
    for option in options:
        path, _, value = option.partition("=")
        level = product
        keys = path.split(".")
        for key in keys[:-1]:
            level = level.setdefault(key, {})
        if value:
            level[keys[-1]] = value
        else:
            level.setdefault(keys[-1], {})
    return product


def _at(product, place):
    for key in place.split("."):
        product = product[key]
    return product


def _write(folder, products):
    for number, product in enumerate(products):
        (folder / f"config_{number}.json").write_text(json.dumps(product))


def test_an_enum_option_is_covered_by_a_product_holding_its_value(tmp_path, parser):
    rbf, linear = (_enum_option(parser, f"{SVR}.Parameters", "kernel", value) for value in ("rbf", "linear"))
    _write(tmp_path, [_product_holding(rbf)])

    assert covered_by_output({rbf, linear}, tmp_path) == {rbf}


def test_an_enum_option_is_not_covered_by_its_value_in_another_attribute(tmp_path, parser):
    scale, auto = (_enum_option(parser, SVR, "GammaType", value) for value in ("scale", "auto"))
    product = _product_holding(scale)
    _at(product, SVR)["gamma"] = "auto"
    _write(tmp_path, [product])

    assert covered_by_output({scale, auto}, tmp_path) == {scale}


def test_an_enum_option_is_covered_only_in_the_place_that_holds_its_value(tmp_path, parser):
    days = {place: _enum_option(parser, place, "TimeUnit", "days") for place in (TASK, STOP, INSPECTION, RECOMMENDATION)}
    _write(tmp_path, [_product_holding(days[TASK], days[STOP])])

    assert covered_by_output(set(days.values()), tmp_path) == {days[TASK], days[STOP]}


def test_the_dimensions_of_the_products_are_the_generators_with_each_enum_dimension_split_by_place(parser):
    generator = feature_dimensions(parser)
    products = output_dimensions(parser)
    places = Counter(attribute for _, attribute in parser.parse_enum_places())
    generator_enums = {dimension[0][len("enum."):].split("=")[0]: [option.split("=")[1] for option in dimension]
                       for dimension in generator if dimension[0].startswith("enum.")}
    product_enums = {}
    for dimension in products:
        if "=" in dimension[0]:
            attribute = dimension[0].split("=")[0].rsplit(".", 1)[1]
            product_enums.setdefault(attribute, []).append([option.split("=", 1)[1] for option in dimension])

    assert sorted(d for d in products if "=" not in d[0]) == sorted(d for d in generator if not d[0].startswith("enum."))
    assert product_enums == {attribute: [values] * places[attribute] for attribute, values in generator_enums.items()}


def test_a_feature_option_is_covered_by_a_product_holding_it(tmp_path, parser):
    maco, nsga2 = _feature_option(parser, ".Algorithms.MACO"), _feature_option(parser, ".Algorithms.NSGA2")
    _write(tmp_path, [_product_holding(maco)])

    assert covered_by_output({maco, nsga2}, tmp_path) == {maco}


def test_an_option_is_not_covered_by_the_option_of_another_place_with_the_same_name(tmp_path, parser):
    surrogate = _feature_option(parser, "Surrogate.ConfigurationTransformers.FloatTransformer")
    optimizer = _feature_option(parser, "Optimizer.ConfigurationTransformers.FloatTransformer")
    _write(tmp_path, [_product_holding(optimizer)])

    assert covered_by_output({surrogate, optimizer}, tmp_path) == {optimizer}


def test_an_option_is_not_covered_by_an_option_whose_name_contains_its_own(tmp_path, parser):
    moead, moead_gen = _feature_option(parser, ".Algorithms.MOEAD"), _feature_option(parser, ".Algorithms.MOEAD_GEN")
    _write(tmp_path, [_product_holding(moead_gen)])

    assert covered_by_output({moead, moead_gen}, tmp_path) == {moead_gen}


def test_options_are_covered_by_numbered_models_and_surrogates(tmp_path, parser):
    svr = _feature_option(parser, "Surrogate.Instance.SupportVectorRegression")
    rbf = _enum_option(parser, f"{SVR}.Parameters", "kernel", "rbf")
    numbered = [option.replace(".Model.", ".Model_0.").replace(".Surrogate.", ".Surrogate_1.") for option in (svr, rbf)]
    _write(tmp_path, [_product_holding(*numbered)])

    assert covered_by_output({svr, rbf}, tmp_path) == {svr, rbf}


def test_a_pairwise_configuration_covers_only_the_options_it_selects(parser):
    surrogate = _feature_option(parser, "Surrogate.ConfigurationTransformers.FloatTransformer")
    optimizer = _feature_option(parser, "Optimizer.ConfigurationTransformers.FloatTransformer")
    configuration = PairwiseConfig(index=0, context_variant="2-float-so", selections=[optimizer])

    assert covered_by_pairwise({surrogate, optimizer}, [configuration]) == {optimizer}


def test_a_pair_of_options_is_covered_by_a_product_holding_both_of_them(tmp_path, parser):
    svr = _feature_option(parser, "Surrogate.Instance.SupportVectorRegression")
    linear = _feature_option(parser, "Surrogate.Instance.LinearRegression")
    rbf, poly = (_enum_option(parser, f"{SVR}.Parameters", "kernel", value) for value in ("rbf", "poly"))
    _write(tmp_path, [_product_holding(svr, rbf)])

    result = tuple_occurrence(tmp_path, [[rbf, poly], [svr, linear]])

    assert (result["total_pairs"], result["covered_pairs"]) == (4, 1)


def test_a_pair_is_not_covered_by_a_product_holding_only_the_same_named_option_of_another_place(tmp_path, parser):
    surrogate = _feature_option(parser, "Surrogate.ConfigurationTransformers.FloatTransformer")
    optimizer = _feature_option(parser, "Optimizer.ConfigurationTransformers.FloatTransformer")
    svr = _feature_option(parser, "Surrogate.Instance.SupportVectorRegression")
    _write(tmp_path, [_product_holding(optimizer, svr)])

    result = tuple_occurrence(tmp_path, [[surrogate], [svr]])

    assert result["covered_pairs"] == 0


def test_products_that_differ_only_in_what_is_no_option_are_not_diverse(tmp_path, parser):
    svr = _feature_option(parser, "Surrogate.Instance.SupportVectorRegression")
    first, second = _product_holding(svr), _product_holding(svr)
    first["Parameters"], second["Parameters"] = {"C": 1.0}, {"C": 10.0, "Type": "sklearn_model_wrapper"}
    _write(tmp_path, [first, second])

    assert configuration_diversity(tmp_path, output_dimensions(parser))["avg"] == 0.0


def test_products_holding_other_options_are_diverse(tmp_path, parser):
    svr = _feature_option(parser, "Surrogate.Instance.SupportVectorRegression")
    linear = _feature_option(parser, "Surrogate.Instance.LinearRegression")
    _write(tmp_path, [_product_holding(svr), _product_holding(linear)])

    assert configuration_diversity(tmp_path, output_dimensions(parser))["avg"] > 0.0


def test_the_exhaustive_space_has_a_copy_for_every_context_the_generator_samples():
    reduction = configuration_space_reduction([["a", "b"], ["c", "d", "e"]], pairwise_count=1)

    assert reduction["exhaustive_theoretical"] == 2 * 3 * len(CONTEXT_VARIANTS)
