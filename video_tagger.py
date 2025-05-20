import tkinter as tk
from tkinter import ttk
import cv2
import csv
import os
from PIL import Image, ImageTk
import argparse
import sys

# Define paths here
VIDEO_PATH = "example/tennis_test.mp4"
LABELS_CSV = "example/labels.csv"
# By default, output csv is saved to the same path as the video + "_tagged.csv"
OUTPUT_CSV = None

class VideoTagger:
    def __init__(self, root, video_path, label_list, output_csv):
        self.root = root
        self.video_path = video_path
        self.labels = label_list
        self.output_csv = output_csv
        self.current_frame_idx = 0
        self.clicked_points = []
        self.is_playing = False
        self.slider_programmatic = False


        self.selected_label = tk.StringVar(value=self.labels[0])

        self.cap = cv2.VideoCapture(self.video_path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.duration = self.total_frames / self.fps

        self.setup_gui()
        self._canvas_img_id = None  # Used to store the image ID on the canvas
        self.root.update_idletasks()
        self.display_width = self.canvas.winfo_width()
        self.display_height = self.canvas.winfo_height()
        self.load_frame(self.current_frame_idx)
        self.root.bind("<Left>", lambda event: self.prev_frame())
        self.root.bind("<Right>", lambda event: self.next_frame())

    def setup_gui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=450)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)

        ctrl_frame = tk.Frame(self.root)
        ctrl_frame.pack()

        tk.Button(ctrl_frame, text="Play", command=self.play_video).grid(row=0, column=0)
        tk.Button(ctrl_frame, text="Pause", command=self.pause_video).grid(row=0, column=1)
        tk.Button(ctrl_frame, text="<< Prev", command=self.prev_frame).grid(row=0, column=2)
        tk.Button(ctrl_frame, text=">> Next", command=self.next_frame).grid(row=0, column=3)
        tk.Button(ctrl_frame, text="Reset Frame", command=self.reset_clicks).grid(row=0, column=4)

        tk.Label(ctrl_frame, text="Select Label:").grid(row=0, column=5)
        self.label_menu = ttk.Combobox(ctrl_frame, textvariable=self.selected_label,
                                       values=self.labels, state="readonly", width=15)
        self.label_menu.grid(row=0, column=6)

        self.frame_label = tk.Label(ctrl_frame, text="Frame: 0")
        self.frame_label.grid(row=0, column=7, padx=10)

        slider_frame = tk.Frame(self.root)
        slider_frame.pack(fill=tk.X, padx=10, pady=5)

        self.slider_time_label = tk.Label(slider_frame, text="00:00:00")
        self.slider_time_label.pack(side=tk.LEFT, padx=5)

        self.slider = tk.Scale(slider_frame, from_=0, to=int(self.duration), orient=tk.HORIZONTAL,
                            showvalue=0, command=self.on_slider_move, length=700)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.slider.pack(fill=tk.X, padx=10, pady=5)

        table_frame = tk.Frame(self.root)
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.table = ttk.Treeview(table_frame, columns=("Frame", "Label", "X", "Y", "Delete"), show="headings", height=6)
        for col in ("Frame", "Label", "X", "Y", "Delete"):
            self.table.heading(col, text=col)
            self.table.column(col, width=100, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)

        self.table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.table.bind("<Button-1>", self.on_table_click)

        save_btn = tk.Button(self.root, text="Save & Exit", command=self.on_exit)
        save_btn.pack(pady=5)

    def seconds_to_hms(self, secs):
        h = int(secs) // 3600
        m = (int(secs) % 3600) // 60
        s = int(secs) % 60
        return f"{h:02}:{m:02}:{s:02}"

    def load_frame(self, frame_idx):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.cap.read()
        if not ret:
            print(f"Failed to load frame {frame_idx}")
            return
        self.frame_bgr = frame.copy()
        self.frame_label.config(text=f"Frame: {frame_idx}")
        self.display_frame()
        self.update_table()

    def display_frame(self):
        display = self.frame_bgr.copy()
        self.original_width = display.shape[1]
        self.original_height = display.shape[0]

        for fr, lbl, x, y in self.clicked_points:
            if fr == self.current_frame_idx:
                cv2.circle(display, (x, y), 4, (0, 255, 0), -1)
                cv2.putText(display, f"{lbl} - ({x}, {y})", (x + 5, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        display_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        resized_img = Image.fromarray(display_rgb).resize((self.display_width, self.display_height))
        self.tk_img = ImageTk.PhotoImage(resized_img)

        if self._canvas_img_id is None:
            self._canvas_img_id = self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        else:
            self.canvas.itemconfig(self._canvas_img_id, image=self.tk_img)


    def on_click(self, event):
        x_scale = self.frame_bgr.shape[1] / 800
        y_scale = self.frame_bgr.shape[0] / 450
        x = int(event.x * x_scale)
        y = int(event.y * y_scale)
        label = self.selected_label.get()

        self.clicked_points = [
            (fr, lbl, xp, yp) for fr, lbl, xp, yp in self.clicked_points
            if not (fr == self.current_frame_idx and lbl == label)
        ]

        self.clicked_points.append((self.current_frame_idx, label, x, y))
        print(f"Clicked: Frame {self.current_frame_idx}, {label}, ({x}, {y})")

        current_idx = self.labels.index(label)
        next_idx = (current_idx + 1) % len(self.labels)
        self.selected_label.set(self.labels[next_idx])
        self.label_menu.set(self.labels[next_idx])

        self.display_frame()
        self.update_table()

        if self.labels_filled():
            self.next_frame()

    def labels_filled(self):
        return set(lbl for fr, lbl, _, _ in self.clicked_points if fr == self.current_frame_idx) == set(self.labels)

    def prev_frame(self):
        self.current_frame_idx = max(0, self.current_frame_idx - 1)
        self.slider_programmatic = True
        time_sec = self.current_frame_idx / self.fps
        self.slider.set(time_sec)
        self.slider_time_label.config(text=self.seconds_to_hms(time_sec))
        self.slider_programmatic = False
        self.load_frame(self.current_frame_idx)

    def next_frame(self):
        self.current_frame_idx = min(self.total_frames - 1, self.current_frame_idx + 1)
        self.slider_programmatic = True
        time_sec = self.current_frame_idx / self.fps
        self.slider.set(time_sec)
        self.slider_time_label.config(text=self.seconds_to_hms(time_sec))
        self.slider_programmatic = False
        self.load_frame(self.current_frame_idx)

    def on_slider_move(self, val):
        if self.slider_programmatic:
            return
        seconds = float(val)
        self.slider_time_label.config(text=self.seconds_to_hms(seconds))
        self.current_frame_idx = int(seconds * self.fps)
        self.load_frame(self.current_frame_idx)


    def reset_clicks(self):
        self.clicked_points = [pt for pt in self.clicked_points if pt[0] != self.current_frame_idx]
        self.label_menu.set(self.labels[0])
        self.display_frame()
        self.update_table()

    def update_table(self):
        for row in self.table.get_children():
            self.table.delete(row)
        for fr, lbl, x, y in self.clicked_points:
            if fr == self.current_frame_idx:
                self.table.insert("", "end", values=(fr, lbl, x, y, "Delete"))

    def on_table_click(self, event):
        region = self.table.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.table.identify_column(event.x)
        row = self.table.identify_row(event.y)
        if not row or col != "#5":
            return
        values = self.table.item(row)["values"]
        if len(values) != 5:
            return
        try:
            fr, lbl, x, y, _ = values
            fr = int(fr)
            x = int(x)
            y = int(y)
        except ValueError:
            return
        self.clicked_points = [
            pt for pt in self.clicked_points
            if not (pt[0] == fr and pt[1] == lbl and pt[2] == x and pt[3] == y)
        ]
        self.display_frame()
        self.update_table()

    def play_video(self):
        if not self.is_playing:
            self.is_playing = True
            self.auto_play()

    def pause_video(self):
        self.is_playing = False

    def auto_play(self):
        if self.is_playing and self.current_frame_idx < self.total_frames - 1:
            self.next_frame()
            self.root.after(int(1000 / self.fps), self.auto_play)

    def on_exit(self):
        # ensure directory exists
        os.makedirs(os.path.dirname(self.output_csv) or ".", exist_ok=True)

        # write one final CSV with header + all clicks
        with open(self.output_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "label", "x", "y"])
            # sort by frame then label for readability
            for fr, lbl, x, y in sorted(self.clicked_points, key=lambda t: (t[0], t[1])):
                writer.writerow([fr, lbl, x, y])

        print(f"Saved {len(self.clicked_points)} clicks to {self.output_csv}")
        self.root.destroy()
        sys.exit(0)


def load_labels(label_csv):
    labels = []
    with open(label_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            labels.append(row["label"])
    return labels

def main(video_path=None, labels_csv=None, output_csv=None):
    if video_path is None or labels_csv is None:
        print("Please specify at least a video path and a labels CSV.")
        return

    labels = load_labels(labels_csv)
    if not labels:
        print("No labels found.")
        return

    if output_csv is None:
        base = os.path.splitext(os.path.basename(video_path))[0]
        directory = os.path.dirname(video_path)
        output_csv = os.path.join(directory, base + "_tagged.csv")

    root = tk.Tk()
    root.title("Video Point Tagger")
    VideoTagger(root, video_path, labels, output_csv)
    root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="GUI tool for tagging video points")
        parser.add_argument("video_path", type=str, help="Path to video file")
        parser.add_argument("labels_csv", type=str, help="CSV with label column")
        parser.add_argument("--output_csv", type=str, help="Optional output CSV path")
        args = parser.parse_args()
        main(args.video_path, args.labels_csv, args.output_csv)
    else:
        # Define your paths here if you don't want to use command line
        main(VIDEO_PATH, LABELS_CSV, OUTPUT_CSV)