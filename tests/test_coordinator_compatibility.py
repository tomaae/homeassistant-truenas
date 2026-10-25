"""Reporting and update-status compatibility across TrueNAS API versions."""

from unittest.mock import Mock

import pytest

from custom_components.truenas.coordinator import TrueNASCoordinator

MIB = 1024 * 1024


def graph(name, **means):
    """Build a reporting response with named aggregation dimensions."""
    return {
        "name": name,
        "legend": ["time", *means],
        "aggregations": {"mean": means},
    }


@pytest.fixture
def coordinator():
    """Exercise polling methods without starting HA or opening a socket."""
    obj = object.__new__(TrueNASCoordinator)
    obj.ds = {"system_info": {}, "interface": {}, "disk": {}}
    obj.api = Mock()
    obj.api.connected.return_value = True
    obj.api.error = ""
    obj.api.query.side_effect = lambda method, **kwargs: (
        {"version": "25.10.7", "physmem": 8192 * MIB} if method == "system.info" else []
    )
    obj.host = "nas.example"
    obj._version_major = 0
    obj._version_minor = 0
    obj._is_virtual = False
    obj.get_systeminfo()
    obj.api.query.reset_mock(side_effect=True)
    return obj


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("TrueNAS-SCALE-24.10.2", (24, 10)),
        ("TrueNAS-SCALE-25.04.2", (25, 4)),
        ("25.10.7", (25, 10)),
        ("26.0.0", (26, 0)),
    ],
)
def test_version_formats(coordinator, version, expected):
    coordinator._version_major = coordinator._version_minor = 0
    coordinator.api.query.side_effect = lambda method, **kwargs: (
        {"version": version, "physmem": 8192 * MIB} if method == "system.info" else []
    )
    coordinator.get_systeminfo()
    assert (coordinator._version_major, coordinator._version_minor) == expected


@pytest.mark.parametrize(
    ("version", "method"),
    [
        ((24, 10), "reporting.netdata_get_data"),
        ((25, 4), "reporting.netdata_get_data"),
        ((25, 10), "reporting.get_data"),
        ((26, 0), "reporting.get_data"),
    ],
)
def test_reporting_endpoint_and_ordered_timestamps(coordinator, version, method):
    coordinator._version_major, coordinator._version_minor = version
    coordinator.api.query.return_value = []
    coordinator.get_systemstats()
    args, kwargs = coordinator.api.query.call_args
    assert args == (method,)
    graphs, query = kwargs["params"]
    assert {g["name"] for g in graphs} == {
        "load",
        "cputemp",
        "cpu",
        "arcsize",
        "memory",
    }
    assert isinstance(query["start"], int)
    assert query["end"] - query["start"] == 60
    assert query["aggregate"] is True


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (graph("cpu", cpu=31.3934, cpu0=99), 31.39),
        (graph("cpu", cpu=0), 0),
        (graph("cpu", cpu=None), None),
        (graph("cpu", system=7.5, user=12.5, idle=80), 20),
    ],
)
def test_cpu_response_formats(coordinator, response, expected):
    coordinator.api.query.return_value = [response]
    coordinator.get_systemstats()
    assert coordinator.ds["system_info"]["cpu_usage"] == expected


def test_available_memory_is_bytes(coordinator):
    coordinator.api.query.return_value = [graph("memory", available=2048 * MIB)]
    coordinator.get_systemstats()
    info = coordinator.ds["system_info"]
    assert info["memory-total_value"] == 8192 * MIB
    assert info["memory-free_value"] == 2048 * MIB
    assert info["memory-used_value"] == 6144 * MIB
    assert info["memory-usage_percent"] == 75


def test_legacy_memory_is_mebibytes(coordinator):
    coordinator.api.query.return_value = [
        graph("memory", free=2048, used=4096, cached=1024, buffers=1024)
    ]
    coordinator.get_systemstats()
    info = coordinator.ds["system_info"]
    assert info["memory-free_value"] == 2048 * MIB
    assert info["memory-used_value"] == 4096 * MIB
    assert info["memory-cached_value"] == 1024 * MIB
    assert info["memory-buffered_value"] == 1024 * MIB
    assert info["memory-usage_percent"] == 75


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (graph("arcsize", size=2493169541), 2493169541),
        (graph("arcsize", arc_size=2048), 2048 * MIB),
        (graph("arcsize", size=0), 0),
    ],
)
def test_arc_response_formats(coordinator, response, expected):
    coordinator.api.query.return_value = [response]
    coordinator.get_systemstats()
    assert coordinator.ds["system_info"]["cache_size-arc_value"] == expected


