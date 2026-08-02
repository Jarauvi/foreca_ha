"""Tests for the Foreca sensor entities."""

from __future__ import annotations

from unittest.mock import Mock

from custom_components.foreca_ha.const import DOMAIN
from custom_components.foreca_ha.coordinator import ForecaDataUpdateCoordinator
from custom_components.foreca_ha.sensor import (
    SENSOR_DESCRIPTIONS,
    ForecaCustomSensor,
    async_setup_entry,
)

COORDINATOR_DATA = {
    "clothing_desc": "Lämmin takki",
    "aqi_val": 3.0,
    "aqi_desc": "Kohtalainen",
    "uv_val": 2.0,
    "uv_desc": "Alhainen",
    "warnings_val": "Metsäpalovaroitus",
    "snow_depth": 12,
    "snow_depth_station": "Mikkeli lentoasema",
    "snow_depth_time": "20250328060000",
    "lake_temp": 4.5,
    "lake_temp_station": "Saimaa",
    "ice_thickness": 20,
    "ice_thickness_station": "Kyyvesi, Haukivuori",
}


def make_coordinator(hass):
    """Build a coordinator pre-populated with sample data."""
    coordinator = ForecaDataUpdateCoordinator(
        hass,
        "https://www.foreca.fi/Finland/Helsinki",
        "Mikkeli lentoasema",
        "Saimaa",
        "Kyyvesi, Haukivuori",
    )
    coordinator.data = dict(COORDINATOR_DATA)
    return coordinator


def make_sensors(hass, data=None):
    """Build the full set of sensors for the entry, optionally overriding data."""
    coordinator = make_coordinator(hass)
    if data is not None:
        coordinator.data = data
    sensors = [
        ForecaCustomSensor(
            coordinator, desc, "entry_1", "Finland/Helsinki/Ita-Pasila"
        )
        for desc in SENSOR_DESCRIPTIONS
    ]
    return sensors, coordinator


async def test_sensor_count(hass):
    """One sensor is created per descriptor."""
    sensors, _ = make_sensors(hass)
    assert len(sensors) == len(SENSOR_DESCRIPTIONS)


async def test_unique_ids(hass):
    """Each sensor has a unique id based on entry id and key."""
    sensors, _ = make_sensors(hass)
    unique_ids = {s.unique_id for s in sensors}
    assert unique_ids == {f"entry_1_{desc.key}" for desc in SENSOR_DESCRIPTIONS}


async def test_has_entity_name(hass):
    """Sensors use the entity registry name."""
    sensors, _ = make_sensors(hass)
    assert all(s.has_entity_name for s in sensors)


async def test_device_info(hass):
    """All sensors share one device per entry."""
    sensors, _ = make_sensors(hass)
    for sensor in sensors:
        assert sensor.device_info["identifiers"] == {(DOMAIN, "entry_1")}
        assert sensor.device_info["name"] == "Foreca Ita-Pasila"
        assert sensor.device_info["manufacturer"] == "Foreca"


async def test_native_values(hass):
    """Sensors read their value from the coordinator data."""
    sensors, _ = make_sensors(hass)
    by_key = {s.entity_description.key: s for s in sensors}

    assert by_key["aqi_val"].native_value == 3.0
    assert by_key["aqi_desc"].native_value == "Kohtalainen"
    assert by_key["uv_val"].native_value == 2.0
    assert by_key["uv_desc"].native_value == "Alhainen"
    assert by_key["clothing_desc"].native_value == "Lämmin takki"
    assert by_key["warnings_val"].native_value == "Metsäpalovaroitus"
    assert by_key["snow_depth"].native_value == 12
    assert by_key["lake_temp"].native_value == 4.5
    assert by_key["ice_thickness"].native_value == 20


async def test_missing_data_returns_none(hass):
    """A sensor with no matching coordinator key reports None."""
    sensors, _ = make_sensors(hass, data={})
    for sensor in sensors:
        assert sensor.native_value is None


async def test_extra_state_attributes_for_snow_depth(hass):
    sensors, _ = make_sensors(hass)
    by_key = {s.entity_description.key: s for s in sensors}

    assert by_key["snow_depth"].extra_state_attributes == {
        "observation_station": "Mikkeli lentoasema",
        "observation_time": "20250328060000",
    }


async def test_extra_state_attributes_for_lake_temp(hass):
    sensors, _ = make_sensors(hass)
    by_key = {s.entity_description.key: s for s in sensors}

    assert by_key["lake_temp"].extra_state_attributes == {
        "observation_station": "Saimaa",
    }


async def test_extra_state_attributes_for_ice_thickness(hass):
    sensors, _ = make_sensors(hass)
    by_key = {s.entity_description.key: s for s in sensors}

    assert by_key["ice_thickness"].extra_state_attributes == {
        "observation_station": "Kyyvesi, Haukivuori",
    }


async def test_extra_state_attributes_none_for_other_sensors(hass):
    sensors, _ = make_sensors(hass)
    by_key = {s.entity_description.key: s for s in sensors}

    for key in ("clothing_desc", "aqi_val", "uv_val", "warnings_val"):
        assert by_key[key].extra_state_attributes is None


async def test_unavailable_when_coordinator_fails(hass):
    """Sensors are unavailable when the coordinator's last update failed."""
    sensors, coordinator = make_sensors(hass)
    coordinator.last_update_success = False

    for sensor in sensors:
        assert sensor.available is False


async def test_available_when_coordinator_succeeds(hass):
    sensors, coordinator = make_sensors(hass)
    coordinator.last_update_success = True

    for sensor in sensors:
        assert sensor.available is True


async def test_async_setup_entry(hass):
    """async_setup_entry creates a sensor per descriptor via async_add_entities."""
    entry = Mock()
    entry.entry_id = "entry_1"
    entry.data = {"location_path": "Finland/Helsinki/Ita-Pasila"}
    coordinator = make_coordinator(hass)
    hass.data[DOMAIN] = {entry.entry_id: coordinator}

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    assert add_entities.called
    entities = add_entities.call_args[0][0]
    assert len(entities) == len(SENSOR_DESCRIPTIONS)
    assert all(isinstance(e, ForecaCustomSensor) for e in entities)
    # Second positional arg is `update_before_add`.
    assert add_entities.call_args[0][1] is True

