import requests
from datetime import datetime, timedelta, timezone

def fetch_ripe_update_data(query: str, max_records: int = 1000):
    now = datetime.now(timezone.utc)
    until = now - timedelta(minutes=1)
    start = until - timedelta(hours=1)

    params = {
        "resource": ("AS" + query) if query.isdigit() else query,
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endtime": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rrcs": "",
        "max_records": str(max_records)
    }

    url = "https://stat.ripe.net/data/bgp-updates/data.json"
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        upd = resp.json().get("data", {}).get("updates", [])
        results = []
        for u in upd:
            results.append({
                "timestamp": u.get("timestamp"),
                "type": "announcement" if u.get("type") == "A" else "withdrawal",
                "prefix": u.get("target_prefix"),
                "origin_as": (u.get("path") or [])[-1] if u.get("path") else None,
                "peer_as": None,
                "info": u.get("community") or ""
            })
            if len(results) >= max_records:
                break
        return results
    except Exception as e:
        return str(e)