@pytest.mark.parametrize("error", ["malformed_result", "request failed"])
def test_graph_failure_isolation_is_bounded_and_keeps_valid_results(
    coordinator, error, caplog
):
    coordinator.api.error = error

    def query(method, params):
        graphs, options = params
        assert options["start"] < options["end"]
        assert options["aggregate"] is True
        if len(graphs) > 1 or graphs[0]["name"] == "cputemp":
            return None
        return [graph("cpu", cpu=25)] if graphs[0]["name"] == "cpu" else []

    coordinator.api.query.side_effect = query
    coordinator.get_systemstats()
    assert coordinator.api.query.call_count == 6
    assert "cputemp" in caplog.text
    assert coordinator.ds["system_info"]["cpu_usage"] == 25


@pytest.mark.parametrize("version", [(24, 10), (25, 4)])
def test_legacy_update_check(coordinator, version):
    coordinator._version_major, coordinator._version_minor = version
    coordinator.api.query.return_value = {"status": "AVAILABLE", "version": "next"}
    coordinator.get_updatecheck()
    coordinator.api.query.assert_called_once_with("update.check_available")
    assert coordinator.ds["system_info"]["update_available"] is True
    assert coordinator.ds["system_info"]["update_version"] == "next"


@pytest.mark.parametrize("version", [(25, 10), (26, 0)])
@pytest.mark.parametrize("new_version", [None, {"version": "next"}])
def test_current_update_status(coordinator, version, new_version):
    coordinator._version_major, coordinator._version_minor = version
    coordinator.api.query.return_value = {
        "code": "NORMAL",
        "status": {"new_version": new_version},
    }
    coordinator.get_updatecheck()
    coordinator.api.query.assert_called_once_with("update.status")
    info = coordinator.ds["system_info"]
    assert info["update_available"] is bool(new_version)
    assert info["update_version"] == ("next" if new_version else "25.10.7")


@pytest.mark.parametrize("response", [None, {"code": "ERROR", "status": None}])
def test_failed_update_check_does_not_erase_known_update(coordinator, response):
    info = coordinator.ds["system_info"]
    info.update(update_available=True, update_version="next")
    coordinator.api.query.return_value = response
    coordinator.get_updatecheck()
    assert info["update_status"] == "unknown"
    assert info["update_available"] is True
    assert info["update_version"] == "next"


def test_disk_temperatures_need_no_version_specific_argument_names(coordinator):
    coordinator.api.query.side_effect = lambda method, **kwargs: (
        [{"identifier": "disk-1", "name": "sda"}]
        if method == "disk.query"
        else {"sda": 36}
    )
    coordinator.get_disk()
    assert coordinator.ds["disk"]["disk-1"]["temperature"] == 36
    assert coordinator.api.query.call_args.args == ("disk.temperatures",)
    assert coordinator.api.query.call_args.kwargs == {"params": {}}


def test_transport_failure_does_not_disable_supported_graphs(coordinator, caplog):
    coordinator.api.query.return_value = None
    coordinator.api.error = "connection reset"
    coordinator.api.connected.return_value = False
    coordinator.get_systemstats()
    assert coordinator.api.query.call_count == 2
    assert "failed this poll" in caplog.text


@pytest.mark.parametrize("total", [32, 0, None])
def test_total_cpu_clears_old_component_attributes(coordinator, total):
    coordinator.api.query.return_value = [
        graph("cpu", softirq=1, system=7, user=12, nice=2, iowait=3, idle=75)
    ]
    coordinator.get_systemstats()
    info = coordinator.ds["system_info"]
    assert info["cpu_system"] == 7
    coordinator.api.query.return_value = [graph("cpu", cpu=total)]
    coordinator.get_systemstats()
    assert info["cpu_usage"] == total
    for component in ("softirq", "system", "user", "nice", "iowait", "idle"):
        assert info[f"cpu_{component}"] is None


def test_legacy_cpu_components_can_return_after_a_total_response(coordinator):
    coordinator.api.query.return_value = [graph("cpu", cpu=32)]
    coordinator.get_systemstats()
    coordinator.api.query.return_value = [
        graph("cpu", softirq=1, system=7, user=12, nice=2, iowait=3, idle=75)
    ]
    coordinator.get_systemstats()
    info = coordinator.ds["system_info"]
    assert info["cpu_usage"] == 19
    assert info["cpu_system"] == 7
    assert info["cpu_idle"] == 75


def test_available_memory_clears_old_cached_and_buffered_attributes(coordinator):
    coordinator.api.query.return_value = [
        graph("memory", free=2048, used=4096, cached=1024, buffers=1024)
    ]
    coordinator.get_systemstats()
    coordinator.api.query.return_value = [graph("memory", available=2048 * MIB)]
    coordinator.get_systemstats()
    info = coordinator.ds["system_info"]
    assert info["memory-used_value"] == 6144 * MIB
    assert info["memory-cached_value"] is None
    assert info["memory-buffered_value"] is None


def test_legacy_memory_details_can_return_after_available_memory(coordinator):
    coordinator.api.query.return_value = [graph("memory", available=2048 * MIB)]
    coordinator.get_systemstats()
    coordinator.api.query.return_value = [
        graph("memory", free=2048, used=4096, cached=1024, buffers=1024)
    ]
    coordinator.get_systemstats()
    info = coordinator.ds["system_info"]
    assert info["memory-cached_value"] == 1024 * MIB
    assert info["memory-buffered_value"] == 1024 * MIB


