"""TrueNAS Controller."""

import asyncio
import pytz
from datetime import datetime, timedelta

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_API_KEY,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .helper import parse_api
from .truenas_api import TrueNASAPI

DEFAULT_TIME_ZONE = None


def utc_from_timestamp(timestamp: float) -> datetime:
    """Return a UTC time from a timestamp."""
    return pytz.utc.localize(datetime.utcfromtimestamp(timestamp))


def as_local(dattim: datetime) -> datetime:
    """Convert a UTC datetime object to local time zone."""
    if dattim.tzinfo == DEFAULT_TIME_ZONE:
        return dattim
    if dattim.tzinfo is None:
        dattim = pytz.utc.localize(dattim)

    return dattim.astimezone(DEFAULT_TIME_ZONE)


# ---------------------------
#   TrueNASControllerData
# ---------------------------
class TrueNASControllerData(object):
    """TrueNASControllerData Class."""

    def __init__(self, hass, config_entry):
        """Initialize OMVController."""
        self.hass = hass
        self.config_entry = config_entry
        self.name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]

        self.data = {
            "disk": {},
            "pool": {},
            "dataset": {},
            "system_info": {},
            "jail": {},
        }

        self.listeners = []
        self.lock = asyncio.Lock()

        self.api = TrueNASAPI(
            hass,
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_API_KEY],
            config_entry.data[CONF_SSL],
            config_entry.data[CONF_VERIFY_SSL],
        )

        self._force_update_callback = None

    # ---------------------------
    #   async_init
    # ---------------------------
    async def async_init(self):
        self._force_update_callback = async_track_time_interval(
            self.hass, self.force_update, timedelta(seconds=60)
        )

    # ---------------------------
    #   signal_update
    # ---------------------------
    @property
    def signal_update(self):
        """Event to signal new data."""
        return f"{DOMAIN}-update-{self.name}"

    # ---------------------------
    #   async_reset
    # ---------------------------
    async def async_reset(self):
        """Reset dispatchers."""
        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()

        self.listeners = []
        return True

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self):
        """Return connected state."""
        return self.api.connected()

    # ---------------------------
    #   force_update
    # ---------------------------
    @callback
    async def force_update(self, _now=None):
        """Trigger update by timer."""
        await self.async_update()

    # ---------------------------
    #   async_update
    # ---------------------------
    async def async_update(self):
        """Update TrueNAS data."""
        try:
            await asyncio.wait_for(self.lock.acquire(), timeout=10)
        except:
            return

        await self.hass.async_add_executor_job(self.get_systeminfo)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_disk)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_pool)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_dataset)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_jail)

        async_dispatcher_send(self.hass, self.signal_update)
        self.lock.release()

    # ---------------------------
    #   get_systeminfo
    # ---------------------------
    def get_systeminfo(self):
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
            ],
        )

        now = datetime.now().replace(microsecond=0)
        uptime_tm = datetime.timestamp(
            now - timedelta(seconds=int(self.data["system_info"]["uptime_seconds"]))
        )
        self.data["system_info"]["uptimeEpoch"] = str(
            as_local(utc_from_timestamp(uptime_tm)).isoformat()
        )

        # Get graphs
        tmp_graph = self.api.query(
            "reporting/get_data",
            method="post",
            params={
                "graphs": [
                    {"name": "load"},
                    {"name": "cputemp"},
                    {"name": "cpu"},
                    {"name": "arcsize"},
                    {"name": "arcratio"},
                ],
                "reporting_query": {
                    "start": "now-60s",
                    "end": "now-30s",
                    "aggregate": True,
                },
            },
        )
        if not isinstance(tmp_graph, list):
            return

        for i in range(len(tmp_graph)):
            if "name" not in tmp_graph[i]:
                continue

            # CPU load
            if tmp_graph[i]["name"] == "load":
                if "aggregations" in tmp_graph[i]:
                    tmp_list = {}
                    for e in range(len(tmp_graph[i]["legend"])):
                        tmp_list[tmp_graph[i]["legend"][e]] = tmp_graph[i][
                            "aggregations"
                        ]["mean"][e]

                    for tmp_load in ("load_shortterm", "load_midterm", "load_longterm"):
                        if tmp_load in tmp_list:
                            self.data["system_info"][tmp_load] = round(
                                tmp_list[tmp_load], 2
                            )
                else:
                    for tmp_load in ("load_shortterm", "load_midterm", "load_longterm"):
                        self.data["system_info"][tmp_load] = 0.0

            # CPU temperature
            if tmp_graph[i]["name"] == "cputemp":
                if "aggregations" in tmp_graph[i]:
                    self.data["system_info"]["cpu_temperature"] = round(
                        max(tmp_graph[i]["aggregations"]["mean"]), 1
                    )
                else:
                    self.data["system_info"]["cpu_temperature"] = 0.0

            # CPU load
            if tmp_graph[i]["name"] == "cpu":
                if "aggregations" in tmp_graph[i]:
                    tmp_list = {}
                    for e in range(len(tmp_graph[i]["legend"])):
                        tmp_list[tmp_graph[i]["legend"][e]] = tmp_graph[i][
                            "aggregations"
                        ]["mean"][e]

                    for tmp_load in ("interrupt", "system", "user", "nice", "idle"):
                        if tmp_load in tmp_list:
                            self.data["system_info"][f"cpu_{tmp_load}"] = round(
                                tmp_list[tmp_load], 2
                            )
                    self.data["system_info"]["cpu_usage"] = round(
                        self.data["system_info"]["cpu_system"]
                        + self.data["system_info"]["cpu_user"],
                        2,
                    )
                else:
                    for tmp_load in ("interrupt", "system", "user", "nice", "idle"):
                        self.data["system_info"][f"cpu_{tmp_load}"] = 0.0
                        self.data["system_info"]["cpu_usage"] = 0.0

            # arcsize
            if tmp_graph[i]["name"] == "arcsize":
                if "aggregations" in tmp_graph[i]:
                    tmp_list = {}
                    for e in range(len(tmp_graph[i]["legend"])):
                        tmp_list[tmp_graph[i]["legend"][e]] = tmp_graph[i][
                            "aggregations"
                        ]["mean"][e]

                    for tmp_load in ("cache_size-arc_value", "cache_size-L2_value"):
                        if tmp_load in tmp_list:
                            if not tmp_list[tmp_load]:
                                tmp_list[tmp_load] = 0

                            self.data["system_info"][tmp_load] = round(
                                tmp_list[tmp_load] / 1073741824, 2
                            )
                else:
                    for tmp_load in ("cache_size-arc_value", "cache_size-L2_value"):
                        self.data["system_info"][tmp_load] = 0.0

            # arcratio
            if tmp_graph[i]["name"] == "arcratio":
                if "aggregations" in tmp_graph[i]:
                    tmp_list = {}
                    for e in range(len(tmp_graph[i]["legend"])):
                        tmp_list[tmp_graph[i]["legend"][e]] = tmp_graph[i][
                            "aggregations"
                        ]["mean"][e]

                    for tmp_load in ("cache_ratio-arc_value", "cache_ratio-L2_value"):
                        if tmp_load in tmp_list:
                            if not tmp_list[tmp_load]:
                                tmp_list[tmp_load] = 0

                            self.data["system_info"][tmp_load] = round(
                                tmp_list[tmp_load], 2
                            )
                else:
                    for tmp_load in ("cache_ratio-arc_value", "cache_ratio-L2_value"):
                        self.data["system_info"][tmp_load] = 0.0

    # ---------------------------
    #   get_pool
    # ---------------------------
    def get_pool(self):
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
            ],
        )

    # ---------------------------
    #   get_dataset
    # ---------------------------
    def get_dataset(self):
        """Get datasets from TrueNAS."""
        self.data["dataset"] = parse_api(
            data=self.data["dataset"],
            source=self.api.query("pool/dataset"),
            key="id",
            vals=[
                {"name": "id", "default": "unknown"},
                {"name": "type", "default": "unknown"},
                {"name": "name", "default": "unknown"},
                {"name": "pool", "default": "unknown"},
                {"name": "mountpoint", "default": "unknown"},
                {"name": "comments", "default": ""},
                {"name": "deduplication", "default": "unknown"},
                {"name": "atime", "type": "bool", "default": False},
                {"name": "casesensitivity", "default": "unknown"},
                {"name": "checksum", "default": "unknown"},
                {"name": "exec", "type": "bool", "default": False},
                {"name": "sync", "default": "unknown"},
                {"name": "compression", "default": "unknown"},
                {"name": "compressratio", "default": "unknown"},
                {"name": "quota", "default": "unknown"},
                {"name": "copies", "default": 0},
                {"name": "readonly", "type": "bool", "default": False},
                {"name": "recordsize", "default": 0},
                {"name": "encryption_algorithm", "default": "unknown"},
                {"name": "used", "default": 0},
                {"name": "available", "default": 0},
            ],
            ensure_vals=[
                {"name": "usage", "default": 0},
            ],
        )

        for uid in self.data["dataset"]:
            used = self.data["dataset"][uid]["used"]
            total = self.data["dataset"][uid]["available"] + used
            self.data["dataset"][uid]["usage"] = round((total - used) / total * 100, 2)

    # ---------------------------
    #   get_disk
    # ---------------------------
    def get_disk(self):
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

        temps = self.api.query(
            "disk/temperatures",
            method="post",
            params={"names": []},
        )

        for uid in self.data["disk"]:
            if uid in temps:
                self.data["disk"][uid]["temperature"] = temps[uid]

    # ---------------------------
    #   get_jail
    # ---------------------------
    def get_jail(self):
        """Get jails from TrueNAS."""
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
                {"name": "state", "default": "unknown"},
                {"name": "type", "default": "unknown"},
                {"name": "plugin_name", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "running", "type": "bool", "default": False},
            ],
        )

        for uid in self.data["jail"]:
            if self.data["jail"][uid]["state"] == "up":
                self.data["jail"][uid]["running"] = True
