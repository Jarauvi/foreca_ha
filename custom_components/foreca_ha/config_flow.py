import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, LAKE_TEMP_STATIONS, SNOW_DEPTH_STATIONS, ICE_THICKNESS_STATIONS

class ForecaCustomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Foreca Custom Attributes."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user inputs the location."""
        errors = {}

        if user_input is not None:
            # Clean up the path input just in case they paste the whole URL
            location_path = user_input["location_path"].replace("https://www.foreca.fi/", "").strip("/")
            snow_station = user_input.get("snow_station", "").strip()
            lake_station = user_input.get("lake_station", "").strip()
            ice_station = user_input.get("ice_station", "").strip()
            
            # Use the last part of the path as the title (e.g., "Valkolansaari")
            title = location_path.split("/")[-1].capitalize()

            return self.async_create_entry(
                title=title,
                data={
                    "location_path": location_path,
                    "snow_station": snow_station,
                    "lake_station": lake_station,
                    "ice_station": ice_station
                }
            )

        # Default form shown to user
        data_schema = vol.Schema({
            vol.Required("location_path", default="Finland/Mikkeli/Valkolansaari"): cv.string,
            vol.Required("snow_station", default="Mikkeli lentoasema"): vol.In(SNOW_DEPTH_STATIONS),
            vol.Required("lake_station", default="Saimaa"): vol.In(LAKE_TEMP_STATIONS),
            vol.Required("ice_station", default="Kyyvesi, Haukivuori"): vol.In(ICE_THICKNESS_STATIONS),
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )