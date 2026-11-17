import difflib
import re
from pathlib import Path

import pytest

MAIN_NODE = Path(__file__).resolve().parents[2]
BASE = MAIN_NODE / "Resources" / "tests" / "waffle_models" / "base.wfl"
COPY_FOLDERS = [MAIN_NODE / "Resources", MAIN_NODE / "test_gen_approach" / "test_generation"]

CONTEXT_START = re.compile(r"^Context \{", re.MULTILINE)
SHARED_OBJECTIVES_RULES_START = re.compile(r"^ *\[if size childs\.self > 1 and fcard\.TransferLearning", re.MULTILINE)
SEARCH_SPACE_START = re.compile(r"^ *SearchSpace \{", re.MULTILINE)
SEARCH_SPACE_STRUCTURE_START = re.compile(r"^ *xor Structure \{", re.MULTILINE)
FEATURE_MODEL_START = re.compile(r"^ConfigurationSelection \{", re.MULTILINE)


def _copies():
    return sorted(path for folder in COPY_FOLDERS for path in folder.rglob("*.wfl") if path != BASE)


def _find(pattern, text, after=0):
    match = pattern.search(text, after)
    if match is None:
        raise LookupError(f"anchor not found: {pattern.pattern}")
    return match.start()


def _sections(text):
    """The parts of a model that must equal base.wfl: the abstract definitions, the rules on the objectives, the
    search space's structure and rules, and the feature model.

    A copy may differ from base.wfl only in the task block, the objectives and the search-space parameters, which
    sit between these parts. The anchors are tokens of the model: where the context starts, the first rule on the
    objectives, where the search space and its structure start, and where the feature model starts.
    """
    context_start = _find(CONTEXT_START, text)
    objectives_rules_start = _find(SHARED_OBJECTIVES_RULES_START, text, context_start)
    search_space_start = _find(SEARCH_SPACE_START, text, objectives_rules_start)
    structure_start = _find(SEARCH_SPACE_STRUCTURE_START, text, search_space_start)
    feature_model_start = _find(FEATURE_MODEL_START, text, structure_start)
    return {
        "abstract definitions": text[:context_start],
        "rules on the objectives": text[objectives_rules_start:search_space_start].rstrip(),  # not the blank lines after them
        "search space structure and rules": text[structure_start:feature_model_start],
        "feature model": text[feature_model_start:],
    }


def drift(copy_text, base_text):
    """The sections in which a copy differs from base.wfl, each with the lines that differ; empty if it is in sync."""
    try:
        copy_sections = _sections(copy_text)
    except LookupError as error:
        return [str(error)]
    report = []
    for name, expected in _sections(base_text).items():
        if copy_sections[name] != expected:
            lines = difflib.unified_diff(expected.splitlines(), copy_sections[name].splitlines(),
                                         "base.wfl", "copy", lineterm="", n=0)
            report.append(f"{name}:\n" + "\n".join(list(lines)[:20]))
    return report


@pytest.mark.parametrize("copy", _copies(), ids=lambda path: str(path.relative_to(MAIN_NODE)))
def test_copy_of_the_feature_model_matches_base_outside_its_own_context(copy):
    report = drift(copy.read_text(), BASE.read_text())

    assert not report, f"{copy.relative_to(MAIN_NODE)} differs from base.wfl in:\n" + "\n".join(report)


def test_every_folder_contributes_copies_and_the_generators_base_is_one_of_them():
    copies = _copies()

    assert any(MAIN_NODE / "Resources" in path.parents for path in copies)
    assert any(MAIN_NODE / "test_gen_approach" / "test_generation" / "WaffleTestingModels" in path.parents for path in copies)
    assert MAIN_NODE / "test_gen_approach" / "test_generation" / "base.wfl" in copies


@pytest.fixture
def base_text():
    return BASE.read_text()


def test_a_changed_rule_of_the_feature_model_is_reported(base_text):
    rule = "[min Weights >= 0]"
    assert rule in base_text

    report = drift(base_text.replace(rule, "[min Weights >= 1]", 1), base_text)

    assert [entry.split(":")[0] for entry in report] == ["feature model"]
    assert "[min Weights >= 1]" in report[0]


def test_a_changed_abstract_definition_is_reported(base_text):
    rule = "[MaxExpectedValue > MinExpectedValue]"
    assert rule in base_text

    report = drift(base_text.replace(rule, "[MaxExpectedValue >= MinExpectedValue]", 1), base_text)

    assert [entry.split(":")[0] for entry in report] == ["abstract definitions"]


def test_a_missing_rule_on_the_objectives_is_reported(base_text):
    rule = "[if size childs.self.Objectives < 2 then fcard.PlotSelection.Plot.ParetoFront = 0]"
    assert rule in base_text

    report = drift(base_text.replace(rule, "", 1), base_text)

    assert [entry.split(":")[0] for entry in report] == ["rules on the objectives"]


def test_a_rule_on_the_objectives_moved_to_another_block_is_reported(base_text):
    rule = "      [if size childs.self > 1 and fcard.TransferLearning > 0 then self excludes TransferLearning.ModelRecommendation.DynamicModelsRecommendation]\n"
    block_end = "    }\n    [if size childs.self.Objectives > 1"
    assert rule in base_text and block_end in base_text

    moved = base_text.replace(rule, "", 1).replace(block_end, "    }\n" + rule + "    [if size childs.self.Objectives > 1", 1)

    assert [entry.split(":")[0] for entry in drift(moved, base_text)] == ["rules on the objectives"]


def test_a_changed_search_space_rule_is_reported(base_text):
    rule = "[fcard.ConfigurationSelection.Predictor.Model = size unique Level at self]"
    assert rule in base_text

    report = drift(base_text.replace(rule, "[fcard.ConfigurationSelection.Predictor.Model = 1]", 1), base_text)

    assert [entry.split(":")[0] for entry in report] == ["search space structure and rules"]


def test_a_copy_without_an_anchor_is_reported_by_the_anchor(base_text):
    report = drift(base_text.replace("xor Structure {", "xor Layout {", 1), base_text)

    assert len(report) == 1 and report[0].startswith("anchor not found") and "xor Structure" in report[0]


def test_other_objectives_task_block_and_parameters_are_not_reported(base_text):
    two_objectives = base_text.replace("      /*\n", "", 1).replace("      */\n", "", 1)
    maximized = two_objectives.replace('[Name = "Y2"]\n        [DataType = "float"]\n        [Minimization = true]',
                                       '[Name = "Y2"]\n        [DataType = "float"]\n        [Minimization = false]', 1)
    own_task = maximized.replace('[TaskName = "test"]', '[TaskName = "my_task"]', 1)
    own_parameters = own_task.replace("X1 : FloatHyperparameter", "X1 : NominalHyperparameter {\n      A : Category\n      B : Category\n      [Default = \"Context.SearchSpace.X1.A\"]\n    }", 1)
    assert two_objectives != base_text and maximized != two_objectives and own_parameters != own_task

    assert drift(own_parameters, base_text) == []
