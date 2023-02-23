"""Constants used by the TrueNAS integration."""
from homeassistant.const import Platform

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.UPDATE,
]

DOMAIN = "truenas"
DEFAULT_NAME = "root"
ATTRIBUTION = "Data provided by TrueNAS integration"

DEFAULT_HOST = "10.0.0.1"
DEFAULT_USERNAME = "admin"

DEFAULT_DEVICE_NAME = "TrueNAS"
DEFAULT_SSL = False
DEFAULT_SSL_VERIFY = True

TO_REDACT = {
    "username",
    "password",
    "encryption_password",
    "encryption_salt",
    "host",
    "api_key",
    "serial",
    "system_serial",
    "ip4_addr",
    "ip6_addr",
    "account",
    "key",
}

SERVICE_CLOUDSYNC_RUN = "cloudsync_run"
SCHEMA_SERVICE_CLOUDSYNC_RUN = {}

SERVICE_DATASET_SNAPSHOT = "dataset_snapshot"
SCHEMA_SERVICE_DATASET_SNAPSHOT = {}

SERVICE_SYSTEM_REBOOT = "system_reboot"
SCHEMA_SERVICE_SYSTEM_REBOOT = {}

SERVICE_SYSTEM_SHUTDOWN = "system_shutdown"
SCHEMA_SERVICE_SYSTEM_SHUTDOWN = {}

SERVICE_SERVICE_START = "service_start"
SCHEMA_SERVICE_SERVICE_START = {}
SERVICE_SERVICE_STOP = "service_stop"
SCHEMA_SERVICE_SERVICE_STOP = {}
SERVICE_SERVICE_RESTART = "service_restart"
SCHEMA_SERVICE_SERVICE_RESTART = {}
SERVICE_SERVICE_RELOAD = "service_reload"
SCHEMA_SERVICE_SERVICE_RELOAD = {}

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

SERVICE_APP_START = "app_start"
SCHEMA_SERVICE_APP_START = {}
SERVICE_APP_STOP = "app_stop"
SCHEMA_SERVICE_APP_STOP = {}
