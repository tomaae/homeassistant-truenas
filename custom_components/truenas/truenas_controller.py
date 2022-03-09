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
            "pool": {},
            "dataset": {},
            "system_info": {},
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
            await self.hass.async_add_executor_job(self.get_pool)
        if self.api.connected():
            await self.hass.async_add_executor_job(self.get_dataset)

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
            ensure_vals=[{"name": "uptimeEpoch", "default": 0}],
        )

        now = datetime.now().replace(microsecond=0)
        uptime_tm = datetime.timestamp(
            now - timedelta(seconds=int(self.data["system_info"]["uptime_seconds"]))
        )
        self.data["system_info"]["uptimeEpoch"] = str(
            as_local(utc_from_timestamp(uptime_tm)).isoformat()
        )

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
