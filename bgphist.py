import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import requests
import io
import folium
from streamlit_folium import st_folium
import random

st.set_page_config(layout="wide")
st.title("📡 RIPE Stat ASN & Prefix Data Explorer")

# Popular Queries dropdown options
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

def is_asn(val): 
    val = val.strip().upper()
    return val.startswith("AS") or val.isdigit()

def is_prefix(val): 
    return "/" in val

@st.cache_data(show_spinner=False)
def fetch_json_cached(url, params):
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def draw_as_path_graph(as_paths):
    G = nx.DiGraph()
    edge_freq = {}
    for path in as_paths:
        if not isinstance(path, list) or len(path) < 2:
            continue
        for i in range(len(path)-1):
            edge = (path[i], path[i+1])
            edge_freq[edge] = edge_freq.get(edge, 0) + 1
    for edge, freq in edge_freq.items():
        G.add_edge(edge[0], edge[1], weight=freq)
    if len(G.nodes) == 0:
        st.warning("Not enough AS path data to build hops graph.")
        return

    fig, ax = plt.subplots(figsize=(10, 7))
    pos = nx.spring_layout(G, k=0.5, seed=42)
    edges, weights = zip(*nx.get_edge_attributes(G, 'weight').items())
    nx.draw_networkx_nodes(G, pos, node_size=300, node_color='lightgreen', ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=edges, width=[w * 0.1 for w in weights],
                           arrowstyle='->', arrowsize=10, edge_color='gray', ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=8, ax=ax)
    ax.set_title("AS Path Hops Network Graph")
    ax.axis('off')
    st.pyplot(fig)

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    st.download_button("📤 Download AS Path Graph (PNG)", buf.getvalue(), file_name="as_path_graph.png", mime="image/png")

def filter_dataframe(df, column_name, label="Filter by"):
    user_input = st.text_input(f"{label} ({column_name})", "")
    if user_input:
        return df[df[column_name].astype(str).str.contains(user_input, case=False, na=False)]
    return df

def generate_color():
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

def show_geo_map(resource):
    try:
        m = None
        if resource.upper().startswith("AS"):
            prefixes_data = fetch_json_cached("https://stat.ripe.net/data/announced-prefixes/data.json", {"resource": resource})
            prefixes = prefixes_data.get("data", {}).get("prefixes", [])
            if not prefixes:
                st.warning("No prefixes found for this ASN.")
                return

            prefixes = prefixes[:10]  # Limit to top 10 prefixes to speed up map loading

            m = folium.Map(location=[20,0], zoom_start=2)
            progress = st.progress(0)
            total = len(prefixes)
            for idx, prefix_entry in enumerate(prefixes):
                prefix = prefix_entry.get("prefix")
                if not prefix:
                    continue
                try:
                    geo_data = fetch_json_cached("https://stat.ripe.net/data/geoloc/data.json", {"resource": prefix})
                    locations = geo_data.get("data", {}).get("locations", [])
                    color = generate_color()
                    for loc in locations:
                        folium.CircleMarker(
                            location=[loc['latitude'], loc['longitude']],
                            radius=5,
                            popup=f"{prefix} ({loc.get('city','')}, {loc.get('country','')})",
                            color=color,
                            fill=True,
                            fill_color=color
                        ).add_to(m)
                except:
                    pass
                progress.progress(int((idx+1)/total * 100))
            progress.empty()

            st.subheader(f"🌍 Geolocation Map of Announced Prefixes for {resource} (top 10 shown)")
            st_folium(m, width=900, height=600)
        else:
            geo_data = fetch_json_cached("https://stat.ripe.net/data/geoloc/data.json", {"resource": resource})
            locations = geo_data.get("data", {}).get("locations", [])
            if not locations:
                st.warning("No geolocation data found.")
                return
            m = folium.Map(location=[locations[0]['latitude'], locations[0]['longitude']], zoom_start=3)
            for loc in locations:
                folium.Marker(
                    [loc['latitude'], loc['longitude']],
                    popup=f"{resource} ({loc.get('city', '')}, {loc.get('country', '')})"
                ).add_to(m)
            st.subheader(f"🌍 Geolocation Map for {resource}")
            st_folium(m, width=900, height=600)
    except Exception as e:
        st.error(f"Geolocation fetch failed: {e}")

# UI Inputs
selection = st.selectbox("Choose ASN or Prefix", list(popular_queries.keys()))
input_val = st.text_input("Enter ASN or Prefix", "") if selection == "🔧 Custom Input" else popular_queries[selection]

