"""TrueNAS Controller."""

from __future__ import annotations

import logging

from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
)

from .api import TrueNASAPI
from .apiparser import parse_api, utc_from_timestamp
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   TrueNASControllerData
# ---------------------------
class TrueNASCoordinator(DataUpdateCoordinator[None]):
    """TrueNASCoordinator Class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize TrueNASCoordinator."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry

        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

        self.name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]

        self.ds = {
            "interface": {},
            "disk": {},
            "pool": {},
            "dataset": {},
            "system_info": {},
            "service": {},
            "jail": {},
            "vm": {},
            "cloudsync": {},
            "replication": {},
            "snapshottask": {},
            "app": {},
        }

        self.api = TrueNASAPI(
            hass,
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_API_KEY],
            config_entry.data[CONF_SSL],
            config_entry.data[CONF_VERIFY_SSL],
        )

        self._systemstats_errored = []
        self.datasets_hass_device_id = None
        self.last_updatecheck_update = datetime(1970, 1, 1)

        self._is_scale = False
        self._is_virtual = False
        self._version_major = 0

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self) -> str:
        """Return connected state."""
        return self.api.connected()

    # ---------------------------
    #   _async_update_data
    # ---------------------------
    async def _async_update_data(self):
        """Update TrueNAS data."""
        await self.hass.async_add_executor_job(self.get_systeminfo)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_systemstats)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_service)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_disk)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_dataset)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_pool)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_jail)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_vm)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_cloudsync)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_replication)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_snapshottask)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_app)

        delta = datetime.now().replace(microsecond=0) - self.last_updatecheck_update
        if self.api.connected() and delta.total_seconds() > 60 * 60 * 12:
            await self.hass.async_add_executor_job(self.get_updatecheck)
            self.last_updatecheck_update = datetime.now().replace(microsecond=0)

        if not self.api.connected():
            raise UpdateFailed("TrueNas Disconnected")

        return self.ds

    # ---------------------------
    #   get_systeminfo
    # ---------------------------
    def get_systeminfo(self) -> None:
        """Get system info from TrueNAS."""
        self.ds["system_info"] = parse_api(
            data=self.ds["system_info"],
            source=self.api.query("system/info"),
            vals=[
                {"name": "version", "default": "unknown"},
                {"name": "hostname", "default": "unknown"},
                {"name": "uptime_seconds", "default": 0},
                {"name": "system_serial", "default": "unknown"},
                {"name": "system_product", "default": "unknown"},
                {"name": "system_manufacturer", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "uptimeEpoch", "default": 0},
                {"name": "cpu_temperature", "default": 0.0},
                {"name": "load_shortterm", "default": 0.0},
                {"name": "load_midterm", "default": 0.0},
                {"name": "load_longterm", "default": 0.0},
                {"name": "cpu_interrupt", "default": 0.0},
                {"name": "cpu_system", "default": 0.0},
                {"name": "cpu_user", "default": 0.0},
                {"name": "cpu_nice", "default": 0.0},
                {"name": "cpu_idle", "default": 0.0},
                {"name": "cpu_usage", "default": 0.0},
                {"name": "cache_size-arc_value", "default": 0.0},
                {"name": "memory-used_value", "default": 0.0},
                {"name": "memory-free_value", "default": 0.0},
                {"name": "memory-cached_value", "default": 0.0},
                {"name": "memory-buffered_value", "default": 0.0},
                {"name": "memory-total_value", "default": 0.0},
                {"name": "memory-usage_percent", "default": 0},
                {"name": "update_available", "type": "bool", "default": False},
                {"name": "update_progress", "default": 0},
                {"name": "update_jobid", "default": 0},
                {"name": "update_state", "default": "unknown"},
            ],
        )
        if not self.api.connected():
            return

        if not self.ds["system_info"]["update_available"]:
            self.ds["system_info"]["update_version"] = self.ds["system_info"]["version"]

        if self.ds["system_info"]["update_jobid"]:
            self.ds["system_info"] = parse_api(
                data=self.ds["system_info"],
                source=self.api.query(
                    "core/get_jobs",
                    method="get",
                    params={"id": self.ds["system_info"]["update_jobid"]},
                ),
                vals=[
                    {
                        "name": "update_progress",
                        "source": "progress/percent",
                        "default": 0,
                    },
                    {
                        "name": "update_state",
                        "source": "state",
                        "default": "unknown",
                    },
                ],
            )
            if not self.api.connected():
                return

            if (
                self.ds["system_info"]["update_state"] != "RUNNING"
                or not self.ds["system_info"]["update_available"]
            ):
                self.ds["system_info"]["update_progress"] = 0
                self.ds["system_info"]["update_jobid"] = 0
                self.ds["system_info"]["update_state"] = "unknown"

        self._is_scale = bool(
            self.ds["system_info"]["version"].startswith("TrueNAS-SCALE-")
        )
        if not self._version_major:
            self._version_major = int(
                self.ds["system_info"]
                .get("version")
                .removeprefix("TrueNAS-")
                .removeprefix("SCALE-")
                .split(".")[0]
            )

        self._is_virtual = self.ds["system_info"]["system_manufacturer"] in [
            "QEMU",
            "VMware, Inc.",
        ] or self.ds["system_info"]["system_product"] in [
            "VirtualBox",
        ]

        if self.ds["system_info"]["uptime_seconds"] > 0:
            now = datetime.now().replace(microsecond=0)
            uptime_tm = datetime.timestamp(
                now - timedelta(seconds=int(self.ds["system_info"]["uptime_seconds"]))
            )
            self.ds["system_info"]["uptimeEpoch"] = utc_from_timestamp(uptime_tm)

        self.ds["interface"] = parse_api(
            data=self.ds["interface"],
            source=self.api.query("interface"),
            key="id",
            vals=[
                {"name": "id", "default": "unknown"},
                {"name": "name", "default": "unknown"},
                {"name": "description", "default": "unknown"},
                {"name": "mtu", "default": "unknown"},
                {
                    "name": "link_state",
                    "source": "state/link_state",
                    "default": "unknown",
                },
                {
                    "name": "active_media_type",
                    "source": "state/active_media_type",
                    "default": "unknown",
                },
                {
                    "name": "active_media_subtype",
                    "source": "state/active_media_subtype",
                    "default": "unknown",
                },
                {
                    "name": "link_address",
                    "source": "state/link_address",
                    "default": "unknown",
                },
            ],
            ensure_vals=[
                {"name": "rx", "default": 0},
                {"name": "tx", "default": 0},
            ],
        )

    # ---------------------------
    #   get_updatecheck
    # ---------------------------
    def get_updatecheck(self) -> None:
        self.ds["system_info"] = parse_api(
            data=self.ds["system_info"],
            source=self.api.query("update/check_available", method="post"),
            vals=[
                {
                    "name": "update_status",
                    "source": "status",
                    "default": "unknown",
                },
                {
                    "name": "update_version",
                    "source": "version",
                    "default": "unknown",
                },
            ],
        )

        if not self.api.connected():
            return

        self.ds["system_info"]["update_available"] = (
            self.ds["system_info"]["update_status"] == "AVAILABLE"
        )

    # ---------------------------
    #   get_systemstats
    # ---------------------------
    def get_systemstats(self) -> None:
        """Get system statistics."""
        tmp_params = {
            "graphs": [
                {"name": "load"},
                {"name": "cputemp"},
                {"name": "cpu"},
                {"name": "arcsize"},
                {"name": "memory"},
            ],
            "reporting_query": {
                "start": "now-90s",
                "end": "now-30s",
                "aggregate": True,
            },
        }
        if self._is_scale and self._version_major == 23:
            tmp_params = {
                "graphs": [
                    {"name": "load"},
                    {"name": "cputemp"},
                    {"name": "cpu"},
                    {"name": "arcsize"},
                    {"name": "memory"},
                ],
                "reporting_query_netdata": {
                    "start": "-90",
                    "end": "-30",
                    "aggregate": True,
                },
            }
        elif self._is_scale and self._version_major >= 24:
            tmp_params = {
                "graphs": [
                    {"name": "load"},
                    {"name": "cputemp"},
                    {"name": "cpu"},
                    {"name": "arcsize"},
                    {"name": "memory"},
                ],
                "reporting_query": {
                    "start": "-90",
                    "end": "-30",
                    "aggregate": True,
                },
            }

        for uid, vals in self.ds["interface"].items():
            tmp_params["graphs"].append({"name": "interface", "identifier": uid})

        if self._is_virtual:
            tmp_params["graphs"].remove({"name": "cputemp"})

        for tmp in tmp_params["graphs"]:
            if tmp["name"] in self._systemstats_errored:
                tmp_params["graphs"].remove(tmp)

        if not tmp_params["graphs"]:
            return

        reporting_path = "reporting/get_data"
        if self._is_scale and self._version_major >= 23:
            reporting_path = "reporting/netdata_get_data"

        tmp_graph = self.api.query(
            reporting_path,
            method="post",
            params=tmp_params,
        )

        if not isinstance(tmp_graph, list):
            if self.api.error == 500:
                for tmp in tmp_params["graphs"]:
                    tmp_params2 = {
                        "graphs": [tmp],
                        "reporting_query": {
                            "start": "now-90s",
                            "end": "now-30s",
                            "aggregate": True,
                        },
                    }

                    if self._is_scale and self._version_major == 23:
                        tmp_params2 = {
                            "graphs": [tmp],
                            "reporting_query_netdata": {
                                "start": "-90",
                                "end": "-30",
                                "aggregate": True,
                            },
                        }
                    elif self._is_scale and self._version_major >= 24:
                        tmp_params2 = {
                            "graphs": [tmp],
                            "reporting_query": {
                                "start": "-90",
                                "end": "-30",
                                "aggregate": "true",
                            },
                        }

                    tmp2 = self.api.query(
                        reporting_path,
                        method="post",
                        params=tmp_params2,
                    )
                    if not isinstance(tmp2, list) and self.api.error == 500:
                        self._systemstats_errored.append(tmp["name"])

                _LOGGER.warning(
                    "TrueNAS %s fetching following graphs failed, check your NAS: %s",
                    self.host,
                    self._systemstats_errored,
                )
                self.get_systemstats()

            return

        for i in range(len(tmp_graph)):
            if "name" not in tmp_graph[i]:
                continue

            # CPU temperature
            if tmp_graph[i]["name"] == "cputemp":
                if "aggregations" in tmp_graph[i]:
                    if self._is_scale and self._version_major >= 23:
                        self.ds["system_info"]["cpu_temperature"] = round(
                            max(tmp_graph[i]["aggregations"]["mean"].values()), 2
                        )
                    else:
                        self.ds["system_info"]["cpu_temperature"] = round(
                            max(
                                list(filter(None, tmp_graph[i]["aggregations"]["mean"]))
                            ),
                            1,
                        )
                else:
                    self.ds["system_info"]["cpu_temperature"] = 0.0

            # CPU load
            if tmp_graph[i]["name"] == "load":
                tmp_arr = ("load_shortterm", "load_midterm", "load_longterm")
                if self._is_scale and self._version_major >= 23:
                    tmp_arr = ("shortterm", "midterm", "longterm")

                self._systemstats_process(tmp_arr, tmp_graph[i], "load")

            # CPU usage
            if tmp_graph[i]["name"] == "cpu":
                tmp_arr = ("interrupt", "system", "user", "nice", "idle")
                if self._is_scale and self._version_major >= 23:
                    tmp_arr = ("softirq", "system", "user", "nice", "iowait", "idle")

                self._systemstats_process(tmp_arr, tmp_graph[i], "cpu")
                self.ds["system_info"]["cpu_usage"] = round(
                    self.ds["system_info"]["cpu_system"]
                    + self.ds["system_info"]["cpu_user"],
                    2,
                )

            # Interface
            if tmp_graph[i]["name"] == "interface":
                tmp_etc = tmp_graph[i]["identifier"]
                if tmp_etc in self.ds["interface"]:
                    # 12->13 API change
                    tmp_graph[i]["legend"] = [
                        tmp.replace("if_octets_", "") for tmp in tmp_graph[i]["legend"]
                    ]
                    if self._is_scale and self._version_major >= 23:
                        tmp_graph[i]["legend"] = [
                            tmp.replace("received", "rx")
                            for tmp in tmp_graph[i]["legend"]
                        ]
                        tmp_graph[i]["legend"] = [
                            tmp.replace("sent", "tx") for tmp in tmp_graph[i]["legend"]
                        ]
                        tmp_graph[i]["aggregations"]["mean"] = {
                            k.replace("received", "rx"): v
                            for k, v in tmp_graph[i]["aggregations"]["mean"].items()
                        }
                        tmp_graph[i]["aggregations"]["mean"] = {
                            k.replace("sent", "tx"): v
                            for k, v in tmp_graph[i]["aggregations"]["mean"].items()
                        }

                    tmp_arr = ("rx", "tx")
                    if "aggregations" in tmp_graph[i]:
                        for e in range(len(tmp_graph[i]["legend"])):
                            tmp_var = tmp_graph[i]["legend"][e]
                            if tmp_var in tmp_arr:
                                if self._is_scale and self._version_major >= 23:
                                    tmp_val = (
                                        tmp_graph[i]["aggregations"]["mean"][tmp_var]
                                        or 0.0
                                        if tmp_var
                                        in tmp_graph[i]["aggregations"]["mean"]
                                        else 0.0
                                    )
                                    self.ds["interface"][tmp_etc][tmp_var] = round(
                                        (tmp_val * 0.12207), 2
                                    )
                                else:
                                    tmp_val = (
                                        tmp_graph[i]["aggregations"]["mean"][e] or 0.0
                                        if e in tmp_graph[i]["aggregations"]["mean"]
                                        else 0.0
                                    )
                                    self.ds["interface"][tmp_etc][tmp_var] = round(
                                        (tmp_val / 1024), 2
                                    )
                    else:
                        for tmp_load in tmp_arr:
                            self.ds["interface"][tmp_etc][tmp_load] = 0.0

            # memory
            if tmp_graph[i]["name"] == "memory":
                tmp_arr = (
                    "memory-used_value",
                    "memory-free_value",
                    "memory-cached_value",
                    "memory-buffered_value",
                )
                if self._is_scale and self._version_major >= 23:
                    tmp_arr = (
                        "free",
                        "used",
                        "cached",
                        "buffers",
                    )
                self._systemstats_process(tmp_arr, tmp_graph[i], "memory")
                self.ds["system_info"]["memory-total_value"] = round(
                    self.ds["system_info"]["memory-used_value"]
                    + self.ds["system_info"]["memory-free_value"]
                    + self.ds["system_info"]["cache_size-arc_value"]
                )
                if self.ds["system_info"]["memory-total_value"] > 0:
                    self.ds["system_info"]["memory-usage_percent"] = round(
                        100
                        * (
                            float(self.ds["system_info"]["memory-total_value"])
                            - float(self.ds["system_info"]["memory-free_value"])
                        )
                        / float(self.ds["system_info"]["memory-total_value"])
                    )

            # arcsize
            if tmp_graph[i]["name"] == "arcsize":
                tmp_arr = "cache_size-arc_value"
                if self._is_scale and self._version_major >= 23:
                    tmp_arr = "arc_size"
                self._systemstats_process(tmp_arr, tmp_graph[i], "arcsize")

    # ---------------------------
    #   _systemstats_process
    # ---------------------------
    def _systemstats_process(self, arr, graph, t) -> None:
        if "aggregations" in graph:
            for e in range(len(graph["legend"])):
                tmp_var = graph["legend"][e]
                if tmp_var in arr:
                    if self._is_scale and self._version_major >= 23:
                        e = tmp_var

                    tmp_val = graph["aggregations"]["mean"][e] or 0.0
                    if t == "memory":

                        if self._is_scale and self._version_major >= 23:
                            if tmp_var == "free":
                                self.ds["system_info"]["memory-free_value"] = round(
                                    tmp_val * 1024 * 1024
                                )
                            elif tmp_var == "used":
                                self.ds["system_info"]["memory-used_value"] = round(
                                    tmp_val * 1024 * 1024
                                )
                            elif tmp_var == "cached":
                                self.ds["system_info"]["memory-cached_value"] = round(
                                    tmp_val * 1024 * 1024
                                )
                            elif tmp_var == "buffers":
                                self.ds["system_info"]["memory-buffered_value"] = round(
                                    tmp_val * 1024 * 1024
                                )
                        else:
                            self.ds["system_info"][tmp_var] = tmp_val
                    elif t == "cpu":
                        self.ds["system_info"][f"cpu_{tmp_var}"] = round(tmp_val, 2)
                    elif t == "load":
                        if self._is_scale and self._version_major >= 23:
                            self.ds["system_info"][f"load_{tmp_var}"] = round(
                                tmp_val, 2
                            )
                        else:
                            self.ds["system_info"][tmp_var] = round(tmp_val, 2)
                    elif t == "arcsize":
                        if self._is_scale and self._version_major >= 23:
                            tmp_val = tmp_val * 1024 * 1024
                            self.ds["system_info"]["cache_size-arc_value"] = round(
                                tmp_val, 2
                            )
                        else:
                            self.ds["system_info"][tmp_var] = round(tmp_val, 2)
                    else:
                        self.ds["system_info"][tmp_var] = round(tmp_val, 2)
        else:
            for tmp_load in arr:
                if t == "cpu":
                    self.ds["system_info"][f"cpu_{tmp_load}"] = 0.0
                else:
                    self.ds["system_info"][tmp_load] = 0.0

    # ---------------------------
    #   get_service
    # ---------------------------
    def get_service(self) -> None:
        """Get service info from TrueNAS."""
        self.ds["service"] = parse_api(
            data=self.ds["service"],
            source=self.api.query("service"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "service", "default": "unknown"},
                {"name": "enable", "type": "bool", "default": False},
                {"name": "state", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "running", "type": "bool", "default": False},
            ],
        )

        for uid, vals in self.ds["service"].items():
            self.ds["service"][uid]["running"] = vals["state"] == "RUNNING"

    # ---------------------------
    #   get_pool
    # ---------------------------
    def get_pool(self) -> None:
        """Get pools from TrueNAS."""
        self.ds["pool"] = parse_api(
            data=self.ds["pool"],
            source=self.api.query("pool"),
            key="guid",
            vals=[
                {"name": "guid", "default": 0},
                {"name": "id", "default": 0},
                {"name": "name", "default": "unknown"},
                {"name": "path", "default": "unknown"},
                {"name": "status", "default": "unknown"},
                {"name": "healthy", "type": "bool", "default": False},
                {"name": "is_decrypted", "type": "bool", "default": False},
                {
                    "name": "autotrim",
                    "source": "autotrim/parsed",
                    "type": "bool",
                    "default": False,
                },
                {
                    "name": "scan_function",
                    "source": "scan/function",
                    "default": "unknown",
                },
                {"name": "scrub_state", "source": "scan/state", "default": "unknown"},
                {
                    "name": "scrub_start",
                    "source": "scan/start_time/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
                {
                    "name": "scrub_end",
                    "source": "scan/end_time/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
                {
                    "name": "scrub_secs_left",
                    "source": "scan/total_secs_left",
                    "default": 0,
                },
            ],
            ensure_vals=[
                {"name": "available_gib", "default": 0.0},
                {"name": "total_gib", "default": 0.0},
                {"name": "usage", "default": 0.0},
            ],
        )

        self.ds["pool"] = parse_api(
            data=self.ds["pool"],
            source=self.api.query("boot/get_state"),
            key="name",
            vals=[
                {"name": "guid", "default": "boot-pool"},
                {"name": "id", "default": "boot-pool"},
                {"name": "name", "default": "unknown"},
                {"name": "path", "default": "unknown"},
                {"name": "status", "default": "unknown"},
                {"name": "healthy", "type": "bool", "default": False},
                {"name": "is_decrypted", "type": "bool", "default": False},
                {
                    "name": "autotrim",
                    "source": "autotrim/parsed",
                    "type": "bool",
                    "default": False,
                },
                {"name": "root_dataset"},
                {
                    "name": "root_dataset_available",
                    "source": "root_dataset/properties/available/parsed",
                    "default": 0,
                },
                {
                    "name": "root_dataset_used",
                    "source": "root_dataset/properties/used/parsed",
                    "default": 0,
                },
                {
                    "name": "scan_function",
                    "source": "scan/function",
                    "default": "unknown",
                },
                {"name": "scrub_state", "source": "scan/state", "default": "unknown"},
                {
                    "name": "scrub_start",
                    "source": "scan/start_time/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
                {
                    "name": "scrub_end",
                    "source": "scan/end_time/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
                {
                    "name": "scrub_secs_left",
                    "source": "scan/total_secs_left",
                    "default": 0,
                },
                {"name": "allocated", "default": 0},
                {"name": "free", "default": 0},
            ],
            ensure_vals=[
                {"name": "available_gib", "default": 0.0},
                {"name": "total_gib", "default": 0.0},
                {"name": "usage", "default": 0.0},
            ],
        )

        # Process pools
        tmp_dataset_available = {}
        tmp_dataset_total = {}
        for uid, vals in self.ds["dataset"].items():
            tmp_dataset_available[self.ds["dataset"][uid]["mountpoint"]] = vals[
                "available"
            ]

            tmp_dataset_total[self.ds["dataset"][uid]["mountpoint"]] = (
                vals["available"] + vals["used"]
            )

        for uid, vals in self.ds["pool"].items():
            if vals["path"] in tmp_dataset_available:
                self.ds["pool"][uid]["available_gib"] = tmp_dataset_available[
                    vals["path"]
                ]

            if vals["path"] in tmp_dataset_total:
                self.ds["pool"][uid]["total_gib"] = tmp_dataset_total[vals["path"]]

            if vals["name"] in ["boot-pool", "freenas-boot"]:
                if self._is_scale and self._version_major >= 23:
                    self.ds["pool"][uid]["available_gib"] = vals["free"]
                    self.ds["pool"][uid]["total_gib"] = vals["free"] + vals["allocated"]
                else:
                    self.ds["pool"][uid]["available_gib"] = vals[
                        "root_dataset_available"
                    ]
                    self.ds["pool"][uid]["total_gib"] = (
                        vals["root_dataset_available"] + vals["root_dataset_used"]
                    )

                self.ds["pool"][uid].pop("root_dataset")

            if self.ds["pool"][uid]["total_gib"] > 0:
                self.ds["pool"][uid]["usage"] = round(
                    (
                        self.ds["pool"][uid]["available_gib"]
                        / self.ds["pool"][uid]["total_gib"]
                    )
                    * 100
                )
            else:
                self.ds["pool"][uid]["usage"] = 0

    # ---------------------------
    #   get_dataset
    # ---------------------------
    def get_dataset(self) -> None:
        """Get datasets from TrueNAS."""
        self.ds["dataset"] = parse_api(
            data={},
            source=self.api.query("pool/dataset"),
            key="id",
            vals=[
                {"name": "id", "default": "unknown"},
                {"name": "type", "default": "unknown"},
                {"name": "name", "default": "unknown"},
                {"name": "pool", "default": "unknown"},
                {"name": "mountpoint", "default": "unknown"},
                {"name": "comments", "source": "comments/parsed", "default": ""},
                {
                    "name": "deduplication",
                    "source": "deduplication/parsed",
                    "type": "bool",
                    "default": False,
                },
                {
                    "name": "atime",
                    "source": "atime/parsed",
                    "type": "bool",
                    "default": False,
                },
                {
                    "name": "casesensitivity",
                    "source": "casesensitivity/parsed",
                    "default": "unknown",
                },
                {"name": "checksum", "source": "checksum/parsed", "default": "unknown"},
                {
                    "name": "exec",
                    "source": "exec/parsed",
                    "type": "bool",
                    "default": False,
                },
                {"name": "sync", "source": "sync/parsed", "default": "unknown"},
                {
                    "name": "compression",
                    "source": "compression/parsed",
                    "default": "unknown",
                },
                {
                    "name": "compressratio",
                    "source": "compressratio/parsed",
                    "default": "unknown",
                },
                {"name": "quota", "source": "quota/parsed", "default": "unknown"},
                {"name": "copies", "source": "copies/parsed", "default": 0},
                {
                    "name": "readonly",
                    "source": "readonly/parsed",
                    "type": "bool",
                    "default": False,
                },
                {"name": "recordsize", "source": "recordsize/parsed", "default": 0},
                {
                    "name": "encryption_algorithm",
                    "source": "encryption_algorithm/parsed",
                    "default": "unknown",
                },
                {"name": "used", "source": "used/parsed", "default": 0},
                {"name": "available", "source": "available/parsed", "default": 0},
            ],
            ensure_vals=[
                {"name": "used_gb", "default": 0},
            ],
        )

        for uid, vals in self.ds["dataset"].items():
            self.ds["dataset"][uid]["used_gb"] = vals["used"]

        if len(self.ds["dataset"]) == 0:
            return

        # entities_to_be_removed = []
        # if not self.datasets_hass_device_id:
        #     device_registry = dr.async_get(self.hass)
        #     for device in device_registry.devices.values():
        #         if (
        #             self.config_entry.entry_id in device.config_entries
        #             and device.name.endswith("Datasets")
        #         ):
        #             self.datasets_hass_device_id = device.id
        #             _LOGGER.debug(f"datasets device: {device.name}")
        #
        #     if not self.datasets_hass_device_id:
        #         return
        #
        # _LOGGER.debug(f"datasets_hass_device_id: {self.datasets_hass_device_id}")
        # entity_registry = er.async_get(self.hass)
        # entity_entries = async_entries_for_config_entry(
        #     entity_registry, self.config_entry.entry_id
        # )
        # for entity in entity_entries:
        #     if (
        #         entity.device_id == self.datasets_hass_device_id
        #         and entity.unique_id.removeprefix(f"{self.name.lower()}-dataset-")
        #         not in map(
        #             lambda x: str.replace(x, "/", "_"),
        #             map(str.lower, self.ds["dataset"].keys()),
        #         )
        #     ):
        #         _LOGGER.debug(f"dataset to be removed: {entity.unique_id}")
        #         entities_to_be_removed.append(entity.entity_id)
        #
        # for entity_id in entities_to_be_removed:
        #     entity_registry.async_remove(entity_id)

    # ---------------------------
    #   get_disk
    # ---------------------------
    def get_disk(self) -> None:
        """Get disks from TrueNAS."""
        self.ds["disk"] = parse_api(
            data=self.ds["disk"],
            source=self.api.query("disk"),
            key="identifier",
            vals=[
                {"name": "name", "default": "unknown"},
                {"name": "devname", "default": "unknown"},
                {"name": "serial", "default": "unknown"},
                {"name": "size", "default": "unknown"},
                {"name": "hddstandby", "default": "unknown"},
                {"name": "hddstandby_force", "type": "bool", "default": False},
                {"name": "advpowermgmt", "default": "unknown"},
                {"name": "acousticlevel", "default": "unknown"},
                {"name": "togglesmart", "type": "bool", "default": False},
                {"name": "model", "default": "unknown"},
                {"name": "rotationrate", "default": "unknown"},
                {"name": "type", "default": "unknown"},
                {"name": "zfs_guid", "default": "unknown"},
                {"name": "identifier", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "temperature", "default": 0},
            ],
        )

        # Get disk temperatures
        temps = self.api.query(
            "disk/temperatures",
            method="post",
            params={"names": []},
        )

        if temps:
            for uid, vals in self.ds["disk"].items():
                if vals["name"] in temps:  # looks for devname here
                    self.ds["disk"][uid]["temperature"] = temps[vals["name"]]
                    # return devname temp to uid disk
                    # I feel like this will break in the future when TrueNAS updates to a more sensible system. Currently their own long term stats are broken by the changing devnames.

    # ---------------------------
    #   get_jail
    # ---------------------------
    def get_jail(self) -> None:
        """Get jails from TrueNAS."""
        if self._is_scale:
            return

        self.ds["jail"] = parse_api(
            data=self.ds["jail"],
            source=self.api.query("jail"),
            key="id",
            vals=[
                {"name": "id", "default": "unknown"},
                {"name": "comment", "default": "unknown"},
                {"name": "host_hostname", "default": "unknown"},
                {"name": "jail_zfs_dataset", "default": "unknown"},
                {"name": "last_started", "default": "unknown"},
                {"name": "ip4_addr", "default": "unknown"},
                {"name": "ip6_addr", "default": "unknown"},
                {"name": "release", "default": "unknown"},
                {"name": "state", "type": "bool", "default": False},
                {"name": "type", "default": "unknown"},
                {"name": "plugin_name", "default": "unknown"},
            ],
        )

    # ---------------------------
    #   get_vm
    # ---------------------------
    def get_vm(self) -> None:
        """Get VMs from TrueNAS."""
        self.ds["vm"] = parse_api(
            data=self.ds["vm"],
            source=self.api.query("vm"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "name", "default": "unknown"},
                {"name": "description", "default": "unknown"},
                {"name": "vcpus", "default": 0},
                {"name": "memory", "default": 0},
                {"name": "autostart", "type": "bool", "default": False},
                {"name": "cores", "default": 0},
                {"name": "threads", "default": 0},
                {"name": "state", "source": "status/state", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "running", "type": "bool", "default": False},
            ],
        )

        for uid, vals in self.ds["vm"].items():
            self.ds["vm"][uid]["running"] = vals["state"] == "RUNNING"

    # ---------------------------
    #   get_cloudsync
    # ---------------------------
    def get_cloudsync(self) -> None:
        """Get cloudsync from TrueNAS."""
        self.ds["cloudsync"] = parse_api(
            data=self.ds["cloudsync"],
            source=self.api.query("cloudsync"),
            key="id",
            vals=[
                {"name": "id", "default": "unknown"},
                {"name": "description", "default": "unknown"},
                {"name": "direction", "default": "unknown"},
                {"name": "path", "default": "unknown"},
                {"name": "enabled", "type": "bool", "default": False},
                {"name": "transfer_mode", "default": "unknown"},
                {"name": "snapshot", "type": "bool", "default": False},
                {"name": "state", "source": "job/state", "default": "unknown"},
                {
                    "name": "time_started",
                    "source": "job/time_started/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
                {
                    "name": "time_finished",
                    "source": "job/time_finished/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
                {"name": "job_percent", "source": "job/progress/percent", "default": 0},
                {
                    "name": "job_description",
                    "source": "job/progress/description",
                    "default": "unknown",
                },
            ],
        )

    # ---------------------------
    #   get_replication
    # ---------------------------
    def get_replication(self) -> None:
        """Get replication from TrueNAS."""
        self.ds["replication"] = parse_api(
            data=self.ds["replication"],
            source=self.api.query("replication"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "name", "default": "unknown"},
                {"name": "source_datasets", "default": "unknown"},
                {"name": "target_dataset", "default": "unknown"},
                {"name": "recursive", "type": "bool", "default": False},
                {"name": "enabled", "type": "bool", "default": False},
                {"name": "direction", "default": "unknown"},
                {"name": "transport", "default": "unknown"},
                {"name": "auto", "type": "bool", "default": False},
                {"name": "retention_policy", "default": "unknown"},
                {"name": "state", "source": "job/state", "default": "unknown"},
                {
                    "name": "time_started",
                    "source": "job/time_started/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
                {
                    "name": "time_finished",
                    "source": "job/time_finished/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
                {"name": "job_percent", "source": "job/progress/percent", "default": 0},
                {
                    "name": "job_description",
                    "source": "job/progress/description",
                    "default": "unknown",
                },
            ],
        )

    # ---------------------------
    #   get_snapshottask
    # ---------------------------
    def get_snapshottask(self) -> None:
        """Get replication from TrueNAS."""
        self.ds["snapshottask"] = parse_api(
            data=self.ds["snapshottask"],
            source=self.api.query("pool/snapshottask"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "dataset", "default": "unknown"},
                {"name": "recursive", "type": "bool", "default": False},
                {"name": "lifetime_value", "default": 0},
                {"name": "lifetime_unit", "default": "unknown"},
                {"name": "enabled", "type": "bool", "default": False},
                {"name": "naming_schema", "default": "unknown"},
                {"name": "allow_empty", "type": "bool", "default": False},
                {"name": "vmware_sync", "type": "bool", "default": False},
                {"name": "state", "source": "state/state", "default": "unknown"},
                {
                    "name": "datetime",
                    "source": "state/datetime/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
            ],
        )

    # ---------------------------
    #   get_app
    # ---------------------------
    def get_app(self) -> None:
        """Get Apps from TrueNAS."""
        if not self._is_scale:
            return

        self.ds["app"] = parse_api(
            data=self.ds["app"],
            source=self.api.query("chart/release"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "name", "default": "unknown"},
                {"name": "human_version", "default": "unknown"},
                {"name": "update_available", "default": "unknown"},
                {"name": "container_images_update_available", "default": "unknown"},
                {"name": "portal", "source": "portals/open", "default": "unknown"},
                {"name": "status", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "running", "type": "bool", "default": False},
            ],
        )

        for uid, vals in self.ds["app"].items():
            self.ds["app"][uid]["running"] = vals["status"] == "ACTIVE"
