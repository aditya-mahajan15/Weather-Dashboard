import os
import requests
import json
from datetime import date

LIMIT = 800
COUNTER_FILE = "api_counter.json"

API_KEY = "6412b3f79c1029a44c81d0d1eaeed24c"
# API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

BASE_ONECALL = "https://api.openweathermap.org/data/3.0/onecall"
BASE_GEOCODE = "https://api.openweathermap.org/geo/1.0/direct"


class WeatherAPIError(Exception):
    pass


def check_api_limit():
    today = str(date.today())

    try:
        with open(COUNTER_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        data = {"date": today, "count": 0}

    if data["date"] != today:
        data = {"date": today, "count": 0}

    if data["count"] >= LIMIT:
        raise WeatherAPIError(f"Daily API limit reached ({LIMIT} calls).")

    data["count"] += 1

    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f)


def _get_json(url: str, params: dict):
    check_api_limit()

    if not API_KEY:
        raise WeatherAPIError("Missing API key. Set OPENWEATHER_API_KEY environment variable.")

    params = {**params, "appid": API_KEY}
    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    # Geocoding endpoint returns a list
    if isinstance(data, list):
        return data

    cod = str(data.get("cod", r.status_code))
    if cod != "200":
        msg = data.get("message", "Unknown API error")
        raise WeatherAPIError(f"OpenWeather error ({cod}): {msg}")

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