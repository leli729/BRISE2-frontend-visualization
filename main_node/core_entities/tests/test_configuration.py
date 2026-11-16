from core_entities.configuration import Configuration


class TestPredictedResult:

    def test_a_new_configuration_holds_no_predicted_result(self):
        configuration = Configuration({"x": 1.0}, Configuration.Type.FROM_SELECTOR, "experiment_id")

        assert configuration.predicted_result == {}

    def test_the_predicted_result_survives_the_json_round_trip(self):
        configuration = Configuration({"x": 1.0}, Configuration.Type.PREDICTED, "experiment_id")
        configuration.predicted_result = {"Y1": {"Minimization": True, "Value": 0.5}}

        restored = Configuration.from_json(configuration.to_json())

        assert restored.predicted_result == {"Y1": {"Minimization": True, "Value": 0.5}}
