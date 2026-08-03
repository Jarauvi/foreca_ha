<div align="center" border-radius="15px">
  <img src="https://github.com/Jarauvi/foreca_ha/blob/main/custom_components/foreca_ha/brand/icon@2x.png?raw=true" width="64">

  # Foreca Scraper for Home Assistant

  [![Home Assistant](https://img.shields.io/badge/home%20assistant-%2341BDF5.svg?style=for-the-badge&logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
  [![Version](https://img.shields.io/badge/Version-0.1.0-orange.svg?style=for-the-badge)](https://github.com/Jarauvi/foreca_ha)
   [![Tests](https://github.com/Jarauvi/foreca_ha/actions/workflows/tests.yaml/badge.svg)](https://github.com/Jarauvi/foreca_ha/actions)
  ![Cloud Polling](https://img.shields.io/badge/IOT_class-Cloud_polling-blue?style=for-the-badge)

  **Fetches environmental data for Home Assistant from Foreca.**
  *Get specific insights like clothing recommendations, air quality, lake temperatures, and ice thickness.*
</div>

---

## ✨ Features

- **Hybrid Data Sourcing**: Combines HTML scraping for environmental data, Vector Tile (PBF) decoding for snow depth, and JSON APIs for aquatic data.
- **Device-Centric**: All sensors are automatically grouped under a single **Foreca [Location]** device.
- **Preconfigured Stations**: Searchable dropdown lists for Snow, Lake, and Ice observation stations to ensure data accuracy.
- **Deep Insights**: Access data often missing from standard weather integrations (e.g., UV Index descriptions and clothing recommendations).
- **Localization**: Full support for **Finnish (FI)** and **English (EN)**.

---

## 🚀 Installation

### Option 1: HACS (Recommended)
1. Open **HACS** > **Integrations**.
2. Click the three dots in the top right and select **Custom Repositories**.
3. Paste: `https://github.com/Jarauvi/foreca_ha`
4. Select category **Integration** and click **Add**.
5. Find "Foreca" and click **Download**.
6. **Restart** Home Assistant.

### Option 2: Manual
1. Download the `foreca_ha` folder from `custom_components/`.
2. Copy it to your Home Assistant `config/custom_components/` directory.
3. **Restart** Home Assistant.

---

## ⚙️ Configuration

1. Navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** ➕ and search for **Foreca**.
3. Complete the following configuration options:

| Option | Description |
| :--- | :--- |
| **Location path** | The URL path from Foreca.fi (e.g., `Finland/Helsinki/Ita-Pasila`, you can find this by searching the preferred location from the pages and copying the URL). |
| **Snow observation station** | Select the nearest station for snow depth data (MVT decoding). |
| **Lake temperature station** | Select the lake station for water temperature data (JSON API). |
| **Ice thickness station** | Select the station for ice thickness data (JSON API). |

---

## 📊 Available Sensors

### 🌍 General Environment (Scraped)
| Entity ID (Example) | Name (FI) | Description |
| :--- | :--- | :--- |
| `clothing_desc` | Pukeutumissuositus | Text-based recommendation for outdoor clothing. |
| `aqi_val` | Ilmanlaatu | Numerical Air Quality Index (AQI). |
| `aqi_desc` | Ilmanlaatu kuvaus | Descriptive state of the current air quality. |
| `uv_val` | UV-indeksi | Current numerical UV Index level. |
| `uv_desc` | UV-indeksi kuvaus | Safety recommendation based on UV intensity. |
| `warnings_val` | Säävaroitukset | Active weather warnings for the selected location. |

### ❄️ Winter & Aquatic Conditions (API/Tiles)
| Entity ID | Name (FI) | Description |
| :--- | :--- | :--- |
| `snow_depth` | Lumensyvyys | Snow depth in **cm** at the selected observation station. |
| `lake_temp` | Järviveden lämpötila | Surface water temperature in **°C**. |
| `ice_thickness` | Jään paksuus | Current thickness of ice in **cm**. |

*Note: Aquatic sensors include the observation station name as an attribute.*

---

## 🛠️ Technical Details

This integration uses `beautifulsoup4` for HTML parsing and a bundled pure-Python decoder for decoding highly compressed weather map layers (MVT/Protobuf). The `DataUpdateCoordinator` is optimized to fetch all three data sources (HTML, Tiles, JSON) in a single update cycle every 30 minutes to stay within fair usage limits.

---

## ⚠️ Disclaimer
This integration is a community project and is **not** affiliated with, endorsed by, or supported by Foreca.
