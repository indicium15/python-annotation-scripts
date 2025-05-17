import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import csv
import os
import argparse
import sys

class CourtSelector:
    def __init__(self, video_path, num_points, output_csv):
        self.video_path = video_path
        self.num_points = num_points
        self.output_csv = output_csv
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video '{self.video_path}'")
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.current_frame_idx = 0

        self.points = [
            {"index": i+1, "x": "", "y": "", "grx": "", "gry": ""}
            for i in range(self.num_points)
        ]

        self.root = tk.Tk()
        self.root.title("Select Court Points")
        self.root.protocol("WM_DELETE_WINDOW", self.on_save)
        self.root.bind("<Left>", lambda e: self.prev_frame())
        self.root.bind("<Right>", lambda e: self.next_frame())

        self.setup_gui()
        self.root.update_idletasks()
        self.display_width = self.canvas.winfo_width()
        self.display_height = self.canvas.winfo_height()
        self.load_frame()
        self.root.mainloop()


    def setup_gui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=450)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)

        ctrl = tk.Frame(self.root)
        ctrl.pack(pady=5)
        tk.Button(ctrl, text="<< Prev", command=self.prev_frame).grid(row=0, column=0)
        tk.Button(ctrl, text=">> Next", command=self.next_frame).grid(row=0, column=1)
        tk.Button(ctrl, text="Reset", command=self.reset_points).grid(row=0, column=2)
        self.frame_label = tk.Label(ctrl, text="Frame: 0")
        self.frame_label.grid(row=0, column=3, padx=10)

        outer_frame = tk.Frame(self.root)
        outer_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        canvas = tk.Canvas(outer_frame, height=300)
        scrollbar = tk.Scrollbar(outer_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        table_window = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        def resize_canvas(event):
            canvas.itemconfig(table_window, width=event.width)
        canvas.bind("<Configure>", resize_canvas)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        cols = ("Point", "X", "Y", "GrX", "GrY", "Delete")
        self.table = ttk.Treeview(self.scrollable_frame, columns=cols, show="headings", height=20)
        for c in cols:
            self.table.heading(c, text=c)
            self.table.column(c, width=80, anchor=tk.CENTER)
        self.table.pack(fill="both", expand=True)
        self.table.bind("<Button-1>", self.on_table_click)
        self.table.bind("<Double-1>", self.on_double_click)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Save & Exit", command=self.on_save).pack()

    def load_frame(self):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx)
        ret, frame = self.cap.read()
        if not ret:
            return
        self.frame_bgr = frame.copy()
        self.frame_label.config(text=f"Frame: {self.current_frame_idx}")
        self.display_frame()
        self.update_table()

    def display_frame(self):
        self.canvas.delete("all")  # Clear previous frame (optional but avoids stacking)
        disp = self.frame_bgr.copy()
        for pt in self.points:
            if pt["x"] and pt["y"]:
                x, y = int(pt["x"]), int(pt["y"])
                cv2.circle(disp, (x,y), 5, (0,255,0), -1)
                cv2.putText(disp, f"P{pt['index']}", (x+5,y-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)

        self.original_width = disp.shape[1]
        self.original_height = disp.shape[0]

        img = Image.fromarray(rgb).resize((self.display_width, self.display_height))
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

    def update_table(self):
        for r in self.table.get_children():
            self.table.delete(r)
        for pt in self.points:
            vals = (f"Point{pt['index']}", pt["x"], pt["y"], pt["grx"], pt["gry"], "Delete")
            self.table.insert("", "end", iid=str(pt["index"]), values=vals)

    def on_click(self, event):
        # Scale back to original resolution
        x_scale = self.original_width / self.display_width
        y_scale = self.original_height / self.display_height

        fx = int(event.x * x_scale)
        fy = int(event.y * y_scale)

        for pt in self.points:
            if not pt["x"] and not pt["y"]:
                pt["x"], pt["y"] = str(fx), str(fy)
                break
        self.display_frame()
        self.update_table()


    def on_table_click(self, event):
        if self.table.identify("region", event.x, event.y) != "cell":
            return
        col = self.table.identify_column(event.x)
        row = self.table.identify_row(event.y)
        if not row or col != "#6":
            return
        idx = int(row) - 1
        self.points[idx].update({"x": "", "y": "", "grx": "", "gry": ""})
        self.display_frame()
        self.update_table()

    def on_double_click(self, event):
        if self.table.identify("region", event.x, event.y) != "cell":
            return
        col = self.table.identify_column(event.x)
        row = self.table.identify_row(event.y)
        if not row or col not in ("#4", "#5"):
            return
        ci = int(col.replace("#", "")) - 1
        x0, y0, w, h = self.table.bbox(row, col)
        old = self.table.item(row)["values"][ci]
        entry = tk.Entry(self.table)
        entry.insert(0, old)
        entry.place(x=x0, y=y0, width=w, height=h)
        entry.focus()
        def save(e=None):
            new = entry.get()
            pt = self.points[int(row)-1]
            if ci == 3: pt["grx"] = new
            else: pt["gry"] = new
            entry.destroy()
            self.update_table()
        entry.bind("<Return>", save)
        entry.bind("<FocusOut>", lambda e: entry.destroy())

    def prev_frame(self):
        if self.current_frame_idx > 0:
            self.current_frame_idx -= 1
            self.load_frame()

    def next_frame(self):
        if self.current_frame_idx < self.total_frames - 1:
            self.current_frame_idx += 1
            self.load_frame()

    def reset_points(self):
        for pt in self.points:
            pt.update({"x": "", "y": "", "grx": "", "gry": ""})
        self.display_frame()
        self.update_table()

    def on_save(self):
        os.makedirs(os.path.dirname(self.output_csv) or ".", exist_ok=True)
        with open(self.output_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Point", "X", "Y", "GrX", "GrY"])
            for pt in self.points:
                writer.writerow([
                    f"Point{pt['index']}", pt["x"], pt["y"], pt["grx"], pt["gry"]
                ])
        self.root.destroy()

def main(video_path=None, num_points=None, output_csv=None):
    if not video_path or not num_points:
        print("Error: You must provide at least a video path and number of points.")
        return

    if output_csv is None:
        base = os.path.splitext(os.path.basename(video_path))[0]
        folder = os.path.dirname(video_path)
        output_csv = os.path.join(folder, base + "_calibrated.csv")

    CourtSelector(video_path, num_points, output_csv)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Court point selector with calibration")
        parser.add_argument("num_points", type=int, help="Number of points to tag")
        parser.add_argument("video_path", type=str, help="Path to video file")
        parser.add_argument("--output_csv", type=str, help="Optional output CSV path")
        args = parser.parse_args()
        main(args.video_path, args.num_points, args.output_csv)
    else:
        # Define your paths here if you don't want to use command line
        VIDEO_PATH = "example/tennis_test.mp4"
        NUM_POINTS = 4
        # By default, output csv is saved to the same path as the video + "_calibrated.csv"
        OUTPUT_CSV = None
        main(VIDEO_PATH, NUM_POINTS)
