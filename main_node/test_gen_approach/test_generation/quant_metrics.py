"""
Metric abbreviations
  FC  = Feature Coverage
  TSS = Test Suite Size
  CSR = Configuration Space Reduction
  ICR = Invalid Configuration Ratio
  TO  = Tuple Occurrence / pairwise coverage
  RC  = Redundant Configurations
  CD  = Configuration Diversity (Jaccard)

"""

import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

from dimension_blacklist import feature_dimensions
from wfl_parser_textx import WflParserTextX
from pairwise_generator import CONTEXT_VARIANTS, generate_pairwise


GRAMMAR_PATH = "grammar.tx"
WFL_PATH = "base.wfl"
OUTPUT_DIR = Path("output_configs")


# Cross-tree constraint pairs that cannot coexist in any valid WFL configuration.

INFEASIBLE_PAIRS: set = {
    frozenset({"NSGA2", "MOEAD"}),
    frozenset({"NSGA2", "MOEAD_GEN"}),
    frozenset({"LinearRegression", "Pure"}),
    frozenset({"SupportVectorRegression", "Pure"}),
    frozenset({"GradientBoostingRegressor", "Pure"}),
    frozenset({"BayesianRidgeRegression", "Pure"}),
    frozenset({"MultiArmedBandit", "Pure"}),
    frozenset({"TreeParzenEstimator", "Pure"}),
    frozenset({"TreeParzenEstimator", "DynamicCompositional"}),
    frozenset({"TreeParzenEstimator", "Portfolio"}),
    frozenset({"MultiLayerPerceptronRegressor", "Pure"}),
    frozenset({"BestMultiPointProposal", "Portfolio"}),
}


def _key_paths(obj, path=()) -> set:
    # Every key path of a nested JSON object, as dotted strings. The number a hierarchical product adds to its models
    # (Model_0), and the models of several objectives to their surrogates and optimizers (Surrogate_1), is removed.
    paths = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = path + (re.sub(r"_\d+$", "", key),)
            paths.add(".".join(here))
            paths |= _key_paths(value, here)
    elif isinstance(obj, list):
        for value in obj:
            paths |= _key_paths(value, path)
    return paths


def _string_values(obj, path=()) -> set:
    # Every (key path, value) pair of a nested JSON object whose value is a string, the paths as in _key_paths
    pairs = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = path + (re.sub(r"_\d+$", "", key),)
            if isinstance(value, str):
                pairs.add((".".join(here), value))
            pairs |= _string_values(value, here)
    elif isinstance(obj, list):
        for value in obj:
            pairs |= _string_values(value, path)
    return pairs


def options_of_product(product: dict, options: set) -> set:
    # The options of the feature model a product holds: a feature at its path in the product, an enum option
    # ("<path of the attribute>=<value>") as the value of the attribute at its path
    paths = _key_paths(product)
    values = _string_values(product)
    held = set()
    for option in options:
        if "=" in option:
            path, value = option.split("=", 1)
            if (path, value) in values:
                held.add(option)
        elif option in paths:
            held.add(option)
    return held


def output_dimensions(parser: WflParserTextX) -> list:
    # The dimensions of the options a product holds: the generator's, except that an enum dimension (one value for
    # every place of its attribute) is split into a dimension per place, whose options are "<place>.<attribute>=<value>"
    places = {}
    for place, attribute in parser.parse_enum_places():
        places.setdefault(attribute, []).append(place)
    dimensions = []
    for dimension in feature_dimensions(parser):
        if not dimension[0].startswith("enum."):
            dimensions.append(dimension)
            continue
        attribute = dimension[0][len("enum."):].split("=")[0]
        values = [option.split("=", 1)[1] for option in dimension]
        for place in places[attribute]:
            dimensions.append([f"{place}.{attribute}={value}" for value in values])
    return dimensions


def _load_products(output_dir: Path) -> list:
    return [json.loads(f.read_text()) for f in sorted(output_dir.glob("*.json"))]


