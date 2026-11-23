import pytest

from generator_paths import BASE, GRAMMAR, MODELS
from selenium_validator import WaffleSeleniumValidator


# The feature model puts no bound on MaxTimeToRunTask, and a limit of 0 would mean "terminate immediately" as soon as
# the limit is enforced again. The walk enters a positive limit instead, whatever the unit of the row.

@pytest.fixture(scope="module")
def validator(tmp_path_factory):
    return WaffleSeleniumValidator(str(GRAMMAR), str(BASE), str(MODELS), output_dir=tmp_path_factory.mktemp("out"))


def test_every_row_enters_a_positive_time_limit_for_a_task(validator, configurations):
    limits = {cfg.index: validator._get_fill_value("MaxTimeToRunTask", cfg, dict(validator._min_max)) for cfg in configurations}

    assert all(limit.isdigit() and int(limit) > 0 for limit in limits.values()), limits
