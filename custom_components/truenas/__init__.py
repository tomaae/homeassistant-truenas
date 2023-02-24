"""The TrueNAS integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import TrueNASDataUpdateCoordinator


# ---------------------------
#   update_listener
# ---------------------------
async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TrueNAS config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = TrueNASDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


# ---------------------------
#   async_unload_entry
# ---------------------------
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload TrueNAS config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        controller = hass.data[DOMAIN][entry.entry_id]
        await controller.async_reset()
        hass.data[DOMAIN].pop(entry.entry_id)

    return True
