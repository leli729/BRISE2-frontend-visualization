import bson
import numpy as np

from core_entities.configuration import Configuration
from core_entities.objectives import Criterion

Y1_MINIMIZED = Criterion("Y1", minimization=True)


class TestPredictedResult:

    @staticmethod
    def _configuration():
        return Configuration({"x": 1.0}, Configuration.Type.PREDICTED, "experiment_id")

    def test_a_new_configuration_holds_no_predicted_result(self):
        configuration = Configuration({"x": 1.0}, Configuration.Type.FROM_SELECTOR, "experiment_id")

        assert configuration.predicted_result == {}

    def test_values_are_added_under_the_region_and_the_name_of_their_criterion_with_its_direction(self):
        configuration = self._configuration()

        configuration.add_predicted_result("0", Y1_MINIMIZED, 0.5)
        configuration.add_predicted_result("1", Y1_MINIMIZED, 0.6)
        configuration.add_predicted_result("1", Criterion("ratio(Y1)", minimization=False), 1.7)

        assert configuration.predicted_result == {
            "0": {"Y1": {"Minimization": True, "Value": 0.5}},
            "1": {"Y1": {"Minimization": True, "Value": 0.6},
                  "ratio(Y1)": {"Minimization": False, "Value": 1.7}}}

    def test_a_value_is_stored_as_a_float_the_database_can_encode(self):
        configuration = self._configuration()

        configuration.add_predicted_result("0", Y1_MINIMIZED, np.int64(3))  # e.g. an integer objective

        value = configuration.predicted_result["0"]["Y1"]["Value"]
        assert type(value) is float and value == 3.0
        bson.encode(configuration.get_configuration_record())  # a numpy.int64 would raise

    def test_the_predicted_result_survives_the_json_round_trip(self):
        configuration = self._configuration()
        configuration.add_predicted_result("0", Y1_MINIMIZED, 0.5)

        restored = Configuration.from_json(configuration.to_json())

        assert restored.predicted_result == {"0": {"Y1": {"Minimization": True, "Value": 0.5}}}
