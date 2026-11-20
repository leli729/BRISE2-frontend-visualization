"""
Blacklist of features and values that get no pairwise dimension.

The parser reads every feature of the model. The features below are not run by Phase 2 (or can't run), so a pair spent
on them tests nothing. An entry leaves the blacklist when Phase 2's reach grows.

An entry matches an option equal to it or below it ("entry."). A dimension that loses options keeps the rest, and one
left with fewer than two options is dropped.

Usage:
    from dimension_blacklist import feature_dimensions
    dimensions = feature_dimensions(WflParserTextX("grammar.tx", "base.wfl"))
"""

from typing import Dict, List

from wfl_parser_textx import WflParserTextX


BLACKLIST: Dict[str, str] = {
    "PlotSelection": "frontend only; Phase 2 draws no plot",
    "DistributionMode": "read only by the worker client; Phase 2 has no worker",
    "RepetitionManager": "the repeater is not run by Phase 2, which writes results without it",
    "ConfigurationSelection.Predictor.Model.Validator.ExternalValidator.EnergyValidator":
        "needs an energy objective, which no test context has",
    "enum.GammaType=float":
        "[if GammaType == \"float\" then self.Parameters.gamma == self.GammaFloat] compares a string with a float: "
        "Waffle rejects every product (found 2026-11-18)",
    "enum.CType=float":
        "[if CType == \"float\" then self.Parameters.c == self.CFloat] has the same form as GammaType's: Waffle rejects "
        "every product (Expression (10.0 == 10.0), found 2026-11-18)",
    "enum.kernel=precomputed":
        "SVR expects a square kernel matrix and BRISE builds none (fit raises ValueError)",
}


def _is_blacklisted(option: str) -> bool:
    return any(option == entry or option.startswith(entry + ".") for entry in BLACKLIST)


def apply_blacklist(dimensions: List[List[str]]) -> List[List[str]]:
    kept = ([option for option in dimension if not _is_blacklisted(option)] for dimension in dimensions)
    return [dimension for dimension in kept if len(dimension) > 1]


def feature_dimensions(parser: WflParserTextX) -> List[List[str]]:
    """The dimensions the pairwise generator samples: the parser's features and enum attributes, minus the blacklist."""
    return apply_blacklist(parser.parse_features() + parser.parse_enum_dimensions())