def test_reporting_retries_use_real_websocket_error_handling(coordinator, caplog):
    from json import dumps, loads

    from custom_components.truenas.api import TrueNASAPI

    api = TrueNASAPI("nas.example", "test-key")
    api._connected = True
    api._ws = Mock()
    error = {
        "jsonrpc": "2.0",
        "id": 0,
        "error": {"code": -32000, "message": "Graph unavailable"},
    }
    api._ws.recv.side_effect = [
        dumps(error),
        dumps({"result": []}),
        dumps(error),
        dumps({"result": [graph("cpu", cpu=25)]}),
        dumps({"result": []}),
        dumps({"result": []}),
    ]
    coordinator.api = api
    coordinator.get_systemstats()
    assert api._ws.send.call_count == 6
    assert "cputemp" in caplog.text
    assert coordinator.ds["system_info"]["cpu_usage"] == 25
    requests = [loads(call.args[0]) for call in api._ws.send.call_args_list]
    assert all(r["method"] == "reporting.get_data" for r in requests)
    assert len(requests[0]["params"][0]) == 5
    assert all(len(r["params"][0]) == 1 for r in requests[1:])


def test_temporary_graph_failure_recovers_on_the_next_poll(coordinator):
    requests = []
    failed = graph("cputemp", core0=55)

    def first_poll(method, params):
        graphs, options = params
        requests.append(graphs)
        if len(graphs) > 1 or graphs[0]["name"] == "cputemp":
            return {"error": {"message": "temporarily unavailable"}}
        return []

    coordinator.api.query.side_effect = first_poll
    coordinator.get_systemstats()
    assert len(requests) == 6
    coordinator.api.query.reset_mock(side_effect=True)
    coordinator.api.query.return_value = [failed]
    coordinator.get_systemstats()
    graphs = coordinator.api.query.call_args.kwargs["params"][0]
    assert {"name": "cputemp"} in graphs
    assert coordinator.ds["system_info"]["cpu_temperature"] == 55


def test_interface_failure_does_not_hide_other_interfaces(coordinator, caplog):
    coordinator.ds["interface"] = {"eth0": {}, "eth1": {}}

    def first_poll(method, params):
        graphs, options = params
        if len(graphs) > 1 or graphs[0] == {"name": "interface", "identifier": "eth0"}:
            return {"error": {"message": "temporarily unavailable"}}
        if graphs[0].get("identifier") == "eth1":
            result = graph("interface", received=100, sent=50)
            result["identifier"] = "eth1"
            return [result]
        return []

    coordinator.api.query.side_effect = first_poll
    coordinator.get_systemstats()
    assert coordinator.ds["interface"]["eth1"]["rx"] == 12.21
    assert "eth0" in caplog.text
    assert "eth1" not in caplog.text
    coordinator.api.query.reset_mock(side_effect=True)
    coordinator.api.query.return_value = []
    coordinator.get_systemstats()
    graphs = coordinator.api.query.call_args.kwargs["params"][0]
    assert {"name": "interface", "identifier": "eth0"} in graphs
    assert {"name": "interface", "identifier": "eth1"} in graphs


@pytest.mark.parametrize(
    "response",
    [
        graph("memory", available=None),
        graph("memory", free=None, used=4096, cached=None, buffers=None),
        {"name": "memory", "legend": ["time", "available"]},
        graph("memory"),
    ],
)
def test_missing_memory_does_not_report_full_usage(coordinator, response):
    coordinator.api.query.return_value = [graph("memory", available=2048 * MIB)]
    coordinator.get_systemstats()
    assert coordinator.ds["system_info"]["memory-usage_percent"] == 75
    coordinator.api.query.return_value = [response]
    coordinator.get_systemstats()
    info = coordinator.ds["system_info"]
    assert info["memory-free_value"] is None
    assert info["memory-usage_percent"] is None
    assert info["memory-cached_value"] is None
    assert info["memory-buffered_value"] is None
    if "available" in response.get("legend", []):
        assert info["memory-used_value"] is None


def test_zero_available_memory_is_a_valid_measurement(coordinator):
    coordinator.api.query.return_value = [graph("memory", available=0)]
    coordinator.get_systemstats()
    info = coordinator.ds["system_info"]
    assert info["memory-free_value"] == 0
    assert info["memory-used_value"] == 8192 * MIB
    assert info["memory-usage_percent"] == 100


def test_available_memory_recovers_after_missing_reading(coordinator):
    coordinator.api.query.return_value = [graph("memory", available=None)]
    coordinator.get_systemstats()
    coordinator.api.query.return_value = [graph("memory", available=2048 * MIB)]
    coordinator.get_systemstats()
    assert coordinator.ds["system_info"]["memory-usage_percent"] == 75
