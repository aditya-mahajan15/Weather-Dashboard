import os
import streamlit as st
import requests
from counter import get_today_api_calls, increment_total_api_calls

# OpenWeather onecall endpoint is the only paid/charged endpoint in this app.
DAILY_LIMIT = 800

# Prefer secure Streamlit secrets, fallback to env var for local development.
API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.getenv("OPENWEATHER_API_KEY", "")

# One Call usage is metered. Geocoding and Air Pollution are free tiers for this app.
BASE_ONECALL = "https://api.openweathermap.org/data/3.0/onecall"
BASE_GEOCODE = "https://api.openweathermap.org/geo/1.0/direct"
BASE_AIR_POLLUTION = "http://api.openweathermap.org/data/2.5/air_pollution"


class WeatherAPIError(Exception):
    """Custom exception for OpenWeather API issues."""
    pass



def _get_json(url: str, params: dict):
    """Request OpenWeather API and return deserialized JSON.

    For One Call (paid) requests we enforce daily limits and increment usage.
    Other endpoints are considered free and do not contribute to the limit.
    """
    if not API_KEY:
        raise WeatherAPIError("Missing API key.")

    chargeable = url == BASE_ONECALL
    if chargeable:
        today_calls = get_today_api_calls()
        if today_calls >= DAILY_LIMIT:
            raise WeatherAPIError(
                "Daily API limit reached (800 calls for One Call API). Please try again tomorrow."
            )

    params = {**params, "appid": API_KEY}

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        if chargeable:
            increment_total_api_calls()
        raise WeatherAPIError(f"Request failed: {e}")
    except ValueError:
        if chargeable:
            increment_total_api_calls()
        raise WeatherAPIError("Invalid response received from OpenWeather API.")

    if chargeable:
        increment_total_api_calls()

    # For list responses (geocoding) we can return directly.
    if isinstance(data, list):
        return data

    # OpenWeather may return cod/message for 400+ errors in JSON body.
    cod = str(data.get("cod", r.status_code))
    if cod != "200":
        msg = data.get("message", "Unknown API error")
        raise WeatherAPIError(f"OpenWeather error ({cod}): {msg}")

    return data


def search_locations(city: str) -> list[dict]:
    """Search locations by city name using OpenWeather geocoding.

    Returns up to 5 matches.
    """
    data = _get_json(
        BASE_GEOCODE,
        {
            "q": city,
            "limit": 5
        }
    )

    if not data:
        raise WeatherAPIError("City not found")

    return data


def get_air_quality_by_coords(lat: float, lon: float) -> int:
    """Retrieve AQI rating for a coordinate pair.

    AQI is returned as an integer 1-5, where 1=Good and 5=Very Poor.
    """
    data = _get_json(
        BASE_AIR_POLLUTION,
        {
            "lat": lat,
            "lon": lon
        }
    )

    try:
        return data["list"][0]["main"]["aqi"]
    except (KeyError, IndexError, TypeError):
        raise WeatherAPIError("AQI data not available")


def get_weather_onecall_by_coords(lat: float, lon: float) -> dict:
    """Query One Call API and return normalized weather object."""
    data = _get_json(
        BASE_ONECALL,
        {
            "lat": lat,
            "lon": lon,
            "units": "metric",
            "exclude": "minutely"
        }
    )

    current = data["current"]
    alerts = data.get("alerts", [])
    daily = data["daily"]

    # AQI is retrieved from a separate endpoint because One Call API v3 no longer bundles it.
    aqi = get_air_quality_by_coords(lat, lon)

    return {
        "temp": current["temp"],
        "humidity": current["humidity"],
        "wind_speed": current["wind_speed"],
        "wind_deg": current.get("wind_deg"),
        "feels_like": current["feels_like"],
        "description": current["weather"][0]["description"],
        "temp_min": daily[0]["temp"]["min"],
        "temp_max": daily[0]["temp"]["max"],
        "alerts": alerts,
        "daily": daily,
        "hourly": data.get("hourly", []),
        "uv_index": current.get("uvi"),
        "pressure": current.get("pressure"),
        "sunrise": current.get("sunrise"),
        "sunset": current.get("sunset"),
        "timezone_offset": data.get("timezone_offset", 0),
        "aqi": aqi,
    }