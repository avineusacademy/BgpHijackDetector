from fastapi import WebSocket

frontend_clients = set()

async def connect_client(websocket: WebSocket):
    await websocket.accept()
    frontend_clients.add(websocket)

async def disconnect_client(websocket: WebSocket):
    frontend_clients.remove(websocket)
