import asyncio
import websockets
import json

async def client():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        await websocket.send("Hello server!")
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Received from server: {data}")

if __name__ == "__main__":
    asyncio.run(client())
