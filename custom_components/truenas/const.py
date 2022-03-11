"""Constants used by the TrueNAS integration."""
from homeassistant.const import Platform

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

DOMAIN = "truenas"
DEFAULT_NAME = "root"
ATTRIBUTION = "Data provided by TrueNAS integration"

DEFAULT_HOST = "10.0.0.1"
DEFAULT_USERNAME = "admin"

DEFAULT_DEVICE_NAME = "TrueNAS"
DEFAULT_SSL = False
DEFAULT_SSL_VERIFY = True

SERVICE_CLOUDSYNC_RUN = "cloudsync_run"
SCHEMA_SERVICE_CLOUDSYNC_RUN = {}

SERVICE_JAIL_START = "jail_start"
SCHEMA_SERVICE_JAIL_START = {}
SERVICE_JAIL_STOP = "jail_stop"
SCHEMA_SERVICE_JAIL_STOP = {}
SERVICE_JAIL_RESTART = "jail_restart"
SCHEMA_SERVICE_JAIL_RESTART = {}

SERVICE_VM_START = "vm_start"
SCHEMA_SERVICE_VM_START = {}
SERVICE_VM_STOP = "vm_stop"
SCHEMA_SERVICE_VM_STOP = {}
