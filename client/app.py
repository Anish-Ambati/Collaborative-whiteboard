import tkinter as tk
from tkinter import colorchooser, simpledialog
import asyncio
import json
import websockets
import threading

class CollaborativeWhiteboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Collaborative Whiteboard")

        self.canvas = tk.Canvas(self.root, width=800, height=600, bg="white")
        self.canvas.pack()

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="Undo", command=self.request_undo).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Pick Color", command=self.pick_color).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Pen", command=lambda: self.set_tool("pen")).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Rectangle", command=lambda: self.set_tool("rectangle")).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Circle", command=lambda: self.set_tool("circle")).pack(side=tk.LEFT, padx=5)

        self.current_color = "black"
        self.tool = "pen"

        self.username = simpledialog.askstring("Username", "Enter your name:")
        self.room_id = simpledialog.askstring("Room", "Enter room ID:")

        self.websocket = None
        self.loop = asyncio.new_event_loop()

        self.start_x = None
        self.start_y = None
        self.is_replaying = False

        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.end_stroke)

        threading.Thread(target=self.start_async_loop, daemon=True).start()
        self.root.mainloop()

    def set_tool(self, tool):
        self.tool = tool

    def pick_color(self):
        color = colorchooser.askcolor(title="Choose color")[1]
        if color:
            self.current_color = color

    def start_draw(self, event):
        self.start_x, self.start_y = event.x, event.y

    def draw(self, event):
        if self.tool != "pen":
            return

        payload = {
            "tool": "pen",
            "x1": self.start_x,
            "y1": self.start_y,
            "x2": event.x,
            "y2": event.y,
            "color": self.current_color,
            "width": 2
        }

        # ✅ LOCAL RENDER
        self.render_draw(payload)

        # ✅ SEND TO SERVER
        asyncio.run_coroutine_threadsafe(
            self.send({"type": "draw", "payload": payload}),
            self.loop
        )

        self.start_x, self.start_y = event.x, event.y

    def end_stroke(self, event):
        if self.tool in {"rectangle", "circle"}:
            payload = {
                "tool": self.tool,
                "x1": self.start_x,
                "y1": self.start_y,
                "x2": event.x,
                "y2": event.y,
                "color": self.current_color,
                "width": 2
            }

            self.render_draw(payload)

            asyncio.run_coroutine_threadsafe(
                self.send({"type": "draw", "payload": payload}),
                self.loop
            )

        asyncio.run_coroutine_threadsafe(
            self.send({"type": "end_stroke", "payload": {}}),
            self.loop
        )

    def request_undo(self):
        asyncio.run_coroutine_threadsafe(
            self.send({"type": "undo", "payload": {}}),
            self.loop
        )

    async def send(self, data):
        if self.websocket:
            await self.websocket.send(json.dumps(data))

    async def receive(self):
        async for raw in self.websocket:
            message = json.loads(raw)
            msg_type = message["type"]

            if msg_type == "draw":
                if not self.is_replaying:
                    self.render_draw(message["payload"])

            elif msg_type == "reset":
                self.is_replaying = True
                self.canvas.delete("all")

                for action in message["payload"]["actions"]:
                    if action["type"] == "draw":
                        self.render_draw(action["payload"])

                self.is_replaying = False

    def render_draw(self, p):
        if p["tool"] == "pen":
            self.canvas.create_line(
                p["x1"], p["y1"], p["x2"], p["y2"],
                fill=p["color"], width=p["width"]
            )
        elif p["tool"] == "rectangle":
            self.canvas.create_rectangle(
                p["x1"], p["y1"], p["x2"], p["y2"],
                outline=p["color"], width=p["width"]
            )
        elif p["tool"] == "circle":
            self.canvas.create_oval(
                p["x1"], p["y1"], p["x2"], p["y2"],
                outline=p["color"], width=p["width"]
            )

    async def connect(self):
        self.websocket = await websockets.connect(
            f"ws://localhost:8000/ws/{self.room_id}"
        )
        await self.receive()

    def start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect())


if __name__ == "__main__":
    CollaborativeWhiteboard()
