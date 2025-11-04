import cv2
import numpy as np
from Laser_Helpers import send, connect, close, move_to, burn, wait_for_idle
import time
# --- Load homography (maps full-frame pixels -> task-space mm) ---
H = np.load("homography_matrix.npy")

# --- Constants ---
CAM_INDEX = 1
MIN_AREA = 1# keep as you had it
MAX_AREA = 4
X_MIN, X_MAX = 0.0, 450.0
Y_MIN, Y_MAX = 0.0, 440.0
MIN_BLACK = 185

# --- Camera setup ---
cap = cv2.VideoCapture(CAM_INDEX)
if not cap.isOpened():
    raise SystemExit("Camera not found")


cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)

cap.set(cv2.CAP_PROP_EXPOSURE, -6.8)   
cap.set(cv2.CAP_PROP_BRIGHTNESS, .5)
cap.set(cv2.CAP_PROP_CONTRAST, 100)
print('Camera settings applied.')


ok, frame = cap.read()
if not ok:
    raise SystemExit("Camera failed")

# --- Select ROI ---
rx, ry, rw, rh = [int(v) for v in cv2.selectROI("Select ROI (press ENTER)", frame, fromCenter=False, showCrosshair=True)]
cv2.destroyWindow("Select ROI (press ENTER)")
if rw == 0 or rh == 0:
    raise SystemExit("No ROI selected")

print("Running. ENTER to print & save filtered points, q/ESC to quit.")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    # --- Crop to ROI and threshold ---
    crop = frame[ry:ry+rh, rx:rx+rw]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, MIN_BLACK, 255, cv2.THRESH_BINARY_INV)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bw, connectivity=8)
    if num_labels > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        valid_labels = np.where((areas >= MIN_AREA) & (areas <= MAX_AREA))[0] + 1
    else:
        valid_labels = np.array([], dtype=np.int32)
    if len(valid_labels) > 0:
        print(f'Max Area: {np.max(stats[:, cv2.CC_STAT_AREA])}, Min Area: {np.min(stats[1:, cv2.CC_STAT_AREA])}, Valid Labels: {len(valid_labels)}')
    # --- ROI centroids to full-frame coordinates ---
    centroids_roi = centroids[valid_labels]       # (cx, cy) relative to ROI
    centroids_full = centroids_roi + np.array([rx, ry])  # shifted into full frame

    # --- For display (in ROI window only) ---
    vis = crop.copy()
    task_points = []
    image_points_full = []

    for i, (cx_full, cy_full) in enumerate(centroids_full):
        # Convert to homogeneous coordinates
        p_full = np.array([cx_full, cy_full, 1.0], dtype=np.float64)

        # Apply homography: full-frame px → task-space mm
        w = H.dot(p_full)
        if w[2] == 0:
            continue
        w = w / w[2]
        X, Y = float(w[0]), float(w[1])

        inside = (X_MIN < X < X_MAX) and (Y_MIN < Y < Y_MAX)
        color = (0, 255, 0) if inside else (0, 0, 255)

        # Draw on ROI window (so subtract rx, ry)
        cv2.circle(vis, (int(cx_full - rx), int(cy_full - ry)), 5, color, 2)
        cv2.putText(vis, str(i), (int(cx_full - rx) + 6, int(cy_full - ry) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        if inside:
            task_points.append((X, Y))
            image_points_full.append((cx_full, cy_full))

    # --- Display live feed ---
    cv2.imshow("Binary", bw)
    cv2.imshow("Numbered Centroids (ROI view)", vis)

    # --- Handle keypress ---
    key = cv2.waitKey(1) & 0xFF
    if key in (13, 10) or len(valid_labels) == 26:  # ENTER
        if len(task_points) == 0:
            print("No valid task-space points to save.")
        else:
            print("Kept points (Image_px -> Task_mm):")
            for img_pt, task_pt in zip(image_points_full, task_points):
                print(f"Image ({img_pt[0]:.1f}, {img_pt[1]:.1f})  ->  Task (X={task_pt[0]:.2f} mm, Y={task_pt[1]:.2f} mm)")
            np.savez("obliteration_points.npz",
                     task_points=np.array(task_points, dtype=np.float32),
                     image_points=np.array(image_points_full, dtype=np.float32),
                     roi_x=int(rx), roi_y=int(ry))
            print(f"Saved {len(task_points)} points to 'obliteration_points.npz' (roi_x={rx}, roi_y={ry})")

    if key == ord('q') or key == 27:
        break


cap.release()
cv2.destroyAllWindows()


# --- Load points & execute burns ---
data = np.load("obliteration_points.npz")
task = data["task_points"]
print(task)
ser = connect()
send(ser, "$H")
wait_for_idle(ser)

for X, Y in task:
    time.sleep(0.5)
    move_to(ser, X, Y)
    time.sleep(0.5)
    burn(ser, power=300, duration=0.45)


