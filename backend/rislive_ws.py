from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import asyncio
import json
from datetime import datetime
from websocket_handler import frontend_clients, connect_client, disconnect_client
import websockets

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await connect_client(websocket)
    try:
        while True:
            await websocket.receive_text()  # keeps connection alive
    except WebSocketDisconnect:
        await disconnect_client(websocket)

async def ris_live_listener():
    uri = "wss://ris-live.ripe.net/v1/ws/"
    async with websockets.connect(uri) as websocket:
        subscribe_msg = {
            "type": "ris_sub",
            "data": {
                "type": "UPDATE"
            }
        }
        await websocket.send(json.dumps(subscribe_msg))

        while True:
            try:
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
                            "timestamp": datetime.utcfromtimestamp(timestamp).isoformat()
                        }

                        for ws in list(frontend_clients):
                            await ws.send_json(update)

            except Exception as e:
                print(f"[RIS Live Error] {e}")
                await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(ris_live_listener())

if __name__ == "__main__":
    uvicorn.run("rislive_ws:app", host="0.0.0.0", port=8765)
