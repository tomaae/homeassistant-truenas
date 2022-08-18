"""The TrueNAS integration"""
from .const import DOMAIN, PLATFORMS
from .truenas_controller import TrueNASControllerData


# ---------------------------
#   async_setup
# ---------------------------
async def async_setup(hass, _config):
    """Set up configured OMV Controller"""
    hass.data[DOMAIN] = {}
    return True


# ---------------------------
#   update_listener
# ---------------------------
async def update_listener(hass, config_entry) -> None:
    """Handle options update"""
    await hass.config_entries.async_reload(config_entry.entry_id)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass, config_entry):
    """Set up TrueNAS config entry"""
    controller = TrueNASControllerData(hass, config_entry)
    await controller.async_update()
    await controller.async_init()

    hass.data[DOMAIN][config_entry.entry_id] = controller

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    return True


# ---------------------------
#   async_unload_entry
# ---------------------------
async def async_unload_entry(hass, config_entry):
    """Unload TrueNAS config entry"""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        controller = hass.data[DOMAIN][config_entry.entry_id]
        await controller.async_reset()
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return True
