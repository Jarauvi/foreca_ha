"""DataUpdateCoordinator for Foreca integration."""
from __future__ import annotations

import logging
import re
from datetime import timedelta

from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN, HEADERS, LABEL_MAP, SCAN_INTERVAL, LAKE_TEMP_URL, ICE_URL
from . import mvt_decoder

_LOGGER = logging.getLogger(__name__)


class ForecaDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Foreca data."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        snow_station: str,
        lake_station: str,
        ice_station: str,
    ):
        """Initialize the coordinator."""
        self.url = url
        self.snow_station = snow_station
        self.lake_station = lake_station
        self.ice_station = ice_station
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{url}",
            update_interval=SCAN_INTERVAL,
        )

    def _decode_mvt_tile(self, content: bytes) -> dict:
        """Decode MVT tile in the executor thread."""
        try:
            return mvt_decoder.decode(content)
        except Exception as e:
            _LOGGER.error("Error decoding MVT tile: %s", e)
            return {}

    async def _async_update_data(self):
        """Fetch data from Foreca."""
        data = {}
        session = async_get_clientsession(self.hass)

        # 1. Fetch HTML
        try:
            async with session.get(self.url, headers=HEADERS, timeout=10) as response:
                if response.status != 200:
                    raise UpdateFailed(
                        f"Error fetching Foreca page: {response.status}"
                    )
                html = await response.text()
        except Exception as e:
            raise UpdateFailed(f"Failed to connect to Foreca: {e}")

        # 2. Fetch Snow Depth (PBF)
        latest_utc = dt_util.utcnow() - timedelta(minutes=20)
        basetime = latest_utc.strftime("%Y%m%d%H0000")
        pbf_url = f"https://map-cf.foreca.net/tile/snow_depth_obs/{basetime}/4/9/4.pbf"

        try:
            async with session.get(pbf_url, headers=HEADERS, timeout=10) as pbf_response:
                if pbf_response.status == 200:
                    pbf_content = await pbf_response.read()
                    tile_data = await self.hass.async_add_executor_job(
                        self._decode_mvt_tile, pbf_content
                    )

                    features = tile_data.get("data", {}).get("features", [])
                    station_features = [
                        f["properties"]
                        for f in features
                        if f.get("properties", {}).get("name") == self.snow_station
                    ]

                    if station_features:
                        station_features.sort(key=lambda x: x.get("time", ""))
                        latest_obs = station_features[-1]
                        data["snow_depth"] = latest_obs.get("val", 0)
                        data["snow_depth_station"] = self.snow_station
                        data["snow_depth_time"] = latest_obs.get("time")
        except Exception as pbf_err:
            _LOGGER.debug("Snow depth tile not available: %s", pbf_err)

        # 3. Fetch Lake Temperature (JSON)
        try:
            async with session.get(
                LAKE_TEMP_URL, headers=HEADERS, timeout=10
            ) as response:
                if response.status == 200:
                    json_data = await response.json()
                    stations = json_data.get("stations", [])

                    s_id = None
                    s_real_name = None
                    for s in stations:
                        if s.get("name") == self.lake_station:
                            s_id = str(s.get("id"))
                            s_real_name = s.get("name")
                            break

                    if s_id:
                        obs_list = json_data.get("observations", {}).get(s_id, {})
                        # Forecast/Obs dates are YYYYMMDD000000
                        today = dt_util.now().strftime("%Y%m%d000000")

                        obs = obs_list.get(today)
                        if not obs:
                            # Fallback to the latest available entry in the dictionary
                            sorted_keys = sorted(obs_list.keys())
                            if sorted_keys:
                                obs = obs_list[sorted_keys[-1]]

                        if obs:
                            data["lake_temp"] = obs.get("t")
                            data["lake_temp_station"] = s_real_name
        except Exception as lake_err:
            _LOGGER.debug("Lake temperature data not available: %s", lake_err)

        # 4. Fetch Ice Thickness (JSON)
        try:
            async with session.get(
                ICE_URL, headers=HEADERS, timeout=10
            ) as response:
                if response.status == 200:
                    json_data = await response.json()
                    stations = json_data.get("stations", [])

                    s_id = None
                    s_real_name = None
                    for s in stations:
                        if s.get("name") == self.ice_station:
                            s_id = str(s.get("id"))
                            s_real_name = s.get("name")
                            break

                    if s_id:
                        obs_list = json_data.get("observations", {}).get(s_id, [])
                        # Ice data is a list of observations.
                        # Find the latest non-null value.
                        latest_obs = None
                        for obs in reversed(obs_list):
                            if obs.get("v") is not None:
                                latest_obs = obs
                                break

                        if latest_obs:
                            data["ice_thickness"] = latest_obs.get("v")
                            data["ice_thickness_station"] = s_real_name
        except Exception as ice_err:
            _LOGGER.debug("Ice thickness data not available: %s", ice_err)

        # 5. Parse HTML
        soup = BeautifulSoup(html, "html.parser")
        try:
            for title in soup.find_all("li", class_="title"):
                title_text = title.get_text(strip=True)
                key_prefix = next(
                    (v for k, v in LABEL_MAP.items() if k in title_text), None
                )
                if not key_prefix:
                    continue

                val_li = title.find_next_sibling("li", class_="value")
                if not val_li:
                    continue

                if key_prefix == "warnings":
                    img = val_li.find("img")
                    warning_text = img.get("title") if img else "Ei varoituksia"
                    data["warnings_val"] = warning_text
                else:
                    raw_val = val_li.get_text(strip=True)
                    # Try to convert to float for measurements
                    # by stripping non-numeric junk
                    clean_val = re.sub(r"[^\d,.-]", "", raw_val).replace(",", ".")
                    try:
                        if clean_val and clean_val not in ("-", "."):
                            data[f"{key_prefix}_val"] = float(clean_val)
                        else:
                            data[f"{key_prefix}_val"] = raw_val
                    except ValueError:
                        data[f"{key_prefix}_val"] = raw_val

                    descr_li = title.find_next_sibling("li", class_="descr")
                    if descr_li:
                        data[f"{key_prefix}_desc"] = descr_li.get_text(strip=True)

            return data
        except Exception as parse_err:
            _LOGGER.error("Failed to parse Foreca HTML: %s", parse_err)
            return data
