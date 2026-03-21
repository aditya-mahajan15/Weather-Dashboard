import streamlit as st
from supabase import create_client, Client
from datetime import date

@st.cache_resource
def get_supabase() -> Client:
    """Return cached Supabase client instance."""
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

def get_today_api_calls() -> int:
    """Read today's metered One Call API calls from the database."""
    supabase = get_supabase()
    today = str(date.today())

    res = (
        supabase.table("app_daily_stats")
        .select("api_calls")
        .eq("stat_date", today)
        .execute()
    )

    if res.data:
        return res.data[0]["api_calls"]
    return 0

def increment_total_api_calls():
    """Increment the One Call API counter via Supabase RPC."""
    supabase = get_supabase()
    supabase.rpc("increment_api_calls_today").execute()