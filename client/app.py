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

        # Buttons and sliders
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        self.undo_button = tk.Button(button_frame, text="Undo", command=self.handle_undo)
        self.undo_button.pack(side=tk.LEFT, padx=5)

        self.color_button = tk.Button(button_frame, text="Pick Color", command=self.pick_color)
        self.color_button.pack(side=tk.LEFT, padx=5)

        tk.Label(button_frame, text="Thickness:").pack(side=tk.LEFT)
        self.thickness_slider = tk.Scale(button_frame, from_=1, to=10, orient=tk.HORIZONTAL)
        self.thickness_slider.set(2)
        self.thickness_slider.pack(side=tk.LEFT, padx=5)

        self.current_color = "black"
        self.username = simpledialog.askstring("Username", "Enter your name:")

        self.websocket = None
        self.loop = asyncio.new_event_loop()
        self.last_x = None
        self.last_y = None

        self.current_stroke = []
        self.strokes = []

        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.end_stroke)

        threading.Thread(target=self.start_async_loop, daemon=True).start()
        self.root.mainloop()

    def pick_color(self):
        color = colorchooser.askcolor(title="Choose line color")[1]
        if color:
            self.current_color = color

    def start_draw(self, event):
        self.last_x = event.x
        self.last_y = event.y
        self.current_stroke = []

    def draw(self, event):
        x, y = event.x, event.y
        thickness = self.thickness_slider.get()
        line_id = self.canvas.create_line(self.last_x, self.last_y, x, y, fill=self.current_color, width=thickness)
        self.current_stroke.append(line_id)

        data = {
            "type": "draw",
            "x1": self.last_x,
            "y1": self.last_y,
            "x2": x,
            "y2": y,
            "color": self.current_color,
            "thickness": thickness,
            "username": self.username
        }
        asyncio.run_coroutine_threadsafe(self.send_data(data), self.loop)
        self.last_x = x
        self.last_y = y

    def end_stroke(self, event):
        if self.current_stroke:
            self.strokes.append(self.current_stroke)
            self.current_stroke = []

        data = {"type": "end_stroke", "username": self.username}
        asyncio.run_coroutine_threadsafe(self.send_data(data), self.loop)

    def handle_undo(self):
        if self.strokes:
            last_stroke = self.strokes.pop()
            for line_id in last_stroke:
                self.canvas.delete(line_id)

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
                    color = data.get("color", "black")
                    thickness = data.get("thickness", 2)
                    line = self.canvas.create_line(
                        data["x1"], data["y1"], data["x2"], data["y2"],
                        fill=color, width=thickness
                    )
                    self.current_stroke.append(line)
                elif data["type"] == "end_stroke":
                    if self.current_stroke:
                        self.strokes.append(self.current_stroke)
                        self.current_stroke = []
                        if data.get("username") and data["username"] != self.username:
                            self.show_username(data["username"], self.last_x, self.last_y)
                elif data["type"] == "undo":
                    if self.strokes:
                        last_stroke = self.strokes.pop()
                        for line_id in last_stroke:
                            self.canvas.delete(line_id)
        except Exception as e:
            print("WebSocket error:", e)

    def show_username(self, username, x, y):
        label = self.canvas.create_text(x + 10, y + 10, text=username, fill="gray", font=("Arial", 8))
        self.root.after(2000, lambda: self.canvas.delete(label))

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
