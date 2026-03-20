import streamlit as st
from supabase import create_client, Client
from datetime import date

@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

def get_today_api_calls() -> int:
    supabase = get_supabase()
    today = str(date.today())  # ✅ important

    res = (
        supabase.table("app_daily_stats")
        .select("api_calls")
        .eq("stat_date", today)  # ✅ fixed
        .execute()
    )

    if res.data:
        return res.data[0]["api_calls"]
    return 0

def increment_total_api_calls():
    supabase = get_supabase()
    supabase.rpc("increment_api_calls_today").execute()