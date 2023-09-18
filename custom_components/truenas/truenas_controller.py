"""TrueNAS Controller."""
from asyncio import Lock as Asyncio_lock, wait_for as asyncio_wait_for
from datetime import datetime, timedelta
from logging import getLogger

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.event import async_track_time_interval

from .apiparser import parse_api, utc_from_timestamp
from .const import DOMAIN
from .helper import as_local, b2gib
from .truenas_api import TrueNASAPI

_LOGGER = getLogger(__name__)


# ---------------------------
#   TrueNASControllerData
# ---------------------------
class TrueNASControllerData(object):
    """TrueNASControllerData Class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize TrueNASController."""
        self.hass = hass
        self.config_entry = config_entry
        self.name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]

        self.data = {
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

        self.listeners = []
        self.lock = Asyncio_lock()

        self.api = TrueNASAPI(
            hass,
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_API_KEY],
            config_entry.data[CONF_SSL],
            config_entry.data[CONF_VERIFY_SSL],
        )

        self._systemstats_errored = []
        self.datasets_hass_device_id = None

        self._force_update_callback = None
        self._is_scale = False
        self._is_virtual = False

    # ---------------------------
    #   async_init
    # ---------------------------
    async def async_init(self) -> None:
        """Initialize."""
        self._force_update_callback = async_track_time_interval(
            self.hass, self.force_update, timedelta(seconds=60)
        )

    # ---------------------------
    #   signal_update
    # ---------------------------
    @property
    def signal_update(self) -> str:
        """Event to signal new data."""
        return f"{DOMAIN}-update-{self.name}"

    # ---------------------------
    #   async_reset
    # ---------------------------
    async def async_reset(self) -> bool:
        """Reset dispatchers."""
        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()

        self.listeners = []
        return True

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self) -> str:
        """Return connected state."""
        return self.api.connected()

    # ---------------------------
    #   force_update
    # ---------------------------
    @callback
    async def force_update(self, _now=None) -> None:
        """Trigger update by timer."""
        await self.async_update()

    # ---------------------------
    #   async_update
    # ---------------------------
    async def async_update(self):
        """Update TrueNAS data."""
        try:
            await asyncio_wait_for(self.lock.acquire(), timeout=10)
        except Exception:
            return

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
        if self.api.connected() and self._is_scale:
            await self.hass.async_add_executor_job(self.get_app)

        async_dispatcher_send(self.hass, self.signal_update)
        self.lock.release()

    # ---------------------------
    #   get_systeminfo
    # ---------------------------
    def get_systeminfo(self) -> None:
        """Get system info from TrueNAS."""
        self.data["system_info"] = parse_api(
            data=self.data["system_info"],
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
                {"name": "cache_size-L2_value", "default": 0.0},
                {"name": "cache_ratio-arc_value", "default": 0},
                {"name": "cache_ratio-L2_value", "default": 0},
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

        self.data["system_info"] = parse_api(
            data=self.data["system_info"],
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

        self.data["system_info"]["update_available"] = (
            self.data["system_info"]["update_status"] == "AVAILABLE"
        )

        if not self.data["system_info"]["update_available"]:
            self.data["system_info"]["update_version"] = self.data["system_info"][
                "version"
            ]

        if self.data["system_info"]["update_jobid"]:
            self.data["system_info"] = parse_api(
                data=self.data["system_info"],
                source=self.api.query(
                    "core/get_jobs",
                    method="get",
                    params={"id": self.data["system_info"]["update_jobid"]},
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
                self.data["system_info"]["update_state"] != "RUNNING"
                or not self.data["system_info"]["update_available"]
            ):
                self.data["system_info"]["update_progress"] = 0
                self.data["system_info"]["update_jobid"] = 0
                self.data["system_info"]["update_state"] = "unknown"

        self._is_scale = bool(
            self.data["system_info"]["version"].startswith("TrueNAS-SCALE-")
        )

        self._is_virtual = self.data["system_info"]["system_manufacturer"] in [
            "QEMU",
            "VMware, Inc.",
        ] or self.data["system_info"]["system_product"] in [
            "VirtualBox",
        ]

        if self.data["system_info"]["uptime_seconds"] > 0:
            now = datetime.now().replace(microsecond=0)
            uptime_tm = datetime.timestamp(
                now - timedelta(seconds=int(self.data["system_info"]["uptime_seconds"]))
            )
            self.data["system_info"]["uptimeEpoch"] = str(
                as_local(utc_from_timestamp(uptime_tm)).isoformat()
            )

        self.data["interface"] = parse_api(
            data=self.data["interface"],
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
                {"name": "arcratio"},
                {"name": "memory"},
            ],
            "reporting_query": {
                "start": "now-90s",
                "end": "now-30s",
                "aggregate": True,
            },
        }

        for uid, vals in self.data["interface"].items():
            tmp_params["graphs"].append({"name": "interface", "identifier": uid})

        if self._is_virtual:
            tmp_params["graphs"].remove({"name": "cputemp"})

        for tmp in tmp_params["graphs"]:
            if tmp["name"] in self._systemstats_errored:
                tmp_params["graphs"].remove(tmp)

        if not tmp_params["graphs"]:
            return

        tmp_graph = self.api.query(
            "reporting/get_data",
            method="post",
            params=tmp_params,
        )

        if not isinstance(tmp_graph, list):
            if self.api.error == 500:
                for tmp in tmp_params["graphs"]:
                    tmp2 = self.api.query(
                        "reporting/get_data",
                        method="post",
                        params={
                            "graphs": [
                                tmp,
                            ],
                            "reporting_query": {
                                "start": "now-90s",
                                "end": "now-30s",
                                "aggregate": True,
                            },
                        },
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
                    self.data["system_info"]["cpu_temperature"] = round(
                        max(list(filter(None, tmp_graph[i]["aggregations"]["mean"]))), 1
                    )
                else:
                    self.data["system_info"]["cpu_temperature"] = 0.0

            # CPU load
            if tmp_graph[i]["name"] == "load":
                tmp_arr = ("load_shortterm", "load_midterm", "load_longterm")
                self._systemstats_process(tmp_arr, tmp_graph[i], "")

            # CPU usage
            if tmp_graph[i]["name"] == "cpu":
                tmp_arr = ("interrupt", "system", "user", "nice", "idle")
                self._systemstats_process(tmp_arr, tmp_graph[i], "cpu")
                self.data["system_info"]["cpu_usage"] = round(
                    self.data["system_info"]["cpu_system"]
                    + self.data["system_info"]["cpu_user"],
                    2,
                )

            # Interface
            if tmp_graph[i]["name"] == "interface":
                tmp_etc = tmp_graph[i]["identifier"]
                if tmp_etc in self.data["interface"]:
                    # 12->13 API change
                    tmp_graph[i]["legend"] = [
                        tmp.replace("if_octets_", "") for tmp in tmp_graph[i]["legend"]
                    ]
                    tmp_arr = ("rx", "tx")
                    if "aggregations" in tmp_graph[i]:
                        for e in range(len(tmp_graph[i]["legend"])):
                            tmp_var = tmp_graph[i]["legend"][e]
                            if tmp_var in tmp_arr:
                                tmp_val = tmp_graph[i]["aggregations"]["mean"][e] or 0.0
                                self.data["interface"][tmp_etc][tmp_var] = round(
                                    (tmp_val / 1024), 2
                                )
                    else:
                        for tmp_load in tmp_arr:
                            self.data["interface"][tmp_etc][tmp_load] = 0.0

            # arcratio
            if tmp_graph[i]["name"] == "memory":
                tmp_arr = (
                    "memory-used_value",
                    "memory-free_value",
                    "memory-cached_value",
                    "memory-buffered_value",
                )
                self._systemstats_process(tmp_arr, tmp_graph[i], "memory")
                self.data["system_info"]["memory-total_value"] = round(
                    self.data["system_info"]["memory-used_value"]
                    + self.data["system_info"]["memory-free_value"]
                    + self.data["system_info"]["cache_size-arc_value"],
                    2,
                )
                if self.data["system_info"]["memory-total_value"] > 0:
                    self.data["system_info"]["memory-usage_percent"] = round(
                        100
                        * (
                            float(self.data["system_info"]["memory-total_value"])
                            - float(self.data["system_info"]["memory-free_value"])
                        )
                        / float(self.data["system_info"]["memory-total_value"]),
                        0,
                    )

            # arcsize
            if tmp_graph[i]["name"] == "arcsize":
                tmp_arr = ("cache_size-arc_value", "cache_size-L2_value")
                self._systemstats_process(tmp_arr, tmp_graph[i], "memory")

            # arcratio
            if tmp_graph[i]["name"] == "arcratio":
                tmp_arr = ("cache_ratio-arc_value", "cache_ratio-L2_value")
                self._systemstats_process(tmp_arr, tmp_graph[i], "")

    # ---------------------------
    #   _systemstats_process
    # ---------------------------
    def _systemstats_process(self, arr, graph, t) -> None:
        if "aggregations" in graph:
            for e in range(len(graph["legend"])):
                tmp_var = graph["legend"][e]
                if tmp_var in arr:
                    tmp_val = graph["aggregations"]["mean"][e] or 0.0
                    if t == "memory":
                        self.data["system_info"][tmp_var] = b2gib(tmp_val)
                    elif t == "cpu":
                        self.data["system_info"][f"cpu_{tmp_var}"] = round(tmp_val, 2)
                    else:
                        self.data["system_info"][tmp_var] = round(tmp_val, 2)
        else:
            for tmp_load in arr:
                if t == "cpu":
                    self.data["system_info"][f"cpu_{tmp_load}"] = 0.0
                else:
                    self.data["system_info"][tmp_load] = 0.0

    # ---------------------------
    #   get_service
    # ---------------------------
    def get_service(self) -> None:
        """Get service info from TrueNAS."""
        self.data["service"] = parse_api(
            data=self.data["service"],
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

        for uid, vals in self.data["service"].items():
            self.data["service"][uid]["running"] = vals["state"] == "RUNNING"

    # ---------------------------
    #   get_pool
    # ---------------------------
    def get_pool(self) -> None:
        """Get pools from TrueNAS."""
        self.data["pool"] = parse_api(
            data=self.data["pool"],
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
            ],
        )

        self.data["pool"] = parse_api(
            data=self.data["pool"],
            source=self.api.query("boot/get_state"),
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
            ],
            ensure_vals=[
                {"name": "available_gib", "default": 0.0},
                {"name": "total_gib", "default": 0.0},
            ],
        )

        # Process pools
        tmp_dataset_available = {}
        tmp_dataset_total = {}
        for uid, vals in self.data["dataset"].items():
            tmp_dataset_available[self.data["dataset"][uid]["mountpoint"]] = b2gib(
                vals["available"]
            )
            tmp_dataset_total[self.data["dataset"][uid]["mountpoint"]] = b2gib(
                vals["available"] + vals["used"]
            )

        for uid, vals in self.data["pool"].items():
            if vals["path"] in tmp_dataset_available:
                self.data["pool"][uid]["available_gib"] = tmp_dataset_available[
                    vals["path"]
                ]

            if vals["path"] in tmp_dataset_total:
                self.data["pool"][uid]["total_gib"] = tmp_dataset_total[vals["path"]]

            if vals["name"] in ["boot-pool", "freenas-boot"]:
                self.data["pool"][uid]["available_gib"] = b2gib(
                    vals["root_dataset_available"]
                )
                self.data["pool"][uid]["total_gib"] = b2gib(
                    vals["root_dataset_available"] + vals["root_dataset_used"]
                )
                self.data["pool"][uid].pop("root_dataset")

    # ---------------------------
    #   get_dataset
    # ---------------------------
    def get_dataset(self) -> None:
        """Get datasets from TrueNAS."""
        self.data["dataset"] = parse_api(
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

        for uid, vals in self.data["dataset"].items():
            self.data["dataset"][uid]["used_gb"] = b2gib(vals["used"])

        if len(self.data["dataset"]) == 0:
            return

        entities_to_be_removed = []
        if not self.datasets_hass_device_id:
            device_registry = dr.async_get(self.hass)
            for device in device_registry.devices.values():
                if (
                    self.config_entry.entry_id in device.config_entries
                    and device.name.endswith(" Datasets")
                ):
                    self.datasets_hass_device_id = device.id
                    _LOGGER.debug(f"datasets device: {device.name}")

            if not self.datasets_hass_device_id:
                return

        _LOGGER.debug(f"datasets_hass_device_id: {self.datasets_hass_device_id}")
        entity_registry = er.async_get(self.hass)
        entity_entries = async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )
        for entity in entity_entries:
            if (
                entity.device_id == self.datasets_hass_device_id
                and entity.unique_id.removeprefix(f"{self.name.lower()}-dataset-")
                not in map(str.lower, self.data["dataset"].keys())
            ):
                _LOGGER.debug(f"dataset to be removed: {entity.unique_id}")
                entities_to_be_removed.append(entity.entity_id)

        for entity_id in entities_to_be_removed:
            entity_registry.async_remove(entity_id)

    # ---------------------------
    #   get_disk
    # ---------------------------
    def get_disk(self) -> None:
        """Get disks from TrueNAS."""
        self.data["disk"] = parse_api(
            data=self.data["disk"],
            source=self.api.query("disk"),
            key="devname",
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
            for uid in self.data["disk"]:
                if uid in temps:
                    self.data["disk"][uid]["temperature"] = temps[uid]

    # ---------------------------
    #   get_jail
    # ---------------------------
    def get_jail(self) -> None:
        """Get jails from TrueNAS."""
        if self._is_scale:
            return

        self.data["jail"] = parse_api(
            data=self.data["jail"],
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
        self.data["vm"] = parse_api(
            data=self.data["vm"],
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

        for uid, vals in self.data["vm"].items():
            self.data["vm"][uid]["running"] = vals["state"] == "RUNNING"

    # ---------------------------
    #   get_cloudsync
    # ---------------------------
    def get_cloudsync(self) -> None:
        """Get cloudsync from TrueNAS."""
        self.data["cloudsync"] = parse_api(
            data=self.data["cloudsync"],
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
        self.data["replication"] = parse_api(
            data=self.data["replication"],
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
        self.data["snapshottask"] = parse_api(
            data=self.data["snapshottask"],
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
    def get_app(self):
        """Get Apps from TrueNAS."""
        self.data["app"] = parse_api(
            data=self.data["app"],
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

        for uid, vals in self.data["app"].items():
            self.data["app"][uid]["running"] = vals["status"] == "ACTIVE"
