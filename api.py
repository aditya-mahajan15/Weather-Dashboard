import os
import streamlit as st
import requests
from counter import get_today_api_calls, increment_total_api_calls

DAILY_LIMIT = 800

API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.getenv("OPENWEATHER_API_KEY", "")

BASE_ONECALL = "https://api.openweathermap.org/data/3.0/onecall"
BASE_GEOCODE = "https://api.openweathermap.org/geo/1.0/direct"


class WeatherAPIError(Exception):
    pass



def _get_json(url: str, params: dict):

    if not API_KEY:
        raise WeatherAPIError("Missing API key.")
    
    today_calls = get_today_api_calls()
    if today_calls >= DAILY_LIMIT:
        raise WeatherAPIError(
            "Daily API limit reached (800 calls). Please try again tomorrow."
        )

    params = {**params, "appid": API_KEY}

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise WeatherAPIError(f"Request failed: {e}")
    except ValueError:
        raise WeatherAPIError("Invalid response received from OpenWeather API.")

    if isinstance(data, list):
        increment_total_api_calls()
        return data

    cod = str(data.get("cod", r.status_code))
    if cod != "200":
        msg = data.get("message", "Unknown API error")
        raise WeatherAPIError(f"OpenWeather error ({cod}): {msg}")

    increment_total_api_calls()
    return data


def search_locations(city: str) -> list[dict]:
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


def get_weather_onecall_by_coords(lat: float, lon: float) -> dict:
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
    }