def get_parser_features(grammar_path: str, wfl_path: str) -> list:
    # Return the dimensions the generator samples (one list per dimension): the parser's, minus the blacklist
    parser = WflParserTextX(grammar_path, wfl_path)
    return feature_dimensions(parser)


def covered_by_pairwise(all_values: set, configs) -> set:
    # Return feature values that at least one pairwise config selects
    selected = set()
    for cfg in configs:
        selected |= set(cfg.selections)
    return all_values & selected


def covered_by_output(all_values: set, output_dir: Path) -> set:
    # Return feature values that at least one valid output JSON config holds
    if not output_dir.exists():
        return set()
    covered = set()
    for product in _load_products(output_dir):
        covered |= options_of_product(product, all_values)
    return covered


def configuration_space_reduction(
    feature_dims: list,
    pairwise_count: int,
    context_count: int = len(CONTEXT_VARIANTS),
) -> dict:
    """
    Compute Configuration Space Reduction (CSR).

    Theoretical exhaustive space = product of all WFL dimension sizes and context variants.
    This is the number of configurations that would need to be tested without any
    combinatorial reduction strategy

    """
    exhaustive = 1
    for dim in feature_dims:
        exhaustive *= len(dim)
    exhaustive *= context_count

    csr_ratio = pairwise_count / exhaustive
    return {
        "exhaustive_theoretical": exhaustive,
        "pairwise_count": pairwise_count,
        "csr_ratio": csr_ratio,
        "reduction_pct": (1 - csr_ratio) * 100,
    }


def configuration_diversity(output_dir: Path, feature_dims: list) -> dict:
    """
    Compute Jaccard-based diversity across all pairs of valid output configs, over the options of the feature model
    each one holds

    Returns avg, min, max diversity and number of pairs evaluated
    """
    if not output_dir.exists():
        return {"avg": 0.0, "min": 0.0, "max": 0.0, "pairs": 0}

    products = _load_products(output_dir)
    if len(products) < 2:
        return {"avg": 0.0, "min": 0.0, "max": 0.0, "pairs": len(products)}

    options = {v for dim in feature_dims for v in dim if not v.endswith(".None")}
    feature_sets = [options_of_product(product, options) for product in products]
    distances = []
    for a, b in combinations(feature_sets, 2):
        union = a | b
        d = 1.0 - len(a & b) / len(union) if union else 0.0
        distances.append(d)

    return {
        "avg": sum(distances) / len(distances),
        "min": min(distances),
        "max": max(distances),
        "pairs": len(distances),
    }


