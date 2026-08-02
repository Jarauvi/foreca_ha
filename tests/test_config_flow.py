"""Tests for the Foreca config flow."""

from __future__ import annotations

import voluptuous as vol

from custom_components.foreca_ha.config_flow import ForecaCustomConfigFlow
from custom_components.foreca_ha.const import (
    ICE_THICKNESS_STATIONS,
    LAKE_TEMP_STATIONS,
    SNOW_DEPTH_STATIONS,
)


def _flow(hass) -> ForecaCustomConfigFlow:
    """Create a config flow instance bound to the test hass."""
    flow = ForecaCustomConfigFlow()
    flow.hass = hass
    return flow


def _field_names(result) -> list[str]:
    """Extract the field names from a voluptuous schema."""
    schema = result["data_schema"].schema
    return [str(getattr(key, "schema", key)) for key in schema]


def _field(result, name: str):
    """Extract a single field validator by name from a voluptuous schema."""
    schema = result["data_schema"].schema
    for key, field in schema.items():
        if str(getattr(key, "schema", key)) == name:
            return field
    return None



async def test_show_form_with_all_fields(hass):
    """The initial form shows all four configuration fields."""
    flow = _flow(hass)
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    fields = _field_names(result)
    assert fields == ["location_path", "snow_station", "lake_station", "ice_station"]


async def test_create_entry_normalizes_full_url(hass):
    """A pasted full URL is stripped down to the path."""
    flow = _flow(hass)
    result = await flow.async_step_user(
        user_input={
            "location_path": "https://www.foreca.fi/Finland/Helsinki/Ita-Pasila/",
            "snow_station": "Helsinki Kaisaniemi",
            "lake_station": "Saimaa",
            "ice_station": "Kyyvesi, Haukivuori",
        }
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Ita-pasila"
    assert result["data"]["location_path"] == "Finland/Helsinki/Ita-Pasila"
    assert result["data"]["snow_station"] == "Helsinki Kaisaniemi"
    assert result["data"]["lake_station"] == "Saimaa"
    assert result["data"]["ice_station"] == "Kyyvesi, Haukivuori"


async def test_create_entry_keeps_short_path(hass):
    """A path without a scheme is stored unchanged."""
    flow = _flow(hass)
    result = await flow.async_step_user(
        user_input={
            "location_path": "Finland/Mikkeli/Valkolansaari",
            "snow_station": "Mikkeli lentoasema",
            "lake_station": "Saimaa",
            "ice_station": "Kyyvesi, Haukivuori",
        }
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Valkolansaari"
    assert result["data"]["location_path"] == "Finland/Mikkeli/Valkolansaari"


async def test_create_entry_strips_whitespace(hass):
    """Station names have surrounding whitespace removed."""
    flow = _flow(hass)
    result = await flow.async_step_user(
        user_input={
            "location_path": "Finland/Helsinki",
            "snow_station": "  Helsinki Kaisaniemi  ",
            "lake_station": " Saimaa ",
            "ice_station": " Kyyvesi, Haukivuori ",
        }
    )

    assert result["type"] == "create_entry"
    assert result["data"]["snow_station"] == "Helsinki Kaisaniemi"
    assert result["data"]["lake_station"] == "Saimaa"
    assert result["data"]["ice_station"] == "Kyyvesi, Haukivuori"


async def test_create_entry_deep_location_title(hass):
    """The title uses the last path segment."""
    flow = _flow(hass)
    result = await flow.async_step_user(
        user_input={
            "location_path": "Finland/North-Karelia/Joensuu/Keskusta",
            "snow_station": "Mikkeli lentoasema",
            "lake_station": "Saimaa",
            "ice_station": "Kyyvesi, Haukivuori",
        }
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Keskusta"
    assert result["data"]["location_path"] == "Finland/North-Karelia/Joensuu/Keskusta"


async def test_form_uses_station_choices(hass):
    """The station fields use the predefined station lists as choices."""
    flow = _flow(hass)
    result = await flow.async_step_user(user_input=None)

    # Snow station selector should be vol.In with the station list.
    snow_field = _field(result, "snow_station")
    assert isinstance(snow_field, vol.In)
    assert "Mikkeli lentoasema" in snow_field.container
    assert len(snow_field.container) == len(SNOW_DEPTH_STATIONS)

    lake_field = _field(result, "lake_station")
    assert isinstance(lake_field, vol.In)
    assert "Saimaa" in lake_field.container
    assert len(lake_field.container) == len(LAKE_TEMP_STATIONS)

    ice_field = _field(result, "ice_station")
    assert isinstance(ice_field, vol.In)
    assert "Kyyvesi, Haukivuori" in ice_field.container
    assert len(ice_field.container) == len(ICE_THICKNESS_STATIONS)


