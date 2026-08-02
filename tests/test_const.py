"""Tests for the integration's constants module."""

from __future__ import annotations

from custom_components.foreca_ha.const import (
    BASE_URL,
    DOMAIN,
    HEADERS,
    ICE_THICKNESS_STATIONS,
    ICE_URL,
    LABEL_MAP,
    LAKE_TEMP_STATIONS,
    LAKE_TEMP_URL,
    SCAN_INTERVAL,
    SNOW_DEPTH_STATIONS,
)


def test_domain():
    assert DOMAIN == "foreca_ha"


def test_base_url():
    assert BASE_URL == "https://www.foreca.fi/"


def test_api_urls():
    assert LAKE_TEMP_URL == "https://www.foreca.fi/api/lake-temp"
    assert ICE_URL == "https://www.foreca.fi/api/ice"


def test_scan_interval_is_30_minutes():
    assert SCAN_INTERVAL.total_seconds() == 30 * 60


def test_headers_contain_user_agent():
    assert "User-Agent" in HEADERS
    assert "Chrome/" in HEADERS["User-Agent"]


def test_label_map_covers_expected_keys():
    assert LABEL_MAP["Ulkopukeutuminen"] == "clothing"
    assert LABEL_MAP["Ilmanlaatu"] == "aqi"
    assert LABEL_MAP["UV-indeksi"] == "uv"
    assert LABEL_MAP["Säävaroitukset"] == "warnings"


def test_snow_depth_stations_non_empty():
    assert len(SNOW_DEPTH_STATIONS) > 50
    assert "Mikkeli lentoasema" in SNOW_DEPTH_STATIONS
    assert "Helsinki Kaisaniemi" in SNOW_DEPTH_STATIONS


def test_lake_temp_stations_non_empty():
    assert len(LAKE_TEMP_STATIONS) > 20
    assert "Saimaa" in LAKE_TEMP_STATIONS
    assert "Päijänne" in LAKE_TEMP_STATIONS


def test_ice_thickness_stations_non_empty():
    assert len(ICE_THICKNESS_STATIONS) > 30
    assert "Kyyvesi, Haukivuori" in ICE_THICKNESS_STATIONS


def test_stations_unique():
    """Station lists should not contain duplicate names."""
    assert len(set(SNOW_DEPTH_STATIONS)) == len(SNOW_DEPTH_STATIONS)
    assert len(set(LAKE_TEMP_STATIONS)) == len(LAKE_TEMP_STATIONS)
    assert len(set(ICE_THICKNESS_STATIONS)) == len(ICE_THICKNESS_STATIONS)

