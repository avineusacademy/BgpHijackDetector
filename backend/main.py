from fastapi import FastAPI, WebSocket, Query, HTTPException
from datetime import datetime, timedelta
from ipaddress import ip_network
from typing import Optional
from bgpstream_utils import get_bgpstream_data
from websocket_handler import connect_client, disconnect_client
import asyncio
from rislive_ws import ris_live_listener

app = FastAPI()

@app.get("/bgpstream")
async def bgpstream_route(from_time: str, until_time: str):
    return get_bgpstream_data(from_time, until_time)

@app.get("/api/bgp-historic")
async def bgp_historic(
    query: str = Query(..., description="Prefix (CIDR) or AS number"),
    from_time: Optional[str] = Query(None, description="Start time in ISO format"),
    until_time: Optional[str] = Query(None, description="End time in ISO format"),
):
    try:
        # Default time window: last 1 hour UTC if not provided
        if until_time is None:
            until_dt = datetime.utcnow()
            until_time = until_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            until_dt = datetime.strptime(until_time, "%Y-%m-%dT%H:%M:%SZ")

        if from_time is None:
            from_dt = until_dt - timedelta(hours=1)
            from_time = from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            from_dt = datetime.strptime(from_time, "%Y-%m-%dT%H:%M:%SZ")

        # Fetch raw data
        raw_data = get_bgpstream_data(from_time, until_time)

        # Determine if query is CIDR prefix
        try:
            query_net = ip_network(query, strict=False)
            is_prefix_query = True
        except ValueError:
            is_prefix_query = False
            query_net = None

        query_as = query.upper().replace("AS", "").strip()

        filtered = []
        for item in raw_data:
            prefix_str = item.get("prefix", "")
            origin_as_str = str(item.get("origin_as", ""))
            peer_as_str = str(item.get("peer_as", ""))

            # Prefix match for CIDR queries
            if is_prefix_query:
                try:
                    prefix_net = ip_network(prefix_str, strict=False)
                    if prefix_net.subnet_of(query_net) or query_net.subnet_of(prefix_net):
                        filtered.append(item)
                        continue
                except ValueError:
                    pass

            # AS number match
            if query_as and (query_as == origin_as_str or query_as == peer_as_str):
                filtered.append(item)
                continue

        return filtered

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching historic data: {str(e)}")

@app.websocket("/ws/ris-live")
async def ris_websocket(ws: WebSocket):
    await connect_client(ws)
    try:
        while True:
            await ws.receive_text()  # Keep connection alive
    except:
        await disconnect_client(ws)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(ris_live_listener())