if input_val:
    val = input_val.strip()
    is_as = is_asn(val)
    is_pre = is_prefix(val)

    if not (is_as or is_pre):
        st.error("Please enter a valid ASN (e.g. AS15169 or 15169) or IP prefix (e.g. 8.8.8.0/24).")
        st.stop()

    if is_as:
        asn = val.upper().replace("AS", "")
        st.header(f"🧠 Data for AS{asn}")

        # AS Overview
        try:
            data = fetch_json_cached("https://stat.ripe.net/data/as-overview/data.json", {"resource": f"AS{asn}"})
            overview = data.get("data", {}).get("overview", {})
        except Exception as e:
            st.error(f"Failed to fetch AS Overview: {e}")
            overview = {}

        if overview:
            st.subheader("🔍 AS Overview")
            st.table(pd.DataFrame(overview, index=[0]).T)

        # Geolocation map of all announced prefixes
        show_geo_map(f"AS{asn}")

        # Announced Prefixes
        try:
            data = fetch_json_cached("https://stat.ripe.net/data/announced-prefixes/data.json", {"resource": f"AS{asn}"})
            prefixes = data.get("data", {}).get("prefixes", [])
        except Exception as e:
            st.error(f"Failed to fetch announced prefixes: {e}")
            prefixes = []

        if prefixes:
            st.subheader("📦 Announced Prefixes")
            df_prefixes = pd.DataFrame(prefixes)

            if 'path' in df_prefixes.columns:
                df_prefixes['as_path_str'] = df_prefixes['path'].apply(lambda p: ' '.join(map(str, p)) if isinstance(p, list) else "")
                df_prefixes['as_path_length'] = df_prefixes['path'].apply(lambda p: len(p) if isinstance(p, list) else 0)

            columns_to_show = [c for c in ['prefix', 'origin', 'next_hop', 'as_path_str', 'as_path_length'] if c in df_prefixes.columns]

            filtered = filter_dataframe(df_prefixes[columns_to_show], "prefix", label="🔍 Search Prefix")

            st.markdown(f"**Total Prefixes (filtered):** {len(filtered)}")
            if 'as_path_length' in filtered.columns:
                st.markdown(f"**Avg AS Path Length:** {filtered['as_path_length'].mean():.2f}")
            st.dataframe(filtered)

            st.download_button("📥 Download Prefixes CSV", filtered.to_csv(index=False).encode('utf-8'),
                               file_name="announced_prefixes.csv", mime="text/csv")

            # IPv4 vs IPv6 Pie chart
            if 'prefix' in df_prefixes.columns:
                df_prefixes['family'] = df_prefixes['prefix'].apply(lambda x: 'IPv6' if ':' in x else 'IPv4')
                pie_data = df_prefixes['family'].value_counts()
                fig, ax = plt.subplots()
                ax.pie(pie_data, labels=pie_data.index, autopct='%1.1f%%', startangle=140)
                ax.set_title("IPv4 vs IPv6 Distribution")
                st.pyplot(fig)

    elif is_pre:
        prefix = val
        st.header(f"📨 Routing Status for {prefix}")

        try:
            data = fetch_json_cached("https://stat.ripe.net/data/routing-status/data.json", {"resource": prefix})
            announcements = data.get("data", {}).get("announcements", [])
        except Exception as e:
            st.error(f"Failed to fetch routing status: {e}")
            announcements = []

        # Show geolocation of prefix
        show_geo_map(prefix)

        if announcements:
            df = pd.DataFrame(announcements)
            if 'path' in df.columns:
                df['as_path_str'] = df['path'].apply(lambda p: ' '.join(map(str, p)) if isinstance(p, list) else "")
                df['as_path_length'] = df['path'].apply(lambda p: len(p) if isinstance(p, list) else 0)

            columns_to_show = [c for c in ['prefix', 'origin', 'next_hop', 'as_path_str', 'as_path_length'] if c in df.columns]

            st.subheader("📜 Routing Announcements")
            filtered = filter_dataframe(df[columns_to_show], "origin", label="🔍 Search Origin ASN")

            st.markdown(f"**Total Announcements (filtered):** {len(filtered)}")
            if 'as_path_length' in filtered.columns:
                st.markdown(f"**Avg AS Path Length:** {filtered['as_path_length'].mean():.2f}")
            st.dataframe(filtered)

            st.download_button("📥 Download Announcements CSV", filtered.to_csv(index=False).encode('utf-8'),
                               file_name="routing_announcements.csv", mime="text/csv")

            # AS path graph
            if 'path' in df.columns and df['path'].notnull().any():
                as_paths = df['path'].dropna().tolist()
                draw_as_path_graph(as_paths)

else:
    st.info("Select or enter an ASN or prefix above.")

