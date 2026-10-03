# Weather Dashboard

A Python and Streamlit dashboard for exploring current weather, hourly conditions, air quality, and a five-day temperature forecast. Search for a city, choose the matching location, and view weather data from OpenWeather in a dark-themed interface.

## Features

- **Location search:** Find up to five matching locations, with state and country labels to distinguish cities with the same name.
- **Current conditions:** Temperature, humidity, wind speed, feels-like temperature, daily temperature range, and air quality.
- **Hourly outlook:** Up to ten cards showing current and upcoming conditions, with sunrise or sunset inserted when it falls within the displayed window.
- **Five-day forecast:** Interactive Plotly chart comparing daily minimum and maximum temperatures.
- **Weather alerts:** Display active alert titles returned by OpenWeather.
- **Air quality guidance:** OpenWeather's five-level AQI scale, from Good to Very Poor.
- **Caching and refresh:** Cache location and weather responses for ten minutes, with a manual refresh button.
- **Usage tracking:** Store daily One Call request counts in Supabase and enforce an application-side limit of 800 requests per day.

Temperatures are displayed in **°C**, wind speed in **km/h**, and forecast times use the selected location's UTC offset.

## Technology

| Component | Purpose |
| --- | --- |
| Python / Streamlit | Application logic and web interface |
| pandas | Forecast data preparation and timestamps |
| Plotly Express | Interactive temperature chart |
| Requests | HTTP requests to OpenWeather |
| Supabase / PostgreSQL | Persistent daily API usage counter |
| OpenWeather | Geocoding, One Call 3.0 weather data, and Air Pollution data |

## Getting started

### 1. Prerequisites

