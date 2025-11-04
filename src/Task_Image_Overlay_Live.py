# Task_Image_Overlay_Live.py
import cv2
import numpy as np
import time

# --- Load homography (image_px -> task_mm) ---
H = np.load("homography_matrix.npy")
H_inv = np.linalg.inv(H)  # task -> image

# --- Camera setup ---
CAM_INDEX = 1
cap = cv2.VideoCapture(CAM_INDEX)
if not cap.isOpened():
    raise SystemExit("Camera not found")
time.sleep(0.2)

# --- Define task-space grid (mm) ---
x_vals = np.linspace(0, 450, 10)   # match Calibration_Grid_Burner.py
y_vals = np.linspace(0, 440, 9)
grid_points_task = np.array([[x, y, 1.0] for y in y_vals for x in x_vals], dtype=np.float64)

# --- Mouse click callback ---
def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        pixel_pt = np.array([[x, y, 1]], dtype=np.float64).T
        task_pt = H @ pixel_pt
        task_pt /= task_pt[2]
        X, Y = task_pt[0][0], task_pt[1][0]
        print(f"Clicked Pixel ({x:.1f}, {y:.1f}) → Task-space (X={X:.2f} mm, Y={Y:.2f} mm)")

cv2.namedWindow("Task-Image Overlay")
cv2.setMouseCallback("Task-Image Overlay", on_mouse)

print("Running live feed. Click to print coordinates. Press 'q' to quit.")
cv2.namedWindow("Raw Camera Feed")

while True:
    ok, frame = cap.read()
    raw_frame = frame.copy()
    cv2.imshow("Raw Camera Feed", raw_frame)   # Show untouched live feed

    if not ok:
        print("Camera read failed.")
        break

    # --- Project task-space grid into image ---
    img_pts = []
    for p in grid_points_task:
        q = H_inv @ p
        q /= q[2]
        img_pts.append((int(q[0]), int(q[1])))
    img_pts = np.array(img_pts, dtype=int)

    # --- Draw green points on frame ---
    for (x, y) in img_pts:
        cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)

    # --- Show image ---
    cv2.imshow("Task-Image Overlay", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == 27:
        break

cap.release()
cv2.destroyAllWindows()
