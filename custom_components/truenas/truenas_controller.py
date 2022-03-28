"""TrueNAS Controller"""
from asyncio import wait_for as asyncio_wait_for, Lock as Asyncio_lock
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
from .apiparser import parse_api, utc_from_timestamp
from .truenas_api import TrueNASAPI
from .helper import as_local, b2gib


# ---------------------------
#   TrueNASControllerData
# ---------------------------
class TrueNASControllerData(object):
    """TrueNASControllerData Class"""

    def __init__(self, hass, config_entry):
        """Initialize TrueNASController"""
        self.hass = hass
        self.config_entry = config_entry
        self.name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]

        self.data = {
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

        self._force_update_callback = None
        self._is_scale = False
        self._is_virtual = False

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
        """Event to signal new data"""
        return f"{DOMAIN}-update-{self.name}"

    # ---------------------------
    #   async_reset
    # ---------------------------
    async def async_reset(self):
        """Reset dispatchers"""
        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()

        self.listeners = []
        return True

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self):
        """Return connected state"""
        return self.api.connected()

    # ---------------------------
    #   force_update
    # ---------------------------
    @callback
    async def force_update(self, _now=None):
        """Trigger update by timer"""
        await self.async_update()

    # ---------------------------
    #   async_update
    # ---------------------------
    async def async_update(self):
        """Update TrueNAS data"""
        try:
            await asyncio_wait_for(self.lock.acquire(), timeout=10)
        except:
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

        async_dispatcher_send(self.hass, self.signal_update)
        self.lock.release()

    # ---------------------------
    #   get_systeminfo
    # ---------------------------
    def get_systeminfo(self):
        """Get system info from TrueNAS"""
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

        self._is_scale = bool(
            self.data["system_info"]["version"].startswith("TrueNAS-SCALE-")
        )

        self._is_virtual = self.data["system_info"]["system_product"] in [
            "VirtualBox",
            "VMware Virtual Platform",
        ]

        if self.data["system_info"]["uptime_seconds"] > 0:
            now = datetime.now().replace(microsecond=0)
            uptime_tm = datetime.timestamp(
                now - timedelta(seconds=int(self.data["system_info"]["uptime_seconds"]))
            )
            self.data["system_info"]["uptimeEpoch"] = str(
                as_local(utc_from_timestamp(uptime_tm)).isoformat()
            )

    # ---------------------------
    #   get_systemstats
    # ---------------------------
    def get_systemstats(self):
        # Get graphs
        tmp_params = {
            "graphs": [
                {"name": "load"},
                {"name": "cputemp"},
                {"name": "cpu"},
                {"name": "arcsize"},
                {"name": "arcratio"},
            ],
            "reporting_query": {
                "start": "now-90s",
                "end": "now-30s",
                "aggregate": True,
            },
        }

        if self._is_virtual:
            tmp_params["graphs"].remove({"name": "cputemp"})

        tmp_graph = self.api.query(
            "reporting/get_data",
            method="post",
            params=tmp_params,
        )

        if not isinstance(tmp_graph, list):
            return

        for i in range(len(tmp_graph)):
            if "name" not in tmp_graph[i]:
                continue

            # CPU temperature
            if tmp_graph[i]["name"] == "cputemp":
                if "aggregations" in tmp_graph[i]:
                    self.data["system_info"]["cpu_temperature"] = round(
                        max(tmp_graph[i]["aggregations"]["mean"]), 1
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

            # arcsize
            if tmp_graph[i]["name"] == "arcsize":
                tmp_arr = ("cache_size-arc_value", "cache_size-L2_value")
                self._systemstats_process(tmp_arr, tmp_graph[i], "arcsize")

            # arcratio
            if tmp_graph[i]["name"] == "arcratio":
                tmp_arr = ("cache_ratio-arc_value", "cache_ratio-L2_value")
                self._systemstats_process(tmp_arr, tmp_graph[i], "")

    # ---------------------------
    #   _systemstats_process
    # ---------------------------
    def _systemstats_process(self, arr, graph, t):
        if "aggregations" in graph:
            for e in range(len(graph["legend"])):
                tmp_var = graph["legend"][e]
                if tmp_var in arr:
                    tmp_val = graph["aggregations"]["mean"][e] or 0.0
                    if t == "arcsize":
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
    def get_service(self):
        """Get service info from TrueNAS"""
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
    def get_pool(self):
        """Get pools from TrueNAS"""
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
                },
                {
                    "name": "scrub_end",
                    "source": "scan/end_time/$date",
                    "default": 0,
                },
                {
                    "name": "scrub_secs_left",
                    "source": "scan/total_secs_left",
                    "default": 0,
                },
            ],
            ensure_vals=[
                {"name": "available_gib", "default": 0.0},
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
            ],
        )

        # Process pools
        tmp_dataset = {
            self.data["dataset"][uid]["mountpoint"]: b2gib(vals["available"])
            for uid, vals in self.data["dataset"].items()
        }

        for uid, vals in self.data["pool"].items():
            if vals["path"] in tmp_dataset:
                self.data["pool"][uid]["available_gib"] = tmp_dataset[vals["path"]]

            if vals["name"] == "boot-pool":
                self.data["pool"][uid]["available_gib"] = b2gib(
                    vals["root_dataset_available"]
                )
                self.data["pool"][uid].pop("root_dataset")

    # ---------------------------
    #   get_dataset
    # ---------------------------
    def get_dataset(self):
        """Get datasets from TrueNAS"""
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

    # ---------------------------
    #   get_disk
    # ---------------------------
    def get_disk(self):
        """Get disks from TrueNAS"""
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
        for uid in self.data["disk"]:
            if uid in temps:
                self.data["disk"][uid]["temperature"] = temps[uid]

    # ---------------------------
    #   get_jail
    # ---------------------------
    def get_jail(self):
        """Get jails from TrueNAS"""
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
    def get_vm(self):
        """Get VMs from TrueNAS"""
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
    def get_cloudsync(self):
        """Get cloudsync from TrueNAS"""
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
    def get_replication(self):
        """Get replication from TrueNAS"""
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
    def get_snapshottask(self):
        """Get replication from TrueNAS"""
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
