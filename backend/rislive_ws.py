from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import json
from datetime import datetime
import websockets

app = FastAPI()

frontend_clients = set()
PING_INTERVAL = 10  # seconds
PING_TIMEOUT = 15   # seconds

# --- Client Connection Management ---

async def connect_client(ws: WebSocket):
    await ws.accept()
    frontend_clients.add(ws)

async def disconnect_client(ws: WebSocket):
    frontend_clients.discard(ws)
    try:
        # Only attempt close if not already closed
        await ws.close()
    except RuntimeError:
        # WebSocket already closed, ignore
        pass

# --- Health Check Endpoint ---

@app.get("/health")
async def health():
    return {"status": "ok"}

# --- WebSocket Handler for Frontend Connections ---

@app.websocket("/ws/ris-live")
async def ris_websocket(ws: WebSocket):
    await connect_client(ws)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=PING_TIMEOUT)
            except asyncio.TimeoutError:
                # Ping timeout, just continue waiting or could send ping if desired
                continue

            if msg == "ping":
                await ws.send_text("pong")

    except WebSocketDisconnect:
        # Client disconnected normally
        await disconnect_client(ws)

    except Exception as e:
        print(f"[WS Error] {e}")
        await disconnect_client(ws)

# --- RIS Live Stream Listener ---

async def ris_live_listener():
    uri = "wss://ris-live.ripe.net/v1/ws/"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("INFO:rislive_ws:Subscribed to RIS UPDATE stream.")
                subscribe_msg = {
                    "type": "ris_sub",
                    "data": {
                        "type": "UPDATE"
                    }
                }
                await websocket.send(json.dumps(subscribe_msg))

                while True:
                    msg = await websocket.recv()
                    data = json.loads(msg)

                    if data.get("type") == "UPDATE":
                        announcements = data.get("data", {}).get("announcements", [])
                        for ann in announcements:
                            prefix = ann.get("prefix", "")
                            origin_as = ann.get("next_hop", "")
                            timestamp = data["data"]["timestamp"]

                            update = {
                                "prefix": prefix,
                                "origin_as": origin_as,
                                "timestamp": datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%SZ")
                            }

                            # Broadcast update to all connected frontend clients
                            for client in list(frontend_clients):
                                try:
                                    await client.send_json(update)
                                except Exception:
                                    await disconnect_client(client)

        except Exception as e:
            print(f"[RIS Live Error] {e}")
            await asyncio.sleep(5)

# --- Background Task for Heartbeat Pings ---

async def websocket_heartbeat():
    while True:
        await asyncio.sleep(PING_INTERVAL)

        stale_clients = []
        for client in list(frontend_clients):
            try:
                await client.send_text("ping")
            except Exception:
                stale_clients.append(client)

        for client in stale_clients:
            await disconnect_client(client)

# --- Startup Hook ---

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(ris_live_listener())
    asyncio.create_task(websocket_heartbeat())
