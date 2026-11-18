import pytest

from generator_paths import BASE, GRAMMAR
from pairwise_generator import generate_pairwise
from wfl_parser_textx import WflParserTextX


@pytest.fixture(scope="session")
def parser():
    return WflParserTextX(str(GRAMMAR), str(BASE))


@pytest.fixture(scope="session")
def configurations():
    return generate_pairwise(str(GRAMMAR), str(BASE))
