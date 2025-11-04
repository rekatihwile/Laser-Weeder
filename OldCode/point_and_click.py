# click_to_move.py
# Calibrate a homography from camera pixels -> laser bed mm, then click to jog there (laser OFF).
# Usage: python click_to_move.py COM3 450 450   # COM port, bed_width_mm, bed_height_mm

import sys, json, time
import numpy as np
import cv2
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
# Enforce 400 x 400 limits regardless of CLI args
BED_W = 400.0
BED_H = 400.0

H_PATH = "homography_click_to_move.json"

# ---- Serial helpers (single open handle; laser belt-and-suspenders OFF) ----
def open_serial(port, baud=115200):
    ser = serial.Serial(port, baudrate=baud, timeout=0.1, write_timeout=0.2)
    # Ensure laser is off, set absolute/mm
    try:
        ser.write(b"M5\n")      # laser off now
        ser.write(b"G90\n")     # absolute mode
        ser.write(b"G21\n")     # mm
        ser.flush()
    except Exception:
        pass

    # Home the machine immediately on startup
    try:
        print("Homing machine (sending $H)...")
        ser.write(b"$H\n")
        ser.flush()
        # Read responses for a short window so homing progress is visible
        t_end = time.time() + 5.0
        while time.time() < t_end:
            try:
                if ser.in_waiting:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        print(f"<< {line}")
                        # stop early if controller acknowledges completion with 'ok'
                        if line.lower().startswith("ok"):
                            break
            except Exception:
                break
    except Exception as e:
        print(f"Warning: homing command failed: {e}")

    # small settle (kept minimal)
    time.sleep(0.05)
    return ser

def send_abs_move(ser, x=None, y=None, z=None, rapid=True, feed=3000):
    parts = []
    if x is not None: parts.append(f"X{float(x):.3f}")
    if y is not None: parts.append(f"Y{float(y):.3f}")
    if z is not None: parts.append(f"Z{float(z):.3f}")
    if not parts: return
    # keep laser OFF
    ser.write(b"M5\n")
    cmd = ("G0 " if rapid else f"G1 F{feed} ") + " ".join(parts) + "\n"
    ser.write(cmd.encode("ascii", "ignore"))

# ---- Homography I/O ----
def save_H(H, path):
    d = {"H": H.tolist()}
    with open(path, "w") as f:
        json.dump(d, f)

def load_H(path):
    try:
        with open(path, "r") as f:
            d = json.load(f)
        H = np.array(d["H"], dtype=np.float64)
        if H.shape == (3,3):
            return H
    except Exception:
        pass
    return None

# ---- Calibration (4 clicks) ----
# We use the *bed* corner coordinates as:
# (0,0), (BED_W,0), (BED_W,BED_H), (0,BED_H)  in clockwise order.
# You will click the same four corners in the image in the SAME order.
CAL_ORDER = ["Bottom-Left (0,0)",
             "Bottom-Right (W,0)",
             "Top-Right (W,H)",
             "Top-Left (0,H)"]

def compute_H(pixels, bedW, bedH):
    img_pts = np.array(pixels, dtype=np.float64)             # Nx2
    bed_pts = np.array([[0,0], [bedW,0], [bedW,bedH], [0,bedH]], dtype=np.float64)
    H, _ = cv2.findHomography(img_pts, bed_pts, method=0)    # Direct Linear Transform
    return H

def apply_H(H, u, v):
    p = np.array([ [ [u, v] ] ], dtype=np.float64)   # shape (1,1,2)
    q = cv2.perspectiveTransform(p, H)[0,0]          # returns shape (1,1,2)
    return float(q[0]), float(q[1])

# ---- Main UI ----
def main():
    ser = open_serial(PORT)
    
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if sys.platform.startswith("win") else cv2.VideoCapture(0)
    if not cap or not cap.isOpened():
        print("ERROR: could not open camera 0; try a different index/backend.")
        return

    H = load_H(H_PATH)
    clicks = []
    need_cal = H is None

    win = "Camera (q to quit)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    msg = ""
    def on_mouse(event, x, y, flags, param):
        nonlocal clicks, H, msg
        if event == cv2.EVENT_LBUTTONDOWN:
            if H is None:
                clicks.append((x, y))
                # Tell the user which bed corner to click next (image point)
                next_idx = min(len(clicks)-1, 3)
                msg = f"Captured {len(clicks)}/4 — image point for: {CAL_ORDER[next_idx]}"
                if len(clicks) == 4:
                    H = compute_H(clicks, BED_W, BED_H)
                    save_H(H, H_PATH)
                    msg = "Calibration saved. Now click anywhere in the IMAGE to jog there."
            else:
                # map click -> bed
                X, Y = apply_H(H, x, y)
                # clamp to bed bounds (optional)
                X = min(max(X, 0.0), BED_W)
                Y = min(max(Y, 0.0), BED_H)
                send_abs_move(ser, X, Y, rapid=True)
                msg = f"Move -> X={X:.2f} Y={Y:.2f} (clicked image point)"

    cv2.setMouseCallback(win, on_mouse)

    if need_cal:
        # Clear, explicit instruction about clicking in the camera image:
        msg = ("Calibration: IN THE CAMERA IMAGE click the four bed corners in "
               "CLOCKWISE order, starting with the Bottom-Left corner of the BED "
               "(i.e. the bottom-left corner as it appears in the image).")

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        # simple overlay text
        overlay = frame.copy()
        y0 = 25
        for i, t in enumerate(["CLICK-TO-MOVE (laser OFF)",
                               f"Bed: {BED_W:.0f} x {BED_H:.0f} mm",
                               "Press 'r' to reset calibration",
                               msg]):
            cv2.putText(overlay, t, (10, y0 + 20*i),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2, cv2.LINE_AA)

        # draw clicked points during calibration
        if H is None:
            for i, (cx, cy) in enumerate(clicks):
                cv2.circle(overlay, (cx, cy), 4, (0,255,0), -1)
                cv2.putText(overlay, str(i+1), (cx+6, cy-6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2, cv2.LINE_AA)

        cv2.imshow(win, overlay)
        k = cv2.waitKey(30) & 0xFF
        if k in (27, ord('q')):
            break
        if k == ord('r'):
            H = None
            clicks = []
            msg = f"Calibration reset. Click: {', '.join(CAL_ORDER)}"
            try:
                open(H_PATH, "w").write("")  # clear file
            except Exception:
                pass

    cap.release()
    cv2.destroyAllWindows()

    # extra safety on exit
    try:
        ser.write(b"M5\n")
        ser.close()
    except Exception:
        pass

if __name__ == "__main__":
    main()