def tuple_occurrence(output_dir: Path, feature_dims: list) -> dict:
    """
    Count how often each cross-dimensional feature pair (2-tuple) appears across
    the valid output configs

    A pair is counted as 'covered' if it appears in at least one valid output config.
    Occurrence per pair is measured by checking if a config holds both options

    Returns occurrence statistics and both coverage percentages.
    """
    if not output_dir.exists():
        return {}

    products = _load_products(output_dir)
    if not products:
        return {}

    # Non-.None values per dimension
    non_none_dims = [[v for v in dim if not v.endswith(".None")] for dim in feature_dims]
    options = {v for dim in non_none_dims for v in dim}
    config_option_sets = [options_of_product(product, options) for product in products]

    # Cross-dimensional pairs, infeasible pairs excluded from the start
    def _infeasible(v_i, v_j) -> bool:
        return frozenset({v_i.split(".")[-1], v_j.split(".")[-1]}) in INFEASIBLE_PAIRS

    all_cross_pairs = [
        (v_i, v_j)
        for i in range(len(non_none_dims))
        for j in range(i + 1, len(non_none_dims))
        for v_i in non_none_dims[i]
        for v_j in non_none_dims[j]
    ]
    infeasible_count = sum(1 for v_i, v_j in all_cross_pairs if _infeasible(v_i, v_j))
    pairs = [p for p in all_cross_pairs if not _infeasible(*p)]

    # Count occurrences: how many valid configs contain both features of a pair
    occurrence = {}
    for v_i, v_j in pairs:
        occurrence[(v_i, v_j)] = sum(1 for held in config_option_sets if v_i in held and v_j in held)

    covered = sum(1 for p in pairs if occurrence[p] > 0)
    counts = [occurrence[p] for p in pairs]

    # Redundant Configurations (RC): excess tuple occurrences beyond the first
    rc_total = sum(max(0, c - 1) for c in counts)
    rr = rc_total / len(pairs) if pairs else 0.0
    # Efficiency score: fraction of total tuple work that was non-redundant
    total_tuple_work = sum(counts)
    efficiency = covered / total_tuple_work if total_tuple_work else 1.0

    return {
        "total_pairs": len(pairs),
        "infeasible_pairs": infeasible_count,
        "covered_pairs": covered,
        "coverage_pct": 100 * covered / len(pairs) if pairs else 0,
        "min_occurrence": min(counts) if counts else 0,
        "max_occurrence": max(counts) if counts else 0,
        "avg_occurrence": sum(counts) / len(counts) if counts else 0,
        # RC metrics
        "rc_total": rc_total,
        "redundancy_ratio": rr,
        "efficiency_score": efficiency,
    }


def compute_metrics(
    grammar_path: str = GRAMMAR_PATH,
    wfl_path: str = WFL_PATH,
    output_dir: Path = OUTPUT_DIR,
) -> dict:
    parser = WflParserTextX(grammar_path, wfl_path)
    feature_dims = feature_dimensions(parser)
    output_dims = output_dimensions(parser)
    all_values = [v for dim in feature_dims for v in dim]
    all_values_set = set(all_values)
    non_none_set = {v for v in all_values_set if not v.endswith(".None")}
    total = len(all_values_set)
    total_non_none = len(non_none_set)

    configs = generate_pairwise(grammar_path, wfl_path)

    pairwise_covered = covered_by_pairwise(all_values_set, configs)
    pairwise_covered_non_none = pairwise_covered & non_none_set

    # the options a product holds; a .None option is a feature a product lacks, no product holds it
    output_options = {v for dim in output_dims for v in dim if not v.endswith(".None")}
    output_covered_non_none = covered_by_output(output_options, output_dir)

    valid_configs = list(output_dir.glob("*.json")) if output_dir.exists() else []

    csr = configuration_space_reduction(feature_dims, len(configs))
    diversity = configuration_diversity(output_dir, output_dims)
    to = tuple_occurrence(output_dir, output_dims)

    invalid_count = len(configs) - len(valid_configs)
    icr = invalid_count / len(configs) if configs else 0.0

    return {
        "feature_dimensions": len(feature_dims),
        # Feature Coverage (incl. .None) ---
        "total_feature_values": total,
        "pairwise_configs": len(configs),
        "pairwise_covered": len(pairwise_covered),
        "pairwise_coverage_pct": 100 * len(pairwise_covered) / total if total else 0,
        "valid_configs": len(valid_configs),
        # Feature Coverage (excl. .None) ---
        "total_feature_values_non_none": total_non_none,
        "pairwise_covered_non_none": len(pairwise_covered_non_none),
        "pairwise_coverage_pct_non_none": 100 * len(pairwise_covered_non_none) / total_non_none if total_non_none else 0,
        "output_total_non_none": len(output_options),
        "output_covered_non_none": len(output_covered_non_none),
        "output_coverage_pct_non_none": 100 * len(output_covered_non_none) / len(output_options) if output_options else 0,
        "uncovered_by_output_non_none": sorted(output_options - output_covered_non_none),
        # Configuration Space Reduction
        "csr": csr,
        # Invalid Configuration Ratio
        "invalid_configs": invalid_count,
        "icr": icr,
        "vcr": 1.0 - icr,
        # Configuration Diversity (Jaccard)
        "diversity": diversity,
        # Tuple Occurrence + Redundant Configurations
        "tuple_occurrence": to,
    }


