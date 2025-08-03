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

        self.undo_button = tk.Button(button_frame, text="Undo", command=self.handle_undo)
        self.undo_button.pack(side=tk.LEFT, padx=5)

        self.color_button = tk.Button(button_frame, text="Pick Color", command=self.pick_color)
        self.color_button.pack(side=tk.LEFT, padx=5)

        self.pen_button = tk.Button(button_frame, text="Pen", command=lambda: self.set_tool("pen"))
        self.pen_button.pack(side=tk.LEFT, padx=5)

        self.rect_button = tk.Button(button_frame, text="Rectangle", command=lambda: self.set_tool("rectangle"))
        self.rect_button.pack(side=tk.LEFT, padx=5)

        self.circle_button = tk.Button(button_frame, text="Circle", command=lambda: self.set_tool("circle"))
        self.circle_button.pack(side=tk.LEFT, padx=5)

        self.current_color = "black"
        self.username = simpledialog.askstring("Username", "Enter your name:")
        self.websocket = None
        self.loop = asyncio.new_event_loop()

        self.tool = "pen"
        self.strokes = []
        self.current_stroke = []
        self.start_x = None
        self.start_y = None

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
        self.current_stroke = []

    def draw(self, event):
        if self.tool == "pen":
            x, y = event.x, event.y
            line = self.canvas.create_line(self.start_x, self.start_y, x, y, fill=self.current_color, width=2)
            self.current_stroke.append(line)

            data = {
                "type": "draw",
                "tool": "pen",
                "x1": self.start_x,
                "y1": self.start_y,
                "x2": x,
                "y2": y,
                "color": self.current_color,
                "username": self.username
            }
            asyncio.run_coroutine_threadsafe(self.send_data(data), self.loop)
            self.start_x, self.start_y = x, y

    def end_stroke(self, event):
        shape_id = None
        if self.tool == "rectangle":
            shape_id = self.canvas.create_rectangle(self.start_x, self.start_y, event.x, event.y, outline=self.current_color, width=2)
        elif self.tool == "circle":
            shape_id = self.canvas.create_oval(self.start_x, self.start_y, event.x, event.y, outline=self.current_color, width=2)

        if shape_id:
            self.current_stroke.append(shape_id)
            data = {
                "type": "draw",
                "tool": self.tool,
                "x1": self.start_x,
                "y1": self.start_y,
                "x2": event.x,
                "y2": event.y,
                "color": self.current_color,
                "username": self.username
            }
            asyncio.run_coroutine_threadsafe(self.send_data(data), self.loop)

        if self.current_stroke:
            self.strokes.append(self.current_stroke)
            self.current_stroke = []

        data = {"type": "end_stroke", "username": self.username}
        asyncio.run_coroutine_threadsafe(self.send_data(data), self.loop)

    def handle_undo(self):
        if self.strokes:
            last_stroke = self.strokes.pop()
            for shape in last_stroke:
                self.canvas.delete(shape)

            data = {"type": "undo", "username": self.username}
            asyncio.run_coroutine_threadsafe(self.send_data(data), self.loop)

    async def send_data(self, data):
        if self.websocket:
            await self.websocket.send(json.dumps(data))

    async def receive_data(self):
        try:
            async for message in self.websocket:
                data = json.loads(message)
                if data["type"] == "draw":
                    tool = data.get("tool", "pen")
                    color = data.get("color", "black")
                    if tool == "pen":
                        line = self.canvas.create_line(data["x1"], data["y1"], data["x2"], data["y2"], fill=color, width=2)
                        self.current_stroke.append(line)
                    elif tool == "rectangle":
                        rect = self.canvas.create_rectangle(data["x1"], data["y1"], data["x2"], data["y2"], outline=color, width=2)
                        self.current_stroke.append(rect)
                    elif tool == "circle":
                        oval = self.canvas.create_oval(data["x1"], data["y1"], data["x2"], data["y2"], outline=color, width=2)
                        self.current_stroke.append(oval)

                elif data["type"] == "end_stroke":
                    if self.current_stroke:
                        self.strokes.append(self.current_stroke)
                        self.current_stroke = []

                elif data["type"] == "undo":
                    if self.strokes:
                        last_stroke = self.strokes.pop()
                        for item in last_stroke:
                            self.canvas.delete(item)

        except Exception as e:
            print("WebSocket error:", e)

    async def connect(self):
        try:
            self.websocket = await websockets.connect("ws://localhost:8000/ws")
            print("Connected to WebSocket")
            await self.receive_data()
        except Exception as e:
            print(f"Connection error: {e}")

    def start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect())

if __name__ == "__main__":
    CollaborativeWhiteboard()