- Python **3.11** (the version used by the included development container).
- Git.
- An [OpenWeather account](https://openweathermap.org/) and an API key with access to **One Call API 3.0**, Geocoding, and Air Pollution.
- A [Supabase project](https://supabase.com/).

Check the provider's current access requirements and pricing before running the app. A general OpenWeather API key alone may not provide One Call 3.0 access.

### 2. Clone and install

```bash
git clone https://github.com/aditya-mahajan15/Weather-Dashboard.git
cd Weather-Dashboard
python3 -m venv myenv
source myenv/bin/activate
python -m pip install -r requirements.txt
```

The commands above target macOS or Linux. The existing hourly time formatting uses `%-I`, which is platform-dependent; Windows users can use WSL or the included Linux development container.

### 3. Set up the Supabase counter

The application expects an `app_daily_stats` table and an `increment_api_calls_today` RPC function. Supabase is required for fetching weather because the app checks the stored counter before each One Call request.

For a new project, run this SQL in the Supabase SQL Editor:

```sql
create table public.app_daily_stats (
    stat_date date primary key,
    api_calls integer not null default 0 check (api_calls >= 0)
);

alter table public.app_daily_stats enable row level security;

create or replace function public.increment_api_calls_today()
returns void
language sql
security invoker
set search_path = public
as $$
    insert into public.app_daily_stats (stat_date, api_calls)
    values (current_date, 1)
    on conflict (stat_date)
    do update set api_calls = public.app_daily_stats.api_calls + 1;
$$;

revoke all on table public.app_daily_stats from anon, authenticated;
revoke execute on function public.increment_api_calls_today()
    from public, anon, authenticated;
grant select, insert, update on table public.app_daily_stats to service_role;
grant execute on function public.increment_api_calls_today() to service_role;
```

This setup uses the server-side service role key. Keep that key private: it bypasses row-level security and must never be committed or exposed in browser code. If the table or function already exists, inspect the existing schema before applying changes.

The app reads dates using the Python server's local date, while the SQL function uses the database date. Configure both environments to use the same timezone, preferably UTC, so counts remain consistent around midnight.

### 4. Configure secrets

Create `.streamlit/secrets.toml` in the project root:

```toml
OPENWEATHER_API_KEY = "your_openweather_api_key"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your_server_side_supabase_service_role_key"
```

The repository already ignores `.streamlit/secrets.toml`, `.env`, and `myenv/`.

Use the secrets file for setup. Although `api.py` includes an environment-variable fallback for `OPENWEATHER_API_KEY`, Supabase credentials are read directly from Streamlit secrets. The application does not load `.env` files automatically.

### 5. Start the app

```bash
python -m streamlit run app.py
```

Open [localhost:8501](http://localhost:8501) if your browser does not open automatically. Stop the server with `Ctrl+C`.

## Using the dashboard

1. Enter a city in the sidebar. The default is **Melbourne**.
2. If several locations match, choose the correct city, state, and country.
3. Review current conditions, weather alerts, and air quality.
4. Browse the hourly cards and hover over the five-day chart for temperatures.
5. Select **Refresh Now** to clear Streamlit's data cache and fetch fresh results.

Refresh clears the application's data cache, which can affect other sessions sharing the same server. Cached data expires after ten minutes and is fetched again on a subsequent app run; there is no background polling timer.

## API usage and limits

The application uses three OpenWeather endpoints:

| API | Data used | Counted by this app |
| --- | --- | --- |
| Geocoding | City coordinates and location labels | No |
| One Call 3.0 | Current weather, hourly and daily forecasts, alerts | Yes |
| Air Pollution | Air quality index | No |

`DAILY_LIMIT` in `api.py` is set to **800**. One Call attempts are counted after a successful response, a request failure, or an invalid JSON response. The displayed count is an application counter, not the provider's billing record.

The database increment is atomic, but the limit check and network request are separate operations. Concurrent requests can exceed the application limit, so use provider-side usage controls as well. All deployments using the same Supabase table share the counter.

## Deployment

To deploy with Streamlit Community Cloud:

1. Connect this GitHub repository and select `app.py` as the entry point.
2. Use Python 3.11 where available and install dependencies from `requirements.txt`.
3. Add the three configuration values above to the deployment's Streamlit secrets settings.
4. Ensure the Supabase table and RPC are initialized, then deploy.

The repository also includes a Python 3.11 development container for GitHub Codespaces. It installs the dependencies, starts Streamlit, and forwards port 8501. Add your secrets before using the dashboard. The container's startup command disables CORS and XSRF protection for preview use; use the normal startup command above for deployments.

## Project structure

```text
Weather-Dashboard/
├── app.py                         # Streamlit UI, caching, cards, and chart
├── api.py                         # OpenWeather requests and usage limit
├── counter.py                     # Supabase counter reads and RPC calls
├── requirements.txt               # Python dependencies
├── .streamlit/
│   ├── config.toml                # Dark theme
│   └── secrets.toml               # Local credentials; ignored by Git
├── .devcontainer/
│   └── devcontainer.json          # Python 3.11 / Codespaces setup
├── .gitignore
└── README.md
```

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Missing secrets or `Missing API key.` | Create `.streamlit/secrets.toml` and check all three key names. Restart Streamlit after changing credentials. |
| OpenWeather request fails with 401 or 403 | Check the API key and its access to One Call 3.0 and the other required endpoints. |
| `City not found` | Check spelling or try a more specific query such as `Melbourne,AU`. |
| Supabase table, function, or permission error | Verify the SQL setup, project URL, and server-side key. |
| Daily API limit reached | The stored One Call count has reached 800 for the server date. Wait for the next day and check provider usage before changing limits. |
| Air quality request fails | Check access to the Air Pollution endpoint. An AQI request failure currently prevents the combined weather result from rendering. |
| Weather appears unchanged | Results are cached for ten minutes. Use **Refresh Now** to request fresh data. |

The **Last updated** label shows the time the page rendered on the server; it is not the timestamp of the underlying weather observation.

## Contributing

Issues and pull requests are welcome. Include clear reproduction steps for bugs and a description of expected behavior for proposed changes. For UI changes, test location search, forecast rendering, refresh, and error handling with your own configured credentials.

## License

No license file is currently included in this repository. Contact the repository owner before reusing or distributing the code under assumed license terms.
