import tkinter as tk
from tkinter import ttk
import cv2
import csv
import os
from PIL import Image, ImageTk
import argparse

class VideoTagger:
    def __init__(self, root, video_path, label_list, output_csv):
        self.root = root
        self.video_path = video_path
        self.labels = label_list
        self.output_csv = output_csv
        self.current_frame_idx = 0
        self.clicked_points = []

        self.selected_label = tk.StringVar(value=self.labels[0])

        self.cap = cv2.VideoCapture(self.video_path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self.setup_gui()
        self.load_frame(self.current_frame_idx)

        # Keyboard bindings
        self.root.bind("<Left>", lambda event: self.prev_frame())
        self.root.bind("<Right>", lambda event: self.next_frame())

    def setup_gui(self):
        self.canvas = tk.Canvas(self.root, width=800, height=450)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)

        ctrl_frame = tk.Frame(self.root)
        ctrl_frame.pack()

        tk.Button(ctrl_frame, text="<< Prev", command=self.prev_frame).grid(row=0, column=0)
        tk.Button(ctrl_frame, text=">> Next", command=self.next_frame).grid(row=0, column=1)
        tk.Button(ctrl_frame, text="Reset Frame", command=self.reset_clicks).grid(row=0, column=2)

        tk.Label(ctrl_frame, text="Select Label:").grid(row=0, column=3)
        self.label_menu = ttk.Combobox(ctrl_frame, textvariable=self.selected_label,
                                       values=self.labels, state="readonly", width=15)
        self.label_menu.grid(row=0, column=4)

        self.frame_label = tk.Label(ctrl_frame, text="Frame: 0")
        self.frame_label.grid(row=0, column=5, padx=10)

        # ---- Scrollable Table for Annotations ----
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

        # Bind click on "Delete" column
        self.table.bind("<Button-1>", self.on_table_click)

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
        for fr, lbl, x, y in self.clicked_points:
            if fr != self.current_frame_idx:
                continue
            cv2.circle(display, (x, y), 4, (0, 255, 0), -1)
            cv2.putText(display, f"{lbl} - ({x}, {y})", (x + 5, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        display_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(display_rgb)
        img = img.resize((800, 450))
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

    def on_click(self, event):
        x_scale = self.frame_bgr.shape[1] / 800
        y_scale = self.frame_bgr.shape[0] / 450
        x = int(event.x * x_scale)
        y = int(event.y * y_scale)
        label = self.selected_label.get()

        # Remove previous point for same label + frame
        self.clicked_points = [
            (fr, lbl, xp, yp) for fr, lbl, xp, yp in self.clicked_points
            if not (fr == self.current_frame_idx and lbl == label)
        ]

        # Add new point
        self.clicked_points.append((self.current_frame_idx, label, x, y))
        print(f"Clicked: Frame {self.current_frame_idx}, {label}, ({x}, {y})")

        # Move to next label
        current_idx = self.labels.index(label)
        next_idx = (current_idx + 1) % len(self.labels)
        self.selected_label.set(self.labels[next_idx])
        self.label_menu.set(self.labels[next_idx])

        self.display_frame()
        self.update_table()

        if self.labels_filled():
            self.save_current_points()
            self.next_frame()

    def labels_filled(self):
        return set(lbl for fr, lbl, _, _ in self.clicked_points if fr == self.current_frame_idx) == set(self.labels)

    def save_current_points(self):
        os.makedirs(os.path.dirname(self.output_csv) or ".", exist_ok=True)
        with open(self.output_csv, "a", newline="") as f:
            writer = csv.writer(f)
            for fr, lbl, x, y in self.clicked_points:
                if fr == self.current_frame_idx:
                    writer.writerow([fr, lbl, x, y])
        print(f"Auto-saved points for frame {self.current_frame_idx}")


    def prev_frame(self):
        self.current_frame_idx = max(0, self.current_frame_idx - 1)
        self.load_frame(self.current_frame_idx)

    def next_frame(self):
        self.current_frame_idx = min(self.total_frames - 1, self.current_frame_idx + 1)
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
        if not row or col != "#5":  # "Delete" is column #5 (indexing starts at 1)
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

        # Remove point from internal list
        self.clicked_points = [
            pt for pt in self.clicked_points
            if not (pt[0] == fr and pt[1] == lbl and pt[2] == x and pt[3] == y)
        ]

        self.display_frame()
        self.update_table()


def load_labels(label_csv):
    labels = []
    with open(label_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            labels.append(row["label"])
    return labels

def main(video_path, labels_csv, output_csv):
    labels = load_labels(labels_csv)
    if not labels:
        print("No labels found.")
        return

    if os.path.exists(output_csv):
        os.remove(output_csv)
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "label", "x", "y"])

    root = tk.Tk()
    root.title("Video Point Tagger")
    VideoTagger(root, video_path, labels, output_csv)
    root.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GUI tool for tagging video points")
    parser.add_argument("video_path", type=str, help="Path to video file")
    parser.add_argument("labels_csv", type=str, help="CSV with label column")
    parser.add_argument("output_csv", type=str, help="Path to output CSV file")
    args = parser.parse_args()
    main(args.video_path, args.labels_csv, args.output_csv)
