"""TrueNAS API."""
from logging import getLogger
from threading import Lock
from typing import Any

from requests import get as requests_get, post as requests_post
from voluptuous import Optional

from homeassistant.core import HomeAssistant

_LOGGER = getLogger(__name__)


# ---------------------------
#   TrueNASAPI
# ---------------------------
class TrueNASAPI(object):
    """Handle all communication with TrueNAS."""

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
        self._use_ssl = use_ssl
        self._api_key = api_key
        self._protocol = "https" if self._use_ssl else "http"
        self._ssl_verify = verify_ssl
        if not self._use_ssl:
            self._ssl_verify = True
        self._url = f"{self._protocol}://{self._host}/api/v2.0/"

        self.lock = Lock()
        self._connected = False
        self._error = ""

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
        self.query("pool")

        return self._connected, self._error

    # ---------------------------
    #   query
    # ---------------------------
    def query(
        self, service: str, method: str = "get", params: dict[str, Any] | None = {}
    ) -> Optional(list):
        """Retrieve data from TrueNAS."""
        self.lock.acquire()
        error = False
        try:
            _LOGGER.debug(
                "TrueNAS %s query: %s, %s, %s",
                self._host,
                service,
                method,
                params,
            )

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            }
            if method == "get":
                response = requests_get(
                    f"{self._url}{service}",
                    headers=headers,
                    params=params,
                    verify=self._ssl_verify,
                )

            elif method == "post":
                response = requests_post(
                    f"{self._url}{service}",
                    headers=headers,
                    json=params,
                    verify=self._ssl_verify,
                )

            if response.status_code == 200:
                data = response.json()
                _LOGGER.debug("TrueNAS %s query response: %s", self._host, data)
            else:
                error = True
        except Exception:
            error = True

        if error:
            try:
                errorcode = response.status_code
            except Exception:
                errorcode = "no_response"

            _LOGGER.warning(
                'TrueNAS %s unable to fetch data "%s" (%s)',
                self._host,
                service,
                errorcode,
            )

            if errorcode != 500 and service != "reporting/get_data":
                self._connected = False

            self._error = errorcode
            self.lock.release()
            return None

        self._connected = True
        self._error = ""
        self.lock.release()

        return data

    @property
    def error(self):
        """Return error."""
        return self._error
