from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
from collections import defaultdict

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms = defaultdict(lambda: {"clients": [], "actions": []})


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    room = rooms[room_id]
    room["clients"].append(websocket)

    # Send full state on join
    await websocket.send_text(json.dumps({
        "type": "reset",
        "payload": {"actions": room["actions"]}
    }))

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            msg_type = message["type"]

            if msg_type in {"draw", "end_stroke"}:
                room["actions"].append(message)

                for client in room["clients"]:
                    if client != websocket:
                        await client.send_text(json.dumps(message))

            elif msg_type == "undo":
                while room["actions"]:
                    last = room["actions"].pop()
                    if last["type"] == "end_stroke":
                        break

                reset_msg = {
                    "type": "reset",
                    "payload": {"actions": room["actions"]}
                }

                for client in room["clients"]:
                    await client.send_text(json.dumps(reset_msg))

    except WebSocketDisconnect:
        room["clients"].remove(websocket)
