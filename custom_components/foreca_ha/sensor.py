from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfLength, UnitOfTemperature
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .coordinator import ForecaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="clothing_val",
        name="Clothing",
        translation_key="clothing_val",
        icon="mdi:tshirt-crew",
    ),
    SensorEntityDescription(
        key="clothing_desc",
        name="Clothing description",
        translation_key="clothing_desc",
        icon="mdi:text-information",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="aqi_val",
        name="Air quality",
        translation_key="aqi_val",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
    ),
    SensorEntityDescription(
        key="aqi_desc",
        name="Air quality description",
        translation_key="aqi_desc",
        icon="mdi:comment-text-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="uv_val",
        name="UV index",
        translation_key="uv_val",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-sunny-alert",
    ),
    SensorEntityDescription(
        key="uv_desc",
        name="UV index description",
        translation_key="uv_desc",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="warnings_val",
        name="Weather warnings",
        translation_key="warnings_val",
        icon="mdi:alert-octagon",
    ),
    SensorEntityDescription(
        key="snow_depth",
        name="Snow depth",
        translation_key="snow_depth",
        icon="mdi:snowflake",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="lake_temp",
        name="Lake temperature",
        translation_key="lake_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-thermometer",
    ),
    SensorEntityDescription(
        key="ice_thickness",
        name="Ice thickness",
        translation_key="ice_thickness",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:snowflake-thermometer",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors via Config Flow using a Coordinator."""
    coordinator: ForecaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    location_path = config_entry.data["location_path"]
    
    sensors = [
        ForecaCustomSensor(
            coordinator,
            description,
            config_entry.entry_id,
            location_path
        )
        for description in SENSOR_DESCRIPTIONS
    ]
    
    async_add_entities(sensors, True)


class ForecaCustomSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Foreca Custom Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self, 
        coordinator: ForecaDataUpdateCoordinator, 
        description: SensorEntityDescription, 
        entry_id: str,
        location_name: str
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        friendly_name = location_name.split("/")[-1].replace("_", " ").title()
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=f"Foreca {friendly_name}",
            manufacturer="Foreca",
        )

    @property
    def native_value(self):
        """Return the state of the sensor from the coordinator data."""
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return entity specific state attributes."""
        if self.entity_description.key == "snow_depth":
            return {
                "observation_station": self.coordinator.data.get("snow_depth_station"),
                "observation_time": self.coordinator.data.get("snow_depth_time"),
            }
        if self.entity_description.key == "lake_temp":
            return {
                "observation_station": self.coordinator.data.get("lake_temp_station"),
            }
        if self.entity_description.key == "ice_thickness":
            return {
                "observation_station": self.coordinator.data.get("ice_thickness_station"),
            }
        return None