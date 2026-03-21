import streamlit as st
import pandas as pd
import plotly.express as px
from api import search_locations, get_weather_onecall_by_coords, WeatherAPIError
from counter import get_today_api_calls

st.set_page_config(page_title="Weather Dashboard", layout="wide")

# Global CSS customizations used to improve metric and card styling across the app.
st.markdown("""
<style>
    .main > div {
        padding-top: 1.2rem;
    }

    .block-container {
        max-width: 1450px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        letter-spacing: -0.5px;
    }

    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 18px;
        padding: 22px 22px 20px 22px;
        height: 130px;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 16px;
        margin-bottom: 10px;
    }

    div[data-testid="stMetricValue"] {
        font-size: 36px;
    }

    .hour-card {
        text-align: center;
        min-height: 145px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        color: #f5f7fb;
    }

    .hour-label {
        font-size: 18px;
        font-weight: 700;
    }

    .hour-value {
        font-size: 18px;
        font-weight: 700;
    }

    .section-label {
        font-size: 14px;
        color: rgba(255,255,255,0.72);
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

st.title("Weather & Monitoring Dashboard")
st.caption("Live current conditions, hourly outlook, and 5-day forecast")

# Search input is one of the few user-controlled filters in this dashboard.
city = st.sidebar.text_input("Search location", "Melbourne")

# Manual refresh clears cached API results for the current session.
if st.sidebar.button("Refresh Now"):
    st.cache_data.clear()
    st.rerun()


@st.cache_data(ttl=600)
def load_locations(city_name: str):
    """Memoized lookup of city candidates from geocoding endpoint."""
    return search_locations(city_name)


@st.cache_data(ttl=600)
def load_weather(lat: float, lon: float):
    """Memoized weather fetch for lat/lon to reduce repeated billing hits."""
    return get_weather_onecall_by_coords(lat, lon)


def format_location(loc: dict) -> str:
    """Display-friendly location label from geocoding record."""
    parts = [loc.get("name", "")]
    if loc.get("state"):
        parts.append(loc["state"])
    if loc.get("country"):
        parts.append(loc["country"])
    return ", ".join(parts)

#Convert numeric AQI values into user-friendly text categories.
def aqi_category(aqi: int) -> str:
    return {
        1: "Good",
        2: "Fair",
        3: "Moderate",
        4: "Poor",
        5: "Very Poor",
    }.get(aqi, "Unknown")


if city:
    try:
        locations = load_locations(city)

        if len(locations) == 1:
            selected = locations[0]
        else:
            st.markdown('<div class="section-label">Select the correct location</div>', unsafe_allow_html=True)
            location_options = [format_location(loc) for loc in locations]
            selected_label = st.selectbox("Select the correct location", location_options, label_visibility="collapsed")
            selected = locations[location_options.index(selected_label)]

        current = load_weather(selected["lat"], selected["lon"])
        display_location = format_location(selected)

        st.markdown(f"## {display_location}")
        st.markdown(
            f"<div style='font-size:28px; font-weight:600; margin-bottom:8px;'>"
            f"{current['description'].title()}"
            f"</div>",
            unsafe_allow_html=True
        )

        # Top-level weather metrics displayed in the dashboard header row.
        metric_cols = st.columns(6)
        metric_cols[0].metric("Temperature (°C)", f"{round(current['temp'])}")
        metric_cols[1].metric("Humidity (%)", f"{round(current['humidity'])}")
        metric_cols[2].metric("Wind Speed (km/h)", f"{round(current['wind_speed'] * 3.6)}")
        metric_cols[3].metric("Feels Like (°C)", f"{round(current['feels_like'])}")
        metric_cols[4].metric("Temperature Range (°C)", f"{round(current['temp_min'])} - {round(current['temp_max'])}")
        metric_cols[5].metric("Air Quality", aqi_category(current.get('aqi', 0)))

        # Temporarily store timezone offset for localizing forecasts.
        timezone_offset = current["timezone_offset"]

        # Display active weather alerts from One Call API before AQI status.
        if current["alerts"]:
            for alert in current["alerts"]:
                st.warning(f"⚠ {alert['event']}")
        else:
            st.info("No active weather alerts")

        # AQI alert appears in the same style and helps users act on air quality.
        aqi_value = current.get('aqi')
        aqi_text = aqi_category(aqi_value if aqi_value is not None else 0)

        if aqi_value is None:
            st.info("AQI information not available")
        elif aqi_value <= 2:
            st.info(f"AQI: {aqi_text} (Good/Fair) - air quality is acceptable.")
        elif aqi_value == 3:
            st.warning(f"AQI: {aqi_text} - some pollution is present; sensitive groups should take care.")
        else:
            st.error(f"⚠ AQI: {aqi_text} - unhealthy air quality. Take precautions.")

        st.markdown("### Hourly Forecast")

        sunrise_dt = pd.to_datetime(current["sunrise"] + timezone_offset, unit="s")
        sunset_dt = pd.to_datetime(current["sunset"] + timezone_offset, unit="s")
        visible_hourly = current["hourly"][1:10]

        # Build hourly card model with an optional sunrise/sunset special card insertion.
        cards = [{
            "label": "Now",
            "icon": current["hourly"][0]["weather"][0]["icon"],
            "value": f"{round(current['temp'])}°",
            "is_special": False,
            "dt": pd.to_datetime(current["hourly"][0]["dt"] + timezone_offset, unit="s")
        }]

        for item in visible_hourly:
            card_time = pd.to_datetime(item["dt"] + timezone_offset, unit="s")
            cards.append({
                "label": card_time.strftime("%-I%p"),
                "icon": item["weather"][0]["icon"],
                "value": f"{round(item['temp'])}°",
                "is_special": False,
                "dt": card_time
            })

        start_dt = cards[0]["dt"]
        end_dt = cards[-1]["dt"]

        special_cards = []
        if start_dt <= sunrise_dt <= end_dt:
            special_cards.append({
                "label": sunrise_dt.strftime("%-I:%M%p"),
                "icon": "🌅",
                "value": "Sunrise",
                "is_special": True,
                "dt": sunrise_dt
            })

        if start_dt <= sunset_dt <= end_dt:
            special_cards.append({
                "label": sunset_dt.strftime("%-I:%M%p"),
                "icon": "🌇",
                "value": "Sunset",
                "is_special": True,
                "dt": sunset_dt
            })

        all_cards = sorted(cards + special_cards, key=lambda x: x["dt"])
        final_cards = all_cards[:10]

        next_temp = None
        for c in reversed(final_cards):
            if not c["is_special"] and "°" in c["value"]:
                next_temp = c["value"]
                break

        fallback_temp = f"{round(current['temp'])}°"

        summary_text = (
            f"{current['description'].title()} conditions expected over the next few hours. "
            f"Temperature will move from {round(current['temp'])}° to {next_temp or fallback_temp}. "
            f"Sunset is at {sunset_dt.strftime('%-I:%M%p')}."
        )

        st.info(summary_text)

        hourly_cols = st.columns(len(final_cards))

        for col, card in zip(hourly_cols, final_cards):
            with col:
                st.markdown(
                    f"""
                    <div class="hour-card">
                        <div class="hour-label">{card['label']}</div>
                        <div>
                            {f"<div style='font-size:34px;'>{card['icon']}</div>" if card["is_special"]
                            else f"<img src='https://openweathermap.org/img/wn/{card['icon']}@2x.png' width='50'>"}
                        </div>
                        <div class="hour-value">{card['value']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        daily = current["daily"][:5]

        # Build DataFrame for 5-day temperature forecast chart.
        df = pd.DataFrame({
            "date": [pd.to_datetime(day["dt"] + timezone_offset, unit="s") for day in daily],
            "Min Temp (°C)": [round(day["temp"]["min"]) for day in daily],
            "Max Temp (°C)": [round(day["temp"]["max"]) for day in daily],
        })

        st.markdown("<div style='margin-top:35px'></div>", unsafe_allow_html=True)

        st.markdown(
            f"<div style='font-size:28px; font-weight:700; margin-bottom:10px;'>"
            f"5-Day Temperature Forecast for {selected.get('name', city).title()}"
            f"</div>",
            unsafe_allow_html=True
        )
        
        fig = px.line(
            df,
            x="date",
            y=["Min Temp (°C)", "Max Temp (°C)"],
            markers=True
        )

        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Temperature (°C)",
            legend_title="",
            hovermode="x unified",
            xaxis=dict(
                tickformat="%d %b",
                dtick="D1"
            ),
            yaxis=dict(
                tickmode="linear",
                dtick=2
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=60, b=20),
        )

        fig.update_traces(
            line=dict(width=3),
            marker=dict(size=7),
            hovertemplate="%{y}°C<extra></extra>"
        )

        st.plotly_chart(fig, use_container_width=True)

        st.caption(f"Last updated: {pd.Timestamp.now().strftime('%d %b %Y %H:%M:%S')}")

    except WeatherAPIError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Unexpected error: {e}")

try:
    # Show daily One Call API usage (metered); free geocode/AQI calls are not counted.
    total_calls = get_today_api_calls()
    st.caption(f"API Calls Today: {total_calls}")
except Exception:
    st.caption("API Calls Today: Unavailable")