def print_report(metrics: dict) -> None:
    print("Phase 1 Pipeline — Quantitative Coverage Metrics")

    print(f"\nWFL Feature Model (wfl_parser_textx.py)")
    print(f"Feature dimensions : {metrics['feature_dimensions']}")
    print(f"Total feature values (incl. .None): {metrics['total_feature_values']}")
    print(f"Total feature values (excl. .None): {metrics['total_feature_values_non_none']}")

    print(f"\nPairwise Generation (pairwise_generator.py)")
    print(f"Configurations     : {metrics['pairwise_configs']}")
    print(f"Values covered (incl. .None): {metrics['pairwise_covered']}/{metrics['total_feature_values']}"
          f" ({metrics['pairwise_coverage_pct']:.1f}%)")
    print(f"Values covered (excl. .None): {metrics['pairwise_covered_non_none']}/{metrics['total_feature_values_non_none']}"
          f" ({metrics['pairwise_coverage_pct_non_none']:.1f}%)")

    csr = metrics.get("csr", {})
    if csr:
        print(f"\nConfiguration Space Reduction (CSR)")
        print(f"Exhaustive (theoretical): {csr['exhaustive_theoretical']:,}")
        print(f"Pairwise generated      : {csr['pairwise_count']}")
        print(f"CSR ratio               : {csr['csr_ratio']:.2e}")
        print(f"Reduction               : {csr['reduction_pct']:.4f}%")

    print(f"\nValid Output Configs (output_configs/)")
    print(f"Valid configs      : {metrics['valid_configs']}"
          f" / {metrics['pairwise_configs']} generated"
          f"  (VCR {metrics['vcr']*100:.1f}%  |  ICR {metrics['icr']*100:.1f}%)")
    print(f"Options held, enum attributes by place (excl. .None): {metrics['output_covered_non_none']}/{metrics['output_total_non_none']}"
          f" ({metrics['output_coverage_pct_non_none']:.1f}%)")

    uncovered = metrics["uncovered_by_output_non_none"]
    if uncovered:
        print(f"Uncovered (excl. .None) ({len(uncovered)}):")
        for v in uncovered:
            print(f"  {v}")

    d = metrics.get("diversity", {})
    if d.get("pairs", 0) > 0:
        print(f"\nConfiguration Diversity (Jaccard, {d['pairs']} config pairs)")
        print(f"Avg diversity      : {d['avg']:.4f}")
        print(f"Min diversity      : {d['min']:.4f}")
        print(f"Max diversity      : {d['max']:.4f}")

    to = metrics.get("tuple_occurrence", {})
    if to:
        print(f"\nTuple Occurrence (2-wise, over {metrics['valid_configs']} valid configs)")
        print(f"Feasible pairs     : {to['total_pairs']} (excl. {to['infeasible_pairs']} infeasible)")
        print(f"Covered pairs      : {to['covered_pairs']}/{to['total_pairs']}"
              f" ({to['coverage_pct']:.1f}%)")
        print(f"Occurrence avg/min/max: {to['avg_occurrence']:.2f} / "
              f"{to['min_occurrence']} / {to['max_occurrence']}")
        print(f"\nRedundant Configurations (RC, over valid pairs)")
        print(f"Excess occurrences (RC): {to['rc_total']}")
        print(f"Redundancy ratio (RR)  : {to['redundancy_ratio']:.4f}"
              f"  ({to['redundancy_ratio']*100:.2f}% avg excess per valid pair)")
        print(f"Efficiency score       : {to['efficiency_score']:.4f}"
              f"  (non-redundant work / total tuple work)")

    print()


if __name__ == "__main__":
    metrics = compute_metrics()
    print_report(metrics)
