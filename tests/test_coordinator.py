"""Tests for the Foreca data update coordinator.

These tests use a deterministic fake aiohttp session (``fake_aiohttp.FakeSession``)
registered via ``unittest.mock.patch`` on ``async_get_clientsession``, avoiding
any dependency on library-level HTTP mocking packages.
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from custom_components.foreca_ha.const import BASE_URL, ICE_URL, LAKE_TEMP_URL
from custom_components.foreca_ha.coordinator import ForecaDataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from fake_aiohttp import FakeSession
from mvt_builder import snow_depth_tile

HTML_SAMPLE = """<html><body><ul>
<li class="title">Ulkopukeutuminen</li>
<li class="value">Lämmin takki</li>
<li class="descr">Pukeudu lämpimästi</li>
<li class="title">Ilmanlaatu</li>
<li class="value">4</li>
<li class="descr">Kohtalainen</li>
<li class="title">UV-indeksi</li>
<li class="value">2</li>
<li class="descr">Alhainen</li>
<li class="title">Säävaroitukset</li>
<li class="value"><img title="Metsäpalovaroitus"></li>
</ul></body></html>"""

PBF_URL_PATTERN = re.compile(
    r"https://map-cf\.foreca\.net/tile/snow_depth_obs/.*\.pbf"
)

STATION = "Mikkeli lentoasema"
LAKE = "Saimaa"
ICE = "Kyyvesi, Haukivuori"


def make_coordinator(hass, location_path="Finland/Mikkeli/Valkolansaari"):
    """Build a coordinator and its main page URL."""
    url = f"{BASE_URL}{location_path}"
    coordinator = ForecaDataUpdateCoordinator(
        hass, url, STATION, LAKE, ICE
    )
    return coordinator, url


def patch_session(hass, session: FakeSession):
    """Patch async_get_clientsession to return the given FakeSession."""
    return patch(
        "custom_components.foreca_ha.coordinator.async_get_clientsession",
        return_value=session,
    )


async def test_full_successful_update(hass):
    """All four data sources are fetched and parsed correctly."""
    coordinator, url = make_coordinator(hass)
    session = FakeSession()
    session.add(
        url,
        status=200,
        body=HTML_SAMPLE,
    )
    session.add(
        PBF_URL_PATTERN,
        status=200,
        body=snow_depth_tile(
            [
                (STATION, 10, "20250328040000"),
                (STATION, 18, "20250328060000"),
                ("Helsinki Kaisaniemi", 5, "20250328060000"),
            ]
        ),
    )
    session.add(
        LAKE_TEMP_URL,
        status=200,
        payload={
            "stations": [{"id": 1, "name": LAKE}, {"id": 2, "name": "Päijänne"}],
            "observations": {"1": {"20250301000000": {"t": 4.5}}},
        },
    )
    session.add(
        ICE_URL,
        status=200,
        payload={
            "stations": [{"id": 3, "name": ICE}],
            "observations": {"3": [{"v": None}, {"v": 22}, {"v": None}]},
        },
    )

    with patch_session(hass, session):
        data = await coordinator._async_update_data()

    # Snow depth: filtered by station, sorted by time, latest wins.
    assert data["snow_depth"] == 18
    assert data["snow_depth_station"] == STATION
    assert data["snow_depth_time"] == "20250328060000"

    # Lake temperature: falls back to the latest observation when today's
    # key is not present.
    assert data["lake_temp"] == 4.5
    assert data["lake_temp_station"] == LAKE

    # Ice thickness: picks the latest non-null value.
    assert data["ice_thickness"] == 22
    assert data["ice_thickness_station"] == ICE

    # HTML scraping.
    assert data["clothing_val"] == "Lämmin takki"
    assert data["clothing_desc"] == "Pukeudu lämpimästi"
    assert data["aqi_val"] == 4.0
    assert data["aqi_desc"] == "Kohtalainen"
    assert data["uv_val"] == 2.0
    assert data["uv_desc"] == "Alhainen"
    assert data["warnings_val"] == "Metsäpalovaroitus"


async def test_lake_temp_today_key_used(hass, freezer):
    """When the observation dict contains today's key it is used directly."""
    freezer.move_to("2025-03-28T12:00:00+02:00")
    coordinator, url = make_coordinator(hass)
    session = FakeSession()
    session.add(url, status=200, body=HTML_SAMPLE)
    session.add(PBF_URL_PATTERN, status=404)
    session.add(
        LAKE_TEMP_URL,
        status=200,
        payload={
            "stations": [{"id": 1, "name": LAKE}],
            "observations": {
                "1": {
                    "20250301000000": {"t": 3.0},
                    "20250328000000": {"t": 5.5},
                    "20250401000000": {"t": 7.0},
                }
            },
        },
    )
    session.add(ICE_URL, status=200, payload={"stations": [], "observations": {}})

    with patch_session(hass, session):
        data = await coordinator._async_update_data()

    assert data["lake_temp"] == 5.5


