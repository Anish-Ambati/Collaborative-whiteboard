import asyncio
import tkinter as tk
from tkinter import colorchooser, simpledialog
import websockets
import json
import threading

class CollaborativeWhiteboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Collaborative Whiteboard")
        self.canvas = tk.Canvas(root, width=800, height=600, bg="white")
        self.canvas.pack()

        self.username = simpledialog.askstring("Username", "Enter your username")
        self.current_color = "black"
        self.strokes = []
        self.current_stroke = []
        self.shape_mode = None
        self.temp_shape = None

        self.last_x, self.last_y = None, None

        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.end_stroke)

        self.undo_button = tk.Button(root, text="Undo", command=self.undo)
        self.undo_button.pack()

        button_frame = tk.Frame(root)
        button_frame.pack()

        self.color_button = tk.Button(button_frame, text="Choose Color", command=self.choose_color)
        self.color_button.pack(side=tk.LEFT, padx=5)

        self.rect_button = tk.Button(button_frame, text="Rectangle", command=lambda: self.set_shape_mode("rectangle"))
        self.rect_button.pack(side=tk.LEFT, padx=5)

        self.circle_button = tk.Button(button_frame, text="Circle", command=lambda: self.set_shape_mode("circle"))
        self.circle_button.pack(side=tk.LEFT, padx=5)

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_loop, daemon=True).start()

    def choose_color(self):
        color = colorchooser.askcolor()[1]
        if color:
            self.current_color = color

    def set_shape_mode(self, mode):
        self.shape_mode = mode

    def start_draw(self, event):
        self.last_x = event.x
        self.last_y = event.y
        self.current_stroke = []
        self.temp_shape = None

    def draw(self, event):
        x, y = event.x, event.y
        if self.shape_mode in ["rectangle", "circle"]:
            if self.temp_shape:
                self.canvas.delete(self.temp_shape)
            if self.shape_mode == "rectangle":
                self.temp_shape = self.canvas.create_rectangle(self.last_x, self.last_y, x, y, outline=self.current_color, width=2)
            else:
                self.temp_shape = self.canvas.create_oval(self.last_x, self.last_y, x, y, outline=self.current_color, width=2)
        else:
            line_id = self.canvas.create_line(self.last_x, self.last_y, x, y, fill=self.current_color, width=2)
            self.current_stroke.append(line_id)
            data = {
                "type": "draw",
                "x1": self.last_x, "y1": self.last_y,
                "x2": x, "y2": y,
                "color": self.current_color,
                "username": self.username
            }
            asyncio.run_coroutine_threadsafe(self.send_data(data), self.loop)
            self.last_x, self.last_y = x, y

    def end_stroke(self, event):
        if self.shape_mode in ["rectangle", "circle"] and self.temp_shape:
            shape_data = {
                "type": self.shape_mode,
                "x1": self.last_x, "y1": self.last_y,
                "x2": event.x, "y2": event.y,
                "color": self.current_color,
                "username": self.username
            }
            asyncio.run_coroutine_threadsafe(self.send_data(shape_data), self.loop)
            self.strokes.append([self.temp_shape])
            self.temp_shape = None
        elif self.current_stroke:
            self.strokes.append(self.current_stroke)
            self.current_stroke = []
            data = {"type": "end_stroke", "username": self.username}
            asyncio.run_coroutine_threadsafe(self.send_data(data), self.loop)

    def undo(self):
        if self.strokes:
            last = self.strokes.pop()
            for item in last:
                self.canvas.delete(item)
            data = {"type": "undo", "username": self.username}
            asyncio.run_coroutine_threadsafe(self.send_data(data), self.loop)

    async def connect(self):
        uri = "ws://localhost:8000/ws"
        async with websockets.connect(uri) as websocket:
            self.websocket = websocket
            print("Connected to WebSocket")
            await self.receive_data()

    async def send_data(self, data):
        if hasattr(self, "websocket"):
            await self.websocket.send(json.dumps(data))

    async def receive_data(self):
        async for message in self.websocket:
            data = json.loads(message)
            if data["type"] == "draw":
                line_id = self.canvas.create_line(data["x1"], data["y1"], data["x2"], data["y2"], fill=data["color"], width=2)
                self.strokes.append([line_id])
                if data.get("username") and data["username"] != self.username:
                    self.show_username(data["username"], data["x2"], data["y2"])
            elif data["type"] in ["rectangle", "circle"]:
                if data["type"] == "rectangle":
                    shape_id = self.canvas.create_rectangle(data["x1"], data["y1"], data["x2"], data["y2"], outline=data["color"], width=2)
                else:
                    shape_id = self.canvas.create_oval(data["x1"], data["y1"], data["x2"], data["y2"], outline=data["color"], width=2)
                self.strokes.append([shape_id])
                if data.get("username") and data["username"] != self.username:
                    self.show_username(data["username"], data["x2"], data["y2"])
            elif data["type"] == "undo":
                if self.strokes:
                    last = self.strokes.pop()
                    for item in last:
                        self.canvas.delete(item)

    def show_username(self, name, x, y):
        tag = f"user_{name}_{x}_{y}"
        label = self.canvas.create_text(x + 10, y, text=name, fill="gray", anchor="nw", tag=tag)
        self.root.after(1000, lambda: self.canvas.delete(label))

    def start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect())

if __name__ == "__main__":
    root = tk.Tk()
    app = CollaborativeWhiteboard(root)
    root.mainloop()
