import pandas as pd
import numpy as np
import cv2
import argparse
import sys
import os

# Define paths here
ORIGINAL_CSV = "example/tennis_test_tagged.csv"
COURT_CSV = "example/tennis_test_calibration.csv"

def apply_homography(original_csv, court_csv):
    # Load original and court-tagged points
    original_df = pd.read_csv(original_csv)
    court_df = pd.read_csv(court_csv)

    # Extract pixel and real-world coordinates from court_df
    src_pts = court_df[["X", "Y"]].astype(np.float32).values
    dst_pts = court_df[["GrX", "GrY"]].astype(np.float32).values

    if src_pts.shape[0] < 4:
        raise ValueError("At least 4 points are required to compute homography")

    # Compute homography matrix
    H, _ = cv2.findHomography(src_pts, dst_pts)

    # Find all coordinate column stems (e.g., "left_knee" from "left_knee_x", "left_knee_y")
    coord_cols = [col for col in original_df.columns if col.endswith("_x") or col.endswith("_y")]
    stems = sorted(set(col[:-2] for col in coord_cols if col[:-2] + "_y" in coord_cols))

    # Apply homography to each group of (x, y) columns
    for stem in stems:
        x_col = stem + "x"
        y_col = stem + "y"
        coords = original_df[[x_col, y_col]].values.astype(np.float32)
        coords = np.expand_dims(coords, axis=1)  # Shape: (N, 1, 2)
        projected = cv2.perspectiveTransform(coords, H).squeeze()  # Shape: (N, 2)
        original_df[stem + "x_meters"] = projected[:, 0]
        original_df[stem + "y_meters"] = projected[:, 1]

    # Output file path
    base = os.path.splitext(original_csv)[0]
    output_csv = base + "_homography.csv"
    original_df.to_csv(output_csv, index=False)
    print(f"Saved transformed file to {output_csv}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Apply homography transformation to coordinate CSV")
        parser.add_argument("original_csv", type=str, help="Original CSV with _x and _y columns")
        parser.add_argument("court_csv", type=str, help="CSV with court points (X, Y, GrX, GrY)")
        args = parser.parse_args()
        apply_homography(args.original_csv, args.court_csv)
    else:
        apply_homography(ORIGINAL_CSV, COURT_CSV)