async def test_main_page_non_200_raises(hass):
    """A non-200 main page raises UpdateFailed."""
    coordinator, url = make_coordinator(hass)
    session = FakeSession()
    session.add(url, status=500, body="Internal Server Error")

    with patch_session(hass, session):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


async def test_snow_tile_missing(hass):
    """A missing snow tile should not fail the whole update."""
    coordinator, url = make_coordinator(hass)
    session = FakeSession()
    session.add(url, status=200, body=HTML_SAMPLE)
    session.add(PBF_URL_PATTERN, status=404)
    session.add(LAKE_TEMP_URL, status=200, payload={"stations": [], "observations": {}})
    session.add(ICE_URL, status=200, payload={"stations": [], "observations": {}})

    with patch_session(hass, session):
        data = await coordinator._async_update_data()

    assert "snow_depth" not in data
    assert "lake_temp" not in data
    assert "ice_thickness" not in data
    # HTML data is still parsed.
    assert data["aqi_val"] == 4.0


async def test_invalid_tile_content(hass):
    """Garbage PBF bytes are handled gracefully without a crash."""
    coordinator, url = make_coordinator(hass)
    session = FakeSession()
    session.add(url, status=200, body=HTML_SAMPLE)
    session.add(PBF_URL_PATTERN, status=200, body=b"\xff\xff\xff not a tile")
    session.add(LAKE_TEMP_URL, status=200, payload={"stations": [], "observations": {}})
    session.add(ICE_URL, status=200, payload={"stations": [], "observations": {}})

    with patch_session(hass, session):
        data = await coordinator._async_update_data()

    assert "snow_depth" not in data
    assert data["aqi_val"] == 4.0


async def test_no_matching_snow_station(hass):
    """If no tile feature matches the station, snow data is omitted."""
    coordinator, url = make_coordinator(hass)
    session = FakeSession()
    session.add(url, status=200, body=HTML_SAMPLE)
    session.add(
        PBF_URL_PATTERN,
        status=200,
        body=snow_depth_tile([("Unknown Station", 1, "20250328060000")]),
    )
    session.add(LAKE_TEMP_URL, status=200, payload={"stations": [], "observations": {}})
    session.add(ICE_URL, status=200, payload={"stations": [], "observations": {}})

    with patch_session(hass, session):
        data = await coordinator._async_update_data()

    assert "snow_depth" not in data


async def test_lake_and_ice_stations_not_found(hass):
    """Unknown lake/ice stations simply result in missing aquatic data."""
    coordinator, url = make_coordinator(hass)
    session = FakeSession()
    session.add(url, status=200, body=HTML_SAMPLE)
    session.add(PBF_URL_PATTERN, status=404)
    session.add(
        LAKE_TEMP_URL,
        status=200,
        payload={"stations": [{"id": 9, "name": "Ei löydy"}], "observations": {}},
    )
    session.add(ICE_URL, status=200, payload={"stations": [], "observations": {}})

    with patch_session(hass, session):
        data = await coordinator._async_update_data()

    assert "lake_temp" not in data
    assert "ice_thickness" not in data


async def test_warnings_without_image(hass):
    """Warnings fall back to 'Ei varoituksia' when no image is present."""
    html = """<html><body><ul>
    <li class="title">Säävaroitukset</li>
    <li class="value">Ei varoituksia</li>
    </ul></body></html>"""
    coordinator, url = make_coordinator(hass)
    session = FakeSession()
    session.add(url, status=200, body=html)
    session.add(PBF_URL_PATTERN, status=404)
    session.add(LAKE_TEMP_URL, status=200, payload={"stations": [], "observations": {}})
    session.add(ICE_URL, status=200, payload={"stations": [], "observations": {}})

    with patch_session(hass, session):
        data = await coordinator._async_update_data()

    assert data["warnings_val"] == "Ei varoituksia"


async def test_non_numeric_values_kept_as_text(hass):
    """Non-numeric measurement values are stored as raw text."""
    html = """<html><body><ul>
    <li class="title">Ulkopukeutuminen</li>
    <li class="value">-</li>
    <li class="descr"></li>
    </ul></body></html>"""
    coordinator, url = make_coordinator(hass)
    session = FakeSession()
    session.add(url, status=200, body=html)
    session.add(PBF_URL_PATTERN, status=404)
    session.add(LAKE_TEMP_URL, status=200, payload={"stations": [], "observations": {}})
    session.add(ICE_URL, status=200, payload={"stations": [], "observations": {}})

    with patch_session(hass, session):
        data = await coordinator._async_update_data()

    assert data["clothing_val"] == "-"


async def test_coordinator_metadata(hass):
    """The coordinator exposes its name and update interval."""
    coordinator, _ = make_coordinator(hass)

    assert coordinator.name == "foreca_ha_https://www.foreca.fi/Finland/Mikkeli/Valkolansaari"
    assert coordinator.update_interval is not None
    assert coordinator.snow_station == STATION
    assert coordinator.lake_station == LAKE
    assert coordinator.ice_station == ICE

