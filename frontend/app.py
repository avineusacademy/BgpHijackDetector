import streamlit as st
import pandas as pd
import json
import asyncio
import websockets
import threading
import requests
from datetime import datetime, timedelta, timezone, time

st.set_page_config(page_title="BGP Hijack Detector", layout="wide")
st.title("🛡️ BGP Hijack Detector with Live Stream (RIPE RIS)")

def format_timestamp(ts):
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts

def style_row(row):
    if row["type"] == "withdrawal":
        return ["background-color: #ffcccc"] * len(row)
    elif row["type"] == "announcement":
        return ["background-color: #ccffcc"] * len(row)
    return [""] * len(row)

mode = st.selectbox("Mode", ["Historic (API)", "Live Stream (RIPE RIS)"])

if mode == "Historic (API)":
    st.subheader("🔍 Historic BGP Data Lookup")

    query = st.text_input("Enter prefix (e.g. 192.0.2.0/24) or AS number (e.g. 64500):")

    now = datetime.now(tz=timezone.utc)
    default_from = now - timedelta(hours=1)

    st.write("Select time window (UTC):")

    from_date = st.date_input("From date", value=default_from.date())
    from_time_val = st.time_input("From time", value=time(default_from.hour, default_from.minute))

    until_date = st.date_input("Until date", value=now.date())
    until_time_val = st.time_input("Until time", value=time(now.hour, now.minute))

    from_time = datetime.combine(from_date, from_time_val)
    until_time = datetime.combine(until_date, until_time_val)

    if st.button("Search") and query.strip():
        backend_url = "http://backend:8000/api/bgp-historic"
        params = {
            "query": query.strip(),
            "from_time": from_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "until_time": until_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        try:
            with st.spinner("Fetching historic data..."):
                response = requests.get(backend_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

            if data:
                df = pd.DataFrame(data)
                if "timestamp" in df.columns:
                    df["timestamp"] = df["timestamp"].apply(format_timestamp)

                columns_to_show = ["timestamp", "type", "prefix", "origin_as", "peer_as", "info"]
                df = df.loc[:, df.columns.intersection(columns_to_show)]

                styled_df = df.style.apply(style_row, axis=1)
                st.dataframe(styled_df)
            else:
                st.info("No historic data found for your query.")

        except Exception as e:
            st.error(f"Error fetching historic data: {e}")

elif mode == "Live Stream (RIPE RIS)":
    st.subheader("🌐 Live RIPE RIS Updates (Real-Time WebSocket)")
    st.write("Receiving real-time BGP announcements...")

    log = st.empty()
    table = st.empty()
    updates = []

    async def receive_ris_stream():
        uri = "ws://ws:8765/ws/ris-live"
        try:
            async with websockets.connect(uri) as ws:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    updates.append(data)
                    df = pd.DataFrame(updates[-50:])
                    if "timestamp" in df.columns:
                        df["timestamp"] = df["timestamp"].apply(format_timestamp)
                    cols = ["timestamp", "type", "prefix", "origin_as", "peer_as", "info"]
                    df = df.loc[:, df.columns.intersection(cols)]
                    styled_df = df.style.apply(style_row, axis=1)
                    table.dataframe(styled_df)
                    await asyncio.sleep(0.1)
        except Exception as e:
            log.error(f"❌ WebSocket Error: {e}")

    def start_stream():
        asyncio.run(receive_ris_stream())

    if st.button("Start Stream"):
        threading.Thread(target=start_stream, daemon=True).start()
