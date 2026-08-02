import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, BASE_URL
from .coordinator import ForecaDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Foreca Custom from a config entry."""
    location_path = entry.data["location_path"]
    snow_station = entry.data.get("snow_station", "Mikkeli lentoasema")
    lake_station = entry.data.get("lake_station", "Saimaa")
    ice_station = entry.data.get("ice_station", "Kyyvesi, Haukivuori")
    url = f"{BASE_URL}{location_path}"

    coordinator = ForecaDataUpdateCoordinator(hass, url, snow_station, lake_station, ice_station)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
