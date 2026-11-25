import importlib.util
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

import pika
import pytest
from pika.adapters.blocking_connection import BlockingChannel

os.environ["TEST_MODE"] = 'UNIT_TEST'

from main import MainThread
from tools.front_API import API

API_SUPREME = Path(__file__).resolve().parents[1] / "api-supreme.py"
PLOT_METHODS = {
    "hyperparameter_importances": "calculate_importances",
    "pareto_front": "calculate_pareto",
    "contour": "calculate_contour",
}
# the connection is replaced, so the threads never use the address they are given
UNUSED_HOST = "unused"
UNUSED_PORT = 0
PLOT_QUEUE = "main_plot_queue"
OTHER_QUEUES = ["main_start_queue", "main_status_queue", "main_stop_queue", "main_download_dump_queue"]


class MainThreadStub:
    """MainThread that runs no experiment: it holds the setup it is given as its `experiment`."""
    State = MainThread.State

    def __init__(self, experiment_setup=None):
        self.experiment = experiment_setup

    def start(self):
        pass

    def get_state(self):
        return self.State.IDLE


def arguments_of(method_name, call):
    """The arguments of a recorded call of a BlockingChannel method by their names, however they were passed."""
    signature = inspect.signature(getattr(BlockingChannel, method_name))
    bound = signature.bind(None, *call.args, **call.kwargs)
    bound.apply_defaults()
    return bound.arguments


def new_channel():
    channel = create_autospec(BlockingChannel, instance=True)
    channel._consumer_infos = {}  # a consume loop over no consumers ends at once
    return channel


@pytest.fixture
def connections(monkeypatch):
    """Every connection opened while a test runs, each with a channel of its own, without RabbitMQ."""
    opened = []

    def open_connection(*args, **kwargs):
        connection = MagicMock()
        connection.channel.return_value = new_channel()
        opened.append(connection)
        return connection

    monkeypatch.setattr(pika, "BlockingConnection", open_connection)
    return opened


@pytest.fixture
def api_supreme(connections, monkeypatch):
    """api-supreme.py (its name has a hyphen) loaded with MainThread replaced."""
    API._instance = None
    spec = importlib.util.spec_from_file_location("api_supreme", API_SUPREME)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.MainThread = MainThreadStub
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    yield module
    API._instance = None


@pytest.fixture
def plot_service(api_supreme):
    """The PlotService of the module, which answers each plot with a result that names the method that computed it."""
    service = create_autospec(api_supreme.PlotService, instance=True)
    for method_name in PLOT_METHODS.values():
        getattr(service, method_name).return_value = {"computed by": method_name}
    api_supreme.PlotService = lambda: service
    return service


@pytest.fixture
def consumer(api_supreme, plot_service):
    return api_supreme.ConsumerThread(UNUSED_HOST, UNUSED_PORT)


@pytest.fixture
def plot_consumer(api_supreme, plot_service, consumer):
    return api_supreme.PlotConsumerThread(UNUSED_HOST, UNUSED_PORT, consumer)


def request(body, headers=None):
    """The (channel, method, properties, body) of a callback for a request of the given body."""
    properties = SimpleNamespace(reply_to="reply-queue", correlation_id="correlation-1", headers=headers)
    return new_channel(), SimpleNamespace(delivery_tag=7), properties, json.dumps(body)


def plot_request(plot, payload=None):
    return request({"plot": plot, "payload": payload or {"parameters": ["p"]}})


def assert_replied(channel, expected_body):
    """One reply on the request's reply queue with its correlation id, then its acknowledgement."""
    assert len(channel.basic_publish.call_args_list) == 1
    reply = arguments_of("basic_publish", channel.basic_publish.call_args)
    assert reply["routing_key"] == "reply-queue"
    assert reply["properties"].correlation_id == "correlation-1"
    assert json.loads(reply["body"]) == expected_body
    assert len(channel.basic_ack.call_args_list) == 1
    assert arguments_of("basic_ack", channel.basic_ack.call_args)["delivery_tag"] == 7


def consumed_queues(channel):
    """{queue: callback} of the consumers a channel was given."""
    consumed = {}
    for call in channel.basic_consume.call_args_list:
        consume = arguments_of("basic_consume", call)
        consumed[consume["queue"]] = consume["on_message_callback"]
    return consumed


class TestPlotRequestsFollowTheCurrentExperiment:
    def test_plot_request_after_start_is_answered_for_the_new_experiment(self, consumer, plot_consumer, plot_service):
        consumer.MAIN_THREAD.experiment = "experiment A"
        new_description = {"Context": {"name": "experiment B"}}
        channel, method, properties, body = request({"Method": "GET", "Description": new_description},
                                                    headers={"body_type": "json"})
        consumer.main_start(channel, method, properties, body)

        plot_channel, plot_method, plot_properties, plot_body = plot_request("contour", {"parameters": ["p"]})
        plot_consumer.plot_callback(plot_channel, plot_method, plot_properties, plot_body)

        plot_service.calculate_contour.assert_called_once_with({"parameters": ["p"]}, new_description)


class TestPlotRequestReplies:
    @pytest.mark.parametrize("plot", PLOT_METHODS)
    def test_plot_request_is_answered_with_the_result_of_its_plot_computation(self, plot_consumer, plot):
        channel, method, properties, body = plot_request(plot)
        plot_consumer.plot_callback(channel, method, properties, body)

        assert_replied(channel, {"computed by": PLOT_METHODS[plot]})

    @pytest.mark.parametrize("plot", PLOT_METHODS)
    def test_failing_plot_request_is_answered_with_the_empty_result_of_its_plot(
            self, api_supreme, plot_consumer, plot_service, plot):
        getattr(plot_service, PLOT_METHODS[plot]).side_effect = RuntimeError("no experiment")

        channel, method, properties, body = plot_request(plot)
        plot_consumer.plot_callback(channel, method, properties, body)

        assert_replied(channel, api_supreme.EMPTY_PLOT_RESULTS[plot])

    def test_unknown_plot_request_is_answered_with_an_empty_result(self, plot_consumer):
        channel, method, properties, body = plot_request("no_such_plot")
        plot_consumer.plot_callback(channel, method, properties, body)

        assert_replied(channel, {})


class TestPlotRequestsHaveAConnectionOfTheirOwn:
    def test_plot_queue_is_consumed_on_another_connection_than_start_status_stop_and_download(
            self, connections, consumer, plot_consumer):
        consumer.run()
        plot_consumer.run()

        queues_per_channel = [consumed_queues(connection.channel.return_value) for connection in connections]
        assert sorted(sorted(queues) for queues in queues_per_channel) == [sorted(OTHER_QUEUES), [PLOT_QUEUE]]

    def test_plot_queue_is_consumed_by_the_plot_callback(self, connections, consumer, plot_consumer):
        plot_consumer.run()

        consumed = {queue: callback for connection in connections
                    for queue, callback in consumed_queues(connection.channel.return_value).items()}
        assert consumed == {PLOT_QUEUE: plot_consumer.plot_callback}
