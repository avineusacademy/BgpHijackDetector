import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from pyvis.network import Network
import streamlit.components.v1 as components

# Backend API base URL
BACKEND_URL = "http://backend:8000"

st.title("BGP Historic Data Lookup")

with st.sidebar:
    st.header("🔍 Filters")

    asn_filter = st.text_input("Filter by Origin ASN (e.g. 15169)", value="")
    prefix_filter = st.text_input("Filter by Prefix (e.g. 8.8.8.0/24)", value="")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.utcnow().date() - timedelta(days=1))
        start_time = st.time_input("Start Time", datetime.utcnow().time())
    with col2:
        end_date = st.date_input("End Date", datetime.utcnow().date())
        end_time = st.time_input("End Time", datetime.utcnow().time())

    start_ts = datetime.combine(start_date, start_time).isoformat() + "Z"
    end_ts = datetime.combine(end_date, end_time).isoformat() + "Z"

popular_queries = {
    "🌍 Google (AS15169)": "15169",
    "⚡ Cloudflare (AS13335)": "13335",
    "📘 Meta (AS32934)": "32934",
    "🧠 Microsoft (AS8075)": "8075",
    "📡 Cogent (AS174)": "174",
    "🟢 Google DNS (8.8.8.0/24)": "8.8.8.0/24",
    "🟣 Cloudflare DNS (1.1.1.0/24)": "1.1.1.0/24",
    "🧪 Test Prefix (129.250.0.0/16)": "129.250.0.0/16",
    "🔧 Custom Input": "custom"
}

selected = st.selectbox("Select known prefix/ASN or choose custom:", list(popular_queries.keys()))
query = ""

if popular_queries[selected] == "custom":
    query = st.text_input("Enter custom prefix or ASN (e.g. 192.0.2.0/24 or 64500):")
else:
    query = popular_queries[selected]
    st.info(f"Using predefined value: `{query}`")

start_button = st.button("▶️ Start Lookup")
stop_button = st.button("⏹️ Stop Lookup")

# Initialize session state variables
if "polling" not in st.session_state:
    st.session_state.polling = False
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "progress" not in st.session_state:
    st.session_state.progress = 0
if "status_text" not in st.session_state:
    st.session_state.status_text = "Idle. Submit a query and click Start."
if "result_data" not in st.session_state:
    st.session_state.result_data = pd.DataFrame()

progress_bar = st.progress(st.session_state.progress)
status_text = st.empty()
result_area = st.empty()
debug_area = st.empty()

def submit_job(q, start_ts, end_ts):
    try:
        payload = {
            "resource": q,
            "starttime": start_ts,
            "endtime": end_ts
        }
        debug_area.text(f"DEBUG: Submitting job with payload: {json.dumps(payload)}")
        resp = requests.post(
            f"{BACKEND_URL}/api/bgp-historic-job",
            json=payload,
            timeout=10
        )
        resp.raise_for_status()
        job_id = resp.json().get("job_id")
        debug_area.text(f"DEBUG: Job submitted with ID: {job_id}")
        return job_id
    except requests.exceptions.HTTPError as e:
        error_resp = e.response.json() if e.response else {}
        debug_area.text(f"DEBUG: Submit job error: {e} - Response: {error_resp}")
        st.error(f"Failed to submit job: {e}\nDetails: {error_resp}")
        return None
    except Exception as e:
        st.error(f"Failed to submit job: {e}")
        debug_area.text(f"DEBUG: Submit job error: {e}")
        return None

def poll_job(job_id):
    try:
        resp = requests.get(f"{BACKEND_URL}/api/bgp-historic-job/{job_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        debug_area.text(f"DEBUG: Polling job ID {job_id} status: {data.get('status')}")
        return data
    except Exception as e:
        st.error(f"Failed to poll job status: {e}")
        debug_area.text(f"DEBUG: Poll job error: {e}")
        return None

def create_as_path_graph(data):
    if not data:
        return None
    net = Network(height="400px", width="100%", directed=True)
    try:
        for record in data:
            attrs = record if isinstance(record, dict) else {}
            path = attrs.get("attrs", {}).get("path", [])
            for i in range(len(path)):
                net.add_node(path[i], label=str(path[i]))
                if i > 0:
                    net.add_edge(path[i - 1], path[i])
        return net
    except Exception as e:
        st.warning(f"Graph error: {e}")
        return None

if start_button and query.strip():
    job_id = submit_job(query.strip(), start_ts, end_ts)
    if job_id:
        st.session_state.job_id = job_id
        st.session_state.polling = True
        st.session_state.progress = 0
        st.session_state.status_text = "Job submitted. Polling for results..."
        st.session_state.result_data = pd.DataFrame()

if stop_button:
    st.session_state.polling = False
    st.session_state.job_id = None
    st.session_state.progress = 0
    st.session_state.status_text = "Lookup stopped."
    st.session_state.result_data = pd.DataFrame()
    result_area.empty()
    debug_area.empty()

if st.session_state.polling and st.session_state.job_id:
    job_status = poll_job(st.session_state.job_id)

    if not job_status:
        st.session_state.status_text = "Failed to get job status."
        st.session_state.polling = False
    else:
        status = job_status.get("status")
        data = job_status.get("result")

        if data and data.get("data", {}).get("updates"):
            st.session_state.status_text = "Data received! Stopping lookup."
            st.session_state.polling = False

            records = data.get("data", {}).get("updates", [])

            if asn_filter:
                records = [r for r in records if str(r.get("attrs", {}).get("path", [])[-1]) == asn_filter]
            if prefix_filter:
                records = [r for r in records if prefix_filter in r.get("attrs", {}).get("target_prefix", "")]

            if records:
                rows = []
                for record in records:
                    attrs = record.get("attrs", {})
                    rows.append({
                        "Timestamp": record.get("timestamp"),
                        "Source ID": attrs.get("source_id"),
                        "Target Prefix": attrs.get("target_prefix"),
                        "Path": " → ".join(str(x) for x in attrs.get("path", [])),
                        "Community": ", ".join(attrs.get("community", [])),
                        "Type": record.get("type"),
                    })
                df = pd.DataFrame(rows)
                st.session_state.result_data = df

                graph = create_as_path_graph(records)
                if graph:
                    graph.save_graph("as_path.html")
                    with open("as_path.html", 'r', encoding='utf-8') as f:
                        components.html(f.read(), height=450)
                else:
                    st.warning("No graph generated.")
            else:
                st.warning("No records after filtering.")

            json_str = json.dumps(data, indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_str,
                file_name=f"bgp_updates_{query.replace('/', '_')}.json",
                mime="application/json"
            )

        elif status == "completed":
            st.session_state.progress = 100
            st.session_state.status_text = "Job completed!"
            st.session_state.polling = False

        elif status == "failed":
            st.session_state.progress = 0
            st.session_state.status_text = f"Job failed: {job_status.get('error')}"
            st.session_state.polling = False

        else:
            st.session_state.progress = min(st.session_state.progress + 10, 90)
            st.session_state.status_text = f"Job status: {status}. Polling..."

progress_bar.progress(st.session_state.progress)
status_text.text(st.session_state.status_text)

if not st.session_state.result_data.empty:
    result_area.dataframe(st.session_state.result_data)

debug_area.markdown("### Debug Info")
debug_area.text(f"Polling: {st.session_state.polling}, Job ID: {st.session_state.job_id}")
