"""Tests for the Foreca integration setup and teardown."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.foreca_ha import async_setup_entry, async_unload_entry
from custom_components.foreca_ha.const import BASE_URL, DOMAIN
from custom_components.foreca_ha.coordinator import ForecaDataUpdateCoordinator


def make_entry(**overrides):
    """Build a mock config entry with the default data."""
    data = {
        "location_path": "Finland/Helsinki/Ita-Pasila",
        "snow_station": "Mikkeli lentoasema",
        "lake_station": "Saimaa",
        "ice_station": "Kyyvesi, Haukivuori",
    }
    data.update(overrides)
    entry = Mock()
    entry.entry_id = "entry_1"
    entry.data = data
    return entry


async def test_setup_entry(hass):
    """async_setup_entry wires up a coordinator and forwards platforms."""
    entry = make_entry()

    with (
        patch.object(
            ForecaDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            new=AsyncMock(),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(coordinator, ForecaDataUpdateCoordinator)
    assert coordinator.url == f"{BASE_URL}Finland/Helsinki/Ita-Pasila"
    assert coordinator.snow_station == "Mikkeli lentoasema"
    assert coordinator.lake_station == "Saimaa"
    assert coordinator.ice_station == "Kyyvesi, Haukivuori"


async def test_setup_entry_with_default_stations(hass):
    """Missing station keys fall back to sensible defaults."""
    entry = make_entry()
    del entry.data["snow_station"]
    del entry.data["lake_station"]
    del entry.data["ice_station"]

    with (
        patch.object(
            ForecaDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            new=AsyncMock(),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.snow_station == "Mikkeli lentoasema"
    assert coordinator.lake_station == "Saimaa"
    assert coordinator.ice_station == "Kyyvesi, Haukivuori"


async def test_setup_entry_first_refresh_failure(hass):
    """A failed first refresh should not leave a half-configured entry."""
    entry = make_entry()

    with (
        patch.object(
            ForecaDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            side_effect=Exception("boom"),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(Exception, match="boom"):
            await async_setup_entry(hass, entry)


async def test_unload_entry(hass):
    """async_unload_entry unloads platforms and clears coordinator data."""
    entry = make_entry()
    hass.data[DOMAIN] = {entry.entry_id: Mock()}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    assert hass.data[DOMAIN] == {}


async def test_unload_entry_failure_keeps_data(hass):
    """If unload fails, the coordinator entry is kept."""
    entry = make_entry()
    hass.data[DOMAIN] = {entry.entry_id: Mock()}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=False),
    ):
        result = await async_unload_entry(hass, entry)

    assert result is False
    assert entry.entry_id in hass.data[DOMAIN]

