"""TrueNAS API."""

from logging import getLogger
from threading import Lock
from typing import Any

from voluptuous import Optional
import ssl
import json
from websockets.sync.client import connect, ClientConnection

from homeassistant.core import HomeAssistant

_LOGGER = getLogger(__name__)


# ---------------------------
#   TrueNASAPI
# ---------------------------
class TrueNASAPI(object):
    """Handle all communication with TrueNAS."""

    _ws: ClientConnection

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        api_key: str,
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the TrueNAS API."""
        self._hass = hass
        self._host = host
        self._api_key = api_key
        self._ssl_verify = verify_ssl
        self._url = f"wss://{self._host}/api/current"
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        if verify_ssl:
            self._ssl_context.check_hostname = True
            self._ssl_context.verify_mode = ssl.CERT_REQUIRED
        else:
            self._ssl_context.check_hostname = False
            self._ssl_context.verify_mode = ssl.CERT_NONE

        self.lock = Lock()
        self._connected = False
        self._error = ""
        self.connect()

    # ---------------------------
    #   connect
    # ---------------------------
    def connect(self) -> bool:
        """Return connected boolean."""
        self.lock.acquire()
        self._connected = False
        self._error = ""
        try:
            self._ws = connect(self._url, ssl=self._ssl_context)
        except Exception as e:
            if "Connection refused" in e.args:
                self._error = "connection_refused"

            if "No route to host" in e.args:
                self._error = "invalid_hostname"

            if "timed out while waiting for handshake response" in e.args:
                self._error = "handshake_timeout"

            if "404" in str(e):
                self._error = "api_not_found"

            _LOGGER.error("TrueNAS %s failed to connect (%s)", self._host, e)
            self.lock.release()
            return False

        try:
            payload = {
                "method": "auth.login_with_api_key",
                "jsonrpc": "2.0",
                "id": 0,
                "params": [self._api_key],
            }
            self._ws.send(json.dumps(payload))
            message = self._ws.recv()
            data = json.loads(message)
            self._connected = data["result"]
            if not self._connected:
                self._error = "invalid_key"

        except Exception as e:
            _LOGGER.error("TrueNAS %s failed to login (%s)", self._host, e)
            self.lock.release()
            return False

        self.lock.release()
        return self._connected

    # ---------------------------
    #   disconnect
    # ---------------------------
    def disconnect(self) -> bool:
        """Return connected boolean."""
        self._ws.close()
        self._connected = False
        return self._connected

    # ---------------------------
    #   reconnect
    # ---------------------------
    def reconnect(self) -> bool:
        """Return connected boolean."""
        self.disconnect()
        self.connect()
        return self._connected

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self) -> bool:
        """Return connected boolean."""
        return self._connected

    # ---------------------------
    #   connection_test
    # ---------------------------
    def connection_test(self) -> tuple:
        """Test connection."""
        self.query("system.info")

        return self._connected, self._error

    # ---------------------------
    #   query
    # ---------------------------
    def query(
        self, service: str, method: str = "get", params: dict[str, Any] | None = {}
    ) -> Optional(list):
        """Retrieve data from TrueNAS."""
        self.lock.acquire()
        self._error = ""
        try:
            _LOGGER.debug(
                "TrueNAS %s query: %s, %s, %s",
                self._host,
                service,
                method,
                params,
            )
            payload = {
                "method": service,
                "jsonrpc": "2.0",
                "id": 0,
                "params": [],
            }
            if params != {}:
                payload["params"] = [params]

            self._ws.send(json.dumps(payload))
            message = self._ws.recv()
            data = json.loads(message)
            if "result" in data:
                data = data["result"]
            else:
                self._error = "malformed_result"

            _LOGGER.debug(
                "TrueNAS %s query (%s) response: %s", self._host, service, data
            )
        except Exception as e:
            _LOGGER.warning(
                'TrueNAS %s unable to fetch data "%s" (%s)',
                self._host,
                service,
                e,
            )
            self._error = e
            self.lock.release()
            return None

        self.lock.release()
        return data

    @property
    def error(self):
        """Return error."""
        return self._error
