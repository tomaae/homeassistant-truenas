"""TrueNAS API."""

from logging import getLogger
from threading import Lock
from typing import Any

import ssl
import json
from websockets.sync.client import connect, ClientConnection

_LOGGER = getLogger(__name__)


# ---------------------------
#   TrueNASAPI
# ---------------------------
class TrueNASAPI(object):
    """Handle all communication with TrueNAS."""

    _ws: ClientConnection

    def __init__(
        self,
        host: str,
        api_key: str,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the TrueNAS API."""
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
        self._error_logged = False

    # ---------------------------
    #   connect
    # ---------------------------
    def connect(self) -> bool:
        """Return connected boolean."""
        with self.lock:
            self._connected = False
            self._error = ""
            try:
                self._ws = connect(
                    self._url,
                    ssl=self._ssl_context,
                    max_size=16777216,
                    ping_interval=20,
                )
            except Exception as e:
                if "CERTIFICATE_VERIFY_FAILED" in str(e.args):
                    self._error = "certificate_verify_failed"

                if "The plain HTTP request was sent to HTTPS port" in str(e.args):
                    self._error = "http_used"

                if "TLSV1_UNRECOGNIZED_NAME" in str(e.args):
                    self._error = "tlsv1_not_supported"

                if "No WebSocket UPGRADE" in str(e.args):
                    self._error = "websocket_not_supported"

                if "No address associated with hostname" in e.args:
                    self._error = "unknown_hostname"

                if "Connection refused" in e.args:
                    self._error = "connection_refused"

                if "No route to host" in e.args or "Name or service not known" in str(
                    e
                ):
                    self._error = "invalid_hostname"

                if "timed out while waiting for handshake response" in e.args:
                    self._error = "handshake_timeout"

                if "404" in str(e):
                    self._error = "api_not_found"

                if not self._error_logged:
                    _LOGGER.error("TrueNAS %s failed to connect (%s)", self._host, e)

                self._error_logged = True
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
                if not self._error_logged:
                    _LOGGER.error("TrueNAS %s failed to login (%s)", self._host, e)

                self._error_logged = True
                return False

            self._error_logged = False
            return self._connected

    # ---------------------------
    #   disconnect
    # ---------------------------
    def disconnect(self) -> bool:
        """Return connected boolean."""
        if hasattr(self, "_ws") and self._ws:
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
        self.connect()
        if self.connected():
            self.query("system.info")

        return self._connected, self._error

    # ---------------------------
    #   query
    # ---------------------------
    def query(self, service: str, params: dict[str, Any] | None = {}) -> list | None:
        """Retrieve data from TrueNAS."""
        if not self.connected():
            self.connect()

        with self.lock:
            self._error = ""
            try:
                _LOGGER.debug(
                    "TrueNAS %s query: %s, %s",
                    self._host,
                    service,
                    params,
                )
                payload = {
                    "method": service,
                    "jsonrpc": "2.0",
                    "id": 0,
                    "params": [],
                }
                if params != {}:
                    if type(params) is not list:
                        params = [params]
                    payload["params"] = params

                self._ws.send(json.dumps(payload))
                message = self._ws.recv()
                if message.startswith("{"):
                    data = json.loads(message)
                    if "result" in data:
                        data = data["result"]
                    else:
                        self._error = "malformed_result"

                    if (type(data) is list or type(data) is dict) and "error" in data:
                        if (
                            "data" in data["error"]
                            and "reason" in data["error"]["data"]
                        ):
                            _LOGGER.error(
                                "TrueNAS %s query (%s) error: %s",
                                self._host,
                                service,
                                data["error"]["data"]["reason"],
                            )
                        else:
                            _LOGGER.error(
                                "TrueNAS %s query (%s) error: %s",
                                self._host,
                                service,
                                data["error"]["message"],
                            )
                else:
                    data = message

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
                self.disconnect()
                self._error = str(e)
                return None

            return data

    @property
    def error(self):
        """Return error."""
        return self._error
